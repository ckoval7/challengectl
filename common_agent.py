#!/usr/bin/env python3
"""
Common agent functionality shared between runner and listener agents.

This module contains base classes and utility functions used by both
the runner (transmit) and listener (receive/record) agents.
"""

import logging
import socket
import hashlib
import uuid
import platform
import requests
import urllib3
import yaml
from typing import Optional, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


def get_mac_address() -> Optional[str]:
    """Get the MAC address of the primary network interface.

    Returns:
        MAC address as a string (e.g., "aa:bb:cc:dd:ee:ff"), or None if unavailable
    """
    try:
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
        # Create a consistent ID from system information
        system_info = f"{platform.system()}-{platform.node()}-{platform.machine()}"
        # Hash it to create a consistent ID
        return hashlib.sha256(system_info.encode()).hexdigest()[:32]
    except Exception as e:
        logger.warning(f"Could not retrieve machine ID: {e}")
        return None


class ServerLogHandler(logging.Handler):
    """Custom logging handler that forwards logs to the server."""

    def __init__(self, agent_instance):
        super().__init__()
        self.agent = agent_instance
        self.setLevel(logging.DEBUG)  # Forward all log levels

    def emit(self, record):
        """Send log record to server."""
        # Don't send logs if agent is shutting down
        if not self.agent or not hasattr(self.agent, 'send_log') or not self.agent.running:
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

            self.agent.send_log(record.levelname, msg)
        except Exception:
            # Silently ignore errors to prevent recursion
            pass


