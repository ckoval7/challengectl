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
import socket
import hashlib
import yaml
import requests
import subprocess
import random
import string
import tempfile
import signal
from typing import Optional, Dict, List
import threading
from datetime import datetime

# Import challenge modules from parent directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from challenges import ask, cw, nbfm, ssb_tx, fhss_tx, freedv_tx, spectrum_paint, pocsagtx_osmocom, lrs_pager, lrs_tx  # noqa: E402

# Initial basic logging setup (will be reconfigured in main() after parsing args)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s challengectl-runner[%(process)d]: %(levelname)s: %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S'
)

logger = logging.getLogger(__name__)


def get_mac_address() -> Optional[str]:
    """Get the MAC address of the primary network interface.

    Returns:
        MAC address as a string (e.g., "aa:bb:cc:dd:ee:ff"), or None if unavailable
    """
    try:
        import uuid
        mac = uuid.getnode()
        # Format as colon-separated hex
        mac_str = ':'.join(('%012x' % mac)[i:i+2] for i in range(0, 12, 2))
        return mac_str
    except Exception as e:
        logger.warning(f"Could not retrieve MAC address: {e}")
        return None


def get_machine_id() -> Optional[str]:
    """Get the machine ID from the system.

    Tries to read from:
    - Linux: /etc/machine-id or /var/lib/dbus/machine-id
    - Other platforms: Use a UUID based on hardware characteristics

    Returns:
        Machine ID as a string, or None if unavailable
    """
    # Try Linux machine-id files
    for path in ['/etc/machine-id', '/var/lib/dbus/machine-id']:
        try:
            with open(path, 'r') as f:
                machine_id = f.read().strip()
                if machine_id:
                    return machine_id
        except (FileNotFoundError, PermissionError):
            continue

    # Fallback: use platform-specific identifier
    try:
        import platform
        # Create a consistent ID from system information
        system_info = f"{platform.system()}-{platform.node()}-{platform.machine()}"
        # Hash it to create a consistent ID
        return hashlib.sha256(system_info.encode()).hexdigest()[:32]
    except Exception as e:
        logger.warning(f"Could not retrieve machine ID: {e}")
        return None


class ServerLogHandler(logging.Handler):
    """Custom logging handler that forwards logs to the server."""

    def __init__(self, runner_instance):
        super().__init__()
        self.runner = runner_instance
        self.setLevel(logging.DEBUG)  # Forward all log levels

    def emit(self, record):
        """Send log record to server."""
        if self.runner and hasattr(self.runner, 'send_log'):
            try:
                msg = record.getMessage()

                # Don't forward logs about log sending failures (avoid recursion)
                if 'Failed to send log to server' in msg:
                    return

                # Filter out noisy HTTP request logs from urllib3/requests
                if record.name in ('urllib3.connectionpool', 'requests'):
                    return

                # Filter out debug logs from our own HTTP operations
                if 'Starting new HTTPS connection' in msg or \
                   'Starting new HTTP connection' in msg or \
                   'Resetting dropped connection' in msg:
                    return

                self.runner.send_log(record.levelname, msg)
            except Exception:
                # Silently ignore errors to prevent recursion
                pass


