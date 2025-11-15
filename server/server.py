#!/usr/bin/env python3
"""
Main server entry point for challengectl-server.
Starts the API server and background cleanup tasks.
"""

import argparse
import logging
import sys
import os
from apscheduler.schedulers.background import BackgroundScheduler
import signal
from datetime import datetime

from api import ChallengeCtlAPI
from database import Database

# Log file configuration
LOG_FILE = 'challengectl.server.log'

# Initial basic logging setup (will be reconfigured in main() after parsing args)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s challengectl-server[%(process)d]: %(levelname)s: %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S'
)

logger = logging.getLogger(__name__)


class ChallengeCtlServer:
    """Main server controller with background tasks."""

    def __init__(self, config_path: str, db_path: str, files_dir: str):
        self.config_path = config_path
        self.db_path = db_path
        self.files_dir = files_dir

        # Initialize database (single instance shared with API)
        self.db = Database(db_path)

        # Initialize API with shared database instance
        self.api = ChallengeCtlAPI(config_path, self.db, files_dir)

        # Initialize background scheduler
        self.scheduler = BackgroundScheduler()
        self.setup_background_tasks()

    def setup_background_tasks(self):
        """Setup periodic background cleanup tasks."""

        def cleanup_stale_runners():
            """Cleanup task to mark offline runners."""
            try:
                count = self.db.cleanup_stale_runners(timeout_seconds=90)
                if count > 0:
                    logger.info(f"Cleanup: marked {count} runner(s) as offline")
            except Exception as e:
                logger.error(f"Error in cleanup_stale_runners: {e}")

        def cleanup_stale_assignments():
            """Cleanup task to requeue timed-out challenge assignments."""
            try:
                count = self.db.cleanup_stale_assignments(timeout_minutes=5)
                if count > 0:
                    logger.info(f"Cleanup: requeued {count} stale assignment(s)")
            except Exception as e:
                logger.error(f"Error in cleanup_stale_assignments: {e}")

        # Run cleanup tasks every 30 seconds
        self.scheduler.add_job(
            cleanup_stale_runners,
            'interval',
            seconds=30,
            id='cleanup_runners',
            replace_existing=True
        )

        self.scheduler.add_job(
            cleanup_stale_assignments,
            'interval',
            seconds=30,
            id='cleanup_assignments',
            replace_existing=True
        )

        logger.info("Background cleanup tasks configured")

    def start(self, host='0.0.0.0', port=8443, debug=False):
        """Start the server and background tasks."""
        logger.info("="*60)
        logger.info("ChallengeCtl Server Starting")
        logger.info("="*60)
        logger.info(f"Configuration: {self.config_path}")
        logger.info(f"Database: {self.db_path}")
        logger.info(f"Files directory: {self.files_dir}")
        logger.info(f"Listening on http://{host}:{port}")
        logger.info("For TLS/HTTPS, use nginx reverse proxy (see DEPLOYMENT.md)")
        logger.info("="*60)

        # Start background scheduler
        self.scheduler.start()
        logger.info("Background tasks started")

        # Handle shutdown gracefully
        def shutdown_handler(signum, frame):
            logger.info("Shutdown signal received")
            self.shutdown()
            sys.exit(0)

        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)

        # Start API server (blocking)
        try:
            self.api.run(host=host, port=port, debug=debug)
        except KeyboardInterrupt:
            self.shutdown()

    def shutdown(self):
        """Graceful shutdown."""
        logger.info("Shutting down server...")
        self.scheduler.shutdown(wait=False)
        logger.info("Server stopped")


def argument_parser():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="ChallengeCtl Server - Distributed SDR challenge coordinator"
    )

    parser.add_argument(
        '-c', '--config',
        default='server-config.yml',
        help='Path to server configuration file (default: server-config.yml)'
    )

    parser.add_argument(
        '-d', '--database',
        default='challengectl.db',
        help='Path to SQLite database file (default: challengectl.db)'
    )

    parser.add_argument(
        '-f', '--files-dir',
        default='files',
        help='Directory for challenge files (default: files)'
    )

    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='Host to bind to (default: 0.0.0.0)'
    )

    parser.add_argument(
        '-p', '--port',
        type=int,
        default=8443,
        help='Port to listen on (default: 8443)'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode'
    )

    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Set logging level (default: INFO)'
    )

    return parser


def main():
    """Main entry point."""
    parser = argument_parser()
    args = parser.parse_args()

    # Configure logging with file output and rotation (like standalone challengectl)
    # Rotate existing log file with timestamp before starting new log
    if os.path.exists(LOG_FILE):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        archived_log = f'challengectl.server.{timestamp}.log'
        os.rename(LOG_FILE, archived_log)

    # Convert log level string to logging constant
    log_level = getattr(logging, args.log_level)

    # Reconfigure logging with file output
    # Clear existing handlers and reconfigure
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logging.basicConfig(
        filename=LOG_FILE,
        filemode='w',
        level=log_level,
        format='%(asctime)s challengectl-server[%(process)d]: %(levelname)s: %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S'
    )

    logging.info(f"Logging initialized at {args.log_level} level")

    # Check if config file exists
    if not os.path.exists(args.config):
        logger.error(f"Configuration file not found: {args.config}")
        logger.info("Creating default configuration...")
        create_default_config(args.config)
        logger.info(f"Default configuration created at {args.config}")
        logger.info("Please edit the configuration file and restart the server")
        sys.exit(1)

    # Create server
    server = ChallengeCtlServer(
        config_path=args.config,
        db_path=args.database,
        files_dir=args.files_dir
    )

    # Start server
    server.start(
        host=args.host,
        port=args.port,
        debug=args.debug
    )


def create_default_config(config_path: str):
    """Create a default server configuration file."""
    default_config = """---
# ChallengeCtl Server Configuration

server:
  bind: "0.0.0.0"
  port: 8443

  # API keys for runner authentication
  # Format: runner_id: api_key
  api_keys:
    runner-1: "change-this-key-abc123"
    runner-2: "change-this-key-def456"
    runner-3: "change-this-key-ghi789"
    admin: "change-this-admin-key-xyz999"

  # File storage settings
  files_dir: "files"

  # Runner heartbeat settings
  heartbeat_timeout: 90  # seconds
  assignment_timeout: 300  # seconds (5 minutes)

conference:
  name: "ExampleCon 2025"
  start: "2025-04-05 09:00:00"
  stop: "2025-04-07 18:00:00"

# Challenges will be loaded from this configuration
# Same format as the standalone challengectl config
challenges:
  # Default delays that apply to all challenges unless overridden
  - default_min_delay: 60
    default_max_delay: 90

  # Example challenges
  - name: NBFM_FLAG_1
    frequency: 146550000
    modulation: nbfm
    flag: challenges/examples/example_voice.wav
    wav_samplerate: 48000
    min_delay: 60
    max_delay: 90
    enabled: true

  - name: CW_MORSE_1
    frequency: 146450000
    modulation: cw
    flag: 'CQ CQ CQ DE RFCTF'
    speed: 35
    min_delay: 60
    max_delay: 90
    enabled: true
"""

    with open(config_path, 'w') as f:
        f.write(default_config)


if __name__ == '__main__':
    main()
