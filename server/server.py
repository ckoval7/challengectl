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
import yaml

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

        # Shutdown flag to prevent duplicate shutdown attempts
        self._shutdown_initiated = False

    def setup_background_tasks(self):
        """Setup periodic background cleanup tasks."""

        def cleanup_stale_runners():
            """Cleanup task to mark offline runners."""
            try:
                offline_runners = self.db.cleanup_stale_runners(timeout_seconds=90)
                if offline_runners:
                    logger.info(f"Cleanup: marked {len(offline_runners)} runner(s) as offline")
                    # Broadcast WebSocket events for each runner marked offline
                    from datetime import timezone
                    for runner_id in offline_runners:
                        self.api.broadcast_event('runner_status', {
                            'runner_id': runner_id,
                            'status': 'offline',
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        })
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

        def cleanup_expired_sessions():
            """Cleanup task to remove expired sessions from database."""
            try:
                self.api.cleanup_expired_sessions()
            except Exception as e:
                logger.error(f"Error in cleanup_expired_sessions: {e}")

        def cleanup_expired_totp_codes():
            """Cleanup task to remove expired TOTP codes from memory."""
            try:
                self.api.cleanup_expired_totp_codes()
            except Exception as e:
                logger.error(f"Error in cleanup_expired_totp_codes: {e}")

        # Run session and TOTP cleanup every minute
        self.scheduler.add_job(
            cleanup_expired_sessions,
            'interval',
            seconds=60,
            id='cleanup_sessions',
            replace_existing=True
        )

        self.scheduler.add_job(
            cleanup_expired_totp_codes,
            'interval',
            seconds=60,
            id='cleanup_totp_codes',
            replace_existing=True
        )

        logger.info("Background cleanup tasks configured")

    def start(self, host='0.0.0.0', port=8443, debug=False):
        """Start the server and background tasks."""
        print("="*60)
        print("ChallengeCtl Server Starting")
        print("="*60)
        print(f"Configuration: {self.config_path}")
        print(f"Database: {self.db_path}")
        print(f"Files directory: {self.files_dir}")
        print(f"Listening on http://{host}:{port}")
        print("For TLS/HTTPS, use nginx reverse proxy (see DEPLOYMENT.md)")
        print("="*60)

        logger.info("="*60)
        logger.info("ChallengeCtl Server Starting")
        logger.info("="*60)
        logger.info(f"Configuration: {self.config_path}")
        logger.info(f"Database: {self.db_path}")
        logger.info(f"Files directory: {self.files_dir}")
        logger.info(f"Listening on http://{host}:{port}")
        logger.info("For TLS/HTTPS, use nginx reverse proxy (see DEPLOYMENT.md)")
        logger.info("="*60)

        # Ensure system is not paused on startup
        # Pausing is an operational control, not a persistent state
        if self.db.get_system_state('paused', 'false') == 'true':
            print("System was paused - resuming on startup")
            logger.info("System was paused - resuming on startup")
            self.db.set_system_state('paused', 'false')

        # Reset any stale challenge states on startup
        # Challenges in 'assigned' or 'waiting' state should be requeued
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Get IDs of challenges being reset
            cursor.execute('''
                SELECT challenge_id FROM challenges
                WHERE status IN ('assigned', 'waiting')
                  AND enabled = 1
            ''')
            reset_challenge_ids = [row['challenge_id'] for row in cursor.fetchall()]

            # Reset database state
            cursor.execute('''
                UPDATE challenges
                SET status = 'queued',
                    assigned_to = NULL,
                    assigned_at = NULL,
                    assignment_expires = NULL
                WHERE status IN ('assigned', 'waiting')
                  AND enabled = 1
            ''')
            reset_count = cursor.rowcount
            conn.commit()

            # Clear in-memory timing state for reset challenges
            if reset_challenge_ids:
                with self.db.timing_lock:
                    for cid in reset_challenge_ids:
                        if cid in self.db.challenge_timing:
                            del self.db.challenge_timing[cid]

            if reset_count > 0:
                print(f"Reset {reset_count} challenge(s) to queued state on startup")
                logger.info(f"Reset {reset_count} challenge(s) to queued state on startup")

        # Start background scheduler
        self.scheduler.start()
        print("Background tasks started")
        logger.info("Background tasks started")

        # Check if config and database are in sync
        # Only run this check in the main process (not in Flask reloader's subprocess)
        # Flask sets WERKZEUG_RUN_MAIN in the reloader's child process
        is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'

        if not is_reloader_process or not debug:
            sync_status = self.api.check_config_sync()

            if sync_status.get('in_sync') is False:
                # Concise log message for syslog
                logger.warning(f"Configuration out of sync: {len(sync_status.get('new', []))} new, {len(sync_status.get('removed', []))} removed, {len(sync_status.get('updated', []))} updated challenges")

                # Detailed console output
                print("\n" + "="*60)
                print("CONFIG OUT OF SYNC WARNING")
                print("="*60)
                print("The configuration file has changes not reflected in the database:")
                print()

                if sync_status['new']:
                    print(f"  New challenges in config ({len(sync_status['new'])}):")
                    for name in sync_status['new']:
                        print(f"    - {name}")
                    print()

                if sync_status['removed']:
                    print(f"  Challenges removed from config ({len(sync_status['removed'])}):")
                    for name in sync_status['removed']:
                        print(f"    - {name}")
                    print()

                if sync_status['updated']:
                    print(f"  Challenges with updated config ({len(sync_status['updated'])}):")
                    for name in sync_status['updated']:
                        print(f"    - {name}")
                    print()

                print("RECOMMENDED ACTIONS:")
                print("  1. Use the web UI: Go to Challenges page and click 'Reload from Config'")
                print("  2. OR restart the server after reviewing your configuration file")
                print("="*60 + "\n")
            elif sync_status.get('in_sync') is True:
                print(f"Configuration in sync: {sync_status['total_config']} challenges")
                logger.info(f"Configuration in sync: {sync_status['total_config']} challenges")
            elif sync_status.get('error'):
                print(f"Warning: Could not check config sync: {sync_status['error']}")
                logger.error(f"Could not check config sync: {sync_status['error']}")

        # Handle shutdown gracefully
        def shutdown_handler(signum, frame):
            print("\nShutdown signal received...", flush=True)
            logger.info("Shutdown signal received")
            self.shutdown()

        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)

        # Start API server (blocking)
        print("Starting Flask-SocketIO server...")
        print("Press Ctrl+C to shutdown")
        print()
        self.api.run(host=host, port=port, debug=debug)

    def shutdown(self):
        """Graceful shutdown."""
        # Prevent duplicate shutdown attempts
        if self._shutdown_initiated:
            return

        self._shutdown_initiated = True
        print("Shutting down server...", flush=True)
        logger.info("Shutting down server...")

        # Stop the SocketIO server to unblock the run() call
        try:
            self.api.socketio.stop()
            print("SocketIO server stopped", flush=True)
            logger.info("SocketIO server stopped")
        except Exception as e:
            print(f"Error stopping SocketIO server: {e}", flush=True)
            logger.error(f"Error stopping SocketIO server: {e}")

        # Shutdown scheduler if it's running
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            print("Background scheduler stopped", flush=True)
            logger.info("Background scheduler stopped")

        print("Server stopped", flush=True)
        logger.info("Server stopped")


