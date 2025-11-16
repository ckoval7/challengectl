#!/usr/bin/env python3
"""
Database schema and management for challengectl server.
Uses SQLite for simplicity with 2-3 runners.
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import threading

logger = logging.getLogger(__name__)


class Database:
    """Thread-safe SQLite database wrapper for challengectl server."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()
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
                    last_heartbeat TIMESTAMP,
                    devices JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Challenges table
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
    def register_runner(self, runner_id: str, hostname: str, ip_address: str, devices: List[Dict]) -> bool:
        """Register a new runner or update existing one."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO runners (runner_id, hostname, ip_address, status, last_heartbeat, devices)
                    VALUES (?, ?, ?, 'online', ?, ?)
                    ON CONFLICT(runner_id) DO UPDATE SET
                        hostname = excluded.hostname,
                        ip_address = excluded.ip_address,
                        status = 'online',
                        last_heartbeat = excluded.last_heartbeat,
                        devices = excluded.devices,
                        updated_at = CURRENT_TIMESTAMP
                ''', (runner_id, hostname, ip_address, datetime.now(), json.dumps(devices)))
                conn.commit()
                logger.info(f"Registered runner: {runner_id} from {ip_address}")
                return True
            except Exception as e:
                logger.error(f"Error registering runner {runner_id}: {e}")
                return False

    def update_heartbeat(self, runner_id: str) -> bool:
        """Update runner heartbeat timestamp."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    UPDATE runners
                    SET last_heartbeat = ?, status = 'online', updated_at = CURRENT_TIMESTAMP
                    WHERE runner_id = ?
                ''', (datetime.now(), runner_id))
                conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                logger.error(f"Error updating heartbeat for {runner_id}: {e}")
                return False

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

    def cleanup_stale_runners(self, timeout_seconds: int = 90) -> int:
        """Mark runners as offline if they haven't sent heartbeat within timeout."""
        threshold = datetime.now() - timedelta(seconds=timeout_seconds)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE runners
                SET status = 'offline'
                WHERE status = 'online'
                  AND last_heartbeat < ?
            ''', (threshold,))
            conn.commit()
            count = cursor.rowcount
            if count > 0:
                logger.warning(f"Marked {count} runner(s) as offline due to missed heartbeats")
            return count

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
                # Find next available challenge
                cursor.execute('''
                    SELECT * FROM challenges
                    WHERE status = 'queued'
                      AND enabled = 1
                      AND (next_tx_time IS NULL OR next_tx_time <= CURRENT_TIMESTAMP)
                    ORDER BY priority DESC, last_tx_time ASC NULLS FIRST
                    LIMIT 1
                ''')

                row = cursor.fetchone()

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
                           error_message: Optional[str] = None) -> bool:
        """Mark challenge as completed and requeue it."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            try:
                # Get challenge config to determine delay
                cursor.execute('SELECT config FROM challenges WHERE challenge_id = ?', (challenge_id,))
                row = cursor.fetchone()
                if not row:
                    return False

                config = json.loads(row['config'])
                min_delay = config.get('min_delay', 60)
                max_delay = config.get('max_delay', 90)
                frequency = config.get('frequency', 0)

                # Record transmission in history
                status = 'success' if success else 'failed'
                cursor.execute('''
                    INSERT INTO transmissions (challenge_id, runner_id, device_id, frequency, started_at, completed_at, status, error_message)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?)
                ''', (challenge_id, runner_id, '', frequency, status, error_message))

                # Calculate next transmission time (use average delay)
                avg_delay = (min_delay + max_delay) / 2
                next_tx = datetime.now() + timedelta(seconds=avg_delay)

                # Update challenge status
                cursor.execute('''
                    UPDATE challenges
                    SET status = 'queued',
                        assigned_to = NULL,
                        assigned_at = NULL,
                        assignment_expires = NULL,
                        last_tx_time = CURRENT_TIMESTAMP,
                        next_tx_time = ?,
                        transmission_count = transmission_count + 1
                    WHERE challenge_id = ?
                ''', (next_tx, challenge_id))

                conn.commit()

                logger.info(f"Challenge {challenge_id} completed by {runner_id}: {status}")
                return True

            except Exception as e:
                conn.rollback()
                logger.error(f"Error completing challenge {challenge_id}: {e}")
                return False

    def cleanup_stale_assignments(self, timeout_minutes: int = 5) -> int:
        """Requeue challenges that have been assigned but not completed within timeout."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE challenges
                SET status = 'queued',
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
                cursor.execute('''
                    INSERT INTO users (username, password_hash, totp_secret)
                    VALUES (?, ?, ?)
                ''', (username, password_hash, totp_secret))
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
                return dict(row)
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
                    SUM(CASE WHEN status='assigned' THEN 1 ELSE 0 END) as assigned,
                    SUM(transmission_count) as total_transmissions
                FROM challenges
                WHERE enabled = 1
            ''')
            row = cursor.fetchone()
            stats['challenges_total'] = row['total']
            stats['challenges_queued'] = row['queued']
            stats['challenges_assigned'] = row['assigned']
            stats['total_transmissions'] = row['total_transmissions'] or 0

            # Recent transmission success rate
            cursor.execute('''
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as successful
                FROM transmissions
                WHERE started_at > datetime('now', '-1 hour')
            ''')
            row = cursor.fetchone()
            if row['total'] > 0:
                stats['success_rate'] = (row['successful'] / row['total']) * 100
                stats['transmissions_last_hour'] = row['total']
            else:
                stats['success_rate'] = 0
                stats['transmissions_last_hour'] = 0

            # System state
            stats['paused'] = self.get_system_state('paused', 'false') == 'true'

            return stats
