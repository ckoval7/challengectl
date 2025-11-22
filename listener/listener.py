#!/usr/bin/env python3
"""
Spectrum Listener Agent for ChallengeCtl

Connects to the ChallengeCtl server via WebSocket to receive real-time
recording assignments. When a runner is assigned a transmission task,
this listener captures the RF signal and generates a waterfall image.

Architecture:
- WebSocket connection to server for real-time push notifications
- HTTP endpoints for status reporting and file uploads
- GNU Radio flowgraph for RF capture
- Matplotlib for waterfall image generation
"""

import sys
import os
import time
import logging
import argparse
import yaml
import socket
import hashlib
import requests
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import socketio

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Initial basic logging setup (will be reconfigured in main() after parsing args)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s challengectl-listener[%(process)d]: %(levelname)s: %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S'
)
logger = logging.getLogger(__name__)


class ServerLogHandler(logging.Handler):
    """Custom logging handler that forwards logs to the server."""

    def __init__(self, listener_instance):
        super().__init__()
        self.listener = listener_instance
        self.setLevel(logging.DEBUG)  # Forward all log levels

    def emit(self, record):
        """Send log record to server."""
        # Don't send logs if listener is shutting down
        if not self.listener or not hasattr(self.listener, 'send_log') or not self.listener.running:
            return

        try:
            msg = record.getMessage()

            # Don't forward logs about log sending failures (avoid recursion)
            if 'Failed to send log to server' in msg:
                return

            # Don't forward shutdown-related logs to avoid hanging during shutdown
            if 'Received interrupt signal' in msg or 'shutting down' in msg.lower() or 'Signing out' in msg:
                return

            # Filter out noisy HTTP request logs from urllib3/requests
            if record.name in ('urllib3.connectionpool', 'requests'):
                return

            # Filter out debug logs from our own HTTP operations
            if 'Starting new HTTPS connection' in msg or \
               'Starting new HTTP connection' in msg or \
               'Resetting dropped connection' in msg:
                return

            self.listener.send_log(record.levelname, msg)
        except Exception:
            # Silently ignore errors to prevent recursion
            pass


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