def argument_parser(config=None):
    """Parse command line arguments.

    Args:
        config: Optional dict of configuration values to use as defaults
    """
    # Extract defaults from config if provided
    if config:
        default_host = config.get('server', {}).get('bind', '0.0.0.0')
        default_port = config.get('server', {}).get('port', 8443)
    else:
        default_host = '0.0.0.0'
        default_port = 8443

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
        default=default_host,
        help=f'Host to bind to (default: {default_host} from config or 0.0.0.0)'
    )

    parser.add_argument(
        '-p', '--port',
        type=int,
        default=default_port,
        help=f'Port to listen on (default: {default_port} from config or 8443)'
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
    # First pass: parse only to get config path
    parser = argument_parser()
    args, _ = parser.parse_known_args()

    # Load configuration file (if it exists) to use for defaults
    config = None
    if os.path.exists(args.config):
        try:
            with open(args.config, 'r') as f:
                config = yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"Could not load config for defaults: {e}")

    # Second pass: re-parse with config-based defaults
    parser = argument_parser(config)
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

  # File storage settings
  files_dir: "files"

  # Runner heartbeat settings
  heartbeat_timeout: 90  # seconds
  assignment_timeout: 300  # seconds (5 minutes)

conference:
  name: "ExampleCon 2025"
  start: "2025-04-05 09:00:00"
  stop: "2025-04-07 18:00:00"

# Challenges are configured through the Web UI at /challenge-config
# You can also configure challenges in this file if preferred:
#
# challenges:
#   - name: NBFM_FLAG_1
#     frequency: 146550000
#     modulation: nbfm
#     flag: challenges/examples/example_voice.wav
#     wav_samplerate: 48000
#     min_delay: 60
#     max_delay: 90
#     enabled: true
#
# See the Challenge Management guide for more information:
# https://github.com/ckoval7/challengectl/wiki/Challenge-Management
"""

    with open(config_path, 'w') as f:
        f.write(default_config)


if __name__ == '__main__':
    main()
