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
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import socketio
import traceback
from PIL import Image

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import local listener modules
from spectrum_listener import SpectrumListener
from waterfall_generator import generate_waterfall
from device_manager import DeviceManager
from common_agent import AgentBase, ServerLogHandler, get_mac_address, get_machine_id

# Initial basic logging setup with default INFO level
# This will be reconfigured in main() after parsing CLI args to use the --log-level parameter
logging.basicConfig(
    level=logging.INFO,  # Default level, overridden by CLI args in main()
    format='%(asctime)s challengectl-listener[%(process)d]: %(levelname)s: %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S'
)
logger = logging.getLogger(__name__)


class ListenerAgent(AgentBase):
    """Spectrum listener agent that receives WebSocket recording assignments."""

    def __init__(self, config_path: str, simulate: bool = False, log_level: int = logging.INFO):
        """Initialize listener agent.

        Args:
            config_path: Path to listener configuration YAML file
            simulate: Force simulation mode (generate test data without SDR hardware)
            log_level: Logging level (e.g., logging.DEBUG, logging.INFO)
        """
        # Initialize base agent class
        super().__init__(config_path, agent_type='listener')

        # Listener-specific configuration
        self.simulate = simulate
        self.log_level = log_level

        # Device auto-detection configuration
        self.enable_auto_detection = self.config['agent'].get('enable_auto_detection', True)

        if simulate:
            logger.info("Simulation mode enabled - will generate test data without SDR hardware")

        # Load devices from configuration
        configured_devices = self.detect_devices()

        # Initialize device manager
        self.device_manager = DeviceManager(
            configured_devices=configured_devices,
            enable_auto_detection=self.enable_auto_detection,
            agent_type='listener',
            probe_callback=None  # Listeners don't have custom probe logic
        )

        # WebSocket client
        # Note: reconnection=False because we handle reconnection manually with auth
        # Enable verbose websocket logging only in DEBUG mode
        enable_ws_logging = (self.log_level == logging.DEBUG)
        self.sio = socketio.Client(
            reconnection=False,
            logger=enable_ws_logging,
            engineio_logger=enable_ws_logging
        )

        # Recording state
        self.current_recording = None
        self.recording_lock = threading.Lock()

        # Heartbeat thread
        self.heartbeat_thread = None

        # Reconnection state
        self.reconnecting = False
        self.reconnect_lock = threading.Lock()

        # Register WebSocket event handlers
        self.register_websocket_handlers()

        logger.info(f"Listener initialized: {self.agent_id}")

    @property
    def devices(self):
        """Get all devices (backward compatibility)."""
        return self.device_manager.get_all_devices()

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
            for idx, device in enumerate(devices_config):
                device_info = {
                    'device_id': idx,  # Add device_id for consistency with runner
                    'name': str(device.get('name', '0')),
                    'model': device.get('model', 'rtlsdr'),
                    'gain': device.get('gain', 40),
                    'frequency_limits': device.get('frequency_limits', []),
                    'waterfall_min_dbm': device.get('waterfall_min_dbm'),
                    'waterfall_max_dbm': device.get('waterfall_max_dbm'),
                    'in_use': False,  # Track device availability
                    'source': 'config',  # Mark as configured device
                    'enabled': True  # Configured devices enabled by default
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
                    'device_id': 0,  # Single device gets ID 0
                    'name': device_config.get('id', 'rtlsdr=0'),
                    'model': device_config.get('type', 'rtlsdr'),
                    'gain': gain,
                    'frequency_limits': [],
                    'in_use': False,
                    'source': 'config',
                    'enabled': True
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
        # Get available devices from device manager
        devices = self.device_manager.get_available_devices(frequency=frequency)

        if not devices:
            logger.error(f"No available device for frequency {frequency} Hz")
            return None

        # Return first available device
        selected = devices[0]
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
                logger.debug(f"Handler called with data: {data}")
                logger.debug(f"Received recording assignment: {data}")

                assignment_id = data.get('assignment_id')
                challenge_id = data.get('challenge_id')
                challenge_name = data.get('challenge_name')
                transmission_id = data.get('transmission_id')
                frequency = data.get('frequency')
                expected_start = data.get('expected_start')
                expected_duration = data.get('expected_duration')
                record_iq = data.get('record_iq', False)

                logger.debug(f"Recording assignment details: challenge={challenge_name}, freq={frequency} Hz ({frequency/1e6:.6f} MHz), record_iq={record_iq}")
                logger.info(f"Starting recording thread for {challenge_name}")
                # Schedule recording
                threading.Thread(
                    target=self.handle_recording_assignment,
                    args=(assignment_id, challenge_id, challenge_name, transmission_id,
                          frequency, expected_start, expected_duration, record_iq),
                    daemon=True
                ).start()
                logger.debug(f"Recording thread started")
            except Exception as e:
                logger.error(f"Exception in recording_assignment handler: {e}", exc_info=True)

        @self.sio.on('heartbeat_ack', namespace='/agents')
        def on_heartbeat_ack(data):
            logger.debug(f"Heartbeat acknowledged by server")

        @self.sio.on('agent_devices_updated', namespace='/agents')
        def on_devices_updated(data):
            """Handle device configuration update from server."""
            try:
                logger.debug(f"Received agent_devices_updated event: {data}")
                agent_id = data.get('agent_id')
                if agent_id == self.agent_id:
                    logger.info(f"Device configuration update for this agent ({self.agent_id})")
                    new_devices = data.get('devices', [])
                    logger.debug(f"New devices data: {new_devices}")

                    # Update device list in memory
                    self.devices = []
                    for device in new_devices:
                        device_info = {
                            'name': str(device.get('name', device.get('device_id', '0'))),
                            'model': device.get('model', 'rtlsdr'),
                            'gain': device.get('gain', 40),
                            'frequency_limits': device.get('frequency_limits', []),
                            'waterfall_min_dbm': device.get('waterfall_min_dbm'),
                            'waterfall_max_dbm': device.get('waterfall_max_dbm'),
                            'in_use': False
                        }
                        self.devices.append(device_info)
                        logger.info(f"Updated device config: {device_info['model']}={device_info['name']} "
                                  f"(gain: {device_info['gain']} dB, waterfall: {device_info['waterfall_min_dbm']} to {device_info['waterfall_max_dbm']} dBm)")

                    logger.info(f"Device configuration reloaded: {len(self.devices)} devices")
                else:
                    logger.debug(f"Device update for different agent: {agent_id} (this agent: {self.agent_id})")
            except Exception as e:
                logger.error(f"Error handling device configuration update: {e}", exc_info=True)

    def handle_recording_assignment(self, assignment_id: int, challenge_id: str,
                                   challenge_name: str, transmission_id: int,
                                   frequency: int, expected_start: str,
                                   expected_duration: float, record_iq: bool = False):
        """Handle a recording assignment by capturing RF and generating waterfall.

        Args:
            assignment_id: Assignment ID for tracking
            challenge_id: Challenge ID
            challenge_name: Human-readable challenge name
            transmission_id: Transmission ID for linking
            frequency: Center frequency in Hz
            expected_start: ISO format timestamp of expected transmission start
            expected_duration: Expected duration in seconds
            record_iq: Whether to record IQ data for this recording
        """
        logger.debug(f"handle_recording_assignment started for {challenge_name}, record_iq={record_iq}")

        with self.recording_lock:
            if self.current_recording:
                logger.warning(f"Already recording, cannot start new recording for {challenge_name}")
                return

            self.current_recording = {
                'assignment_id': assignment_id,
                'challenge_id': challenge_id,
                'challenge_name': challenge_name,
                'transmission_id': transmission_id,
                'frequency': frequency,
                'expected_start': expected_start,
                'expected_duration': expected_duration,
                'record_iq': record_iq
            }

        logger.debug(f"Current recording set, proceeding")

        try:
            # Get recording configuration for pre-roll
            recording_config = self.config['agent'].get('recording', {})
            pre_roll = recording_config.get('pre_roll_seconds', 5)

            # Parse expected start time
            logger.debug(f"Parsing expected_start: {expected_start}")
            start_time = datetime.fromisoformat(expected_start.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)

            # Calculate when to actually start recording (before transmission starts)
            # Recording should start pre_roll seconds BEFORE the transmission
            recording_start_time = start_time - timedelta(seconds=pre_roll)
            delay_seconds = (recording_start_time - now).total_seconds()
            logger.debug(f"Transmission starts at: {start_time.isoformat()}")
            logger.debug(f"Recording will start at: {recording_start_time.isoformat()} (pre-roll: {pre_roll}s)")
            logger.debug(f"Delay until recording start: {delay_seconds:.1f}s")

            if delay_seconds > 0:
                logger.info(f"Waiting {delay_seconds:.1f}s to start recording (pre-roll: {pre_roll}s) for {challenge_name}")
                time.sleep(delay_seconds)
            else:
                logger.warning(f"Cannot achieve full pre-roll - starting immediately (late by {-delay_seconds:.1f}s)")

            logger.debug(f"Notifying server recording started")

            # Notify server recording has started
            sample_rate = recording_config.get('sample_rate', 2000000)

            recording_id = self.notify_recording_started(
                challenge_id=challenge_id,
                transmission_id=transmission_id,
                frequency=frequency,
                sample_rate=sample_rate,
                expected_duration=expected_duration,
                record_iq=record_iq
            )

            logger.debug(f"Recording ID from server: {recording_id}")

            if recording_id <= 0:
                logger.error(f"Failed to create recording entry on server")
                return

            # Perform the actual recording
            recording_actual_start = datetime.now(timezone.utc)
            logger.info(f"Starting recording for {challenge_name} at {frequency} Hz (IQ recording: {record_iq})")
            logger.info(f"Recording timeline: pre-roll={pre_roll}s, transmission={expected_duration}s, "
                       f"post-roll={recording_config.get('post_roll_seconds', 5)}s, "
                       f"total={pre_roll + expected_duration + recording_config.get('post_roll_seconds', 5)}s")

            success, image_path, duration, error_message, iq_file_path = self.record_transmission(
                frequency=frequency,
                duration=expected_duration,
                challenge_name=challenge_name,
                record_iq=record_iq
            )

            recording_actual_end = datetime.now(timezone.utc)
            actual_recording_duration = (recording_actual_end - recording_actual_start).total_seconds()
            logger.info(f"Recording completed in {actual_recording_duration:.2f}s (expected: {pre_roll + expected_duration + recording_config.get('post_roll_seconds', 5)}s)")

            # Notify server recording completed
            if success:
                self.notify_recording_complete(
                    recording_id=recording_id,
                    success=True,
                    image_path=image_path,
                    duration=duration,
                    iq_file_path=iq_file_path
                )

                # Upload waterfall image
                self.upload_waterfall_image(recording_id, image_path)

                # Upload IQ file if recorded
                if iq_file_path and os.path.exists(iq_file_path):
                    logger.info(f"Uploading IQ file: {iq_file_path}")
                    self.upload_iq_file(recording_id, iq_file_path)

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
                          challenge_name: str, record_iq: bool = False) -> tuple:
        """Capture RF transmission and generate waterfall image.

        Args:
            frequency: Center frequency in Hz
            duration: Recording duration in seconds
            challenge_name: Challenge name for filename
            record_iq: Whether to record IQ data

        Returns:
            Tuple of (success, image_path, actual_duration, error_message, iq_file_path)
        """
        selected_device = None
        try:
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

            # Generate IQ filename if recording enabled
            iq_file_path = None
            if record_iq:
                # Get modulation from current_recording if available
                modulation = self.current_recording.get('modulation', 'unknown') if self.current_recording else 'unknown'
                sample_rate_khz = sample_rate / 1000
                timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
                iq_filename = f"{challenge_name}_{modulation}_{sample_rate_khz:.0f}kHz_{timestamp}.c32"
                iq_file_path = os.path.join(output_dir, iq_filename)
                logger.info(f"IQ recording will be saved to: {iq_file_path}")

            # Create spectrum listener with device-specific parameters
            listener = SpectrumListener(
                frequency=frequency,
                sample_rate=sample_rate,
                fft_size=fft_size,
                gain=selected_device['gain'],
                device_id=device_id,
                simulate=self.simulate,
                record_iq=record_iq,
                iq_output_path=iq_file_path
            )

            logger.info(f"Tuning SDR to {frequency} Hz ({frequency/1e6:.6f} MHz) with sample rate {sample_rate} Hz ({sample_rate/1e6:.3f} MHz)")
            logger.debug(f"Frequency range: {frequency - sample_rate/2} to {frequency + sample_rate/2} Hz "
                       f"({(frequency - sample_rate/2)/1e6:.6f} to {(frequency + sample_rate/2)/1e6:.6f} MHz)")
            logger.debug(f"Capturing {total_duration}s at {frequency} Hz (SR: {sample_rate}, "
                       f"pre-roll: {pre_roll}s, transmission: {duration}s, post-roll: {post_roll}s)")

            # Start recording
            start_time = time.time()
            logger.debug(f"GNU Radio flowgraph starting for {total_duration}s capture...")
            fft_data = listener.record(duration=total_duration, frame_rate=frame_rate)
            actual_duration = time.time() - start_time
            logger.debug(f"GNU Radio flowgraph completed - captured {len(fft_data)} frames in {actual_duration:.2f}s")

            # Generate waterfall image
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            image_filename = f"{challenge_name}_{timestamp}.png"
            image_path = os.path.join(output_dir, image_filename)

            # Get reference level for power calibration (dBm at full scale)
            reference_level = recording_config.get('reference_level_dbm', -10.0)

            # Get waterfall scale parameters from device config (optional)
            waterfall_min_dbm = selected_device.get('waterfall_min_dbm')
            waterfall_max_dbm = selected_device.get('waterfall_max_dbm')

            logger.info(f"Generating waterfall image: {image_path}")
            logger.info(f"Waterfall settings - min: {waterfall_min_dbm} dBm, max: {waterfall_max_dbm} dBm, reference: {reference_level} dBm")
            generate_waterfall(
                fft_data=fft_data,
                frequency=frequency,
                sample_rate=sample_rate,
                fft_size=fft_size,
                frame_rate=frame_rate,
                output_path=image_path,
                reference_level_dbm=reference_level,
                vmin_dbm=waterfall_min_dbm,
                vmax_dbm=waterfall_max_dbm
            )

            return (True, image_path, actual_duration, None, iq_file_path)

        except Exception as e:
            error_msg = f"Recording failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return (False, None, 0, error_msg, None)
        finally:
            # Release device for next recording (skip for simulated devices)
            if selected_device and not self.simulate:
                selected_device['in_use'] = False
                logger.debug(f"Released device {selected_device['model']}={selected_device['name']}")

    def notify_recording_started(self, challenge_id: str, transmission_id: int,
                                frequency: int, sample_rate: int,
                                expected_duration: float, record_iq: bool = False) -> int:
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
                    'expected_duration': expected_duration,
                    'record_iq': record_iq
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
                                 iq_file_path: Optional[str] = None,
                                 error_message: Optional[str] = None):
        """Notify server that recording has completed."""
        try:
            # Get image dimensions if available
            image_width, image_height = None, None
            if success and image_path:
                with Image.open(image_path) as img:
                    image_width, image_height = img.size

            # Get IQ file size if available
            iq_file_size = None
            if iq_file_path and os.path.exists(iq_file_path):
                iq_file_size = os.path.getsize(iq_file_path)

            response = self.session.post(
                f"{self.server_url}/api/agents/{self.agent_id}/recording/{recording_id}/complete",
                json={
                    'success': success,
                    'duration': duration,
                    'image_width': image_width,
                    'image_height': image_height,
                    'iq_file_size': iq_file_size,
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
            logger.error(traceback.format_exc())

    def upload_iq_file(self, recording_id: int, iq_file_path: str) -> bool:
        """Upload IQ recording file to server.

        Args:
            recording_id: Recording ID
            iq_file_path: Path to IQ file

        Returns:
            True if successful, False otherwise
        """
        try:
            # Verify file exists
            if not os.path.exists(iq_file_path):
                logger.error(f"IQ file not found: {iq_file_path}")
                return False

            file_size = os.path.getsize(iq_file_path)
            logger.info(f"Uploading IQ file for recording {recording_id}: {iq_file_path} ({file_size} bytes)")

            with open(iq_file_path, 'rb') as f:
                files = {'file': (os.path.basename(iq_file_path), f, 'application/octet-stream')}
                response = self.session.post(
                    f"{self.server_url}/api/agents/{self.agent_id}/recording/{recording_id}/upload/iq",
                    files=files,
                    timeout=300  # 5 minute timeout for large IQ files
                )

                if response.status_code == 200:
                    logger.info(f"Successfully uploaded IQ file for recording {recording_id}")
                    return True
                else:
                    logger.error(f"Failed to upload IQ file for recording {recording_id}: HTTP {response.status_code}")
                    logger.error(f"Response: {response.text}")
                    return False

        except Exception as e:
            logger.error(f"Error uploading IQ file for recording {recording_id}: {e}")
            logger.error(traceback.format_exc())
            return False

    def _prepare_devices_info(self) -> list:
        """Prepare device information for server registration/enrollment.

        Returns:
            List of device info dictionaries with device_id, name, model, gain, and frequency_limits
        """
        devices_info = []
        for dev in self.devices:
            devices_info.append({
                'device_id': dev.get('device_id'),
                'name': dev.get('name'),
                'model': dev.get('model'),
                'gain': dev.get('gain'),
                'frequency_limits': dev.get('frequency_limits', [])
            })
        return devices_info

    def register(self) -> bool:
        """Register this listener agent with the server.

        Gets device status and calls parent register method.
        """
        # Get device status from device manager (already probed during startup)
        device_status = self.device_manager.get_device_status_dict()

        # Call parent class register method with device status
        return super().register(device_status)

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
        # Get device status from device manager
        device_status = self.device_manager.get_device_status_dict()

        # Get auto-detected devices
        with self.device_manager.auto_detected_lock:
            auto_detected_payload = [
                {
                    'device_id': d['device_id'],
                    'model': d['model'],
                    'name': d['name'],
                    'device_string': d.get('device_string', f"{d['model']}={d['name']}"),
                    'source': 'auto_detected',
                    'enabled': d.get('enabled', False),
                    'auto_detected_at': d.get('auto_detected_at')
                }
                for d in self.device_manager.auto_detected_devices
            ]

        # Call parent class send_heartbeat method
        response_data = super().send_heartbeat(device_status, auto_detected_payload)

        # Apply config updates from server response
        if response_data:
            device_updates = response_data.get('device_config_updates', [])
            if device_updates:
                self.device_manager.apply_device_config_updates(device_updates)

    def heartbeat_loop(self):
        """Background thread for sending periodic heartbeats."""
        while self.running:
            self.send_heartbeat_http()
            time.sleep(self.heartbeat_interval)

    # send_log is inherited from AgentBase

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
        registered = self.register()

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
                # Send immediate heartbeat after enrollment
                logger.debug("Sending initial heartbeat to update device status")
                self.send_heartbeat_http()
            else:
                print("Failed to register with server and no enrollment token found. Exiting.", flush=True)
                logger.error("Failed to register with server and no enrollment token found")
                return 1
        else:
            print("Registration successful")
            # Send immediate heartbeat to ensure device status is current
            logger.debug("Sending initial heartbeat to update device status")
            self.send_heartbeat_http()

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

        # Start device probe loop thread
        self.device_manager.start_probe_loop()
        print(f"Device probe loop started (event-driven, auto-detect: {self.enable_auto_detection})")
        logger.info(f"Device probe loop started (event-driven, auto-detect: {self.enable_auto_detection})")

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

        print("\n" + "="*60, flush=True)
        print("SHUTTING DOWN LISTENER", flush=True)
        print("="*60, flush=True)

        # Stop device probe loop
        self.device_manager.stop_probe_loop()

        # Disconnect WebSocket
        if self.sio.connected:
            print("Step 1/3: Disconnecting WebSocket...", flush=True)
            try:
                self.sio.disconnect()
                print("  ✓ WebSocket disconnected", flush=True)
            except Exception as e:
                print(f"  ⚠ Error disconnecting WebSocket: {e}", flush=True)
        else:
            print("Step 1/3: WebSocket already disconnected", flush=True)

        # Sign out from server
        print("Step 2/3: Signing out from server...", flush=True)
        try:
            response = self.session.post(
                f"{self.server_url}/api/agents/{self.agent_id}/signout",
                timeout=2  # Short timeout - don't hang if server is down
            )
            if response.status_code == 200:
                print("  ✓ Signed out successfully", flush=True)
            else:
                print(f"  ⚠ Signout failed: HTTP {response.status_code}", flush=True)
        except Exception as e:
            # Server may be down, just print error and continue shutdown
            print(f"  ⚠ Could not reach server: {e}", flush=True)

        print("Step 3/3: Cleanup complete", flush=True)
        print("="*60, flush=True)
        print("LISTENER STOPPED", flush=True)
        print("="*60, flush=True)


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
    agent = ListenerAgent(args.config, simulate=args.simulate, log_level=log_level)
    sys.exit(agent.run())


if __name__ == '__main__':
    main()
