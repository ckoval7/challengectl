#!/usr/bin/env python3
"""
Shared Device Management Module for ChallengeCtl

Provides common device auto-detection, probing, and management functionality
for both runners (TX) and listeners (RX).
"""

import logging
import time
import threading
import os
import sys
import subprocess
import gc  # For explicit USB handle cleanup after osmosdr enumeration
from datetime import datetime, timezone
from typing import List, Dict, Optional, Callable

try:
    import pyudev
    PYUDEV_AVAILABLE = True
except ImportError:
    PYUDEV_AVAILABLE = False

logger = logging.getLogger(__name__)


# Known SDR vendor IDs (for USB device filtering)
SDR_VENDOR_IDS = {
    '1d50',  # Great Scott Gadgets (HackRF, AirSpy)
    '2cf0',  # Nuand (BladeRF)
    '0bda',  # Realtek (RTL-SDR dongles)
    '2500',  # Ettus Research (USRP B-series)
    '3923',  # Ettus Research (USRP X-series)
    '16c0',  # Van Ooijen Technische Informatica (FUNcube Dongle)
}

# USB device classes to block (non-SDR devices)
BLOCKED_USB_CLASSES = {
    '01',  # Audio
    '03',  # HID (keyboards, mice)
    '05',  # Physical
    '06',  # Image
    '07',  # Printer
    '08',  # Mass Storage
    '09',  # Hub
    '0a',  # CDC-Data
    '0b',  # Smart Card
    '0d',  # Content Security
    '0e',  # Video
}


