#!/usr/bin/env python3
"""
ChallengeCtl Runner - Client that runs on each SDR host.
Polls server for tasks, downloads files, executes challenges.
"""

import argparse
import logging
import sys
import os
import time
import hashlib
import yaml
import subprocess
import signal
from typing import Optional, Dict, List
import threading
from datetime import datetime
from multiprocessing import Process

# Import challenge modules from parent directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from challenges import ask_tx as ask, cw_tx as cw, nbfm, ssb_tx, fhss_tx, freedv_tx, spectrum_paint, pocsagtx_osmocom, lrs_tx
from device_manager import DeviceManager
from common_agent import AgentBase, ServerLogHandler, get_mac_address, get_machine_id

# Initial basic logging setup (will be reconfigured in main() after parsing args)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s challengectl-runner[%(process)d]: %(levelname)s: %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S'
)

logger = logging.getLogger(__name__)


class ChallengeCtlRunner(AgentBase):
    """Runner client for executing challenges on SDR devices."""

    def __init__(self, config_path: str):
        # Initialize base agent class
        super().__init__(config_path, agent_type='runner')

        # Runner-specific configuration
        self.runner_id = self.agent_id  # Alias for backward compatibility
        self.cache_dir = self.config['runner'].get('cache_dir', 'cache')
        self.poll_interval = self.config['runner'].get('poll_interval', 10)
        self.spectrum_paint_before_challenge = self.config['runner'].get('spectrum_paint_before_challenge', True)

        # Device auto-detection configuration
        self.enable_auto_detection = self.config['runner'].get('enable_auto_detection', True)

        # Load devices from configuration
        configured_devices = self.load_devices()

        # Initialize device manager
        self.device_manager = DeviceManager(
            configured_devices=configured_devices,
            enable_auto_detection=self.enable_auto_detection,
            agent_type='runner',
            probe_callback=self.check_device_available
        )

        # Cache directory setup
        os.makedirs(self.cache_dir, exist_ok=True)

        # Runner-specific state
        self.current_task = None
        self._shutdown_initiated = False

        # Active task tracking
        self.active_tasks = {}  # Map of challenge_id -> (thread, device_id)

        logger.info(f"Runner initialized: {self.runner_id}")

    @property
    def devices(self):
        """Get all devices (backward compatibility)."""
        return self.device_manager.get_all_devices()

    def load_devices(self) -> List[Dict]:
        """Load and enumerate SDR devices from configuration."""
        devices = []
        radios_config = self.config.get('radios', {})

        # Get model defaults
        models_config = radios_config.get('models', [])
        model_defaults = {}
        for model_conf in models_config:
            model_name = model_conf.get('model')
            if model_name:
                model_defaults[model_name] = model_conf

        # Parse devices
        devices_config = radios_config.get('devices', [])
        for idx, device_conf in enumerate(devices_config):
            model = device_conf.get('model')
            name = device_conf.get('name')
            model_def = model_defaults.get(model, {})

            # Build device string (without bias_t for now - will be added per-antenna during execution)
            device_string = f"{model}={name}"

            # Get device-level settings (for legacy format or fallback)
            device_rf_gain = device_conf.get('rf_gain', model_def.get('rf_gain'))
            device_if_gain = device_conf.get('if_gain', model_def.get('if_gain'))
            device_bias_t = device_conf.get('bias_t', model_def.get('bias_t', False))

            # Parse antenna configuration (supports both old and new formats)
            antennas_config = {}

            if 'antennas' in device_conf:
                # New format: dict of antennas with frequency limits and optional rf_gain per antenna
                if 'antenna' in device_conf or 'frequency_limits' in device_conf:
                    logger.error(f"Device {idx} ({device_string}): Cannot use both 'antennas' dict and legacy 'antenna'/'frequency_limits' fields")
                    sys.exit(1)

                # Parse each antenna's configuration
                for antenna_name, antenna_conf in device_conf['antennas'].items():
                    # Get per-antenna settings, fall back to device-level if not specified
                    antenna_rf_gain = antenna_conf.get('rf_gain', device_rf_gain)
                    antenna_bias_t = antenna_conf.get('bias_t', device_bias_t)

                    antennas_config[antenna_name] = {
                        'frequency_limits': antenna_conf.get('frequency_limits', []),
                        'enabled': antenna_conf.get('enabled', True),
                        'rf_gain': antenna_rf_gain,
                        'bias_t': antenna_bias_t
                    }

                logger.info(f"Device {idx} configured with {len(antennas_config)} antennas: {', '.join(antennas_config.keys())}")
            else:
                # Old format: single antenna with device-level frequency limits (backward compatibility)
                antenna = device_conf.get('antenna', model_def.get('antenna', ''))
                frequency_limits = device_conf.get('frequency_limits', [])
                if antenna:
                    antennas_config[antenna] = {
                        'frequency_limits': frequency_limits,
                        'rf_gain': device_rf_gain,
                        'bias_t': device_bias_t
                    }
                    logger.info(f"Device {idx} configured with single antenna: {antenna} (legacy format)")
                elif frequency_limits:
                    # Edge case: frequency_limits specified but no antenna
                    # Create a default antenna entry with empty name
                    antennas_config[''] = {
                        'frequency_limits': frequency_limits,
                        'rf_gain': device_rf_gain,
                        'bias_t': device_bias_t
                    }
                    logger.warning(f"Device {idx} has frequency_limits but no antenna specified")

            device_info = {
                'device_id': idx,
                'model': model,
                'name': name,
                'device_string': device_string,
                'antennas_config': antennas_config,  # {antenna_name: {frequency_limits: [...], rf_gain: X, bias_t: bool}}
                'rf_gain': device_rf_gain,  # Device-level gain for legacy support
                'if_gain': device_if_gain,  # Device-level if_gain (HackRF only)
                'bias_t': device_bias_t,    # Device-level bias_t for legacy support
                'source': 'config',         # Mark as configured device
                'enabled': True             # Configured devices enabled by default
            }

            devices.append(device_info)
            logger.info(f"Configured device {idx}: {device_string}")

        return devices

    def select_antenna_for_frequency(self, device: Dict, frequency: int) -> Optional[tuple]:
        """Select the appropriate antenna for a given frequency based on device configuration.

        Args:
            device: Device dict with 'antennas_config' key
            frequency: Target frequency in Hz

        Returns:
            Tuple of (antenna_name, bias_t) if a compatible antenna is found, None otherwise
        """
        antennas_config = device.get('antennas_config', {})

        if not antennas_config:
            logger.warning(f"Device {device.get('name')} has no antenna configuration")
            return None

        # Check each antenna's frequency limits
        for antenna_name, antenna_config in antennas_config.items():
            # Skip disabled antennas (default to enabled if not specified)
            if not antenna_config.get('enabled', True):
                logger.debug(f"Antenna '{antenna_name}' is disabled, skipping")
                continue

            frequency_limits = antenna_config.get('frequency_limits', [])

            # If no frequency limits specified, this antenna accepts any frequency
            if not frequency_limits:
                logger.debug(f"Antenna '{antenna_name}' has no frequency limits, accepting frequency {frequency}")
                bias_t = antenna_config.get('bias_t', device.get('bias_t', False))
                return (antenna_name, bias_t)

            # Check if frequency falls within any of the antenna's ranges
            for freq_range in frequency_limits:
                try:
                    # Parse "min-max" format
                    if '-' not in freq_range:
                        logger.warning(f"Invalid frequency range format: {freq_range}")
                        continue

                    min_freq_str, max_freq_str = freq_range.split('-', 1)
                    min_freq = int(min_freq_str.strip())
                    max_freq = int(max_freq_str.strip())

                    if min_freq <= frequency <= max_freq:
                        logger.debug(f"Frequency {frequency} Hz matches antenna '{antenna_name}' range {freq_range}")
                        bias_t = antenna_config.get('bias_t', device.get('bias_t', False))
                        return (antenna_name, bias_t)

                except (ValueError, AttributeError) as e:
                    logger.warning(f"Error parsing frequency range '{freq_range}': {e}")
                    continue

        # No antenna supports this frequency
        logger.debug(f"No antenna on device {device.get('name')} supports frequency {frequency} Hz")
        return None

    def enroll(self) -> bool:
        """Enroll this runner with the server using an enrollment token.

        This is used for initial enrollment with database-stored API keys.
        After enrollment, the runner should be restarted without the enrollment_token in config.
        """
        # Prepare device info for server
        devices_info = []
        for dev in self.devices:
            devices_info.append({
                'device_id': dev['device_id'],
                'model': dev['model'],
                'name': dev['name'],
                'antennas_config': dev['antennas_config']  # Send antenna configurations with frequency limits
            })

        # Call parent class enroll method
        return super().enroll(devices_info)

    def register(self) -> bool:
        """Register this runner with the server.

        Note: This is now primarily for backwards compatibility.
        New runners should use the enrollment process instead.
        """
        # Prepare device info for server
        devices_info = []
        for dev in self.devices:
            devices_info.append({
                'device_id': dev['device_id'],
                'model': dev['model'],
                'name': dev['name'],
                'antennas_config': dev['antennas_config']  # Send antenna configurations with frequency limits
            })

        # Get device status from device manager (already probed during startup)
        device_status = self.device_manager.get_device_status_dict()

        # Call parent class register method
        return super().register(devices_info, device_status)

    def send_heartbeat(self):
        """Send periodic heartbeat to server with device status and auto-detected devices."""
        # Get device status from device manager
        device_status = self.device_manager.get_device_status_dict()

        # Include auto-detected devices in payload
        with self.device_manager.auto_detected_lock:
            auto_detected_payload = [
                {
                    'device_id': d['device_id'],
                    'model': d['model'],
                    'name': d['name'],
                    'device_string': d['device_string'],
                    'antennas_config': d['antennas_config'],
                    'rf_gain': d.get('rf_gain'),
                    'if_gain': d.get('if_gain'),
                    'bias_t': d.get('bias_t'),
                    'source': d['source'],
                    'enabled': d['enabled'],
                    'auto_detected_at': d['auto_detected_at']
                }
                for d in self.device_manager.auto_detected_devices
            ]

        # Call parent class send_heartbeat method
        response_data = super().send_heartbeat(device_status, auto_detected_payload)

        # Check for device config updates from server
        if response_data:
            device_updates = response_data.get('device_config_updates', [])
            if device_updates:
                self.device_manager.apply_device_config_updates(device_updates)

    def signout(self):
        """Sign out from server (graceful shutdown)."""
        # Call parent class signout method
        return super().signout()

    def heartbeat_loop(self):
        """Background thread for sending heartbeats."""
        while self.running:
            self.send_heartbeat()
            time.sleep(self.heartbeat_interval)

    def get_task(self) -> Optional[Dict]:
        """Request next task from server."""
        try:
            response = self.session.get(
                f"{self.server_url}/api/agents/{self.runner_id}/task",
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                task = data.get('task')

                if task:
                    logger.info(f"Received task: {task['name']}")
                    return task
                else:
                    logger.debug("No tasks available")
                    return None
            else:
                logger.warning(f"Get task failed: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error getting task: {e}")
            return None

    def download_file(self, file_hash: str) -> Optional[str]:
        """Download a file from server if not in cache."""
        cache_path = os.path.join(self.cache_dir, file_hash)

        # Check if file exists and verify hash
        if os.path.exists(cache_path):
            with open(cache_path, 'rb') as f:
                existing_hash = hashlib.sha256(f.read()).hexdigest()
                if existing_hash == file_hash:
                    logger.debug(f"File {file_hash[:8]}... found in cache")
                    return cache_path

        # Download file
        try:
            logger.info(f"Downloading {file_hash[:8]}...")

            response = self.session.get(
                f"{self.server_url}/api/files/{file_hash}",
                timeout=60,
                stream=True
            )

            if response.status_code == 200:
                # Write to temp file first
                temp_path = cache_path + '.tmp'
                with open(temp_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                # Verify hash
                with open(temp_path, 'rb') as f:
                    downloaded_hash = hashlib.sha256(f.read()).hexdigest()

                if downloaded_hash != file_hash:
                    logger.error(f"Hash mismatch: {file_hash[:8]}")
                    os.remove(temp_path)
                    return None

                # Move to final location
                os.rename(temp_path, cache_path)
                logger.debug(f"Downloaded {file_hash[:8]}")
                return cache_path

            else:
                logger.error(f"File download failed: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            return None

    def resolve_file_path(self, flag_value: str) -> str:
        """
        Resolve file path from flag value.
        If it's a hash (sha256:...), download from server.
        Otherwise, assume it's a local path.
        """
        if flag_value.startswith('sha256:'):
            file_hash = flag_value[7:]  # Remove 'sha256:' prefix
            return self.download_file(file_hash)
        else:
            # Assume it's a local path relative to parent directory
            parent_dir = os.path.join(os.path.dirname(__file__), '..')
            return os.path.join(parent_dir, flag_value)

    def run_spectrum_paint(self, frequency: int, device_string: str, antenna: str, rf_gain=None, if_gain=None) -> bool:
        """
        Run spectrum paint before a challenge.
        This matches the behavior of the original challengectl.

        Args:
            frequency: Frequency in Hz
            device_string: Device string (e.g., "hackrf=0,biastee=1")
            antenna: Antenna name
            rf_gain: RF gain value (optional)
            if_gain: IF gain value (optional)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Running spectrum paint on {frequency} Hz before challenge")
            p = Process(target=spectrum_paint.main, args=(frequency, device_string, antenna, rf_gain, if_gain))
            p.start()
            p.join()
            success = (p.exitcode == 0)

            if success:
                logger.info("Spectrum paint completed successfully")
            else:
                logger.warning("Spectrum paint failed")

            return success

        except Exception as e:
            logger.error(f"Error running spectrum paint: {e}", exc_info=True)
            return False

    def get_available_device(self, frequency: Optional[int] = None) -> Optional[Dict]:
        """Get next available (non-busy, non-offline) device, optionally filtered by frequency.

        Args:
            frequency: Optional target frequency in Hz. If provided, only returns devices
                      with antennas that support this frequency.

        Returns:
            Device dict or None if all devices are busy, offline, or incompatible
        """
        available_devices = self.device_manager.get_available_devices(frequency=frequency)

        # Filter by antenna compatibility for runners (frequency already filtered by DeviceManager)
        # But we need additional antenna selection logic for multi-antenna devices
        for device in available_devices:
            if frequency is not None:
                antenna_info = self.select_antenna_for_frequency(device, frequency)
                if antenna_info is None:
                    # Device doesn't support this frequency, skip it
                    logger.debug(f"Device {device.get('name')} doesn't support frequency {frequency} Hz")
                    continue

            return device

        return None

    def mark_device_busy(self, device_id: int):
        """Mark a device as busy."""
        self.device_manager.mark_device_busy(device_id)

    def mark_device_available(self, device_id: int):
        """Mark a device as available."""
        self.device_manager.mark_device_available(device_id)

    def get_available_device_count(self) -> int:
        """Get number of devices currently available (not busy and not offline)."""
        available = self.device_manager.get_available_devices()
        return len(available)

    def mark_device_offline(self, device_id: int):
        """Mark a device as offline due to hardware failure."""
        self.device_manager.mark_device_offline(device_id)
        logger.error(f"Device {device_id} marked as OFFLINE due to hardware failure")

    def mark_device_online(self, device_id: int):
        """Mark a previously offline device as online again."""
        self.device_manager.mark_device_online(device_id)
        logger.info(f"Device {device_id} marked as ONLINE")

    def record_device_failure(self, device_id: int) -> int:
        """Record a device failure and return consecutive failure count.

        After 3 consecutive failures, device is marked offline.

        Returns:
            int: Number of consecutive failures
        """
        count = self.device_manager.record_device_failure(device_id)

        if count >= 3:
            self.mark_device_offline(device_id)

        return count

    def record_device_success(self, device_id: int):
        """Record a successful device operation, resetting failure count."""
        # Check if device was offline before recording success
        was_offline = device_id in self.device_manager.offline_devices
        self.device_manager.record_device_success(device_id)

        # If device was offline, bring it back online
        if was_offline:
            self.mark_device_online(device_id)
            logger.info(f"Device {device_id} brought back ONLINE after successful operation")

    def check_device_available(self, device: Dict) -> bool:
        """Check if a device is actually available by attempting to probe it.

        Args:
            device: Device dict with device_string

        Returns:
            bool: True if device responds, False otherwise
        """
        device_string = device['device_string']
        device_id = device['device_id']

        # For BladeRF, we can try to list devices
        if 'bladerf' in device_string.lower():
            try:
                # Try to run bladeRF-cli to check device availability
                result = subprocess.run(
                    ['bladeRF-cli', '-p'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                # If the specific serial is in the device string, check for it
                if 'serial=' in device_string:
                    serial = device_string.split('serial=')[1].split(',')[0].split(':')[0]
                    if serial not in result.stdout:
                        logger.warning(f"Device {device_id}: BladeRF serial {serial} not found")
                        return False

                return result.returncode == 0

            except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
                logger.debug(f"Device {device_id}: BladeRF probe failed: {e}")
                return False

        # For HackRF, check with hackrf_info
        elif 'hackrf' in device_string.lower():
            try:
                result = subprocess.run(
                    ['hackrf_info'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                # Check if hackrf_info found any devices
                if result.returncode == 0:
                    # If using device index (hackrf=0, hackrf=1), check that many devices exist
                    if '=' in device_string:
                        device_index_str = device_string.split('=')[1].split(',')[0].split(':')[0]
                        try:
                            device_index = int(device_index_str)
                            # Count how many "Serial number" lines appear in output
                            device_count = result.stdout.lower().count('serial number')
                            if device_index >= device_count:
                                logger.warning(f"Device {device_id}: HackRF index {device_index} not available (only {device_count} devices found)")
                                return False
                        except ValueError:
                            pass  # Not a numeric index, assume it's a serial or other identifier

                    return True
                else:
                    return False

            except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
                logger.debug(f"Device {device_id}: HackRF probe failed: {e}")
                return False

        # For file sink or unknown devices, assume available
        return True

    def execute_challenge(self, task: Dict, device: Optional[Dict] = None) -> tuple:
        """
        Execute a challenge task.

        Args:
            task: Challenge task dictionary
            device: Specific device to use (if None, selects first available)

        Returns:
            tuple: (success: bool, device_id: int, frequency: int)
        """
        challenge_id = task['challenge_id']
        name = task['name']
        config = task['config']

        modulation = config.get('modulation')
        flag = config.get('flag')
        frequency = config.get('frequency')

        # Handle flag_file_hash if present (from file uploads)
        if 'flag_file_hash' in config and config['flag_file_hash']:
            flag = f"sha256:{config['flag_file_hash']}"

        logger.info(f"Executing challenge: {name} ({modulation}) on {frequency} Hz")

        # Use provided device or select first available that supports the frequency
        if device is None:
            device = self.get_available_device(frequency=frequency)

        if not device:
            logger.error(f"No devices available that support frequency {frequency} Hz")
            return (False, 0, frequency or 0)

        device_id = device['device_id']
        base_device_string = device['device_string']

        # Select appropriate antenna for this frequency
        antenna_info = self.select_antenna_for_frequency(device, frequency)
        if antenna_info is None:
            logger.error(f"Device {device.get('name')} has no antenna supporting frequency {frequency} Hz")
            return (False, device_id, frequency or 0)

        antenna, bias_t = antenna_info

        # Build device string with antenna-specific bias_t
        device_string = base_device_string
        if bias_t:
            device_string += ",biastee=1"

        # Get gain settings for this antenna/device
        antennas_config = device.get('antennas_config', {})
        antenna_config = antennas_config.get(antenna, {})
        rf_gain = antenna_config.get('rf_gain', device.get('rf_gain'))  # Per-antenna or device-level
        if_gain = device.get('if_gain')  # Device-level only (HackRF specific)

        logger.info(f"Using device {device.get('name')} with antenna '{antenna}' for frequency {frequency} Hz (rf_gain={rf_gain}, bias_t={bias_t})")

        try:
            # Run spectrum paint before challenge if configured
            if self.spectrum_paint_before_challenge and modulation != 'paint':
                logger.info("Spectrum paint before challenge is enabled")
                self.run_spectrum_paint(frequency, device_string, antenna, rf_gain, if_gain)
            # Resolve file paths if needed
            if modulation in ['nbfm', 'ssb', 'fhss', 'freedv', 'paint']:
                flag_path = self.resolve_file_path(flag)
                if not flag_path or not os.path.exists(flag_path):
                    logger.error(f"Flag file not found: {flag}")
                    return (False, device_id, frequency or 0)
                flag = flag_path

            # Execute based on modulation type
            if modulation == 'cw':
                speed = config.get('speed', 15)
                def run_cw():
                    cw_opts = cw.argument_parser().parse_args('')
                    cw_opts.deviceargs = device_string
                    cw_opts.freq = frequency
                    cw_opts.flag = flag
                    cw_opts.speed = speed
                    cw_opts.antenna = antenna
                    # Pass gain settings (fixes bug where gains weren't being used)
                    if rf_gain is not None:
                        cw_opts.rfgain = rf_gain
                    if if_gain is not None:
                        cw_opts.ifgain = if_gain
                    cw.main(options=cw_opts)

                
                p = Process(target=run_cw)
                p.start()
                p.join()
                success = (p.exitcode == 0)

            elif modulation == 'ask':
                baud_rate = config.get('baud_rate', 2400)
                repeat = config.get('repeat', 10)

                def run_ask():
                    ask_opts = ask.argument_parser().parse_args('')
                    ask_opts.deviceargs = device_string
                    ask_opts.freq = frequency
                    ask_opts.flag = flag
                    ask_opts.antenna = antenna
                    ask_opts.baud_rate = baud_rate
                    ask_opts.repeat = repeat
                    # Pass gain settings (fixes bug where gains weren't being used)
                    if rf_gain is not None:
                        ask_opts.rfgain = rf_gain
                    if if_gain is not None:
                        ask_opts.ifgain = if_gain
                    ask.main(options=ask_opts)

                p = Process(target=run_ask)
                p.start()
                p.join()
                success = (p.exitcode == 0)

            elif modulation == 'nbfm':
                wav_rate = config.get('wav_samplerate', 48000)

                def run_nbfm():
                    nbfm_opts = nbfm.argument_parser().parse_args('')
                    nbfm_opts.dev = device_string
                    nbfm_opts.freq = frequency
                    nbfm_opts.wav_file = flag
                    nbfm_opts.wav_samp_rate = wav_rate
                    nbfm_opts.antenna = antenna
                    # Pass gain settings (fixes bug where gains weren't being used)
                    if rf_gain is not None:
                        nbfm_opts.rf_gain = rf_gain
                    if if_gain is not None:
                        nbfm_opts.if_gain = if_gain
                    nbfm.main(options=nbfm_opts)

                p = Process(target=run_nbfm)
                p.start()
                p.join()
                success = (p.exitcode == 0)

            elif modulation == 'ssb':
                mode = config.get('mode', 'usb')
                wav_rate = config.get('wav_samplerate', 48000)

                def run_ssb():
                    ssb_opts = ssb_tx.argument_parser().parse_args('')
                    ssb_opts.dev = device_string
                    ssb_opts.freq = frequency
                    ssb_opts.wav_file = flag
                    ssb_opts.wav_samp_rate = wav_rate
                    ssb_opts.mode = mode
                    ssb_opts.antenna = antenna
                    # Pass gain settings
                    if rf_gain is not None:
                        ssb_opts.rf_gain = rf_gain
                    if if_gain is not None:
                        ssb_opts.if_gain = if_gain
                    ssb_tx.main(options=ssb_opts)

                p = Process(target=run_ssb)
                p.start()
                p.join()
                success = (p.exitcode == 0)

            elif modulation == 'fhss':
                wav_rate = config.get('wav_samplerate', 48000)
                channel_spacing = config.get('channel_spacing', 10000)
                hop_rate = config.get('hop_rate', 10)
                hop_time = config.get('hop_time', 60)
                seed = config.get('seed', 'RFHS')

                def run_fhss():
                    fhss_opts = fhss_tx.argument_parser().parse_args('')
                    fhss_opts.dev = device_string
                    fhss_opts.freq = frequency
                    fhss_opts.file = flag
                    fhss_opts.wav_rate = wav_rate
                    fhss_opts.channel_spacing = channel_spacing
                    fhss_opts.hop_rate = hop_rate
                    fhss_opts.hop_time = hop_time
                    fhss_opts.seed = seed
                    fhss_opts.antenna = antenna
                    # Pass gain settings
                    if rf_gain is not None:
                        fhss_opts.rf_gain = rf_gain
                    if if_gain is not None:
                        fhss_opts.if_gain = if_gain
                    fhss_tx.main(options=fhss_opts)

                p = Process(target=run_fhss)
                p.start()
                p.join()
                success = (p.exitcode == 0)

            elif modulation == 'freedv':
                mode = config.get('mode', 'usb')
                wav_rate = config.get('wav_samplerate', 48000)
                text = config.get('text', '')

                def run_freedv():
                    freedv_opts = freedv_tx.argument_parser().parse_args('')
                    freedv_opts.dev = device_string
                    freedv_opts.freq = frequency
                    freedv_opts.wav_file = flag
                    freedv_opts.wav_samp_rate = wav_rate
                    freedv_opts.mode = mode
                    freedv_opts.text = text
                    # Pass gain settings
                    if rf_gain is not None:
                        freedv_opts.rf_gain = rf_gain
                    if if_gain is not None:
                        freedv_opts.if_gain = if_gain
                    # Note: freedv_tx doesn't support antenna parameter yet
                    freedv_tx.main(options=freedv_opts)

                p = Process(target=run_freedv)
                p.start()
                p.join()
                success = (p.exitcode == 0)

            elif modulation == 'pocsag':
                capcode = config.get('capcode', 0)
                pocsag_opts = pocsagtx_osmocom.argument_parser().parse_args('')
                pocsag_opts.deviceargs = device_string
                pocsag_opts.samp_rate = 2400000
                pocsag_opts.pagerfreq = frequency
                pocsag_opts.capcode = capcode
                pocsag_opts.message = flag
                pocsag_opts.antenna = antenna
                # Pass gain settings
                if rf_gain is not None:
                    pocsag_opts.rf_gain = rf_gain
                if if_gain is not None:
                    pocsag_opts.if_gain = if_gain
                pocsagtx_osmocom.main(options=pocsag_opts)
                success = True

            elif modulation == 'lrs':
                def run_lrs(systemid, pagerid, pager_function):
                    lrs_opts = lrs_tx.argument_parser().parse_args('')
                    lrs_opts.deviceargs = device_string
                    lrs_opts.freq = frequency
                    lrs_opts.systemid = systemid
                    lrs_opts.pagerid = pagerid
                    lrs_opts.function = pager_function
                    lrs_opts.printkey = True
                    lrs_opts.antenna = antenna
                    # Pass gain settings (fixes bug where gains weren't being used)
                    if rf_gain is not None:
                        lrs_opts.rf_gain = rf_gain
                    if if_gain is not None:
                        lrs_opts.if_gain = if_gain
                    lrs_tx.main(options=lrs_opts)
                try:
                    parts = flag.split()
                    
                    # Check for the correct number of arguments
                    if len(parts) != 6:
                        raise ValueError("Incorrect number of arguments.")
                        
                    # Check for the correct flags in the correct positions
                    if parts[0] != '-s' or parts[2] != '-p' or parts[4] != '-pf':
                        raise ValueError("Incorrect flag structure.")

                    # Parse the values (indices 1, 3, 5) and convert to integers
                    systemid, pagerid, pager_function = map(int, parts[1::2])
                    p = Process(target=run_lrs, args=(systemid, pagerid, pager_function))
                    p.start()
                    p.join()
                    success = (p.exitcode == 0)
                except (ValueError, IndexError) as e:
                    logger.error(f"Error parsing string: {e}")
                    # Assign error values
                    # systemid, pagerid, pager_function = 1, 1, 1
                    logger.error(f"Bad flag for LRS: {flag}")
                    success = False
                # systemid, pagerid, pager_function = [int(x) for x in flag.split()[1::2]]

            elif modulation == 'paint':
                p = Process(target=spectrum_paint.main, args=(frequency, device_string, antenna, rf_gain, if_gain))
                p.start()
                p.join()
                success = (p.exitcode == 0)

            else:
                logger.error(f"Unknown modulation type: {modulation}")
                success = False

            # Turn off bias-tee if needed
            if 'bladerf' in device_string and 'biastee=1' in device_string:
                self.disable_bladerf_biastee(device_string)

            return (success, device_id, frequency or 0)

        except Exception as e:
            logger.error(f"Error executing challenge: {e}", exc_info=True)
            return (False, device_id if 'device_id' in locals() else 0, frequency or 0)

    def disable_bladerf_biastee(self, device_string: str):
        """Turn off BladeRF bias-tee after transmission."""
        try:
            bladeserial = self.parse_bladerf_serial(device_string)
            serialarg = f'*:serial={bladeserial}'
            subprocess.run(['bladeRF-cli', '-d', serialarg, 'set', 'biastee', 'tx', 'off'])
            logger.debug(f"Disabled bias-tee for BladeRF {bladeserial}")
        except Exception as e:
            logger.error(f"Error disabling bias-tee: {e}")

    def parse_bladerf_serial(self, device_string: str) -> str:
        """Parse BladeRF serial from device string."""
        idx = device_string.find("bladerf=")
        if idx != -1:
            start = idx + 8
            end = start + 32
            return device_string[start:end]
        return ""

    def report_completion(self, challenge_id: str, success: bool,
                          device_id: int, frequency: int,
                          error_message: Optional[str] = None,
                          transmission_id: Optional[int] = None):
        """Report task completion to server."""
        try:
            payload = {
                'challenge_id': challenge_id,
                'success': success,
                'error_message': error_message,
                'device_id': device_id,
                'frequency': frequency
            }
            if transmission_id is not None:
                payload['transmission_id'] = transmission_id

            response = self.session.post(
                f"{self.server_url}/api/agents/{self.runner_id}/complete",
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                logger.info(f"Completion reported for {challenge_id}")
            else:
                logger.warning(f"Completion report failed: {response.status_code}")

        except Exception as e:
            logger.error(f"Error reporting completion: {e}")

    # send_log is inherited from AgentBase

    def execute_task_thread(self, task: Dict, device: Dict):
        """Execute a task in a thread and handle completion.

        Args:
            task: Challenge task dictionary
            device: Device to use for execution
        """
        challenge_id = task['challenge_id']
        transmission_id = task.get('transmission_id')
        device_id = device['device_id']

        try:
            # Check if device is still enabled before executing
            if not device.get('enabled', True):
                error_msg = f"Device {device_id} was disabled before execution could start"
                logger.warning(error_msg)
                self.report_completion(challenge_id, False, device_id, 0, error_msg, transmission_id)
                return

            # Mark device as busy
            self.mark_device_busy(device_id)

            # Validate device is still available before attempting transmission
            if not self.check_device_available(device):
                failure_count = self.record_device_failure(device_id)
                error_msg = f"Device {device_id} not responding (failure {failure_count}/3)"
                logger.error(error_msg)
                self.report_completion(challenge_id, False, device_id, 0, error_msg, transmission_id)
                return

            # Execute challenge on the specified device
            success, used_device_id, frequency = self.execute_challenge(task, device)

            # Record success or failure
            if success:
                self.record_device_success(device_id)
            else:
                failure_count = self.record_device_failure(device_id)
                logger.warning(f"Device {device_id} task failed (failure {failure_count}/3)")

            # Report completion
            error_msg = None if success else "Execution failed"
            self.report_completion(challenge_id, success, used_device_id, frequency, error_msg, transmission_id)

        except RuntimeError as e:
            # Hardware-specific errors (device disconnected, driver issues, etc.)
            error_str = str(e)
            hardware_error_keywords = [
                'failed to open',
                'no devices available',
                'not enough devices',  # HackRF specific
                'device not found',
                'usb error',
                'failed to use',  # HackRF/BladeRF when device index invalid
                'cannot open device'
            ]

            if any(keyword in error_str.lower() for keyword in hardware_error_keywords):
                failure_count = self.record_device_failure(device_id)
                error_msg = f"Hardware error on device {device_id} (failure {failure_count}/3): {error_str[:100]}"
                logger.error(error_msg)
            else:
                error_msg = f"Runtime error: {error_str[:100]}"
                logger.error(f"Error executing task {challenge_id}: {e}", exc_info=True)

            self.report_completion(challenge_id, False, device_id, 0, error_msg, transmission_id)

        except Exception as e:
            logger.error(f"Error executing task {challenge_id}: {e}", exc_info=True)
            # Report failure
            self.report_completion(challenge_id, False, device_id, 0, str(e)[:100], transmission_id)

        finally:
            # Always mark device as available when done
            self.mark_device_available(device_id)

            # Remove from active tasks
            with self.device_manager.device_lock:
                self.active_tasks.pop(challenge_id, None)

    def task_loop(self):
        """Main task execution loop with parallel device support."""
        logger.debug("Task loop started")

        # Track when we last logged offline device warning
        last_offline_warning = 0

        while self.running:
            try:
                # Periodically warn about offline devices (every 60 seconds)
                now = time.time()
                with self.device_manager.device_lock:
                    offline_count = len(self.device_manager.offline_devices)

                if offline_count > 0 and (now - last_offline_warning) > 60:
                    with self.device_manager.device_lock:
                        offline_ids = list(self.device_manager.offline_devices)
                    logger.warning(f"{offline_count} device(s) offline: {offline_ids}")
                    logger.warning("Reconnect devices or restart runner to bring them back online")
                    last_offline_warning = now

                # Check how many devices are available
                available_count = self.get_available_device_count()

                if available_count > 0:
                    # Request tasks for each available device
                    for _ in range(available_count):
                        # Get an available device
                        device = self.get_available_device()
                        if not device:
                            break  # All devices became busy

                        # Get next task
                        task = self.get_task()
                        if not task:
                            break  # No more tasks available

                        challenge_id = task['challenge_id']

                        # Start task execution in a thread
                        thread = threading.Thread(
                            target=self.execute_task_thread,
                            args=(task, device),
                            daemon=True
                        )

                        # Track the active task
                        with self.device_manager.device_lock:
                            self.active_tasks[challenge_id] = (thread, device['device_id'])

                        thread.start()
                        logger.debug(f"Started task {challenge_id} on device {device['device_id']}")

                        # Small delay between starting tasks to avoid race conditions
                        time.sleep(0.5)

                # Clean up finished threads
                with self.device_manager.device_lock:
                    finished = [cid for cid, (thread, _) in self.active_tasks.items() if not thread.is_alive()]
                for cid in finished:
                    with self.device_manager.device_lock:
                        self.active_tasks.pop(cid, None)

                # Wait before next poll
                time.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"Error in task loop: {e}", exc_info=True)
                time.sleep(self.poll_interval)

    def start(self):
        """Start the runner."""
        print("="*60)
        print("ChallengeCtl Runner Starting")
        print("="*60)
        print(f"Runner ID: {self.runner_id}")
        print(f"Server: {self.server_url}")
        print(f"Devices: {len(self.devices)}")

        # Perform initial device health check
        print("\nChecking device availability...")
        for device in self.devices:
            device_id = device['device_id']
            device_name = device.get('name', device['device_string'])
            available = self.check_device_available(device)
            status = "✓ ONLINE" if available else "✗ OFFLINE"
            print(f"  Device {device_id} ({device_name}): {status}")

            if not available:
                self.mark_device_offline(device_id)

        available_count = self.get_available_device_count()
        print(f"\nDevices online: {available_count}/{len(self.devices)}")
        print("="*60)

        logger.info(f"Runner {self.runner_id} starting")
        logger.info(f"Server: {self.server_url}, Devices: {len(self.devices)}")
        logger.info(f"Devices online: {available_count}/{len(self.devices)}")

        # Set up signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            sig_name = signal.Signals(signum).name
            print(f"\n{sig_name} signal received...", flush=True)
            logger.info(f"Received {sig_name} signal, shutting down...")
            self.stop()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Try to register first (works if already enrolled with valid API key)
        print("Registering with server...")
        registered = self.register()

        if not registered:
            # Registration failed - check if we have an enrollment token to try
            enrollment_token = self.config['runner'].get('enrollment_token')
            if enrollment_token:
                print("Registration failed. Attempting enrollment with token...")
                if not self.enroll():
                    print("Failed to enroll with server. Exiting.")
                    logger.error("Failed to enroll with server. Exiting.")
                    sys.exit(1)
                print("Enrollment successful!")
                print("")
                print("NOTE: You can leave 'enrollment_token' in your runner-config.yml.")
                print("It will be ignored on subsequent runs once enrolled.")
                print("")
                # Send immediate heartbeat after enrollment
                logger.debug("Sending initial heartbeat to update device status")
                self.send_heartbeat()
            else:
                print("Failed to register with server and no enrollment token found. Exiting.")
                logger.error("Failed to register with server and no enrollment token found. Exiting.")
                sys.exit(1)
        else:
            print("Registration successful")
            # Send immediate heartbeat to ensure device status is current
            logger.debug("Sending initial heartbeat to update device status")
            self.send_heartbeat()

        # Add server log handler to forward logs
        server_handler = ServerLogHandler(self)
        logging.root.addHandler(server_handler)
        print("Log forwarding to server enabled")
        logger.info("Log forwarding to server enabled")

        self.running = True

        # Start heartbeat thread
        heartbeat_thread = threading.Thread(target=self.heartbeat_loop, daemon=True)
        heartbeat_thread.start()
        print("Heartbeat thread started")
        logger.info("Heartbeat thread started")

        # Start device probe loop thread
        self.device_manager.start_probe_loop()
        print(f"Device probe loop started (event-driven, auto-detect: {self.enable_auto_detection})")
        logger.info(f"Device probe loop started (event-driven, auto-detect: {self.enable_auto_detection})")

        # Start task loop (blocking)
        print("Starting task loop...")
        print("Press Ctrl+C to shutdown")
        print()
        self.task_loop()

    def stop(self):
        """Stop the runner."""
        # Prevent duplicate shutdown attempts
        if self._shutdown_initiated:
            return

        self._shutdown_initiated = True
        print("\n" + "="*60, flush=True)
        print("SHUTTING DOWN RUNNER", flush=True)
        print("="*60, flush=True)
        logger.info("Stopping runner...")
        self.running = False

        # Wait for active tasks to complete (up to 30 seconds)
        max_wait = 30
        waited = 0
        with self.device_manager.device_lock:
            active_count = len(self.active_tasks)

        if active_count > 0:
            print(f"Step 1/3: Waiting for {active_count} active task(s) to complete (max {max_wait}s)...", flush=True)
            logger.info(f"Waiting for {active_count} active task(s) to complete...")

            while waited < max_wait:
                with self.device_manager.device_lock:
                    current_count = len(self.active_tasks)
                    if current_count == 0:
                        break

                # Show progress every 5 seconds
                if waited > 0 and waited % 5 == 0:
                    print(f"  Still waiting... ({current_count} task(s) remaining, {waited}s elapsed)", flush=True)

                time.sleep(1)
                waited += 1

            with self.device_manager.device_lock:
                remaining = len(self.active_tasks)

            if remaining > 0:
                print(f"  ⚠ Warning: {remaining} task(s) still running after {max_wait}s", flush=True)
                logger.warning(f"{remaining} task(s) still running after {max_wait}s")
            else:
                print(f"  ✓ All tasks completed ({waited}s)", flush=True)
                logger.info("All tasks completed")
        else:
            print("Step 1/3: No active tasks to wait for", flush=True)

        # Stop device probe loop
        self.device_manager.stop_probe_loop()

        # Sign out from server
        print("Step 2/3: Signing out from server...", flush=True)
        success = self.signout()
        if success:
            print("  ✓ Signed out successfully", flush=True)
        else:
            print("  ⚠ Signout did not complete successfully", flush=True)

        # Give remaining threads time to finish
        print("Step 3/3: Waiting for background threads to finish...", flush=True)
        time.sleep(1)
        print("  ✓ Cleanup complete", flush=True)

        print("="*60, flush=True)
        print("RUNNER STOPPED", flush=True)
        print("="*60, flush=True)
        logger.info("Runner stopped")

        # Flush all log handlers to ensure messages are written
        for handler in logging.root.handlers:
            handler.flush()

        # Exit cleanly after shutdown
        sys.exit(0)


def argument_parser():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="ChallengeCtl Runner - Execute challenges on SDR devices"
    )

    parser.add_argument(
        '-c', '--config',
        default='runner-config.yml',
        help='Path to runner configuration file (default: runner-config.yml)'
    )

    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Set logging level (default: INFO)'
    )

    return parser


def get_runner_id_from_config(config_path: str) -> str:
    """Load runner_id from config file."""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            return config.get('runner', {}).get('runner_id', 'runner')
    except Exception:
        return 'runner'


def main():
    """Main entry point."""
    parser = argument_parser()
    args = parser.parse_args()

    # Check if config exists
    if not os.path.exists(args.config):
        logger.error(f"Configuration file not found: {args.config}")
        logger.info("Creating default configuration...")
        create_default_config(args.config)
        logger.info(f"Default configuration created at {args.config}")
        logger.info("Please edit the configuration file and restart")
        sys.exit(1)

    # Get runner_id from config to use in log filename
    runner_id = get_runner_id_from_config(args.config)
    log_file = f'challengectl-{runner_id}.log'

    # Configure logging with file output and rotation
    # Rotate existing log file with timestamp before starting new log
    if os.path.exists(log_file):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        archived_log = f'challengectl-{runner_id}.{timestamp}.log'
        os.rename(log_file, archived_log)

    # Convert log level string to logging constant
    log_level = getattr(logging, args.log_level)

    # Reconfigure logging with both file and console output
    # Clear existing handlers and reconfigure
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # Create formatters
    log_format = f'%(asctime)s challengectl-{runner_id}[%(process)d]: %(levelname)s: %(message)s'
    date_format = '%Y-%m-%dT%H:%M:%S'
    formatter = logging.Formatter(log_format, datefmt=date_format)

    # File handler (only log to file, use print() for user-facing messages)
    file_handler = logging.FileHandler(log_file, mode='w')
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logging.root.addHandler(file_handler)

    # Set root logger level
    logging.root.setLevel(log_level)

    logging.info(f"Logging initialized at {args.log_level} level")
    print(f"Logging to {log_file}")

    # Create and start runner
    runner = ChallengeCtlRunner(args.config)
    runner.start()


def create_default_config(config_path: str):
    """Create default runner configuration."""
    default_config = """---
runner:
  runner_id: "runner-1"
  server_url: "https://192.168.1.100:8443"
  api_key: "change-this-key-abc123"

  # TLS/SSL Configuration
  # Path to CA certificate file for server verification
  # Leave blank to use system CA certificates
  ca_cert: ""
  # Set to false to disable SSL verification (development only!)
  verify_ssl: true

  cache_dir: "cache"
  heartbeat_interval: 30
  poll_interval: 10

radios:
  models:
  - model: hackrf
    rf_gain: 14
    if_gain: 32
    bias_t: true

  - model: bladerf
    rf_gain: 43
    bias_t: true

  devices:
  - name: 0
    model: hackrf
    rf_gain: 14
    if_gain: 32
    frequency_limits:
      - "144000000-148000000"
      - "420000000-450000000"
"""

    with open(config_path, 'w') as f:
        f.write(default_config)


if __name__ == '__main__':
    main()
