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
import requests
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import socketio

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ListenerAgent:
    """Spectrum listener agent that receives WebSocket recording assignments."""

    def __init__(self, config_path: str):
        """Initialize listener agent.

        Args:
            config_path: Path to listener configuration YAML file
        """
        self.config = self.load_config(config_path)
        self.agent_id = self.config['agent']['agent_id']
        self.server_url = self.config['agent']['server_url']
        self.api_key = self.config['agent']['api_key']
        self.heartbeat_interval = self.config['agent'].get('heartbeat_interval', 30)

        # WebSocket client
        self.sio = socketio.Client(
            reconnection=True,
            reconnection_delay=self.config['agent'].get('websocket_reconnect_delay', 5),
            logger=False,
            engineio_logger=False
        )

        # Recording state
        self.current_recording = None
        self.recording_lock = threading.Lock()

        # Heartbeat thread
        self.heartbeat_thread = None
        self.running = False

        # Device info
        self.devices = self.detect_devices()

        # Register WebSocket event handlers
        self.register_websocket_handlers()

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

        @self.sio.on('connected', namespace='/agents')
        def on_connected_ack(data):
            logger.info(f"Server acknowledged connection: {data.get('message')}")

        @self.sio.on('recording_assignment', namespace='/agents')
        def on_recording_assignment(data):
            """Handle recording assignment from server."""
            logger.info(f"Received recording assignment: {data}")

            assignment_id = data.get('assignment_id')
            challenge_id = data.get('challenge_id')
            challenge_name = data.get('challenge_name')
            transmission_id = data.get('transmission_id')
            frequency = data.get('frequency')
            expected_start = data.get('expected_start')
            expected_duration = data.get('expected_duration')

            # Schedule recording
            threading.Thread(
                target=self.handle_recording_assignment,
                args=(assignment_id, challenge_id, challenge_name, transmission_id,
                      frequency, expected_start, expected_duration),
                daemon=True
            ).start()

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
                'expected_duration': expected_duration
            }

        try:
            # Parse expected start time
            start_time = datetime.fromisoformat(expected_start.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)

            # Calculate delay until recording should start
            delay_seconds = (start_time - now).total_seconds()

            if delay_seconds > 0:
                logger.info(f"Waiting {delay_seconds:.1f}s until recording starts for {challenge_name}")
                time.sleep(delay_seconds)

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
                device_id=device_id
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
            # Release device for next recording
            if selected_device:
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
            response = requests.post(
                f"{self.server_url}/api/agents/{self.agent_id}/recording/start",
                headers={'Authorization': f'Bearer {self.api_key}'},
                json={
                    'challenge_id': challenge_id,
                    'transmission_id': transmission_id,
                    'frequency': frequency,
                    'sample_rate': sample_rate,
                    'expected_duration': expected_duration
                },
                verify=False,
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

            response = requests.post(
                f"{self.server_url}/api/agents/{self.agent_id}/recording/{recording_id}/complete",
                headers={'Authorization': f'Bearer {self.api_key}'},
                json={
                    'success': success,
                    'duration': duration,
                    'image_width': image_width,
                    'image_height': image_height,
                    'error_message': error_message
                },
                verify=False,
                timeout=10
            )

            if response.status_code != 200:
                logger.error(f"Failed to notify recording complete: {response.status_code}")

        except Exception as e:
            logger.error(f"Error notifying recording complete: {e}")

    def upload_waterfall_image(self, recording_id: int, image_path: str):
        """Upload waterfall PNG image to server."""
        try:
            with open(image_path, 'rb') as f:
                files = {'file': (os.path.basename(image_path), f, 'image/png')}
                response = requests.post(
                    f"{self.server_url}/api/agents/{self.agent_id}/recording/{recording_id}/upload",
                    headers={'Authorization': f'Bearer {self.api_key}'},
                    files=files,
                    verify=False,
                    timeout=60  # Longer timeout for file upload
                )

                if response.status_code == 200:
                    logger.info(f"Successfully uploaded waterfall image")
                else:
                    logger.error(f"Failed to upload waterfall: {response.status_code}")

        except Exception as e:
            logger.error(f"Error uploading waterfall image: {e}")

    def register_with_server(self) -> bool:
        """Register this listener agent with the server via HTTP."""
        try:
            hostname = socket.gethostname()

            response = requests.post(
                f"{self.server_url}/api/agents/register",
                headers={'Authorization': f'Bearer {self.api_key}'},
                json={
                    'agent_type': 'listener',
                    'hostname': hostname,
                    'devices': self.devices
                },
                verify=False,
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

    def send_heartbeat_http(self):
        """Send heartbeat to server via HTTP."""
        try:
            response = requests.post(
                f"{self.server_url}/api/agents/{self.agent_id}/heartbeat",
                headers={'Authorization': f'Bearer {self.api_key}'},
                verify=False,
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

    def run(self):
        """Main run loop for the listener agent."""
        self.running = True

        # Register with server
        if not self.register_with_server():
            logger.error("Failed to register with server, exiting")
            return 1

        # Connect WebSocket
        if not self.connect_websocket():
            logger.error("Failed to connect WebSocket, exiting")
            return 1

        # Start heartbeat thread
        self.heartbeat_thread = threading.Thread(target=self.heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()

        logger.info(f"Listener agent {self.agent_id} running, waiting for assignments...")

        try:
            # Keep main thread alive
            while self.running:
                time.sleep(1)

        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
            self.shutdown()

        return 0

    def shutdown(self):
        """Gracefully shutdown the listener agent."""
        self.running = False

        # Disconnect WebSocket
        if self.sio.connected:
            self.sio.disconnect()

        # Sign out from server
        try:
            requests.post(
                f"{self.server_url}/api/agents/{self.agent_id}/signout",
                headers={'Authorization': f'Bearer {self.api_key}'},
                verify=False,
                timeout=5
            )
        except Exception as e:
            logger.error(f"Error signing out: {e}")

        logger.info("Listener agent shut down")


def main():
    parser = argparse.ArgumentParser(description='ChallengeCtl Spectrum Listener Agent')
    parser.add_argument('--config', '-c', required=True,
                       help='Path to listener configuration YAML file')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    agent = ListenerAgent(args.config)
    sys.exit(agent.run())


if __name__ == '__main__':
    main()