class USBEventMonitor:
    """Monitors USB events and triggers device probing on SDR device changes.

    Uses Linux udev to detect USB device add/remove events and filters
    out non-SDR devices (HID, storage, etc.) to avoid unnecessary probing.
    """

    def __init__(self, probe_callback: Callable, debounce_interval: float = 1.0):
        """Initialize USB event monitor.

        Args:
            probe_callback: Function to call when SDR device change detected
            debounce_interval: Minimum seconds between probe triggers (default: 1.0)
        """
        if not PYUDEV_AVAILABLE:
            raise ImportError("pyudev is not available - USB event monitoring requires pyudev")

        self.probe_callback = probe_callback
        self.debounce_interval = debounce_interval
        self.last_probe_time = 0
        self.debounce_lock = threading.Lock()

        # Initialize pyudev
        self.context = pyudev.Context()
        self.monitor = pyudev.Monitor.from_netlink(self.context)
        self.monitor.filter_by(subsystem='usb')

        # Observer will call _on_usb_event in a separate thread
        self.observer = pyudev.MonitorObserver(self.monitor, self._on_usb_event)

        logger.info("USB event monitor initialized (debounce: %.1fs)", debounce_interval)

    def start(self):
        """Start monitoring USB events."""
        self.observer.start()
        logger.info("USB event monitoring started")

    def stop(self):
        """Stop monitoring USB events."""
        self.observer.stop()
        logger.info("USB event monitoring stopped")

    def _on_usb_event(self, action, device):
        """Handle USB device add/remove events.

        Args:
            action: Event action ('add', 'remove', etc.) - pyudev passes this
            device: pyudev.Device object
        """
        try:
            # Only care about add/remove events
            if action not in ('add', 'remove'):
                return

            # Filter out non-SDR devices
            if not self._is_sdr_device(device):
                return

            # Get device info for logging
            vendor_id = device.get('ID_VENDOR_ID', 'unknown')
            product_id = device.get('ID_MODEL_ID', 'unknown')
            serial = device.get('ID_SERIAL_SHORT', '')

            logger.info(f"USB {action} event: vendor={vendor_id} product={product_id} serial={serial}")

            # Trigger probe with debouncing
            self._trigger_probe_debounced()

        except Exception as e:
            logger.error(f"Error handling USB event: {e}", exc_info=True)

    def _is_sdr_device(self, device) -> bool:
        """Check if USB device is likely an SDR device.

        Args:
            device: pyudev.Device object

        Returns:
            True if device should trigger probe, False otherwise
        """
        # Check vendor ID against known SDR vendors
        vendor_id = device.get('ID_VENDOR_ID', '').lower()
        if vendor_id in SDR_VENDOR_IDS:
            logger.debug(f"USB device matched SDR vendor ID: {vendor_id}")
            return True

        # Check device class - block known non-SDR classes
        device_class = device.get('ID_USB_CLASS_FROM_DATABASE', '').lower()
        interfaces = device.get('ID_USB_INTERFACES', '').lower()

        # Extract class codes from interfaces string (format: ":ffffff00:020200:")
        for interface in interfaces.split(':'):
            if len(interface) >= 2:
                class_code = interface[:2]
                if class_code in BLOCKED_USB_CLASSES:
                    logger.debug(f"USB device blocked by class code: {class_code}")
                    return False

        # Check if it's a vendor-specific device (class 0xFF) or communication device (class 0x02)
        # Many SDRs use vendor-specific class
        if interfaces:
            for interface in interfaces.split(':'):
                if len(interface) >= 2:
                    class_code = interface[:2]
                    if class_code in ('ff', '02'):  # Vendor-specific or Communications
                        logger.debug(f"USB device allowed by class code: {class_code}")
                        return True

        # If we can't determine, be conservative and allow it
        # (Better to have a false positive than miss an SDR)
        logger.debug(f"USB device allowed by default (vendor={vendor_id})")
        return True

    def _trigger_probe_debounced(self):
        """Trigger probe callback with debouncing to prevent rapid successive probes."""
        with self.debounce_lock:
            now = time.time()
            time_since_last = now - self.last_probe_time

            if time_since_last < self.debounce_interval:
                logger.debug(f"Probe debounced (last probe {time_since_last:.1f}s ago)")
                return

            self.last_probe_time = now

        # Call probe callback
        try:
            logger.debug("Triggering immediate device probe from USB event")
            self.probe_callback()
        except Exception as e:
            logger.error(f"Error in probe callback: {e}", exc_info=True)


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

        # Event-driven probing
        self.probe_event = threading.Event()  # Event for triggering immediate probe
        self.probe_thread = None
        self.running = False

        # USB event monitoring
        self.usb_monitor = None
        if PYUDEV_AVAILABLE:
            try:
                self.usb_monitor = USBEventMonitor(
                    probe_callback=self._trigger_immediate_probe,
                    debounce_interval=1.0
                )
                logger.info("USB event monitoring initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize USB event monitoring: {e}")
                self.usb_monitor = None
        else:
            logger.warning("pyudev not available - USB event monitoring disabled")

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
                # Resolve serial for this device (quiet=False for startup - we want to see issues once)
                serial = self.resolve_device_serial(model, str(name), quiet=False)

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
                # Use osmosdr to enumerate RTL-SDR devices
                # osmosdr.device.find() provides serial numbers without permanently claiming devices
                try:
                    import osmosdr

                    # Suppress stderr during device enumeration to hide library warnings
                    stderr_fd = sys.stderr.fileno()
                    old_stderr = os.dup(stderr_fd)
                    devnull = os.open(os.devnull, os.O_WRONLY)
                    os.dup2(devnull, stderr_fd)

                    try:
                        # Find all SDR devices
                        devices = osmosdr.device.find()
                    finally:
                        # Restore stderr
                        os.dup2(old_stderr, stderr_fd)
                        os.close(old_stderr)
                        os.close(devnull)

                    # Extract RTL-SDR serials in order
                    for device in devices:
                        devicestring = device.to_string()
                        attributes = devicestring.split(',')

                        # Check if this is an RTL-SDR device
                        driver = None
                        serial = None
                        for attr in attributes:
                            if attr.startswith('driver='):
                                driver = attr.split('=')[1]
                            elif attr.startswith('serial='):
                                serial = attr.split('=')[1]

                        if driver == 'rtlsdr' and serial:
                            serials.append(serial)

                    # CRITICAL FIX: Explicitly release osmosdr device handles
                    # osmosdr.device.find() creates C/C++ objects with USB handles that persist
                    # until Python GC runs. Without explicit cleanup, handles accumulate across
                    # probe cycles (every 30s) and eventually exhaust USB resources, causing
                    # "usb_claim_interface error -6" and preventing listeners from recording.
                    del devices  # Delete reference to device list
                    gc.collect()  # Force immediate garbage collection to release USB handles
                    logger.debug("Released osmosdr device handles after RTL-SDR enumeration")

                except ImportError:
                    logger.debug("osmosdr not available, cannot enumerate RTL-SDR devices")
                except Exception as e:
                    logger.debug(f"Error enumerating RTL-SDR devices via osmosdr: {e}")

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

    def resolve_device_serial(self, model: str, name: str, quiet: bool = False) -> Optional[str]:
        """Resolve config device name to hardware serial number.

        For index-based names (e.g., "0", "1"), queries hardware to map
        index to serial. For serial-based names, returns the name as-is.

        Args:
            model: Device model (hackrf, bladerf, rtl-sdr, usrp)
            name: Config name (could be index "0" or serial "abc123")
            quiet: If True, suppress error logging (for probing/retries)

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
                if model in ['rtl-sdr', 'rtlsdr']:
                    if len(name) >= 4:
                        # Multi-digit number - treat as serial
                        if not quiet:
                            logger.warning(
                                f"Config references {model}={name}, enumeration found {len(serials)} "
                                f"device(s), treating as serial number instead of index"
                            )
                        return name
                    else:
                        # Single-digit index (0-9) but enumeration returned empty
                        # For RTL-SDR, we intentionally skip enumeration to avoid claiming devices
                        # Return None but don't error - device matching will rely on auto-detection
                        if not quiet:
                            logger.warning(
                                f"Config references {model}={name} by index. "
                                f"For RTL-SDR, serial-based naming (e.g., {model}=1090) is recommended "
                                f"to avoid device claiming issues. Device matching will rely on auto-detection."
                            )
                        return None

                # For non-RTL-SDR devices, log error only if not in quiet mode
                if not quiet:
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
        devices = None  # Initialize for exception safety in finally block

        try:
            # Suppress stderr during device enumeration to hide library warnings
            # (usb_claim_interface errors, ALSA warnings, libusb warnings, etc.)
            stderr_fd = sys.stderr.fileno()
            old_stderr = os.dup(stderr_fd)
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, stderr_fd)

            try:
                # Find all SDR devices
                devices = osmosdr.device.find()
            finally:
                # Restore stderr
                os.dup2(old_stderr, stderr_fd)
                os.close(old_stderr)
                os.close(devnull)

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

        finally:
            # CRITICAL FIX: Always release osmosdr device handles before returning
            # This prevents USB handle leaks that cause RTL-SDR lockups over time.
            # Without this, repeated probe cycles (every 30s) accumulate USB handles
            # until resources are exhausted, preventing recording with "error -6".
            if devices is not None:
                try:
                    del devices  # Delete device list reference
                    gc.collect()  # Force immediate garbage collection
                    logger.debug("Released osmosdr device handles after auto-detection")
                except Exception as cleanup_error:
                    # Log but don't raise - cleanup failure shouldn't break auto-detection
                    logger.warning(f"Error during osmosdr cleanup: {cleanup_error}")

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

            # Resolve config device name to serial (quiet mode - this runs during probing)
            dev_serial = self.resolve_device_serial(dev_model, str(dev_name), quiet=True)

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

    def _trigger_immediate_probe(self):
        """Trigger immediate device probe (called by USB event monitor)."""
        logger.debug("Immediate probe triggered by USB event")
        self.probe_event.set()

    def device_probe_loop(self):
        """Background thread for event-driven device probing and auto-detection.

        Waits for USB events and triggers immediate probing when SDR devices change.
        No time-based polling - purely event-driven.
        """
        logger.info("Device probe loop started (event-driven, no polling)")

        # Perform initial probe at startup
        self._perform_probe_cycle()

        while self.running:
            try:
                # Wait for USB event (blocks until event is set)
                # This is event-driven - no polling!
                self.probe_event.wait()

                # Clear the event flag
                self.probe_event.clear()

                # Perform probe cycle
                self._perform_probe_cycle()

            except Exception as e:
                logger.error(f"Error in device probe loop: {e}", exc_info=True)
                # Brief sleep to avoid tight loop on repeated errors
                time.sleep(1)

    def _perform_probe_cycle(self):
        """Perform a single probe cycle (auto-detect + probe all devices)."""
        # Auto-detect new devices (if enabled)
        if self.enable_auto_detection:
            newly_detected = self.auto_detect_devices()

            if newly_detected:
                with self.auto_detected_lock:
                    self.auto_detected_devices.extend(newly_detected)

                for dev in newly_detected:
                    logger.info(f"New device detected: {dev['model']} {dev.get('name', 'unknown')} "
                              f"(device_id={dev['device_id']}, enabled={dev['enabled']})")

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

    def start_probe_loop(self):
        """Start the device probe loop and USB event monitoring."""
        self.running = True

        # Start probe thread
        self.probe_thread = threading.Thread(target=self.device_probe_loop, daemon=True)
        self.probe_thread.start()

        # Start USB event monitoring
        if self.usb_monitor:
            try:
                self.usb_monitor.start()
                logger.info("Device probe loop and USB event monitoring started "
                           f"(auto-detect: {self.enable_auto_detection})")
            except Exception as e:
                logger.error(f"Failed to start USB event monitoring: {e}")
        else:
            logger.warning("USB event monitoring not available - device changes won't be detected automatically")

    def stop_probe_loop(self):
        """Stop the device probe loop and USB event monitoring."""
        self.running = False

        # Stop USB event monitoring
        if self.usb_monitor:
            try:
                self.usb_monitor.stop()
            except Exception as e:
                logger.error(f"Error stopping USB event monitor: {e}")

        # Signal the probe thread to wake up and exit
        self.probe_event.set()

        # Wait for probe thread to finish
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
