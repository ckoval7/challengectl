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
        self.spectrum_paint_before_challenge = self.config['runner'].get('spectrum_paint_before_challenge', False)

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

        # HTTP session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({'Authorization': f'Bearer {self.api_key}'})

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

    def register(self) -> bool:
        """Register this runner with the server."""
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
                f"{self.server_url}/api/runners/register",
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
        """Send periodic heartbeat to server."""
        try:
            response = self.session.post(
                f"{self.server_url}/api/runners/{self.runner_id}/heartbeat",
                timeout=5
            )

            if response.status_code == 200:
                logger.debug("Heartbeat sent")
            else:
                logger.warning(f"Heartbeat failed: {response.status_code}")

        except Exception as e:
            logger.error(f"Error sending heartbeat: {e}")

    def heartbeat_loop(self):
        """Background thread for sending heartbeats."""
        while self.running:
            self.send_heartbeat()
            time.sleep(self.heartbeat_interval)

    def get_task(self) -> Optional[Dict]:
        """Request next task from server."""
        try:
            response = self.session.get(
                f"{self.server_url}/api/runners/{self.runner_id}/task",
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

    def execute_challenge(self, task: Dict) -> tuple:
        """
        Execute a challenge task.

        Returns:
            tuple: (success: bool, device_id: int, frequency: int)
        """
        challenge_id = task['challenge_id']
        name = task['name']
        config = task['config']

        modulation = config.get('modulation')
        flag = config.get('flag')
        frequency = config.get('frequency')

        logger.info(f"Executing challenge: {name} ({modulation}) on {frequency} Hz")

        # Select first available device (simple strategy for now)
        if not self.devices:
            logger.error("No devices available")
            return (False, 0, frequency or 0)

        device = self.devices[0]
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
                          error_message: Optional[str] = None):
        """Report task completion to server."""
        try:
            response = self.session.post(
                f"{self.server_url}/api/runners/{self.runner_id}/complete",
                json={
                    'challenge_id': challenge_id,
                    'success': success,
                    'error_message': error_message,
                    'device_id': device_id,
                    'frequency': frequency
                },
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
                f"{self.server_url}/api/runners/{self.runner_id}/log",
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

    def task_loop(self):
        """Main task execution loop."""
        logger.debug("Task loop started")

        while self.running:
            try:
                # Get next task
                task = self.get_task()

                if task:
                    self.current_task = task
                    challenge_id = task['challenge_id']

                    # Execute challenge
                    success, device_id, frequency = self.execute_challenge(task)

                    # Report completion
                    error_msg = None if success else "Execution failed"
                    self.report_completion(challenge_id, success, device_id, frequency, error_msg)

                    self.current_task = None

                    # Small delay between tasks
                    time.sleep(3)
                else:
                    # No tasks available, wait before polling again
                    time.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"Error in task loop: {e}", exc_info=True)
                time.sleep(self.poll_interval)

    def start(self):
        """Start the runner."""
        logger.info(f"Runner {self.runner_id} starting")
        logger.info(f"Server: {self.server_url}, Devices: {len(self.devices)}")

        # Register with server
        if not self.register():
            logger.error("Failed to register with server. Exiting.")
            sys.exit(1)

        # Add server log handler to forward logs
        server_handler = ServerLogHandler(self)
        logging.root.addHandler(server_handler)
        logger.info("Log forwarding to server enabled")

        self.running = True

        # Start heartbeat thread
        heartbeat_thread = threading.Thread(target=self.heartbeat_loop, daemon=True)
        heartbeat_thread.start()
        logger.info("Heartbeat thread started")

        # Start task loop (blocking)
        try:
            self.task_loop()
        except KeyboardInterrupt:
            logger.info("Shutdown requested")
            self.stop()

    def stop(self):
        """Stop the runner."""
        logger.info("Stopping runner...")
        self.running = False
        time.sleep(1)
        logger.info("Runner stopped")


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

    # Reconfigure logging with file output
    # Clear existing handlers and reconfigure
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logging.basicConfig(
        filename=log_file,
        filemode='w',
        level=log_level,
        format=f'%(asctime)s challengectl-{runner_id}[%(process)d]: %(levelname)s: %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S'
    )

    logging.info(f"Logging initialized at {args.log_level} level")

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