class ChallengeCtlRunner:
    """Runner client for executing challenges on SDR devices."""

    def __init__(self, config_path: str):
        self.config = self.load_config(config_path)
        self.runner_id = self.config['runner']['runner_id']
        self.server_url = self.config['runner']['server_url'].rstrip('/')
        self.api_key = self.config['runner']['api_key']
        self.cache_dir = self.config['runner'].get('cache_dir', 'cache')
        self.heartbeat_interval = self.config['runner'].get('heartbeat_interval', 30)
        self.poll_interval = self.config['runner'].get('poll_interval', 10)
        self.spectrum_paint_before_challenge = self.config['runner'].get('spectrum_paint_before_challenge', True)

        # TLS configuration
        self.ca_cert = self.config['runner'].get('ca_cert')
        self.verify_ssl = self.config['runner'].get('verify_ssl', True)

        # Devices from configuration
        self.devices = self.load_devices()

        # Cache directory setup
        os.makedirs(self.cache_dir, exist_ok=True)

        # Running state
        self.running = False
        self.current_task = None
        self._shutdown_initiated = False

        # Device availability tracking for parallel execution
        self.device_lock = threading.Lock()
        self.busy_devices = set()  # Set of device_ids currently in use
        self.active_tasks = {}  # Map of challenge_id -> (thread, device_id)
        self.offline_devices = set()  # Set of device_ids that have failed and are offline
        self.device_failure_counts = {}  # Map of device_id -> consecutive failure count

        # HTTP session for connection pooling
        self.session = requests.Session()

        # Get host identifiers for authentication
        mac_address = get_mac_address()
        machine_id = get_machine_id()

        # Set authentication headers including host identifiers
        headers = {'Authorization': f'Bearer {self.api_key}'}
        if mac_address:
            headers['X-Runner-MAC'] = mac_address
        if machine_id:
            headers['X-Runner-Machine-ID'] = machine_id

        self.session.headers.update(headers)
        logger.debug(f"Session configured with host identifiers: MAC={mac_address}, Machine ID={machine_id}")

        # Configure TLS verification
        if self.ca_cert and os.path.exists(self.ca_cert):
            # Use provided CA certificate
            self.session.verify = self.ca_cert
            logger.info(f"Using CA certificate: {self.ca_cert}")
        elif not self.verify_ssl:
            # Disable SSL verification (development only)
            self.session.verify = False
            logger.warning("SSL verification disabled - development mode only!")
            # Disable SSL warnings if verification is disabled
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        else:
            # Use default system CA certificates
            self.session.verify = True
            logger.info("Using system CA certificates")

        logger.info(f"Runner initialized: {self.runner_id}")

    def load_config(self, config_path: str) -> Dict:
        """Load runner configuration from YAML."""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded configuration from {config_path}")
                return config
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            sys.exit(1)

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

            # Build device string (same logic as v2)
            device_string = f"{model}={name}"
            if device_conf.get('bias_t') or model_def.get('bias_t'):
                device_string += ",biastee=1"

            device_info = {
                'device_id': idx,
                'model': model,
                'name': name,
                'device_string': device_string,
                'antenna': device_conf.get('antenna', model_def.get('antenna', '')),
                'frequency_limits': device_conf.get('frequency_limits', [])
            }

            devices.append(device_info)
            logger.info(f"Configured device {idx}: {device_string}")

        return devices

    def enroll(self) -> bool:
        """Enroll this runner with the server using an enrollment token.

        This is used for initial enrollment with database-stored API keys.
        After enrollment, the runner should be restarted without the enrollment_token in config.
        """
        enrollment_token = self.config['runner'].get('enrollment_token')

        if not enrollment_token:
            logger.debug("No enrollment token found, skipping enrollment")
            return False

        try:
            hostname = socket.gethostname()
            mac_address = get_mac_address()
            machine_id = get_machine_id()

            logger.info(f"Enrolling with host identifiers: hostname={hostname}, MAC={mac_address}, machine_id={machine_id}")

            # Prepare device info for server
            devices_info = []
            for dev in self.devices:
                devices_info.append({
                    'device_id': dev['device_id'],
                    'model': dev['model'],
                    'name': dev['name'],
                    'frequency_limits': dev['frequency_limits']
                })

            # Create a session without authentication for enrollment
            enrollment_session = requests.Session()

            # Configure TLS verification same as main session
            if self.ca_cert and os.path.exists(self.ca_cert):
                enrollment_session.verify = self.ca_cert
            elif not self.verify_ssl:
                enrollment_session.verify = False
            else:
                enrollment_session.verify = True

            response = enrollment_session.post(
                f"{self.server_url}/api/enrollment/enroll",
                json={
                    'enrollment_token': enrollment_token,
                    'api_key': self.api_key,
                    'runner_id': self.runner_id,
                    'hostname': hostname,
                    'mac_address': mac_address,
                    'machine_id': machine_id,
                    'devices': devices_info
                },
                timeout=10
            )

            if response.status_code == 201:
                logger.info(f"Successfully enrolled as {self.runner_id}")
                return True
            elif response.status_code == 401:
                logger.error("Enrollment failed: Invalid or expired enrollment token")
                return False
            elif response.status_code == 409:
                logger.info("Runner already enrolled with this token")
                return True  # Return true to continue with normal operation
            else:
                logger.error(f"Enrollment failed: HTTP {response.status_code}")
                try:
                    error_data = response.json()
                    logger.error(f"Error: {error_data.get('error', 'Unknown error')}")
                except Exception:
                    pass
                return False

        except Exception as e:
            logger.error(f"Error during enrollment: {e}")
            return False

    def register(self) -> bool:
        """Register this runner with the server.

        Note: This is now primarily for backwards compatibility.
        New runners should use the enrollment process instead.
        """
        try:
            hostname = socket.gethostname()

            # Prepare device info for server
            devices_info = []
            for dev in self.devices:
                devices_info.append({
                    'device_id': dev['device_id'],
                    'model': dev['model'],
                    'name': dev['name'],
                    'frequency_limits': dev['frequency_limits']
                })

            response = self.session.post(
                f"{self.server_url}/api/agents/register",
                json={
                    'hostname': hostname,
                    'devices': devices_info
                },
                timeout=10
            )

            if response.status_code == 200:
                logger.info(f"Registered as {self.runner_id}")
                return True
            else:
                logger.error(f"Registration failed: HTTP {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error during registration: {e}")
            return False

    def send_heartbeat(self):
        """Send periodic heartbeat to server with device status."""
        try:
            # Collect device status
            device_status = {}
            with self.device_lock:
                for device in self.devices:
                    device_id = device['device_id']
                    if device_id in self.offline_devices:
                        device_status[device_id] = 'offline'
                    elif device_id in self.busy_devices:
                        device_status[device_id] = 'busy'
                    else:
                        device_status[device_id] = 'online'

            response = self.session.post(
                f"{self.server_url}/api/agents/{self.runner_id}/heartbeat",
                json={'device_status': device_status},
                timeout=5
            )

            if response.status_code == 200:
                logger.debug("Heartbeat sent")
            else:
                logger.warning(f"Heartbeat failed: {response.status_code}")

        except Exception as e:
            logger.error(f"Error sending heartbeat: {e}")

    def signout(self):
        """Sign out from server (graceful shutdown)."""
        try:
            logger.info(f"Signing out from server...")
            response = self.session.post(
                f"{self.server_url}/api/agents/{self.runner_id}/signout",
                timeout=5
            )

            if response.status_code == 200:
                print("Signed out successfully", flush=True)
                logger.info("Signed out successfully")
                return True
            else:
                print(f"Signout failed: {response.status_code}", flush=True)
                logger.warning(f"Signout failed: {response.status_code}")
                return False

        except Exception as e:
            print(f"Error during signout: {e}", flush=True)
            logger.error(f"Error during signout: {e}")
            return False

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

    def run_spectrum_paint(self, frequency: int, device_string: str, antenna: str) -> bool:
        """
        Run spectrum paint before a challenge.
        This matches the behavior of the original challengectl.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Running spectrum paint on {frequency} Hz before challenge")
            from multiprocessing import Process
            p = Process(target=spectrum_paint.main, args=(frequency, device_string, antenna))
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

    def get_available_device(self) -> Optional[Dict]:
        """Get next available (non-busy, non-offline) device.

        Returns:
            Device dict or None if all devices are busy or offline
        """
        with self.device_lock:
            for device in self.devices:
                device_id = device['device_id']
                if device_id not in self.busy_devices and device_id not in self.offline_devices:
                    return device
            return None

    def mark_device_busy(self, device_id: int):
        """Mark a device as busy."""
        with self.device_lock:
            self.busy_devices.add(device_id)

    def mark_device_available(self, device_id: int):
        """Mark a device as available."""
        with self.device_lock:
            self.busy_devices.discard(device_id)

    def get_available_device_count(self) -> int:
        """Get number of devices currently available (not busy and not offline)."""
        with self.device_lock:
            total = len(self.devices)
            unavailable = len(self.busy_devices) + len(self.offline_devices)
            return max(0, total - unavailable)

    def mark_device_offline(self, device_id: int):
        """Mark a device as offline due to hardware failure."""
        with self.device_lock:
            if device_id not in self.offline_devices:
                self.offline_devices.add(device_id)
                # Also ensure it's not marked as busy
                self.busy_devices.discard(device_id)
                logger.error(f"Device {device_id} marked as OFFLINE due to hardware failure")

    def mark_device_online(self, device_id: int):
        """Mark a previously offline device as online again."""
        with self.device_lock:
            if device_id in self.offline_devices:
                self.offline_devices.remove(device_id)
                self.device_failure_counts.pop(device_id, None)
                logger.info(f"Device {device_id} marked as ONLINE")

    def record_device_failure(self, device_id: int) -> int:
        """Record a device failure and return consecutive failure count.

        After 3 consecutive failures, device is marked offline.

        Returns:
            int: Number of consecutive failures
        """
        with self.device_lock:
            count = self.device_failure_counts.get(device_id, 0) + 1
            self.device_failure_counts[device_id] = count

            if count >= 3:
                self.mark_device_offline(device_id)

            return count

    def record_device_success(self, device_id: int):
        """Record a successful device operation, resetting failure count."""
        with self.device_lock:
            self.device_failure_counts[device_id] = 0
            # If device was offline, bring it back online
            if device_id in self.offline_devices:
                self.mark_device_online(device_id)

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
                return result.returncode == 0
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

        # Use provided device or select first available
        if device is None:
            device = self.get_available_device()

        if not device:
            logger.error("No devices available")
            return (False, 0, frequency or 0)

        device_id = device['device_id']
        device_string = device['device_string']
        antenna = device['antenna']

        try:
            # Run spectrum paint before challenge if configured
            if self.spectrum_paint_before_challenge and modulation != 'paint':
                logger.info("Spectrum paint before challenge is enabled")
                self.run_spectrum_paint(frequency, device_string, antenna)
            # Resolve file paths if needed
            if modulation in ['nbfm', 'ssb', 'fhss', 'freedv', 'paint']:
                flag_path = self.resolve_file_path(flag)
                if not flag_path or not os.path.exists(flag_path):
                    logger.error(f"Flag file not found: {flag}")
                    return (False, device_id, frequency or 0)
                flag = flag_path

            # Execute based on modulation type
            if modulation == 'cw':
                speed = config.get('speed', 35)
                from multiprocessing import Process
                p = Process(target=cw.main, args=(flag, speed, frequency, device_string, antenna))
                p.start()
                p.join()
                success = (p.exitcode == 0)

            elif modulation == 'ask':
                ask.main(flag.encode("utf-8").hex(), frequency, device_string, antenna)
                success = True

            elif modulation == 'nbfm':
                wav_rate = config.get('wav_samplerate', 48000)
                nbfm_opts = nbfm.argument_parser().parse_args('')
                nbfm_opts.dev = device_string
                nbfm_opts.freq = frequency
                nbfm_opts.wav_file = flag
                nbfm_opts.wav_samp_rate = wav_rate
                nbfm_opts.antenna = antenna
                nbfm.main(options=nbfm_opts)
                success = True

            elif modulation == 'ssb':
                mode = config.get('mode', 'usb')
                wav_rate = config.get('wav_samplerate', 48000)
                ssb_opts = ssb_tx.argument_parser().parse_args('')
                ssb_opts.dev = device_string
                ssb_opts.freq = frequency
                ssb_opts.wav_file = flag
                ssb_opts.wav_samp_rate = wav_rate
                ssb_opts.mode = mode
                ssb_opts.antenna = antenna
                ssb_tx.main(options=ssb_opts)
                success = True

            elif modulation == 'fhss':
                wav_rate = config.get('wav_samplerate', 48000)
                channel_spacing = config.get('channel_spacing', 10000)
                hop_rate = config.get('hop_rate', 10)
                hop_time = config.get('hop_time', 60)
                seed = config.get('seed', 'RFHS')

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
                fhss_tx.main(options=fhss_opts)
                success = True

            elif modulation == 'freedv':
                mode = config.get('mode', 'usb')
                wav_rate = config.get('wav_samplerate', 48000)
                text = config.get('text', '')

                freedv_opts = freedv_tx.argument_parser().parse_args('')
                freedv_opts.dev = device_string
                freedv_opts.freq = frequency
                freedv_opts.wav_file = flag
                freedv_opts.wav_samp_rate = wav_rate
                freedv_opts.mode = mode
                freedv_opts.text = text
                # Note: freedv_tx doesn't support antenna parameter yet
                freedv_tx.main(options=freedv_opts)
                success = True

            elif modulation == 'pocsag':
                capcode = config.get('capcode', 0)
                pocsag_opts = pocsagtx_osmocom.argument_parser().parse_args('')
                pocsag_opts.deviceargs = device_string
                pocsag_opts.samp_rate = 2400000
                pocsag_opts.pagerfreq = frequency
                pocsag_opts.capcode = capcode
                pocsag_opts.message = flag
                pocsag_opts.antenna = antenna
                pocsagtx_osmocom.main(options=pocsag_opts)
                success = True

            elif modulation == 'lrs':
                lrspageropts = lrs_pager.argument_parser().parse_args(flag.split())
                randomstring = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                # Use local temp directory instead of /tmp
                temp_dir = os.path.join(os.getcwd(), 'temp')
                os.makedirs(temp_dir, exist_ok=True)
                outfile = os.path.join(temp_dir, f"lrs_{randomstring}.bin")
                lrspageropts.outputfile = outfile
                lrs_pager.main(options=lrspageropts)

                lrsopts = lrs_tx.argument_parser().parse_args('')
                lrsopts.deviceargs = device_string
                lrsopts.freq = frequency
                lrsopts.binfile = outfile
                lrsopts.antenna = antenna
                lrs_tx.main(options=lrsopts)

                os.remove(outfile)
                success = True

            elif modulation == 'paint':
                from multiprocessing import Process
                p = Process(target=spectrum_paint.main, args=(frequency, device_string, antenna))
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

    def send_log(self, level: str, message: str):
        """Send log entry to server."""
        try:
            self.session.post(
                f"{self.server_url}/api/agents/{self.runner_id}/log",
                json={
                    'log': {
                        'level': level,
                        'message': message,
                        'timestamp': datetime.now().isoformat()
                    }
                },
                timeout=5
            )
        except Exception as e:
            # Log at debug level to avoid recursion
            logger.debug(f"Failed to send log to server: {e}")

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
            if any(keyword in error_str.lower() for keyword in ['failed to open', 'no devices available', 'device not found', 'usb error']):
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
            with self.device_lock:
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
                with self.device_lock:
                    offline_count = len(self.offline_devices)

                if offline_count > 0 and (now - last_offline_warning) > 60:
                    with self.device_lock:
                        offline_ids = list(self.offline_devices)
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
                        with self.device_lock:
                            self.active_tasks[challenge_id] = (thread, device['device_id'])

                        thread.start()
                        logger.debug(f"Started task {challenge_id} on device {device['device_id']}")

                        # Small delay between starting tasks to avoid race conditions
                        time.sleep(0.5)

                # Clean up finished threads
                with self.device_lock:
                    finished = [cid for cid, (thread, _) in self.active_tasks.items() if not thread.is_alive()]
                for cid in finished:
                    with self.device_lock:
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
            else:
                print("Failed to register with server and no enrollment token found. Exiting.")
                logger.error("Failed to register with server and no enrollment token found. Exiting.")
                sys.exit(1)
        else:
            print("Registration successful")

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
        print("Stopping runner...", flush=True)
        logger.info("Stopping runner...")
        self.running = False

        # Wait for active tasks to complete (up to 30 seconds)
        max_wait = 30
        waited = 0
        with self.device_lock:
            active_count = len(self.active_tasks)

        if active_count > 0:
            print(f"Waiting for {active_count} active task(s) to complete...", flush=True)
            logger.info(f"Waiting for {active_count} active task(s) to complete...")

            while waited < max_wait:
                with self.device_lock:
                    if len(self.active_tasks) == 0:
                        break

                time.sleep(1)
                waited += 1

            with self.device_lock:
                remaining = len(self.active_tasks)

            if remaining > 0:
                print(f"Warning: {remaining} task(s) still running after {max_wait}s", flush=True)
                logger.warning(f"{remaining} task(s) still running after {max_wait}s")
            else:
                print("All tasks completed", flush=True)
                logger.info("All tasks completed")

        # Sign out from server
        print("Signing out from server...", flush=True)
        self.signout()

        # Give remaining threads time to finish
        time.sleep(1)
        print("Runner stopped", flush=True)
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
