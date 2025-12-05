#!/usr/bin/env python3
"""
Shared Device Management Module for ChallengeCtl

Provides common device auto-detection, probing, and management functionality
for both runners (TX) and listeners (RX).
"""

import logging
import time
import threading
from datetime import datetime, timezone
from typing import List, Dict, Optional, Callable

logger = logging.getLogger(__name__)


class DeviceManager:
    """Manages SDR device auto-detection, probing, and status tracking.

    This class provides shared functionality for both runners and listeners:
    - Auto-detection of SDR devices using osmosdr
    - Periodic device probing for availability
    - Device status tracking (online/offline/busy/disabled)
    - Enabled/disabled state management
    """

    def __init__(
        self,
        configured_devices: List[Dict],
        device_probe_interval: int = 30,
        enable_auto_detection: bool = True,
        agent_type: str = 'runner',
        probe_callback: Optional[Callable] = None
    ):
        """Initialize device manager.

        Args:
            configured_devices: List of devices from configuration
            device_probe_interval: Seconds between probes (0 to disable)
            enable_auto_detection: Enable automatic device detection
            agent_type: 'runner' or 'listener' (determines device filtering)
            probe_callback: Optional callback(device) -> bool for custom probing
        """
        self.device_probe_interval = device_probe_interval
        self.enable_auto_detection = enable_auto_detection
        self.agent_type = agent_type
        self.probe_callback = probe_callback

        # Resolve serials for configured devices and enrich with serial info
        self.configured_devices = self._enrich_configured_devices(configured_devices)

        # Auto-detected devices
        self.auto_detected_devices = []
        self.auto_detected_lock = threading.Lock()
        self.last_auto_detection = 0

        # Device status tracking
        self.offline_devices = set()  # Set of device_ids that are offline
        self.busy_devices = set()  # Set of device_ids currently in use
        self.device_failure_counts = {}  # Map of device_id -> consecutive failure count
        self.device_lock = threading.Lock()

        # Probe thread
        self.probe_thread = None
        self.running = False

    def _enrich_configured_devices(self, configured_devices: List[Dict]) -> List[Dict]:
        """Enrich configured devices with resolved serial numbers.

        For devices with index-based names (e.g., name="0"), this resolves
        the index to an actual serial number by querying hardware.

        Args:
            configured_devices: List of device dicts from config

        Returns:
            Enriched list of device dicts with 'serial' field added
        """
        enriched = []

        for device in configured_devices:
            # Make a copy to avoid modifying the original
            enriched_device = device.copy()

            model = device.get('model')
            name = device.get('name')

            if model and name is not None:
                # Resolve serial for this device
                serial = self.resolve_device_serial(model, str(name))

                # Add serial to device dict
                enriched_device['serial'] = serial

                if serial:
                    if serial != str(name):
                        # Index was resolved to serial
                        logger.info(
                            f"Config device {model}={name} resolved to serial {serial}"
                        )
                    else:
                        # Name is already a serial
                        logger.debug(f"Config device {model}={name} using serial-based naming")
                else:
                    logger.warning(
                        f"Config device {model}={name} could not be resolved to serial "
                        f"(device may be offline or not connected)"
                    )

            enriched.append(enriched_device)

        return enriched

    def get_all_devices(self) -> List[Dict]:
        """Get combined list of configured + auto-detected devices.

        Returns:
            List of all device dicts (configured + auto-detected)
        """
        with self.auto_detected_lock:
            return self.configured_devices + self.auto_detected_devices

    def get_available_devices(self, frequency: Optional[int] = None) -> List[Dict]:
        """Get list of available devices (enabled, online, not busy).

        Args:
            frequency: Optional frequency filter (Hz)

        Returns:
            List of available device dicts
        """
        available = []

        with self.device_lock:
            all_devices = self.get_all_devices()
            for device in all_devices:
                device_id = device.get('device_id')

                # Skip disabled devices
                if not device.get('enabled', True):
                    continue

                # Skip offline devices
                if device_id in self.offline_devices:
                    continue

                # Skip busy devices
                if device_id in self.busy_devices:
                    continue

                # Check frequency compatibility if specified
                if frequency is not None:
                    if not self._device_supports_frequency(device, frequency):
                        continue

                available.append(device)

        return available

    def _device_supports_frequency(self, device: Dict, frequency: int) -> bool:
        """Check if device supports a given frequency.

        Args:
            device: Device dict
            frequency: Frequency in Hz

        Returns:
            True if device supports frequency, False otherwise
        """
        freq_limits = device.get('frequency_limits', [])

        # No limits = accepts all frequencies
        if not freq_limits:
            return True

        # Check if frequency is within any range
        for freq_range in freq_limits:
            try:
                if '-' in str(freq_range):
                    min_freq, max_freq = map(int, str(freq_range).split('-'))
                    if min_freq <= frequency <= max_freq:
                        return True
            except (ValueError, AttributeError):
                logger.warning(f"Invalid frequency range format: {freq_range}")
                continue

        return False

    def mark_device_busy(self, device_id: int):
        """Mark a device as busy."""
        with self.device_lock:
            self.busy_devices.add(device_id)

    def mark_device_available(self, device_id: int):
        """Mark a device as available (not busy)."""
        with self.device_lock:
            self.busy_devices.discard(device_id)

    def mark_device_offline(self, device_id: int):
        """Mark a device as offline."""
        with self.device_lock:
            self.offline_devices.add(device_id)
            self.device_failure_counts[device_id] = self.device_failure_counts.get(device_id, 0) + 1

    def mark_device_online(self, device_id: int):
        """Mark a device as online."""
        with self.device_lock:
            self.offline_devices.discard(device_id)
            self.device_failure_counts[device_id] = 0

    def record_device_success(self, device_id: int):
        """Record successful operation on device.

        Args:
            device_id: Device ID

        Returns:
            None
        """
        with self.device_lock:
            self.device_failure_counts[device_id] = 0
            # If device was offline, keep it offline until explicit online marking
            # (trust verification - requires successful operation after probe)

    def record_device_failure(self, device_id: int) -> int:
        """Record failed operation on device.

        Args:
            device_id: Device ID

        Returns:
            Number of consecutive failures
        """
        with self.device_lock:
            self.device_failure_counts[device_id] = self.device_failure_counts.get(device_id, 0) + 1
            failure_count = self.device_failure_counts[device_id]

            # Mark offline after 3 consecutive failures
            if failure_count >= 3:
                self.offline_devices.add(device_id)

            return failure_count

    def enumerate_device_serials(self, model: str) -> List[str]:
        """Get ordered list of serial numbers for device type from hardware.

        Queries actual hardware to get device serials in enumeration order.
        This is used to map index-based config entries (e.g., name="0") to
        actual serial numbers.

        Args:
            model: Device model (hackrf, bladerf, rtl-sdr, usrp)

        Returns:
            List of serial numbers in enumeration order (index 0, 1, 2, etc.)
            Empty list if enumeration fails or model not supported
        """
        import subprocess

        serials = []

        try:
            if model == 'hackrf':
                # Run hackrf_info to enumerate devices
                result = subprocess.run(
                    ['hackrf_info'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if result.returncode == 0:
                    # Parse "Serial number:" lines in order
                    for line in result.stdout.split('\n'):
                        if 'Serial number:' in line:
                            serial = line.split(':', 1)[1].strip()
                            # Remove 0x prefix if present
                            if serial.startswith('0x'):
                                serial = serial[2:]
                            # Normalize (remove leading zeros like osmosdr does)
                            serial = serial.lstrip('0') or '0'
                            serials.append(serial)

            elif model == 'bladerf':
                # Run bladeRF-cli -p to enumerate devices
                result = subprocess.run(
                    ['bladeRF-cli', '-p'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if result.returncode == 0:
                    # Parse serial numbers from output
                    # bladeRF-cli -p shows one device per line with serial
                    for line in result.stdout.split('\n'):
                        line = line.strip()
                        if line and not line.startswith('Backend:'):
                            # Serial numbers are typically the main content
                            # Example line: "  Serial:  a4c20e3f12345678"
                            if 'Serial:' in line or 'serial' in line.lower():
                                parts = line.split()
                                for part in parts:
                                    # Look for hex string
                                    if len(part) >= 8 and all(c in '0123456789abcdefABCDEF' for c in part):
                                        serials.append(part.lower())
                                        break

            elif model == 'rtl-sdr' or model == 'rtlsdr':
                # Run rtl_test to enumerate devices
                # Note: rtl_test can hang, so we use a longer timeout to avoid false negatives
                result = subprocess.run(
                    ['rtl_test'],
                    capture_output=True,
                    text=True,
                    timeout=5  # Increased from 2s to 5s to reduce timeouts
                )

                # rtl_test exits with error but still shows device info
                # Parse "Serial number:" or similar from output
                for line in result.stdout.split('\n') + result.stderr.split('\n'):
                    if 'SN:' in line or 'Serial' in line:
                        # Try to extract serial
                        parts = line.split()
                        for part in parts:
                            if len(part) >= 8 and (part.isdigit() or all(c in '0123456789abcdefABCDEF' for c in part)):
                                serials.append(part)
                                break

            elif model == 'usrp' or model == 'uhd':
                # Try uhd_find_devices command
                result = subprocess.run(
                    ['uhd_find_devices'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode == 0:
                    # Parse "Serial:" from output
                    for line in result.stdout.split('\n'):
                        if 'serial:' in line.lower():
                            parts = line.split(':', 1)
                            if len(parts) == 2:
                                serial = parts[1].strip()
                                if serial:
                                    serials.append(serial)

        except FileNotFoundError:
            logger.debug(f"Tool for {model} not found, cannot enumerate serials")
        except subprocess.TimeoutExpired:
            # Timeout during enumeration - log at debug level since this is common
            # for RTL-SDR devices and we have fallback logic
            logger.debug(f"Timeout while enumerating {model} devices (fallback to serial-based matching)")
        except Exception as e:
            logger.error(f"Error enumerating {model} serials: {e}", exc_info=True)

        return serials

    def resolve_device_serial(self, model: str, name: str) -> Optional[str]:
        """Resolve config device name to hardware serial number.

        For index-based names (e.g., "0", "1"), queries hardware to map
        index to serial. For serial-based names, returns the name as-is.

        Args:
            model: Device model (hackrf, bladerf, rtl-sdr, usrp)
            name: Config name (could be index "0" or serial "abc123")

        Returns:
            Serial number if found, None if device not available,
            or the name itself if it's already a serial
        """
        # If name looks like a serial (long hex/alphanumeric string), return as-is
        if not name.isdigit() and len(name) > 8:
            return name

        # If name is numeric index, map to serial
        # BUT: For rtlsdr, only treat 0-9 as indices (serials can be numeric like "1090")
        if name.isdigit():
            index = int(name)

            # For RTL-SDR: only single-digit numbers (0-9) are treated as indices
            # Multi-digit numbers like "1090", "00000001" are serials
            if model in ['rtl-sdr', 'rtlsdr']:
                if index > 9:
                    # Treat as serial number, not index
                    logger.debug(f"Treating {model}={name} as serial (not index)")
                    return name

            serials = self.enumerate_device_serials(model)

            if index < len(serials):
                return serials[index]
            else:
                # If enumeration failed (empty list) but name looks like it could be a serial,
                # treat it as a serial instead of failing
                if model in ['rtl-sdr', 'rtlsdr'] and len(name) >= 4:
                    logger.warning(
                        f"Config references {model}={name}, enumeration found {len(serials)} "
                        f"device(s), treating as serial number instead of index"
                    )
                    return name

                logger.error(
                    f"Config references {model}={name} but only {len(serials)} "
                    f"device(s) found. Device may be disconnected."
                )
                return None

        # Name is short but not numeric - could be short serial, return as-is
        return name

    def auto_detect_devices(self) -> List[Dict]:
        """Auto-detect new SDR devices using osmosdr.

        Returns:
            List of newly-detected device dicts
        """
        try:
            import osmosdr
        except ImportError:
            logger.warning("osmosdr not available, auto-detection disabled")
            return []

        newly_detected = []

        try:
            # Find all SDR devices
            devices = osmosdr.device.find()

            for device in devices:
                devicestring = device.to_string()
                attributes = devicestring.split(',')

                # Extract driver type
                driver = None
                for attr in attributes:
                    if attr.startswith('driver='):
                        driver = attr.split('=')[1]
                        break

                if not driver:
                    continue

                # Filter by agent type
                if not self._should_detect_device(driver):
                    logger.debug(f"Skipping {driver} device (not suitable for {self.agent_type})")
                    continue

                # Parse device info
                device_info = self._parse_detected_device(driver, attributes)
                if not device_info:
                    continue

                # Check if already known
                if self._is_device_known(device_info):
                    continue

                # Assign device_id
                all_devices = self.get_all_devices()
                max_id = max([d.get('device_id', -1) for d in all_devices], default=-1)
                device_info['device_id'] = max_id + 1
                device_info['source'] = 'auto_detected'
                device_info['enabled'] = False  # Disabled by default
                device_info['auto_detected_at'] = datetime.now(timezone.utc).isoformat()

                newly_detected.append(device_info)
                logger.info(f"Auto-detected new device: {device_info['model']} {device_info.get('name', 'unknown')}")

            return newly_detected

        except Exception as e:
            logger.error(f"Error during auto-detection: {e}", exc_info=True)
            return []

    def _should_detect_device(self, driver: str) -> bool:
        """Determine if device should be detected based on agent type.

        Args:
            driver: Driver name (e.g., 'rtlsdr', 'hackrf', 'bladerf')

        Returns:
            True if device should be detected for this agent type
        """
        # RX-only devices
        rx_only_drivers = ['rtlsdr', 'airspy']

        if self.agent_type == 'runner':
            # Runners skip RX-only devices
            return driver not in rx_only_drivers
        else:
            # Listeners detect all devices (including RX-only)
            return True

    def _parse_detected_device(self, driver: str, attributes: List[str]) -> Optional[Dict]:
        """Parse osmosdr device attributes into device dict.

        Args:
            driver: Driver name
            attributes: List of attribute strings from osmosdr

        Returns:
            Device dict or None if parsing fails
        """
        if driver == 'hackrf':
            return self._parse_hackrf_device(attributes)
        elif driver == 'bladerf':
            return self._parse_bladerf_device(attributes)
        elif driver == 'uhd':
            return self._parse_uhd_device(attributes)
        elif driver == 'rtlsdr':
            return self._parse_rtlsdr_device(attributes)
        elif driver == 'airspy':
            return self._parse_airspy_device(attributes)
        else:
            logger.debug(f"Unknown driver type: {driver}")
            return None

    def _parse_hackrf_device(self, attributes: List[str]) -> Optional[Dict]:
        """Parse HackRF device from osmosdr attributes."""
        serial = None
        for attr in attributes:
            if attr.startswith('serial='):
                # Remove leading zeros
                serial = attr.replace('serial=', '').lstrip('0') or '0'
                break

        # Count existing HackRF devices
        hackrf_count = sum(1 for d in self.get_all_devices() if d.get('model') == 'hackrf')

        return {
            'model': 'hackrf',
            'name': str(hackrf_count),  # Index-based
            'serial': serial,  # Explicit serial for matching
            'device_string': f'hackrf={hackrf_count}',
            'antennas_config': {},  # No frequency limits = accepts all
            'rf_gain': 14,
            'if_gain': 32,
            'bias_t': False,
            'in_use': False
        }

    def _parse_bladerf_device(self, attributes: List[str]) -> Optional[Dict]:
        """Parse BladeRF device from osmosdr attributes."""
        serial = None
        for attr in attributes:
            if attr.startswith('serial='):
                serial = attr.split('=')[1]
                break

        if not serial:
            return None

        return {
            'model': 'bladerf',
            'name': serial,
            'serial': serial,  # Explicit serial for matching
            'device_string': f'bladerf={serial}',
            'antennas_config': {},
            'rf_gain': 43,
            'if_gain': None,
            'bias_t': False,
            'in_use': False
        }

    def _parse_uhd_device(self, attributes: List[str]) -> Optional[Dict]:
        """Parse USRP/UHD device from osmosdr attributes."""
        device_type = None
        serial = None

        for attr in attributes:
            if attr.startswith('type='):
                device_type = attr.split('=')[1]
            elif attr.startswith('serial='):
                serial = attr.split('=')[1]

        if not device_type or not serial:
            return None

        return {
            'model': 'usrp',
            'name': f'type={device_type}',
            'serial': serial,  # Explicit serial for matching
            'device_string': f'uhd,type={device_type},serial={serial}',
            'antennas_config': {},
            'rf_gain': 20,
            'if_gain': None,
            'bias_t': False,
            'in_use': False
        }

    def _parse_rtlsdr_device(self, attributes: List[str]) -> Optional[Dict]:
        """Parse RTL-SDR device from osmosdr attributes.

        Uses serial number as unique identifier. RTL-SDR devices always have serials
        (either user-programmed or default like '00000001'). This ensures the same
        physical device gets the same name across multiple detection cycles.
        """
        serial = None
        label = None

        for attr in attributes:
            if attr.startswith('serial='):
                serial = attr.split('=')[1]
            elif attr.startswith('label='):
                label = attr.split('=', 1)[1]

        # Use serial number as name - RTL-SDR devices always have serials
        # (either custom or default like '00000001', '00000002', etc.)
        if serial:
            name = serial
        elif label:
            # Fallback to label if somehow no serial (very rare)
            name = f"label_{label.replace(' ', '_')}"
            logger.warning(f"RTL-SDR detected without serial, using label: {label}")
        else:
            # This should never happen - RTL-SDR devices always have serials
            # If it does, log an error and skip this device
            logger.error("RTL-SDR detected without serial or label - skipping device")
            return None

        return {
            'model': 'rtlsdr',
            'name': name,  # Serial or label-based (never index)
            'serial': serial,  # Explicit serial for matching
            'gain': 40,
            'frequency_limits': [],
            'in_use': False
        }

    def _parse_airspy_device(self, attributes: List[str]) -> Optional[Dict]:
        """Parse AirSpy device from osmosdr attributes.

        Uses serial number as unique identifier. AirSpy devices always have serials.
        This ensures the same physical device gets the same name across detection cycles.
        """
        serial = None
        label = None

        for attr in attributes:
            if attr.startswith('serial='):
                serial = attr.split('=')[1]
            elif attr.startswith('label='):
                label = attr.split('=', 1)[1]

        # Use serial number as name - AirSpy devices always have serials
        if serial:
            name = serial
        elif label:
            # Fallback to label if somehow no serial (very rare)
            name = f"label_{label.replace(' ', '_')}"
            logger.warning(f"AirSpy detected without serial, using label: {label}")
        else:
            # This should never happen - AirSpy devices always have serials
            logger.error("AirSpy detected without serial or label - skipping device")
            return None

        return {
            'model': 'airspy',
            'name': name,  # Serial or label-based (never index)
            'serial': serial,  # Explicit serial for matching
            'gain': 15,  # Default linearity gain
            'frequency_limits': [],
            'in_use': False
        }

    def _is_device_known(self, device_info: Dict) -> bool:
        """Check if device is already known (configured or detected).

        Uses intelligent matching:
        - Extracts serial from device_info
        - Compares serials instead of device_string
        - Handles both index-based and serial-based config entries

        Args:
            device_info: Device dict to check

        Returns:
            True if device already known, False otherwise
        """
        all_devices = self.get_all_devices()

        # Extract serial from device_info (from auto-detection)
        discovered_serial = device_info.get('serial')
        discovered_model = device_info.get('model')

        if not discovered_serial:
            # Fall back to exact string match for devices without serials
            # (or old-style comparison for listener devices)
            if 'device_string' in device_info:
                device_string = device_info['device_string']
                for dev in all_devices:
                    if dev.get('device_string') == device_string:
                        return True
            else:
                # Listener-style comparison
                model = device_info.get('model')
                name = device_info.get('name')
                for dev in all_devices:
                    if dev.get('model') == model and dev.get('name') == name:
                        return True
            return False

        # Compare by serial (smart matching)
        for dev in all_devices:
            dev_model = dev.get('model')
            dev_name = dev.get('name')

            if dev_model != discovered_model:
                continue

            # Resolve config device name to serial
            dev_serial = self.resolve_device_serial(dev_model, str(dev_name))

            if dev_serial == discovered_serial:
                logger.debug(
                    f"Matched discovered {discovered_model}={discovered_serial} "
                    f"to config device {dev_model}={dev_name}"
                )
                return True

        return False

    def probe_device(self, device: Dict) -> bool:
        """Probe device availability.

        Args:
            device: Device dict

        Returns:
            True if device is available, False otherwise
        """
        # Use custom probe callback if provided
        if self.probe_callback:
            return self.probe_callback(device)

        # Default: assume available (subclass should override)
        return True

    def device_probe_loop(self):
        """Background thread for periodic device probing and auto-detection."""
        logger.info("Device probe loop started")

        while self.running:
            try:
                # Auto-detect new devices (if enabled)
                if self.enable_auto_detection:
                    now = time.time()
                    if now - self.last_auto_detection >= self.device_probe_interval:
                        newly_detected = self.auto_detect_devices()

                        if newly_detected:
                            with self.auto_detected_lock:
                                self.auto_detected_devices.extend(newly_detected)

                            for dev in newly_detected:
                                logger.info(f"New device detected: {dev['model']} {dev.get('name', 'unknown')} "
                                          f"(device_id={dev['device_id']}, enabled={dev['enabled']})")

                        self.last_auto_detection = now

                # Probe all known devices
                all_devices = self.get_all_devices()
                for device in all_devices:
                    device_id = device.get('device_id')

                    # Skip disabled devices (don't waste time probing)
                    if not device.get('enabled', True):
                        continue

                    # Probe device
                    is_available = self.probe_device(device)

                    with self.device_lock:
                        currently_offline = device_id in self.offline_devices

                    # Update offline status based on probe result
                    if is_available and currently_offline:
                        # Device probe passed but was offline
                        # Keep offline until successful operation (trust verification)
                        logger.info(f"Device {device_id} probe successful, but keeping offline "
                                  f"until successful operation")
                    elif not is_available and not currently_offline:
                        # Device probe failed and was online
                        failure_count = self.record_device_failure(device_id)
                        logger.warning(f"Device {device_id} probe failed (failure {failure_count}/3)")

                        if failure_count >= 3:
                            logger.error(f"Device {device_id} marked OFFLINE after 3 consecutive probe failures")

                # Wait before next probe cycle
                time.sleep(self.device_probe_interval)

            except Exception as e:
                logger.error(f"Error in device probe loop: {e}", exc_info=True)
                time.sleep(self.device_probe_interval)

    def start_probe_loop(self):
        """Start the device probe loop in a background thread."""
        if self.device_probe_interval <= 0:
            logger.info("Device probing disabled (interval = 0)")
            return

        self.running = True
        self.probe_thread = threading.Thread(target=self.device_probe_loop, daemon=True)
        self.probe_thread.start()
        logger.info(f"Device probe loop started (interval: {self.device_probe_interval}s, "
                   f"auto-detect: {self.enable_auto_detection})")

    def stop_probe_loop(self):
        """Stop the device probe loop."""
        self.running = False
        if self.probe_thread:
            self.probe_thread.join(timeout=2)

    def get_device_status_dict(self) -> Dict[int, str]:
        """Get device status dictionary for heartbeat.

        Returns:
            Dict mapping device_id to status string (online/busy/offline/disabled)
        """
        device_status = {}

        with self.device_lock:
            all_devices = self.get_all_devices()
            for device in all_devices:
                device_id = device.get('device_id')

                if not device.get('enabled', True):
                    device_status[device_id] = 'disabled'
                elif device_id in self.offline_devices:
                    device_status[device_id] = 'offline'
                elif device_id in self.busy_devices:
                    device_status[device_id] = 'busy'
                else:
                    device_status[device_id] = 'online'

        return device_status

    def apply_device_config_updates(self, updates: List[Dict]):
        """Apply device configuration updates from server.

        Args:
            updates: List of device config update dicts with device_id and enabled fields
        """
        for update in updates:
            device_id = update.get('device_id')
            enabled = update.get('enabled')

            if device_id is None or enabled is None:
                continue

            # Find device (configured or auto-detected)
            all_devices = self.get_all_devices()
            for device in all_devices:
                if device.get('device_id') == device_id:
                    old_enabled = device.get('enabled', True)
                    device['enabled'] = enabled

                    if old_enabled != enabled:
                        status = "enabled" if enabled else "disabled"
                        logger.info(f"Device {device_id} ({device.get('model')} {device.get('name')}) {status} via server")

                    break
