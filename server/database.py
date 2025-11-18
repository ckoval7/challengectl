#!/usr/bin/env python3
"""
Database schema and management for challengectl server.
Uses SQLite for simplicity with 2-3 runners.
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import threading

from crypto import encrypt_totp_secret, decrypt_totp_secret

logger = logging.getLogger(__name__)


class Database:
    """Thread-safe SQLite database wrapper for challengectl server."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()

        # In-memory challenge transmission timing
        # Format: {challenge_id: {'last_tx': datetime, 'next_tx': datetime}}
        self.challenge_timing = {}
        self.timing_lock = threading.Lock()

        self.init_database()

    @contextmanager
    def get_connection(self):
        """Get a thread-local database connection."""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                isolation_level='IMMEDIATE'  # Use immediate locks for better concurrency
            )
            self._local.conn.row_factory = sqlite3.Row  # Access columns by name

        try:
            yield self._local.conn
        except Exception:
            self._local.conn.rollback()
            raise

    def init_database(self):
        """Initialize database schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Runners table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS runners (
                    runner_id TEXT PRIMARY KEY,
                    hostname TEXT,
                    ip_address TEXT,
                    status TEXT DEFAULT 'offline',
                    enabled BOOLEAN DEFAULT 1,
                    last_heartbeat TIMESTAMP,
                    devices JSON,
                    api_key_hash TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Enrollment tokens table (for one-time runner registration)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS enrollment_tokens (
                    token TEXT PRIMARY KEY,
                    runner_name TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    used BOOLEAN DEFAULT 0,
                    used_at TIMESTAMP,
                    used_by_runner_id TEXT,
                    FOREIGN KEY (created_by) REFERENCES users(username)
                )
            ''')

            # Challenges table
            # status: 'queued' (ready), 'waiting' (delay timer), 'assigned' (transmitting)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS challenges (
                    challenge_id TEXT PRIMARY KEY,
                    name TEXT UNIQUE,
                    config JSON NOT NULL,
                    status TEXT DEFAULT 'queued',
                    priority INTEGER DEFAULT 0,
                    last_tx_time TIMESTAMP,
                    next_tx_time TIMESTAMP,
                    transmission_count INTEGER DEFAULT 0,
                    assigned_to TEXT,
                    assigned_at TIMESTAMP,
                    assignment_expires TIMESTAMP,
                    enabled BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (assigned_to) REFERENCES runners(runner_id)
                )
            ''')

            # Transmissions history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transmissions (
                    transmission_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    challenge_id TEXT,
                    runner_id TEXT,
                    device_id TEXT,
                    frequency INTEGER,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    status TEXT,
                    error_message TEXT,
                    FOREIGN KEY (challenge_id) REFERENCES challenges(challenge_id),
                    FOREIGN KEY (runner_id) REFERENCES runners(runner_id)
                )
            ''')

            # Files table (tracks uploaded challenge files)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS files (
                    file_hash TEXT PRIMARY KEY,
                    filename TEXT,
                    size INTEGER,
                    mime_type TEXT,
                    file_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # System state table (for global configuration)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_state (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Users table (for admin authentication)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    totp_secret TEXT,
                    enabled BOOLEAN DEFAULT 1,
                    password_change_required BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP
                )
            ''')

            # Sessions table (for persistent session storage)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    session_token TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    expires TIMESTAMP NOT NULL,
                    totp_verified BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
                )
            ''')

            # Create index on username for faster session lookups by user
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_sessions_username ON sessions(username)
            ''')

            # Create index on expires for faster cleanup of expired sessions
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires)
            ''')

            # Create default admin user if no users exist
            cursor.execute('SELECT COUNT(*) as count FROM users')
            user_count = cursor.fetchone()['count']

            if user_count == 0:
                import bcrypt
                import secrets
                import string

                # Create default admin with random password and no TOTP
                # User will create their own account with TOTP on first login
                alphabet = string.ascii_letters + string.digits
                default_password = ''.join(secrets.choice(alphabet) for _ in range(16))
                password_hash = bcrypt.hashpw(default_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

                cursor.execute('''
                    INSERT INTO users (username, password_hash, totp_secret, password_change_required)
                    VALUES (?, ?, NULL, 0)
                ''', ('admin', password_hash))

                # Mark system as requiring initial setup
                cursor.execute('''
                    INSERT INTO system_state (key, value)
                    VALUES ('initial_setup_required', 'true')
                ''')

                # Log to file
                logger.warning("=" * 80)
                logger.warning("DEFAULT ADMIN USER CREATED")
                logger.warning("=" * 80)
                logger.warning(f"Username: admin")
                logger.warning(f"Password: {default_password}")
                logger.warning("")
                logger.warning("IMPORTANT: Log in with these credentials to create your admin account.")
                logger.warning("You will be prompted to create a new user with TOTP 2FA on first login.")
                logger.warning("After setup, you can delete this default admin account.")
                logger.warning("=" * 80)

                # Also print to stdout so it's visible in terminal
                print("\n" + "=" * 80, flush=True)
                print("DEFAULT ADMIN USER CREATED", flush=True)
                print("=" * 80, flush=True)
                print(f"Username: admin", flush=True)
                print(f"Password: {default_password}", flush=True)
                print("", flush=True)
                print("IMPORTANT: Log in with these credentials to create your admin account.", flush=True)
                print("You will be prompted to create a new user with TOTP 2FA on first login.", flush=True)
                print("After setup, you can delete this default admin account.", flush=True)
                print("=" * 80 + "\n", flush=True)

            # Migrations for existing databases
            # Add enabled column to runners table if it doesn't exist
            cursor.execute("PRAGMA table_info(runners)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'enabled' not in columns:
                logger.info("Adding 'enabled' column to runners table")
                cursor.execute('ALTER TABLE runners ADD COLUMN enabled BOOLEAN DEFAULT 1')
            if 'api_key_hash' not in columns:
                logger.info("Adding 'api_key_hash' column to runners table")
                cursor.execute('ALTER TABLE runners ADD COLUMN api_key_hash TEXT')

            # Create indexes
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_challenges_status
                ON challenges(status, next_tx_time, enabled)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_runners_status
                ON runners(status, last_heartbeat)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_transmissions_time
                ON transmissions(started_at DESC)
            ''')

            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")

    # Runner management
    def register_runner(self, runner_id: str, hostname: str, ip_address: str, devices: List[Dict], api_key: Optional[str] = None) -> bool:
        """Register a new runner or update existing one.

        Args:
            runner_id: Unique identifier for the runner
            hostname: Hostname of the runner
            ip_address: IP address of the runner
            devices: List of SDR devices available on this runner
            api_key: Optional API key to set for this runner (will be bcrypt hashed)

        Returns:
            True if successful, False otherwise
        """
        import bcrypt

        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Hash API key if provided
                api_key_hash = None
                if api_key:
                    api_key_hash = bcrypt.hashpw(api_key.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

                cursor.execute('''
                    INSERT INTO runners (runner_id, hostname, ip_address, status, last_heartbeat, devices, api_key_hash)
                    VALUES (?, ?, ?, 'online', ?, ?, ?)
                    ON CONFLICT(runner_id) DO UPDATE SET
                        hostname = excluded.hostname,
                        ip_address = excluded.ip_address,
                        status = 'online',
                        last_heartbeat = excluded.last_heartbeat,
                        devices = excluded.devices,
                        updated_at = CURRENT_TIMESTAMP
                ''', (runner_id, hostname, ip_address, datetime.now(timezone.utc), json.dumps(devices), api_key_hash))
                conn.commit()
                logger.info(f"Registered runner: {runner_id} from {ip_address}")
                return True
            except Exception as e:
                logger.error(f"Error registering runner {runner_id}: {e}")
                return False

    def update_heartbeat(self, runner_id: str) -> tuple[bool, str]:
        """Update runner heartbeat timestamp.

        Returns:
            tuple: (success: bool, previous_status: str)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Get previous status
                cursor.execute('SELECT status FROM runners WHERE runner_id = ?', (runner_id,))
                row = cursor.fetchone()
                previous_status = row['status'] if row else 'offline'

                # Update heartbeat and status
                cursor.execute('''
                    UPDATE runners
                    SET last_heartbeat = ?, status = 'online', updated_at = CURRENT_TIMESTAMP
                    WHERE runner_id = ?
                ''', (datetime.now(timezone.utc), runner_id))
                conn.commit()
                return (cursor.rowcount > 0, previous_status)
            except Exception as e:
                logger.error(f"Error updating heartbeat for {runner_id}: {e}")
                return (False, 'offline')

    def get_runner(self, runner_id: str) -> Optional[Dict]:
        """Get runner details."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM runners WHERE runner_id = ?', (runner_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_all_runners(self) -> List[Dict]:
        """Get all registered runners."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM runners ORDER BY runner_id')
            return [dict(row) for row in cursor.fetchall()]

    def mark_runner_offline(self, runner_id: str) -> bool:
        """Mark a runner as offline."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE runners
                SET status = 'offline', updated_at = CURRENT_TIMESTAMP
                WHERE runner_id = ?
            ''', (runner_id,))
            conn.commit()
            return cursor.rowcount > 0

    def enable_runner(self, runner_id: str) -> bool:
        """Enable a runner to receive task assignments."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE runners
                SET enabled = 1, updated_at = CURRENT_TIMESTAMP
                WHERE runner_id = ?
            ''', (runner_id,))
            conn.commit()
            if cursor.rowcount > 0:
                logger.info(f"Enabled runner: {runner_id}")
            return cursor.rowcount > 0

    def disable_runner(self, runner_id: str) -> bool:
        """Disable a runner from receiving task assignments."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE runners
                SET enabled = 0, updated_at = CURRENT_TIMESTAMP
                WHERE runner_id = ?
            ''', (runner_id,))
            conn.commit()
            if cursor.rowcount > 0:
                logger.info(f"Disabled runner: {runner_id}")
            return cursor.rowcount > 0

    def verify_runner_api_key(self, runner_id: str, api_key: str, current_ip: str, current_hostname: str) -> bool:
        """Verify a runner's API key against the stored bcrypt hash.

        Also validates that the runner is not already active from a different host
        to prevent credential reuse attacks.

        Args:
            runner_id: The runner ID to verify
            api_key: The plaintext API key to check
            current_ip: IP address of the current authentication attempt
            current_hostname: Hostname of the current authentication attempt

        Returns:
            True if the API key is valid and host check passes, False otherwise
        """
        import bcrypt

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT api_key_hash, status, ip_address, hostname, last_heartbeat FROM runners WHERE runner_id = ?', (runner_id,))
            row = cursor.fetchone()

            if not row or not row['api_key_hash']:
                return False

            # Verify the API key using bcrypt
            try:
                api_key_valid = bcrypt.checkpw(api_key.encode('utf-8'), row['api_key_hash'].encode('utf-8'))
            except Exception as e:
                logger.error(f"API key verification error for runner {runner_id}: {e}")
                return False

            if not api_key_valid:
                return False

            # Host validation: prevent credential reuse on different machines
            # Allow if runner is offline, or if from same IP/hostname
            if row['status'] == 'online':
                stored_ip = row['ip_address']
                stored_hostname = row['hostname']

                # Check if last heartbeat is recent (within 2 minutes)
                if row['last_heartbeat']:
                    last_heartbeat = datetime.fromisoformat(row['last_heartbeat'])
                    time_since_heartbeat = (datetime.now(timezone.utc) - last_heartbeat).total_seconds()

                    # Only enforce host check if runner is actively online (heartbeat within 2 minutes)
                    if time_since_heartbeat < 120:
                        # Runner is actively online - verify it's the same host
                        if stored_ip != current_ip and stored_hostname != current_hostname:
                            logger.warning(
                                f"SECURITY: Runner {runner_id} credential reuse attempt! "
                                f"Active on {stored_hostname} ({stored_ip}), "
                                f"rejected attempt from {current_hostname} ({current_ip})"
                            )
                            return False

            return True

    def update_runner_api_key(self, runner_id: str, api_key: str) -> bool:
        """Update a runner's bcrypt-hashed API key.

        Args:
            runner_id: The runner ID to update
            api_key: The plaintext API key to hash and store

        Returns:
            True if successful, False otherwise
        """
        import bcrypt

        with self.get_connection() as conn:
            cursor = conn.cursor()
            api_key_hash = bcrypt.hashpw(api_key.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

            cursor.execute('''
                UPDATE runners
                SET api_key_hash = ?, updated_at = CURRENT_TIMESTAMP
                WHERE runner_id = ?
            ''', (api_key_hash, runner_id))
            conn.commit()
            return cursor.rowcount > 0

    def cleanup_stale_runners(self, timeout_seconds: int = 90) -> list[str]:
        """Mark runners as offline if they haven't sent heartbeat within timeout.

        Returns:
            list: List of runner IDs that were marked offline
        """
        threshold = datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # First get the IDs of runners that will be marked offline
            cursor.execute('''
                SELECT runner_id FROM runners
                WHERE status = 'online'
                  AND last_heartbeat < ?
            ''', (threshold,))
            offline_runners = [row['runner_id'] for row in cursor.fetchall()]

            # Now mark them offline
            if offline_runners:
                cursor.execute('''
                    UPDATE runners
                    SET status = 'offline'
                    WHERE status = 'online'
                      AND last_heartbeat < ?
                ''', (threshold,))
                conn.commit()
                logger.warning(f"Marked {len(offline_runners)} runner(s) as offline due to missed heartbeats")

            return offline_runners

    # Challenge management
    def add_challenge(self, challenge_id: str, name: str, config: Dict) -> bool:
        """Add a new challenge."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO challenges (challenge_id, name, config, next_tx_time)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ''', (challenge_id, name, json.dumps(config)))
                conn.commit()
                logger.info(f"Added challenge: {name} (ID: {challenge_id})")
                return True
            except sqlite3.IntegrityError:
                logger.warning(f"Challenge {name} already exists")
                return False
            except Exception as e:
                logger.error(f"Error adding challenge {name}: {e}")
                return False

    def update_challenge(self, challenge_id: str, config: Dict) -> bool:
        """Update challenge configuration."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE challenges
                SET config = ?
                WHERE challenge_id = ?
            ''', (json.dumps(config), challenge_id))
            conn.commit()
            return cursor.rowcount > 0

    def get_challenge(self, challenge_id: str) -> Optional[Dict]:
        """Get challenge by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM challenges WHERE challenge_id = ?', (challenge_id,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                result['config'] = json.loads(result['config'])
                # Convert SQLite integer to boolean
                result['enabled'] = bool(result['enabled'])
                return result
            return None

    def get_all_challenges(self) -> List[Dict]:
        """Get all challenges."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM challenges ORDER BY name')
            challenges = []
            for row in cursor.fetchall():
                challenge = dict(row)
                challenge['config'] = json.loads(challenge['config'])
                # Convert SQLite integer to boolean
                challenge['enabled'] = bool(challenge['enabled'])
                challenges.append(challenge)
            return challenges

    def assign_challenge(self, runner_id: str, timeout_minutes: int = 5) -> Optional[Dict]:
        """
        Assign next available challenge to a runner.
        Uses pessimistic locking to prevent race conditions.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Start transaction with immediate lock
            conn.execute('BEGIN IMMEDIATE')

            try:
                # Check if runner is enabled
                cursor.execute('SELECT enabled FROM runners WHERE runner_id = ?', (runner_id,))
                runner_row = cursor.fetchone()
                if not runner_row or not runner_row['enabled']:
                    conn.rollback()
                    logger.debug(f"Runner {runner_id} is disabled, skipping task assignment")
                    return None

                # Find next available challenge (queued or waiting with expired delay)
                cursor.execute('''
                    SELECT * FROM challenges
                    WHERE status IN ('queued', 'waiting')
                      AND enabled = 1
                    ORDER BY priority DESC
                ''')

                rows = cursor.fetchall()

                # Filter by timing from in-memory tracking
                now = datetime.now()
                row = None
                with self.timing_lock:
                    for r in rows:
                        cid = r['challenge_id']
                        timing = self.challenge_timing.get(cid, {})
                        next_tx = timing.get('next_tx')

                        # Challenge is ready if no next_tx set or next_tx has passed
                        if next_tx is None or next_tx <= now:
                            row = r
                            # Update waiting -> queued if delay has passed
                            if row['status'] == 'waiting':
                                cursor.execute('''
                                    UPDATE challenges
                                    SET status = 'queued'
                                    WHERE challenge_id = ?
                                ''', (cid,))
                            break

                if row:
                    challenge = dict(row)
                    challenge_id = challenge['challenge_id']

                    # Mark as assigned atomically
                    expires_at = datetime.now() + timedelta(minutes=timeout_minutes)
                    cursor.execute('''
                        UPDATE challenges
                        SET status = 'assigned',
                            assigned_to = ?,
                            assigned_at = CURRENT_TIMESTAMP,
                            assignment_expires = ?
                        WHERE challenge_id = ?
                    ''', (runner_id, expires_at, challenge_id))

                    conn.commit()

                    # Parse config JSON
                    challenge['config'] = json.loads(challenge['config'])
                    # Convert SQLite integer to boolean
                    challenge['enabled'] = bool(challenge['enabled'])

                    logger.info(f"Assigned challenge {challenge['name']} to runner {runner_id}")
                    return challenge
                else:
                    conn.rollback()
                    return None

            except Exception as e:
                conn.rollback()
                logger.error(f"Error assigning challenge to {runner_id}: {e}")
                return None

    def complete_challenge(self, challenge_id: str, runner_id: str, success: bool,
                           error_message: Optional[str] = None) -> Optional[Dict]:
        """Mark challenge as completed and requeue it. Returns challenge config."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            try:
                # Get challenge config to determine delay
                cursor.execute('SELECT config FROM challenges WHERE challenge_id = ?', (challenge_id,))
                row = cursor.fetchone()
                if not row:
                    return None

                config = json.loads(row['config'])
                min_delay = config.get('min_delay', 60)
                max_delay = config.get('max_delay', 90)

                # Calculate next transmission time (use average delay)
                avg_delay = (min_delay + max_delay) / 2
                now = datetime.now()
                next_tx = now + timedelta(seconds=avg_delay)

                # Update in-memory timing
                with self.timing_lock:
                    self.challenge_timing[challenge_id] = {
                        'last_tx': now,
                        'next_tx': next_tx
                    }

                # Update challenge status to waiting (delay timer active)
                cursor.execute('''
                    UPDATE challenges
                    SET status = 'waiting',
                        assigned_to = NULL,
                        assigned_at = NULL,
                        assignment_expires = NULL,
                        transmission_count = transmission_count + 1,
                        last_tx_time = CURRENT_TIMESTAMP
                    WHERE challenge_id = ?
                ''', (challenge_id,))

                conn.commit()

                status = 'success' if success else 'failed'
                logger.info(f"Challenge {challenge_id} completed by {runner_id}: {status}")
                return config

            except Exception as e:
                conn.rollback()
                logger.error(f"Error completing challenge {challenge_id}: {e}")
                return None

    def cleanup_stale_assignments(self, timeout_minutes: int = 5) -> int:
        """Requeue challenges that have been assigned but not completed within timeout."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE challenges
                SET status = 'waiting',
                    assigned_to = NULL,
                    assigned_at = NULL,
                    assignment_expires = NULL
                WHERE status = 'assigned'
                  AND assignment_expires < CURRENT_TIMESTAMP
            ''')

            conn.commit()
            count = cursor.rowcount

            if count > 0:
                logger.warning(f"Requeued {count} stale challenge assignment(s)")

            return count

    def enable_challenge(self, challenge_id: str, enabled: bool = True) -> bool:
        """Enable or disable a challenge."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE challenges
                SET enabled = ?
                WHERE challenge_id = ?
            ''', (1 if enabled else 0, challenge_id))
            conn.commit()
            return cursor.rowcount > 0

    # Transmission history
    def record_transmission_start(self, challenge_id: str, runner_id: str,
                                  device_id: str, frequency: int) -> int:
        """Record the start of a transmission."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO transmissions (challenge_id, runner_id, device_id, frequency, started_at, status)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, 'transmitting')
            ''', (challenge_id, runner_id, device_id, frequency))
            conn.commit()
            return cursor.lastrowid

    def record_transmission_complete(self, transmission_id: int, success: bool,
                                     error_message: Optional[str] = None):
        """Record transmission completion."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            status = 'success' if success else 'failed'
            cursor.execute('''
                UPDATE transmissions
                SET completed_at = CURRENT_TIMESTAMP,
                    status = ?,
                    error_message = ?
                WHERE transmission_id = ?
            ''', (status, error_message, transmission_id))
            conn.commit()

    def get_recent_transmissions(self, limit: int = 50) -> List[Dict]:
        """Get recent transmission history."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.*, c.name as challenge_name
                FROM transmissions t
                LEFT JOIN challenges c ON t.challenge_id = c.challenge_id
                ORDER BY t.started_at DESC
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]

    # File management
    def add_file(self, file_hash: str, filename: str, size: int,
                 mime_type: str, file_path: str) -> bool:
        """Register a file in the database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO files (file_hash, filename, size, mime_type, file_path)
                    VALUES (?, ?, ?, ?, ?)
                ''', (file_hash, filename, size, mime_type, file_path))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                # File already exists
                return True
            except Exception as e:
                logger.error(f"Error adding file {filename}: {e}")
                return False

    def get_file(self, file_hash: str) -> Optional[Dict]:
        """Get file metadata."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM files WHERE file_hash = ?', (file_hash,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    # System state
    def set_system_state(self, key: str, value: str):
        """Set a system state value."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO system_state (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
            ''', (key, value))
            conn.commit()

    def get_system_state(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a system state value."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM system_state WHERE key = ?', (key,))
            row = cursor.fetchone()
            if row:
                return row['value']
            return default

    # User management
    def create_user(self, username: str, password_hash: str, totp_secret: str) -> bool:
        """Create a new admin user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Encrypt TOTP secret before storing
                encrypted_totp_secret = encrypt_totp_secret(totp_secret)

                cursor.execute('''
                    INSERT INTO users (username, password_hash, totp_secret)
                    VALUES (?, ?, ?)
                ''', (username, password_hash, encrypted_totp_secret))
                conn.commit()
                logger.info(f"Created user: {username}")
                return True
            except sqlite3.IntegrityError:
                logger.warning(f"User {username} already exists")
                return False
            except Exception as e:
                logger.error(f"Error creating user {username}: {e}")
                return False

    def get_user(self, username: str) -> Optional[Dict]:
        """Get user details."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            row = cursor.fetchone()
            if row:
                user_dict = dict(row)
                # Decrypt TOTP secret if present
                if user_dict.get('totp_secret'):
                    decrypted_secret = decrypt_totp_secret(user_dict['totp_secret'])
                    # Handle legacy unencrypted secrets
                    if decrypted_secret is None:
                        # If decryption fails, assume it's a legacy unencrypted secret
                        logger.warning(f"User {username} has legacy unencrypted TOTP secret")
                        # Keep the original value for now (will be migrated later)
                    else:
                        user_dict['totp_secret'] = decrypted_secret
                return user_dict
            return None

    def update_last_login(self, username: str) -> bool:
        """Update user's last login timestamp."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users
                SET last_login = CURRENT_TIMESTAMP
                WHERE username = ?
            ''', (username,))
            conn.commit()
            return cursor.rowcount > 0

    def disable_user(self, username: str) -> bool:
        """Disable a user account."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users
                SET enabled = 0
                WHERE username = ?
            ''', (username,))
            conn.commit()
            return cursor.rowcount > 0

    def enable_user(self, username: str) -> bool:
        """Enable a user account."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users
                SET enabled = 1
                WHERE username = ?
            ''', (username,))
            conn.commit()
            return cursor.rowcount > 0

    def change_password(self, username: str, new_password_hash: str) -> bool:
        """Change user password."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users
                SET password_hash = ?
                WHERE username = ?
            ''', (new_password_hash, username))
            conn.commit()
            return cursor.rowcount > 0

    def get_all_users(self) -> List[Dict]:
        """Get all users (excluding password hashes and TOTP secrets)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT username, enabled, password_change_required, created_at, last_login
                FROM users
                ORDER BY username
            ''')
            return [dict(row) for row in cursor.fetchall()]

    def clear_password_change_required(self, username: str) -> bool:
        """Clear password change requirement flag."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users
                SET password_change_required = 0
                WHERE username = ?
            ''', (username,))
            conn.commit()
            return cursor.rowcount > 0

    def delete_user(self, username: str) -> bool:
        """Delete a user account."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM users
                WHERE username = ?
            ''', (username,))
            conn.commit()
            return cursor.rowcount > 0

    # Session management methods

    def create_session(self, session_token: str, username: str, expires: str, totp_verified: bool = False) -> bool:
        """Create a new session in the database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO sessions (session_token, username, expires, totp_verified)
                VALUES (?, ?, ?, ?)
            ''', (session_token, username, expires, 1 if totp_verified else 0))
            conn.commit()
            return cursor.rowcount > 0

    def get_session(self, session_token: str) -> Optional[Dict]:
        """Get a session by token."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT session_token, username, expires, totp_verified, created_at
                FROM sessions
                WHERE session_token = ?
            ''', (session_token,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_session_totp(self, session_token: str) -> bool:
        """Mark a session as TOTP verified."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE sessions
                SET totp_verified = 1
                WHERE session_token = ?
            ''', (session_token,))
            conn.commit()
            return cursor.rowcount > 0

    def update_session_expires(self, session_token: str, new_expires: str) -> bool:
        """Update session expiry time (for sliding sessions)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE sessions
                SET expires = ?
                WHERE session_token = ?
            ''', (new_expires, session_token))
            conn.commit()
            return cursor.rowcount > 0

    def delete_session(self, session_token: str) -> bool:
        """Delete a specific session."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM sessions
                WHERE session_token = ?
            ''', (session_token,))
            conn.commit()
            return cursor.rowcount > 0

    def delete_user_sessions(self, username: str, except_token: Optional[str] = None) -> int:
        """
        Delete all sessions for a user, optionally excluding one session.
        Returns the number of sessions deleted.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if except_token:
                cursor.execute('''
                    DELETE FROM sessions
                    WHERE username = ? AND session_token != ?
                ''', (username, except_token))
            else:
                cursor.execute('''
                    DELETE FROM sessions
                    WHERE username = ?
                ''', (username,))
            conn.commit()
            return cursor.rowcount

    def cleanup_expired_sessions(self) -> int:
        """Delete all expired sessions. Returns the number of sessions deleted.

        SECURITY: Uses UTC timestamps for consistent timezone handling.
        """
        from datetime import datetime
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Use UTC for consistent timezone handling
            now = datetime.utcnow().isoformat()
            cursor.execute('''
                DELETE FROM sessions
                WHERE expires < ?
            ''', (now,))
            conn.commit()
            return cursor.rowcount

    # Enrollment token management
    def create_enrollment_token(self, token: str, runner_name: str, created_by: str, expires_at: datetime) -> bool:
        """Create a new enrollment token for runner registration.

        Args:
            token: The unique enrollment token
            runner_name: Descriptive name for the runner
            created_by: Username of the admin who created the token
            expires_at: When the token expires

        Returns:
            True if successful, False otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO enrollment_tokens (token, runner_name, created_by, expires_at)
                    VALUES (?, ?, ?, ?)
                ''', (token, runner_name, created_by, expires_at))
                conn.commit()
                logger.info(f"Created enrollment token for runner: {runner_name}")
                return True
            except Exception as e:
                logger.error(f"Error creating enrollment token: {e}")
                return False

    def get_enrollment_token(self, token: str) -> Optional[Dict]:
        """Get enrollment token details.

        Args:
            token: The enrollment token to look up

        Returns:
            Token details dict or None if not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM enrollment_tokens WHERE token = ?', (token,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def verify_enrollment_token(self, token: str) -> tuple[bool, Optional[str]]:
        """Verify an enrollment token is valid and unused.

        Args:
            token: The enrollment token to verify

        Returns:
            Tuple of (is_valid, runner_name)
        """
        token_data = self.get_enrollment_token(token)

        if not token_data:
            return (False, None)

        # Check if already used
        if token_data['used']:
            logger.warning(f"Enrollment token already used")
            return (False, None)

        # Check if expired
        expires_at = datetime.fromisoformat(token_data['expires_at'])
        if datetime.now(timezone.utc) > expires_at:
            logger.warning(f"Enrollment token expired")
            return (False, None)

        return (True, token_data['runner_name'])

    def mark_token_used(self, token: str, runner_id: str) -> bool:
        """Mark an enrollment token as used.

        Args:
            token: The enrollment token
            runner_id: The runner ID that used this token

        Returns:
            True if successful, False otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE enrollment_tokens
                SET used = 1, used_at = CURRENT_TIMESTAMP, used_by_runner_id = ?
                WHERE token = ?
            ''', (runner_id, token))
            conn.commit()
            return cursor.rowcount > 0

    def get_all_enrollment_tokens(self) -> List[Dict]:
        """Get all enrollment tokens (for admin view).

        Returns:
            List of all enrollment tokens
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM enrollment_tokens
                ORDER BY created_at DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]

    def delete_enrollment_token(self, token: str) -> bool:
        """Delete an enrollment token.

        Args:
            token: The enrollment token to delete

        Returns:
            True if successful, False otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM enrollment_tokens WHERE token = ?', (token,))
            conn.commit()
            return cursor.rowcount > 0

    def cleanup_expired_tokens(self) -> int:
        """Delete expired enrollment tokens.

        Returns:
            Number of tokens deleted
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM enrollment_tokens
                WHERE expires_at < ? AND used = 0
            ''', (datetime.now(timezone.utc),))
            conn.commit()
            return cursor.rowcount

    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get statistics for the dashboard."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            stats = {}

            # Runner stats
            cursor.execute('SELECT COUNT(*) as total, SUM(CASE WHEN status="online" THEN 1 ELSE 0 END) as online FROM runners')
            row = cursor.fetchone()
            stats['runners_total'] = row['total']
            stats['runners_online'] = row['online']

            # Challenge stats
            cursor.execute('''
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status='queued' THEN 1 ELSE 0 END) as queued,
                    SUM(CASE WHEN status='waiting' THEN 1 ELSE 0 END) as waiting,
                    SUM(CASE WHEN status='assigned' THEN 1 ELSE 0 END) as assigned,
                    SUM(transmission_count) as total_transmissions
                FROM challenges
                WHERE enabled = 1
            ''')
            row = cursor.fetchone()
            stats['challenges_total'] = row['total']
            stats['challenges_queued'] = row['queued']
            stats['challenges_waiting'] = row['waiting']
            stats['challenges_assigned'] = row['assigned']
            stats['total_transmissions'] = row['total_transmissions'] or 0

            # System state
            stats['paused'] = self.get_system_state('paused', 'false') == 'true'

            return stats