class AgentBase:
    """Base class for ChallengeCtl agents (runner and listener).

    Provides common functionality for:
    - Configuration loading
    - HTTP session management with authentication
    - TLS/SSL configuration
    - Server communication (enrollment, registration, heartbeat, signout, logging)
    - Host identification
    """

    def __init__(self, config_path: str, agent_type: str):
        """Initialize agent base.

        Args:
            config_path: Path to configuration YAML file
            agent_type: Type of agent ('runner' or 'listener')
        """
        self.config = self.load_config(config_path)
        self.agent_type = agent_type

        # Get agent configuration from appropriate config section
        # Runners use 'runner' key, listeners use 'agent' key
        if agent_type == 'runner':
            agent_config = self.config.get('runner', {})
            self.agent_id = agent_config.get('runner_id')
        else:  # listener
            agent_config = self.config.get('agent', {})
            self.agent_id = agent_config.get('agent_id')

        self.server_url = agent_config.get('server_url', '').rstrip('/')
        self.api_key = agent_config.get('api_key')
        self.heartbeat_interval = agent_config.get('heartbeat_interval', 30)

        # TLS configuration
        self.ca_cert = agent_config.get('ca_cert')
        self.verify_ssl = agent_config.get('verify_ssl', True)

        # Running state
        self.running = False

        # HTTP session for connection pooling
        self.session = self._create_http_session()

        logger.info(f"{agent_type.capitalize()} initialized: {self.agent_id}")

    def load_config(self, config_path: str) -> Dict:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded configuration from {config_path}")
                return config
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            raise

    def _create_http_session(self) -> requests.Session:
        """Create and configure HTTP session with authentication and TLS settings."""
        session = requests.Session()

        # Get host identifiers for authentication
        mac_address = get_mac_address()
        machine_id = get_machine_id()

        # Set authentication headers including host identifiers
        headers = {'Authorization': f'Bearer {self.api_key}'}
        if mac_address:
            # Use appropriate header name based on agent type
            header_prefix = 'X-Runner' if self.agent_type == 'runner' else 'X-Agent'
            headers[f'{header_prefix}-MAC'] = mac_address
        if machine_id:
            header_prefix = 'X-Runner' if self.agent_type == 'runner' else 'X-Agent'
            headers[f'{header_prefix}-Machine-ID'] = machine_id

        session.headers.update(headers)
        logger.debug(f"Session configured with host identifiers: MAC={mac_address}, Machine ID={machine_id}")

        # Configure TLS verification
        if self.ca_cert and os.path.exists(self.ca_cert):
            # Use provided CA certificate
            session.verify = self.ca_cert
            logger.info(f"Using CA certificate: {self.ca_cert}")
        elif not self.verify_ssl:
            # Disable SSL verification (development only)
            session.verify = False
            logger.warning("SSL verification disabled - development mode only!")
            # Disable SSL warnings if verification is disabled
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        else:
            # Use default system CA certificates
            session.verify = True
            logger.info("Using system CA certificates")

        return session

    def enroll(self, devices_info: list) -> bool:
        """Enroll this agent with the server using an enrollment token.

        Args:
            devices_info: List of device dictionaries to send to server

        Returns:
            True if enrollment successful, False otherwise
        """
        # Get enrollment token from appropriate config section
        if self.agent_type == 'runner':
            enrollment_token = self.config['runner'].get('enrollment_token')
        else:
            enrollment_token = self.config['agent'].get('enrollment_token')

        if not enrollment_token:
            logger.debug("No enrollment token found, skipping enrollment")
            return False

        try:
            hostname = socket.gethostname()
            mac_address = get_mac_address()
            machine_id = get_machine_id()

            logger.info(f"Enrolling with host identifiers: hostname={hostname}, MAC={mac_address}, machine_id={machine_id}")

            # Create a session without authentication for enrollment
            enrollment_session = requests.Session()

            # Configure TLS verification same as main session
            if self.ca_cert and os.path.exists(self.ca_cert):
                enrollment_session.verify = self.ca_cert
            elif not self.verify_ssl:
                enrollment_session.verify = False
            else:
                enrollment_session.verify = True

            # Build enrollment payload
            payload = {
                'enrollment_token': enrollment_token,
                'api_key': self.api_key,
                'hostname': hostname,
                'mac_address': mac_address,
                'machine_id': machine_id,
                'devices': devices_info
            }

            # Add agent-specific fields
            if self.agent_type == 'runner':
                payload['runner_id'] = self.agent_id
            else:
                payload['agent_id'] = self.agent_id
                payload['agent_type'] = 'listener'

            response = enrollment_session.post(
                f"{self.server_url}/api/enrollment/enroll",
                json=payload,
                timeout=10
            )

            if response.status_code == 201:
                logger.info(f"Successfully enrolled as {self.agent_id}")
                return True
            elif response.status_code == 401:
                logger.error("Enrollment failed: Invalid or expired enrollment token")
                return False
            elif response.status_code == 409:
                logger.info(f"{self.agent_type.capitalize()} already enrolled with this token")
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

    def register(self, devices_info: list, device_status: Optional[Dict] = None) -> bool:
        """Register this agent with the server.

        Args:
            devices_info: List of device dictionaries to send to server
            device_status: Optional device status dictionary

        Returns:
            True if registration successful, False otherwise
        """
        try:
            hostname = socket.gethostname()

            payload = {
                'hostname': hostname,
                'devices': devices_info
            }

            # Add agent type for listeners
            if self.agent_type == 'listener':
                payload['agent_type'] = 'listener'

            # Add device status if provided
            if device_status:
                payload['device_status'] = device_status

            response = self.session.post(
                f"{self.server_url}/api/agents/register",
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                logger.info(f"Registered as {self.agent_id}")
                return True
            else:
                logger.error(f"Registration failed: HTTP {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error during registration: {e}")
            return False

    def send_heartbeat(self, device_status: Dict, auto_detected_devices: Optional[list] = None) -> Optional[Dict]:
        """Send heartbeat to server with device status.

        Args:
            device_status: Dictionary of device status
            auto_detected_devices: Optional list of auto-detected devices

        Returns:
            Response data dictionary if successful, None otherwise
        """
        try:
            payload = {'device_status': device_status}

            if auto_detected_devices:
                payload['auto_detected_devices'] = auto_detected_devices

            response = self.session.post(
                f"{self.server_url}/api/agents/{self.agent_id}/heartbeat",
                json=payload,
                timeout=5
            )

            if response.status_code == 200:
                logger.debug("Heartbeat sent")
                return response.json()
            else:
                logger.warning(f"Heartbeat failed: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error sending heartbeat: {e}")
            return None

    def signout(self) -> bool:
        """Sign out from server (graceful shutdown).

        Returns:
            True if signout successful, False otherwise
        """
        try:
            logger.info(f"Signing out from server...")
            response = self.session.post(
                f"{self.server_url}/api/agents/{self.agent_id}/signout",
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

    def send_log(self, level: str, message: str):
        """Send log entry to server.

        Args:
            level: Log level (e.g., 'INFO', 'WARNING', 'ERROR')
            message: Log message
        """
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
                timeout=5
            )
        except Exception as e:
            # Log at debug level to avoid recursion
            logger.debug(f"Failed to send log to server: {e}")


# Missing import for os module
import os