class ListenerAgent:
    """Spectrum listener agent that receives WebSocket recording assignments."""

    def __init__(self, config_path: str, simulate: bool = False):
        """Initialize listener agent.

        Args:
            config_path: Path to listener configuration YAML file
            simulate: Force simulation mode (generate test data without SDR hardware)
        """
        self.config = self.load_config(config_path)
        self.agent_id = self.config['agent']['agent_id']
        self.server_url = self.config['agent']['server_url'].rstrip('/')
        self.api_key = self.config['agent']['api_key']
        self.heartbeat_interval = self.config['agent'].get('heartbeat_interval', 30)
        self.simulate = simulate

        # TLS configuration
        self.ca_cert = self.config['agent'].get('ca_cert')
        self.verify_ssl = self.config['agent'].get('verify_ssl', True)

        if simulate:
            logger.info("Simulation mode enabled - will generate test data without SDR hardware")

        # Device info
        self.devices = self.detect_devices()

        # HTTP session for connection pooling
        self.session = requests.Session()

        # Get host identifiers for authentication
        mac_address = get_mac_address()
        machine_id = get_machine_id()

        # Set authentication headers including host identifiers
        headers = {'Authorization': f'Bearer {self.api_key}'}
        if mac_address:
            headers['X-Agent-MAC'] = mac_address
        if machine_id:
            headers['X-Agent-Machine-ID'] = machine_id

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

        # WebSocket client
        # Note: reconnection=False because we handle reconnection manually with auth
        self.sio = socketio.Client(
            reconnection=False,
            logger=True,
            engineio_logger=True
        )

        # Recording state
        self.current_recording = None
        self.recording_lock = threading.Lock()

        # Heartbeat thread
        self.heartbeat_thread = None
        self.running = False

        # Reconnection state
        self.reconnecting = False
        self.reconnect_lock = threading.Lock()

        # Register WebSocket event handlers
        self.register_websocket_handlers()

        logger.info(f"Listener initialized: {self.agent_id}")

    def load_config(self, config_path: str) -> Dict:
        """Load listener configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded configuration from {config_path}")
                return config
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            sys.exit(1)

    def detect_devices(self) -> list:
        """Detect available SDR devices from configuration.

        Returns:
            List of device dictionaries with name, model, gain, frequency_limits
        """
        devices = []

        # First, try new radios.devices format (multi-device)
        radios_config = self.config.get('radios', {})
        devices_config = radios_config.get('devices', [])

        if devices_config:
            # New format: multiple devices with gain and frequency_limits
            for device in devices_config:
                device_info = {
                    'name': str(device.get('name', '0')),
                    'model': device.get('model', 'rtlsdr'),
                    'gain': device.get('gain', 40),
                    'frequency_limits': device.get('frequency_limits', []),
                    'in_use': False  # Track device availability
                }
                devices.append(device_info)
                logger.info(f"Configured device: {device_info['model']}={device_info['name']} "
                          f"(gain: {device_info['gain']} dB, freq_limits: {device_info['frequency_limits']})")
        else:
            # Fallback to old format: single device in agent.recording.device
            device_config = self.config['agent'].get('recording', {}).get('device', {})
            gain = self.config['agent'].get('recording', {}).get('gain', 40)

            if device_config:
                device_info = {
                    'name': device_config.get('id', 'rtlsdr=0'),
                    'model': device_config.get('type', 'rtlsdr'),
                    'gain': gain,
                    'frequency_limits': [],
                    'in_use': False
                }
                devices.append(device_info)
                logger.info(f"Configured device (legacy format): {device_info['model']}={device_info['name']} "
                          f"(gain: {device_info['gain']} dB)")

        if not devices:
            logger.warning("No SDR devices configured!")

        return devices

    def select_device(self, frequency: int) -> Optional[Dict]:
        """Select an appropriate device for the given frequency.

        Selection criteria:
        1. Device must not be currently in use
        2. If device has frequency_limits, frequency must be within range
        3. If multiple devices match, prefer first match

        Args:
            frequency: Center frequency in Hz

        Returns:
            Device dict if found, None if no suitable device available
        """
        available_devices = []

        for device in self.devices:
            # Skip devices currently in use
            if device.get('in_use', False):
                continue

            freq_limits = device.get('frequency_limits', [])

            # If no frequency limits, device can handle any frequency
            if not freq_limits:
                available_devices.append(device)
                continue

            # Check if frequency is within any of the device's ranges
            for freq_range in freq_limits:
                try:
                    # Parse range like "144000000-148000000"
                    if '-' in freq_range:
                        min_freq, max_freq = map(int, freq_range.split('-'))
                        if min_freq <= frequency <= max_freq:
                            available_devices.append(device)
                            break
                except ValueError:
                    logger.warning(f"Invalid frequency range format: {freq_range}")

        if not available_devices:
            logger.error(f"No available device for frequency {frequency} Hz")
            return None

        # Return first available device
        selected = available_devices[0]
        logger.info(f"Selected device {selected['model']}={selected['name']} "
                   f"for {frequency} Hz (gain: {selected['gain']} dB)")
        return selected

    def register_websocket_handlers(self):
        """Register WebSocket event handlers for SocketIO client."""

        @self.sio.on('connect', namespace='/agents')
        def on_connect():
            logger.info(f"WebSocket connected to server")

        @self.sio.on('disconnect', namespace='/agents')
        def on_disconnect():
            logger.warning("WebSocket disconnected from server")
            # Start reconnection attempt in background thread
            if self.running:
                threading.Thread(target=self.reconnect_websocket, daemon=True).start()

        @self.sio.on('connected', namespace='/agents')
        def on_connected_ack(data):
            logger.info(f"Server acknowledged connection: {data.get('message')}")

        @self.sio.on('recording_assignment', namespace='/agents')
        def on_recording_assignment(data):
            """Handle recording assignment from server."""
            try:
                print(f"[DEBUG] Handler called with data: {data}", flush=True)
                logger.info(f"Received recording assignment: {data}")

                assignment_id = data.get('assignment_id')
                challenge_id = data.get('challenge_id')
                challenge_name = data.get('challenge_name')
                transmission_id = data.get('transmission_id')
                frequency = data.get('frequency')
                expected_start = data.get('expected_start')
                expected_duration = data.get('expected_duration')

                print(f"[DEBUG] Starting recording thread for {challenge_name}", flush=True)
                # Schedule recording
                threading.Thread(
                    target=self.handle_recording_assignment,
                    args=(assignment_id, challenge_id, challenge_name, transmission_id,
                          frequency, expected_start, expected_duration),
                    daemon=True
                ).start()
                print(f"[DEBUG] Recording thread started", flush=True)
            except Exception as e:
                print(f"[ERROR] Exception in recording_assignment handler: {e}", flush=True)
                logger.error(f"Error in recording_assignment handler: {e}", exc_info=True)

        @self.sio.on('heartbeat_ack', namespace='/agents')
        def on_heartbeat_ack(data):
            logger.debug(f"Heartbeat acknowledged by server")

    def handle_recording_assignment(self, assignment_id: int, challenge_id: str,
                                   challenge_name: str, transmission_id: int,
                                   frequency: int, expected_start: str,
                                   expected_duration: float):
        """Handle a recording assignment by capturing RF and generating waterfall.

        Args:
            assignment_id: Assignment ID for tracking
            challenge_id: Challenge ID
            challenge_name: Human-readable challenge name
            transmission_id: Transmission ID for linking
            frequency: Center frequency in Hz
            expected_start: ISO format timestamp of expected transmission start
            expected_duration: Expected duration in seconds
        """
        print(f"[DEBUG] handle_recording_assignment started for {challenge_name}", flush=True)

        with self.recording_lock:
            if self.current_recording:
                logger.warning(f"Already recording, cannot start new recording for {challenge_name}")
                print(f"[DEBUG] Already recording, skipping", flush=True)
                return

            self.current_recording = {
                'assignment_id': assignment_id,
                'challenge_id': challenge_id,
                'challenge_name': challenge_name,
                'transmission_id': transmission_id,
                'frequency': frequency,
                'expected_start': expected_start,
                'expected_duration': expected_duration
            }

        print(f"[DEBUG] Current recording set, proceeding", flush=True)

        try:
            # Parse expected start time
            print(f"[DEBUG] Parsing expected_start: {expected_start}", flush=True)
            start_time = datetime.fromisoformat(expected_start.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)

            # Calculate delay until recording should start
            delay_seconds = (start_time - now).total_seconds()
            print(f"[DEBUG] Delay until start: {delay_seconds:.1f}s", flush=True)

            if delay_seconds > 0:
                logger.info(f"Waiting {delay_seconds:.1f}s until recording starts for {challenge_name}")
                time.sleep(delay_seconds)

            print(f"[DEBUG] Notifying server recording started", flush=True)

            # Notify server recording has started
            recording_config = self.config['agent'].get('recording', {})
            sample_rate = recording_config.get('sample_rate', 2000000)

            recording_id = self.notify_recording_started(
                challenge_id=challenge_id,
                transmission_id=transmission_id,
                frequency=frequency,
                sample_rate=sample_rate,
                expected_duration=expected_duration
            )

            print(f"[DEBUG] Recording ID from server: {recording_id}", flush=True)

            if recording_id <= 0:
                logger.error(f"Failed to create recording entry on server")
                return

            # Perform the actual recording
            logger.info(f"Starting recording for {challenge_name} at {frequency} Hz")
            success, image_path, duration, error_message = self.record_transmission(
                frequency=frequency,
                duration=expected_duration,
                challenge_name=challenge_name
            )

            # Notify server recording completed
            if success:
                self.notify_recording_complete(
                    recording_id=recording_id,
                    success=True,
                    image_path=image_path,
                    duration=duration
                )

                # Upload waterfall image
                self.upload_waterfall_image(recording_id, image_path)

                logger.info(f"Successfully recorded and uploaded waterfall for {challenge_name}")
            else:
                self.notify_recording_complete(
                    recording_id=recording_id,
                    success=False,
                    error_message=error_message
                )
                logger.error(f"Recording failed for {challenge_name}: {error_message}")

        except Exception as e:
            logger.error(f"Error handling recording assignment: {e}", exc_info=True)
        finally:
            with self.recording_lock:
                self.current_recording = None

    def record_transmission(self, frequency: int, duration: float,
                          challenge_name: str) -> tuple:
        """Capture RF transmission and generate waterfall image.

        Args:
            frequency: Center frequency in Hz
            duration: Recording duration in seconds
            challenge_name: Challenge name for filename

        Returns:
            Tuple of (success, image_path, actual_duration, error_message)
        """
        selected_device = None
        try:
            # Import GNU Radio components
            from spectrum_listener import SpectrumListener
            from waterfall_generator import generate_waterfall

            # In simulation mode, create a dummy device
            if self.simulate:
                logger.info(f"Simulation mode: Recording {frequency} Hz (frequency-independent)")
                selected_device = {
                    'name': 'simulated',
                    'model': 'simulated',
                    'gain': 40,
                    'in_use': False
                }
            else:
                # Select appropriate device for this frequency
                selected_device = self.select_device(frequency)
                if not selected_device:
                    error_msg = f"No available device for frequency {frequency} Hz"
                    logger.error(error_msg)
                    return False, None, 0, error_msg

                # Mark device as in use
                selected_device['in_use'] = True

            recording_config = self.config['agent'].get('recording', {})
            output_dir = recording_config.get('output_dir', 'recordings')
            os.makedirs(output_dir, exist_ok=True)

            sample_rate = recording_config.get('sample_rate', 2000000)
            fft_size = recording_config.get('fft_size', 1024)
            frame_rate = recording_config.get('frame_rate', 20)
            pre_roll = recording_config.get('pre_roll_seconds', 5)
            post_roll = recording_config.get('post_roll_seconds', 5)

            # Total recording duration includes pre-roll and post-roll
            total_duration = pre_roll + duration + post_roll

            # Build device identifier string for osmosdr
            device_id = f"{selected_device['model']}={selected_device['name']}"

            # Create spectrum listener with device-specific parameters
            listener = SpectrumListener(
                frequency=frequency,
                sample_rate=sample_rate,
                fft_size=fft_size,
                gain=selected_device['gain'],
                device_id=device_id,
                simulate=self.simulate
            )

            logger.info(f"Capturing {total_duration}s at {frequency} Hz (SR: {sample_rate})")

            # Start recording
            start_time = time.time()
            fft_data = listener.record(duration=total_duration, frame_rate=frame_rate)
            actual_duration = time.time() - start_time

            # Generate waterfall image
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            image_filename = f"{challenge_name}_{timestamp}.png"
            image_path = os.path.join(output_dir, image_filename)

            logger.info(f"Generating waterfall image: {image_path}")
            generate_waterfall(
                fft_data=fft_data,
                frequency=frequency,
                sample_rate=sample_rate,
                fft_size=fft_size,
                frame_rate=frame_rate,
                output_path=image_path
            )

            return (True, image_path, actual_duration, None)

        except Exception as e:
            error_msg = f"Recording failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, None, 0, error_msg)
        finally:
            # Release device for next recording (skip for simulated devices)
            if selected_device and not self.simulate:
                selected_device['in_use'] = False
                logger.debug(f"Released device {selected_device['model']}={selected_device['name']}")

    def notify_recording_started(self, challenge_id: str, transmission_id: int,
                                frequency: int, sample_rate: int,
                                expected_duration: float) -> int:
        """Notify server that recording has started.

        Returns:
            recording_id from server, or -1 on error
        """
        try:
            response = self.session.post(
                f"{self.server_url}/api/agents/{self.agent_id}/recording/start",
                json={
                    'challenge_id': challenge_id,
                    'transmission_id': transmission_id,
                    'frequency': frequency,
                    'sample_rate': sample_rate,
                    'expected_duration': expected_duration
                },
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return data.get('recording_id', -1)
            else:
                logger.error(f"Failed to notify recording start: {response.status_code}")
                return -1

        except Exception as e:
            logger.error(f"Error notifying recording start: {e}")
            return -1

    def notify_recording_complete(self, recording_id: int, success: bool,
                                 image_path: Optional[str] = None,
                                 duration: Optional[float] = None,
                                 error_message: Optional[str] = None):
        """Notify server that recording has completed."""
        try:
            # Get image dimensions if available
            image_width, image_height = None, None
            if success and image_path:
                from PIL import Image
                with Image.open(image_path) as img:
                    image_width, image_height = img.size

            response = self.session.post(
                f"{self.server_url}/api/agents/{self.agent_id}/recording/{recording_id}/complete",
                json={
                    'success': success,
                    'duration': duration,
                    'image_width': image_width,
                    'image_height': image_height,
                    'error_message': error_message
                },
                timeout=10
            )

            if response.status_code != 200:
                logger.error(f"Failed to notify recording complete: {response.status_code}")

        except Exception as e:
            logger.error(f"Error notifying recording complete: {e}")

    def upload_waterfall_image(self, recording_id: int, image_path: str):
        """Upload waterfall PNG image to server."""
        try:
            # Verify file exists
            if not os.path.exists(image_path):
                logger.error(f"Waterfall image file not found: {image_path}")
                return

            file_size = os.path.getsize(image_path)
            logger.info(f"Uploading waterfall image for recording {recording_id}: {image_path} ({file_size} bytes)")

            with open(image_path, 'rb') as f:
                files = {'file': (os.path.basename(image_path), f, 'image/png')}
                response = self.session.post(
                    f"{self.server_url}/api/agents/{self.agent_id}/recording/{recording_id}/upload",
                    files=files,
                    timeout=60  # Longer timeout for file upload
                )

                if response.status_code == 200:
                    logger.info(f"Successfully uploaded waterfall image for recording {recording_id}")
                else:
                    logger.error(f"Failed to upload waterfall for recording {recording_id}: HTTP {response.status_code}")
                    logger.error(f"Response: {response.text}")

        except Exception as e:
            logger.error(f"Error uploading waterfall image for recording {recording_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def enroll(self) -> bool:
        """Enroll this listener with the server using enrollment token.

        Uses the enrollment token from config to register with the server.
        After enrollment, the listener should be restarted without the enrollment_token in config.
        """
        enrollment_token = self.config['agent'].get('enrollment_token')

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
                    'name': dev.get('name'),
                    'model': dev.get('model'),
                    'gain': dev.get('gain'),
                    'frequency_limits': dev.get('frequency_limits', [])
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
                    'agent_id': self.agent_id,
                    'agent_type': 'listener',
                    'hostname': hostname,
                    'mac_address': mac_address,
                    'machine_id': machine_id,
                    'devices': devices_info
                },
                timeout=10
            )

            if response.status_code == 201:
                logger.info(f"Successfully enrolled as {self.agent_id}")
                return True
            elif response.status_code == 401:
                logger.error("Enrollment failed: Invalid or expired enrollment token")
                return False
            elif response.status_code == 409:
                logger.info("Listener already enrolled with this token")
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

    def register_with_server(self) -> bool:
        """Register this listener agent with the server via HTTP.

        Note: This is now primarily for backwards compatibility.
        New listeners should use the enrollment process instead.
        """
        try:
            hostname = socket.gethostname()

            # Prepare device info for server
            devices_info = []
            for dev in self.devices:
                devices_info.append({
                    'name': dev.get('name'),
                    'model': dev.get('model'),
                    'gain': dev.get('gain'),
                    'frequency_limits': dev.get('frequency_limits', [])
                })

            response = self.session.post(
                f"{self.server_url}/api/agents/register",
                json={
                    'agent_type': 'listener',
                    'hostname': hostname,
                    'devices': devices_info
                },
                timeout=10
            )

            if response.status_code == 200:
                logger.info(f"Successfully registered with server as listener {self.agent_id}")
                return True
            else:
                logger.error(f"Failed to register: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error registering with server: {e}")
            return False

    def connect_websocket(self) -> bool:
        """Connect to server WebSocket for real-time assignments."""
        try:
            # Connect with authentication
            auth_data = {
                'agent_id': self.agent_id,
                'api_key': self.api_key
            }

            self.sio.connect(
                self.server_url,
                auth=auth_data,
                namespaces=['/agents'],
                wait_timeout=10
            )

            logger.info("WebSocket connection established")
            return True

        except Exception as e:
            logger.error(f"Failed to connect WebSocket: {e}")
            return False

    def reconnect_websocket(self):
        """Attempt to reconnect WebSocket with exponential backoff."""
        # Prevent multiple reconnection threads
        if not self.reconnect_lock.acquire(blocking=False):
            logger.debug("Reconnection already in progress, skipping")
            return

        try:
            self.reconnecting = True
            max_attempts = 10
            base_delay = 2
            max_delay = 60

            for attempt in range(1, max_attempts + 1):
                if not self.running:
                    logger.info("Listener shutting down, aborting reconnection")
                    return

                # Calculate delay with exponential backoff
                delay = min(base_delay * (2 ** (attempt - 1)), max_delay)

                logger.info(f"WebSocket reconnection attempt {attempt}/{max_attempts} in {delay}s...")
                time.sleep(delay)

                try:
                    # Disconnect first if still connected
                    if self.sio.connected:
                        try:
                            self.sio.disconnect()
                        except:
                            pass

                    # Reconnect with authentication
                    auth_data = {
                        'agent_id': self.agent_id,
                        'api_key': self.api_key
                    }

                    self.sio.connect(
                        self.server_url,
                        auth=auth_data,
                        namespaces=['/agents'],
                        wait_timeout=10
                    )

                    logger.info(f"WebSocket reconnected successfully after {attempt} attempt(s)")
                    return

                except Exception as e:
                    logger.warning(f"Reconnection attempt {attempt} failed: {e}")
                    if attempt == max_attempts:
                        logger.error("Max reconnection attempts reached, giving up")
                        # Could optionally exit here or alert the user

        finally:
            self.reconnecting = False
            self.reconnect_lock.release()

    def send_heartbeat_http(self):
        """Send heartbeat to server via HTTP."""
        try:
            response = self.session.post(
                f"{self.server_url}/api/agents/{self.agent_id}/heartbeat",
                timeout=5
            )

            if response.status_code == 200:
                logger.debug("Heartbeat sent successfully")
            else:
                logger.warning(f"Heartbeat failed: {response.status_code}")

        except Exception as e:
            logger.error(f"Error sending heartbeat: {e}")

    def heartbeat_loop(self):
        """Background thread for sending periodic heartbeats."""
        while self.running:
            self.send_heartbeat_http()
            time.sleep(self.heartbeat_interval)

    def send_log(self, level: str, message: str):
        """Send log entry to server."""
        # Don't try to send logs if shutting down
        if not self.running:
            return

        try:
            self.session.post(
                f"{self.server_url}/api/agents/{self.agent_id}/log",
                json={
                    'log': {
                        'level': level,
                        'message': message,
                        'timestamp': datetime.now().isoformat()
                    }
                },
                timeout=2  # Shorter timeout to avoid hanging during shutdown
            )
        except Exception as e:
            # Log at debug level to avoid recursion
            logger.debug(f"Failed to send log to server: {e}")

    def run(self):
        """Main run loop for the listener agent."""
        self.running = True

        print("="*60)
        print(f"ChallengeCtl Listener Starting")
        print("="*60)
        print(f"Listener ID: {self.agent_id}")
        print(f"Server: {self.server_url}")
        print("="*60)

        logger.info(f"Listener agent {self.agent_id} starting")
        logger.info(f"Server: {self.server_url}")

        # Try to register first (works if already enrolled with valid API key)
        print("Registering with server...")
        registered = self.register_with_server()

        if not registered:
            # Registration failed - check if we have an enrollment token to try
            enrollment_token = self.config['agent'].get('enrollment_token')
            if enrollment_token:
                print("Registration failed. Attempting enrollment with token...")
                if not self.enroll():
                    print("Failed to enroll with server. Exiting.", flush=True)
                    logger.error("Failed to enroll with server")
                    return 1
                print("Enrollment successful!")
                print("")
                print("NOTE: You can leave 'enrollment_token' in your listener-config.yml.")
                print("It will be ignored on subsequent runs once enrolled.")
                print("")
            else:
                print("Failed to register with server and no enrollment token found. Exiting.", flush=True)
                logger.error("Failed to register with server and no enrollment token found")
                return 1
        else:
            print("Registration successful")

        # Add server log handler to forward logs
        server_handler = ServerLogHandler(self)
        logging.root.addHandler(server_handler)
        print("Log forwarding to server enabled")
        logger.info("Log forwarding to server enabled")

        # Connect WebSocket
        print("Connecting WebSocket to server...")
        if not self.connect_websocket():
            print("Failed to connect WebSocket, exiting", flush=True)
            logger.error("Failed to connect WebSocket")
            return 1

        print("WebSocket connected successfully")

        # Start heartbeat thread
        self.heartbeat_thread = threading.Thread(target=self.heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()

        print(f"Listener agent {self.agent_id} running, waiting for assignments...")
        print("Press Ctrl+C to stop")
        logger.info(f"Listener agent {self.agent_id} running, waiting for assignments...")

        try:
            # Keep main thread alive
            while self.running:
                time.sleep(1)

        except KeyboardInterrupt:
            print("\nReceived interrupt signal, shutting down...", flush=True)
            # Set running=False BEFORE logging to prevent log forwarding during shutdown
            self.running = False
            self.shutdown()

        return 0

    def shutdown(self):
        """Gracefully shutdown the listener agent."""
        # Note: self.running is already set to False by caller

        # Disconnect WebSocket
        if self.sio.connected:
            print("Disconnecting WebSocket...", flush=True)
            self.sio.disconnect()

        # Sign out from server
        print("Signing out from server...", flush=True)
        try:
            response = self.session.post(
                f"{self.server_url}/api/agents/{self.agent_id}/signout",
                timeout=2  # Short timeout - don't hang if server is down
            )
            if response.status_code == 200:
                print("Signed out successfully", flush=True)
            else:
                print(f"Signout failed: {response.status_code}", flush=True)
        except Exception as e:
            # Server may be down, just print error and continue shutdown
            print(f"Could not reach server: {e}", flush=True)

        print("Listener agent shut down", flush=True)


def get_agent_id_from_config(config_path: str) -> str:
    """Load agent_id from config file."""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            return config.get('agent', {}).get('agent_id', 'listener')
    except Exception:
        return 'listener'


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="ChallengeCtl Listener - Spectrum recording agent for RF capture"
    )

    parser.add_argument(
        '-c', '--config',
        default='listener-config.yml',
        help='Path to listener configuration file (default: listener-config.yml)'
    )

    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Set logging level (default: INFO)'
    )

    parser.add_argument(
        '--simulate', '-s',
        action='store_true',
        help='Force simulation mode (generate test data without SDR hardware)'
    )

    args = parser.parse_args()

    # Check if config exists
    if not os.path.exists(args.config):
        logger.error(f"Configuration file not found: {args.config}")
        logger.info("Please create a configuration file (see listener/README.md)")
        sys.exit(1)

    # Get agent_id from config to use in log filename
    agent_id = get_agent_id_from_config(args.config)
    log_file = f'challengectl-{agent_id}.log'

    # Configure logging with file output and rotation
    # Rotate existing log file with timestamp before starting new log
    if os.path.exists(log_file):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        archived_log = f'challengectl-{agent_id}.{timestamp}.log'
        os.rename(log_file, archived_log)

    # Convert log level string to logging constant
    log_level = getattr(logging, args.log_level)

    # Reconfigure logging with both file and console output
    # Clear existing handlers and reconfigure
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # Create formatters
    log_format = f'%(asctime)s challengectl-{agent_id}[%(process)d]: %(levelname)s: %(message)s'
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

    # Create and start listener
    agent = ListenerAgent(args.config, simulate=args.simulate)
    sys.exit(agent.run())


if __name__ == '__main__':
    main()
