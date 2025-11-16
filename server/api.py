#!/usr/bin/env python3
"""
REST API server for challengectl using Flask and Flask-SocketIO.
Handles runner communication, challenge distribution, and WebUI serving.
"""

from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from functools import wraps
import logging
import os
import hashlib
import yaml
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import uuid
from collections import deque
import threading
import secrets
import bcrypt
import pyotp

from database import Database

logger = logging.getLogger(__name__)


class WebSocketHandler(logging.Handler):
    """Custom logging handler that broadcasts logs to WebUI via WebSocket."""

    def __init__(self, socketio, log_buffer, buffer_lock):
        super().__init__()
        self.socketio = socketio
        self.log_buffer = log_buffer
        self.buffer_lock = buffer_lock

    def emit(self, record):
        """Emit a log record to WebSocket clients."""
        try:
            log_entry = {
                'type': 'log',
                'source': 'server',
                'level': record.levelname,
                'message': record.getMessage(),
                'timestamp': datetime.fromtimestamp(record.created).isoformat()
            }

            # Add to buffer for historical retrieval
            with self.buffer_lock:
                self.log_buffer.append(log_entry)

            # Broadcast to WebUI
            self.socketio.emit('event', log_entry)
        except Exception as e:
            # Try to log at debug level to avoid recursion
            # If this fails, silently ignore to prevent infinite loop
            try:
                logger.debug(f"WebSocket handler error: {e}")
            except Exception:
                pass


class ChallengeCtlAPI:
    """Main API server for challengectl."""

    def __init__(self, config_path: str, db: Database, files_dir: str):
        # Don't use Flask's static file serving - we'll handle it manually for SPA routing
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = os.urandom(24)

        # Store frontend directory path
        self.frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend/dist'))

        # Enable CORS for development
        CORS(self.app)

        # Initialize SocketIO for real-time updates
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")

        # Use provided database instance
        self.db = db

        # Configuration
        self.config_path = config_path
        self.config = self.load_config(config_path)
        self.api_keys = self.config.get('server', {}).get('api_keys', {})
        self.files_dir = files_dir

        # In-memory log buffer for recent logs (last 500)
        self.log_buffer = deque(maxlen=500)
        self.buffer_lock = threading.Lock()

        # In-memory transmission buffer for recent transmissions (last 50)
        self.transmission_buffer = deque(maxlen=50)
        self.transmission_lock = threading.Lock()

        # Session management for admin authentication
        # Format: {session_token: {'username': str, 'expires': datetime, 'totp_verified': bool}}
        self.sessions = {}
        self.sessions_lock = threading.Lock()

        # Ensure files directory exists
        os.makedirs(self.files_dir, exist_ok=True)

        # Register routes
        self.register_routes()
        self.register_socketio_handlers()

        # Set up WebSocket logging handler
        self.setup_websocket_logging()

        logger.info("ChallengeCtl API initialized")

    def setup_websocket_logging(self):
        """Add WebSocket handler to root logger to broadcast all logs."""
        ws_handler = WebSocketHandler(self.socketio, self.log_buffer, self.buffer_lock)
        ws_handler.setLevel(logging.INFO)
        # Don't format here - we send structured data
        logging.root.addHandler(ws_handler)

    def load_config(self, config_path: str) -> Dict:
        """Load server configuration from YAML."""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded configuration from {config_path}")
                return config
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {}

    def _parse_runner_devices(self, runner: Dict) -> Dict:
        """Parse devices JSON field in runner dict.

        Args:
            runner: Runner dict with 'devices' field (JSON string)

        Returns:
            Runner dict with 'devices' parsed as dict/list
        """
        if runner and runner.get('devices'):
            try:
                runner['devices'] = json.loads(runner['devices'])
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Failed to parse devices for runner {runner.get('runner_id')}")
                runner['devices'] = []
        return runner

    def require_api_key(self, f):
        """Decorator to require API key authentication (for runners only)."""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization')

            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({'error': 'Missing or invalid authorization header'}), 401

            api_key = auth_header[7:]  # Remove 'Bearer ' prefix

            # Find runner_id for this API key
            runner_id = None
            for rid, key in self.api_keys.items():
                if key == api_key:
                    runner_id = rid
                    break

            if not runner_id:
                return jsonify({'error': 'Invalid API key'}), 401

            # Add runner_id to request context
            request.runner_id = runner_id

            return f(*args, **kwargs)

        return decorated_function

    def require_admin_auth(self, f):
        """Decorator to require admin session authentication."""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization')

            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({'error': 'Missing or invalid authorization header'}), 401

            session_token = auth_header[7:]  # Remove 'Bearer ' prefix

            # Check session validity
            with self.sessions_lock:
                session = self.sessions.get(session_token)

                if not session:
                    return jsonify({'error': 'Invalid or expired session'}), 401

                # Check if session is expired
                if datetime.now() > session['expires']:
                    del self.sessions[session_token]
                    return jsonify({'error': 'Session expired'}), 401

                # Check if TOTP was verified
                if not session.get('totp_verified', False):
                    return jsonify({'error': 'TOTP verification required'}), 401

                # Add username to request context
                request.admin_username = session['username']

            return f(*args, **kwargs)

        return decorated_function

    def create_session(self, username: str, totp_verified: bool = False) -> str:
        """Create a new session token for a user."""
        session_token = secrets.token_urlsafe(32)
        expires = datetime.now() + timedelta(hours=24)

        with self.sessions_lock:
            self.sessions[session_token] = {
                'username': username,
                'expires': expires,
                'totp_verified': totp_verified
            }

        return session_token

    def update_session_totp(self, session_token: str) -> bool:
        """Mark session as TOTP verified."""
        with self.sessions_lock:
            if session_token in self.sessions:
                self.sessions[session_token]['totp_verified'] = True
                return True
            return False

    def destroy_session(self, session_token: str) -> bool:
        """Destroy a session."""
        with self.sessions_lock:
            if session_token in self.sessions:
                del self.sessions[session_token]
                return True
            return False

    def cleanup_expired_sessions(self):
        """Remove expired sessions (called periodically)."""
        now = datetime.now()
        with self.sessions_lock:
            expired = [token for token, session in self.sessions.items()
                       if session['expires'] < now]
            for token in expired:
                del self.sessions[token]
            if expired:
                logger.info(f"Cleaned up {len(expired)} expired session(s)")

    def register_routes(self):
        """Register all API routes."""

        # Health check (no auth required)
        @self.app.route('/api/health', methods=['GET'])
        def health_check():
            return jsonify({
                'status': 'ok',
                'timestamp': datetime.now().isoformat()
            })

        # Authentication endpoints
        @self.app.route('/api/auth/login', methods=['POST'])
        def login():
            """Authenticate with username and password, return session token."""
            data = request.json

            if not data:
                return jsonify({'error': 'Missing request body'}), 400

            username = data.get('username')
            password = data.get('password')

            if not username or not password:
                return jsonify({'error': 'Missing username or password'}), 400

            # Get user from database
            user = self.db.get_user(username)

            if not user:
                return jsonify({'error': 'Invalid credentials'}), 401

            if not user.get('enabled'):
                return jsonify({'error': 'Account disabled'}), 403

            # Verify password
            try:
                password_hash = user['password_hash']
                if not bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')):
                    return jsonify({'error': 'Invalid credentials'}), 401
            except Exception as e:
                logger.error(f"Password verification error: {e}")
                return jsonify({'error': 'Authentication failed'}), 500

            # Check if user has TOTP configured
            totp_secret = user.get('totp_secret')
            has_totp = totp_secret is not None and totp_secret != ''

            if has_totp:
                # Create session (not yet TOTP verified)
                session_token = self.create_session(username, totp_verified=False)

                # Return session token and TOTP requirement
                return jsonify({
                    'session_token': session_token,
                    'totp_required': True,
                    'username': username
                }), 200
            else:
                # No TOTP configured - complete login immediately
                session_token = self.create_session(username, totp_verified=True)

                # Update last login timestamp
                self.db.update_last_login(username)

                # Check if initial setup is required
                initial_setup_required = self.db.get_system_state('initial_setup_required', 'false') == 'true'

                logger.info(f"User {username} logged in (no TOTP configured)")

                return jsonify({
                    'status': 'authenticated',
                    'session_token': session_token,
                    'totp_required': False,
                    'initial_setup_required': initial_setup_required,
                    'username': username
                }), 200

        @self.app.route('/api/auth/verify-totp', methods=['POST'])
        def verify_totp():
            """Verify TOTP code and fully authenticate the session."""
            data = request.json

            if not data:
                return jsonify({'error': 'Missing request body'}), 400

            session_token = data.get('session_token')
            totp_code = data.get('totp_code')

            if not session_token or not totp_code:
                return jsonify({'error': 'Missing session_token or totp_code'}), 400

            # Get session
            with self.sessions_lock:
                session = self.sessions.get(session_token)

                if not session:
                    return jsonify({'error': 'Invalid or expired session'}), 401

                if datetime.now() > session['expires']:
                    del self.sessions[session_token]
                    return jsonify({'error': 'Session expired'}), 401

                username = session['username']

            # Get user's TOTP secret
            user = self.db.get_user(username)

            if not user:
                return jsonify({'error': 'User not found'}), 401

            totp_secret = user.get('totp_secret')

            if not totp_secret:
                return jsonify({'error': 'TOTP not configured for this user'}), 500

            # Verify TOTP code
            try:
                totp = pyotp.TOTP(totp_secret)
                if not totp.verify(totp_code, valid_window=1):
                    return jsonify({'error': 'Invalid TOTP code'}), 401
            except Exception as e:
                logger.error(f"TOTP verification error: {e}")
                return jsonify({'error': 'TOTP verification failed'}), 500

            # Mark session as TOTP verified
            if not self.update_session_totp(session_token):
                return jsonify({'error': 'Failed to update session'}), 500

            # Update last login timestamp
            self.db.update_last_login(username)

            logger.info(f"User {username} logged in successfully")

            # Check if password change is required
            password_change_required = user.get('password_change_required', False)

            return jsonify({
                'status': 'authenticated',
                'session_token': session_token,
                'password_change_required': bool(password_change_required),
                'username': username
            }), 200

        @self.app.route('/api/auth/logout', methods=['POST'])
        def logout():
            """Logout and destroy session."""
            auth_header = request.headers.get('Authorization')

            if auth_header and auth_header.startswith('Bearer '):
                session_token = auth_header[7:]
                self.destroy_session(session_token)

            return jsonify({'status': 'logged out'}), 200

        @self.app.route('/api/auth/change-password', methods=['POST'])
        @self.require_admin_auth
        def change_own_password():
            """Change logged-in user's password."""
            data = request.json

            if not data:
                return jsonify({'error': 'Missing request body'}), 400

            current_password = data.get('current_password')
            new_password = data.get('new_password')

            if not current_password or not new_password:
                return jsonify({'error': 'Missing current_password or new_password'}), 400

            if len(new_password) < 8:
                return jsonify({'error': 'Password must be at least 8 characters'}), 400

            username = request.admin_username

            # Get user
            user = self.db.get_user(username)

            if not user:
                return jsonify({'error': 'User not found'}), 401

            # Verify current password
            try:
                password_hash = user['password_hash']
                if not bcrypt.checkpw(current_password.encode('utf-8'), password_hash.encode('utf-8')):
                    return jsonify({'error': 'Current password is incorrect'}), 401
            except Exception as e:
                logger.error(f"Password verification error: {e}")
                return jsonify({'error': 'Authentication failed'}), 500

            # Hash new password
            new_password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

            # Update password
            if not self.db.change_password(username, new_password_hash):
                return jsonify({'error': 'Failed to update password'}), 500

            # Clear password change requirement
            self.db.clear_password_change_required(username)

            logger.info(f"User {username} changed their password")

            return jsonify({'status': 'password changed'}), 200

        # User management endpoints (admin only)
        @self.app.route('/api/users', methods=['GET'])
        @self.require_admin_auth
        def get_users():
            """Get all users."""
            users = self.db.get_all_users()
            return jsonify({'users': users}), 200

        @self.app.route('/api/users', methods=['POST'])
        @self.require_admin_auth
        def create_user_endpoint():
            """Create a new user."""
            data = request.json

            if not data:
                return jsonify({'error': 'Missing request body'}), 400

            username = data.get('username')
            password = data.get('password')

            if not username or not password:
                return jsonify({'error': 'Missing username or password'}), 400

            if len(password) < 8:
                return jsonify({'error': 'Password must be at least 8 characters'}), 400

            # Generate TOTP secret
            totp_secret = pyotp.random_base32()

            # Hash password
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

            # Create user
            if not self.db.create_user(username, password_hash, totp_secret):
                return jsonify({'error': 'User already exists'}), 409

            # Mark initial setup as complete if this is being done during initial setup
            if self.db.get_system_state('initial_setup_required', 'false') == 'true':
                self.db.set_system_state('initial_setup_required', 'false')
                # Disable the default admin account for security
                self.db.disable_user('admin')
                logger.info("Initial setup completed - default admin account disabled")

            # Generate TOTP provisioning URI
            totp = pyotp.TOTP(totp_secret)
            provisioning_uri = totp.provisioning_uri(name=username, issuer_name="ChallengeCtl")

            logger.info(f"User {username} created by {request.admin_username}")

            return jsonify({
                'status': 'created',
                'username': username,
                'totp_secret': totp_secret,
                'provisioning_uri': provisioning_uri
            }), 201

        @self.app.route('/api/users/<username>', methods=['PUT'])
        @self.require_admin_auth
        def update_user_endpoint(username):
            """Update user (enable/disable)."""
            data = request.json

            if not data:
                return jsonify({'error': 'Missing request body'}), 400

            enabled = data.get('enabled')

            if enabled is None:
                return jsonify({'error': 'Missing enabled field'}), 400

            # Check user exists
            user = self.db.get_user(username)
            if not user:
                return jsonify({'error': 'User not found'}), 404

            # Don't allow disabling yourself
            if username == request.admin_username and not enabled:
                return jsonify({'error': 'Cannot disable your own account'}), 400

            # Update user
            if enabled:
                success = self.db.enable_user(username)
            else:
                success = self.db.disable_user(username)

            if not success:
                return jsonify({'error': 'Failed to update user'}), 500

            logger.info(f"User {username} {'enabled' if enabled else 'disabled'} by {request.admin_username}")

            return jsonify({'status': 'updated'}), 200

        @self.app.route('/api/users/<username>', methods=['DELETE'])
        @self.require_admin_auth
        def delete_user_endpoint(username):
            """Delete a user."""
            # Don't allow deleting yourself
            if username == request.admin_username:
                return jsonify({'error': 'Cannot delete your own account'}), 400

            # Check user exists
            user = self.db.get_user(username)
            if not user:
                return jsonify({'error': 'User not found'}), 404

            # Delete user
            if not self.db.delete_user(username):
                return jsonify({'error': 'Failed to delete user'}), 500

            logger.info(f"User {username} deleted by {request.admin_username}")

            return jsonify({'status': 'deleted'}), 200

        @self.app.route('/api/users/<username>/reset-totp', methods=['POST'])
        @self.require_admin_auth
        def reset_user_totp(username):
            """Reset TOTP secret for a user."""
            # Check user exists
            user = self.db.get_user(username)
            if not user:
                return jsonify({'error': 'User not found'}), 404

            # Generate new TOTP secret
            totp_secret = pyotp.random_base32()

            # Update user
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users
                    SET totp_secret = ?
                    WHERE username = ?
                ''', (totp_secret, username))
                conn.commit()

            # Generate TOTP provisioning URI
            totp = pyotp.TOTP(totp_secret)
            provisioning_uri = totp.provisioning_uri(name=username, issuer_name="ChallengeCtl")

            logger.info(f"TOTP reset for user {username} by {request.admin_username}")

            return jsonify({
                'status': 'totp_reset',
                'totp_secret': totp_secret,
                'provisioning_uri': provisioning_uri
            }), 200

        @self.app.route('/api/users/<username>/reset-password', methods=['POST'])
        @self.require_admin_auth
        def reset_user_password(username):
            """Reset a user's password (admin only)."""
            data = request.json

            if not data:
                return jsonify({'error': 'Missing request body'}), 400

            new_password = data.get('new_password')

            if not new_password:
                return jsonify({'error': 'Missing new_password'}), 400

            if len(new_password) < 8:
                return jsonify({'error': 'Password must be at least 8 characters'}), 400

            # Check user exists
            user = self.db.get_user(username)
            if not user:
                return jsonify({'error': 'User not found'}), 404

            # Hash new password
            password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

            # Update password
            if not self.db.change_password(username, password_hash):
                return jsonify({'error': 'Failed to update password'}), 500

            # Mark password change as required on next login
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users
                    SET password_change_required = 1
                    WHERE username = ?
                ''', (username,))
                conn.commit()

            logger.info(f"Password reset for user {username} by {request.admin_username}")

            return jsonify({'status': 'password_reset'}), 200

        # Public dashboard endpoint (no auth required)
        @self.app.route('/api/public/challenges', methods=['GET'])
        def get_public_challenges():
            """Get public view of enabled challenges with configurable visibility."""
            try:
                all_challenges = self.db.get_all_challenges()

                # Filter to only enabled challenges and remove sensitive information
                public_challenges = []
                for challenge in all_challenges:
                    if not challenge.get('enabled'):
                        continue

                    config = challenge.get('config', {})

                    # Build public challenge object with only safe fields
                    public_challenge = {
                        'challenge_id': challenge['challenge_id'],
                        'name': challenge['name'],
                        'modulation': config.get('modulation', 'unknown'),
                        'transmission_count': challenge.get('transmission_count', 0),
                    }

                    # Conditionally add fields based on public view settings
                    public_view = config.get('public_view', {})

                    # Show frequency if enabled (default: True)
                    if public_view.get('show_frequency', True):
                        frequency = config.get('frequency')
                        if frequency:
                            # Format frequency in MHz for readability
                            freq_mhz = frequency / 1_000_000
                            public_challenge['frequency'] = frequency
                            public_challenge['frequency_display'] = f"{freq_mhz:.3f} MHz"

                    # Show last transmission time if enabled (default: False)
                    if public_view.get('show_last_tx_time', False):
                        last_tx = challenge.get('last_tx_time')
                        if last_tx:
                            public_challenge['last_tx_time'] = last_tx

                    # Show active status if enabled (default: True)
                    if public_view.get('show_active_status', True):
                        # Check if currently assigned (actively transmitting)
                        is_active = (challenge.get('status') == 'assigned' and
                                     challenge.get('assigned_to') is not None)
                        public_challenge['is_active'] = is_active

                    public_challenges.append(public_challenge)

                # Sort by name
                public_challenges.sort(key=lambda x: x['name'])

                return jsonify({
                    'challenges': public_challenges,
                    'count': len(public_challenges),
                    'timestamp': datetime.now().isoformat()
                }), 200

            except Exception as e:
                logger.error(f"Error getting public challenges: {e}")
                return jsonify({'error': 'Internal server error'}), 500

        # Runner endpoints
        @self.app.route('/api/runners/register', methods=['POST'])
        @self.require_api_key
        def register_runner():
            """Register a runner with the server."""
            data = request.json

            # Validate request body
            if not data:
                return jsonify({'error': 'Missing request body'}), 400

            runner_id = request.runner_id

            # Validate required fields
            hostname = data.get('hostname')
            if not hostname or not hostname.strip():
                return jsonify({'error': 'Missing required field: hostname'}), 400

            devices = data.get('devices')
            if devices is None:
                return jsonify({'error': 'Missing required field: devices'}), 400

            if not isinstance(devices, list):
                return jsonify({'error': 'Field "devices" must be a list'}), 400

            ip_address = request.remote_addr

            success = self.db.register_runner(runner_id, hostname, ip_address, devices)

            if success:
                # Broadcast runner online event
                self.broadcast_event('runner_status', {
                    'runner_id': runner_id,
                    'status': 'online',
                    'timestamp': datetime.now().isoformat()
                })

                return jsonify({
                    'status': 'registered',
                    'runner_id': runner_id
                }), 200
            else:
                return jsonify({'error': 'Registration failed'}), 500

        @self.app.route('/api/runners/<runner_id>/heartbeat', methods=['POST'])
        @self.require_api_key
        def heartbeat(runner_id):
            """Update runner heartbeat."""
            if request.runner_id != runner_id:
                return jsonify({'error': 'Unauthorized'}), 403

            success = self.db.update_heartbeat(runner_id)

            if success:
                return jsonify({'status': 'ok'}), 200
            else:
                return jsonify({'error': 'Runner not found'}), 404

        @self.app.route('/api/runners/<runner_id>/task', methods=['GET'])
        @self.require_api_key
        def get_task(runner_id):
            """Get next challenge assignment for runner."""
            if request.runner_id != runner_id:
                return jsonify({'error': 'Unauthorized'}), 403

            # Check if system is paused
            if self.db.get_system_state('paused', 'false') == 'true':
                return jsonify({'task': None, 'message': 'System paused'}), 200

            # Assign challenge
            challenge = self.db.assign_challenge(runner_id)

            if challenge:
                # Broadcast assignment event
                self.broadcast_event('challenge_assigned', {
                    'runner_id': runner_id,
                    'challenge_id': challenge['challenge_id'],
                    'challenge_name': challenge['name'],
                    'timestamp': datetime.now().isoformat()
                })

                return jsonify({
                    'task': {
                        'challenge_id': challenge['challenge_id'],
                        'name': challenge['name'],
                        'config': challenge['config']
                    }
                }), 200
            else:
                return jsonify({'task': None, 'message': 'No challenges available'}), 200

        @self.app.route('/api/runners/<runner_id>/complete', methods=['POST'])
        @self.require_api_key
        def complete_task(runner_id):
            """Mark challenge as completed."""
            if request.runner_id != runner_id:
                return jsonify({'error': 'Unauthorized'}), 403

            data = request.json

            # Validate request body
            if not data:
                return jsonify({'error': 'Missing request body'}), 400

            # Validate required fields
            challenge_id = data.get('challenge_id')
            if not challenge_id:
                return jsonify({'error': 'Missing required field: challenge_id'}), 400

            success = data.get('success', False)
            if not isinstance(success, bool):
                return jsonify({'error': 'Field "success" must be a boolean'}), 400

            error_message = data.get('error_message')
            # device_id and frequency are logged but not currently used
            # device_id = data.get('device_id', '')
            # frequency = data.get('frequency', 0)

            # Get challenge info and requeue
            challenge = self.db.get_challenge(challenge_id)
            challenge_name = challenge['name'] if challenge else challenge_id

            config = self.db.complete_challenge(challenge_id, runner_id, success, error_message)
            if not config:
                return jsonify({'error': 'Challenge not found'}), 404

            # Add to in-memory transmission buffer
            timestamp = datetime.now().isoformat()
            transmission = {
                'started_at': timestamp,
                'runner_id': runner_id,
                'challenge_id': challenge_id,
                'challenge_name': challenge_name,
                'frequency': config.get('frequency', 0),
                'status': 'success' if success else 'failed',
                'error_message': error_message
            }

            with self.transmission_lock:
                self.transmission_buffer.appendleft(transmission)
                logger.info(f"Added transmission to buffer. Buffer size: {len(self.transmission_buffer)}")

            # Broadcast completion event
            self.broadcast_event('transmission_complete', {
                'runner_id': runner_id,
                'challenge_id': challenge_id,
                'challenge_name': challenge_name,
                'frequency': config.get('frequency', 0),
                'status': 'success' if success else 'failed',
                'error_message': error_message,
                'timestamp': timestamp
            })

            return jsonify({'status': 'recorded'}), 200

        @self.app.route('/api/runners/<runner_id>/log', methods=['POST'])
        @self.require_api_key
        def upload_log(runner_id):
            """Receive log entries from runner."""
            if request.runner_id != runner_id:
                return jsonify({'error': 'Unauthorized'}), 403

            data = request.json
            log_entry = data.get('log', {})

            # Create structured log event
            log_event = {
                'type': 'log',
                'source': runner_id,
                'level': log_entry.get('level', 'INFO'),
                'message': log_entry.get('message', ''),
                'timestamp': log_entry.get('timestamp', datetime.now().isoformat())
            }

            # Add to log buffer
            with self.buffer_lock:
                self.log_buffer.append(log_event)

            # Broadcast log event to WebUI
            self.broadcast_event('log', log_event)

            return jsonify({'status': 'received'}), 200

        # Admin/WebUI endpoints
        @self.app.route('/api/dashboard', methods=['GET'])
        @self.require_admin_auth
        def get_dashboard():
            """Get dashboard statistics and data."""
            stats = self.db.get_dashboard_stats()
            runners = self.db.get_all_runners()

            # Get recent transmissions from in-memory buffer
            with self.transmission_lock:
                recent_transmissions = list(self.transmission_buffer)
                logger.debug(f"Dashboard: Returning {len(recent_transmissions)} transmissions from buffer")

                # Calculate success rate from in-memory transmissions
                if recent_transmissions:
                    successful = sum(1 for t in recent_transmissions if t.get('status') == 'success')
                    stats['success_rate'] = (successful / len(recent_transmissions)) * 100
                else:
                    stats['success_rate'] = 0

            # Parse runner devices JSON
            runners = [self._parse_runner_devices(r) for r in runners]

            return jsonify({
                'stats': stats,
                'runners': runners,
                'recent_transmissions': recent_transmissions
            }), 200

        @self.app.route('/api/logs', methods=['GET'])
        @self.require_admin_auth
        def get_logs():
            """Get recent log entries from in-memory buffer."""
            limit = request.args.get('limit', 500, type=int)

            # Get logs from buffer (thread-safe)
            with self.buffer_lock:
                # Convert deque to list and get most recent entries
                # Logs are in chronological order (oldest to newest)
                logs_list = list(self.log_buffer)

                # Return most recent logs
                recent_logs = logs_list[-limit:] if limit < len(logs_list) else logs_list

            return jsonify({
                'logs': recent_logs,
                'total': len(recent_logs)
            }), 200

        @self.app.route('/api/runners', methods=['GET'])
        @self.require_admin_auth
        def get_runners():
            """Get all registered runners."""
            runners = self.db.get_all_runners()

            # Parse devices JSON
            runners = [self._parse_runner_devices(r) for r in runners]

            return jsonify({'runners': runners}), 200

        @self.app.route('/api/runners/<runner_id>', methods=['GET'])
        @self.require_admin_auth
        def get_runner_details(runner_id):
            """Get details for a specific runner."""
            runner = self.db.get_runner(runner_id)

            if runner:
                runner = self._parse_runner_devices(runner)
                return jsonify(runner), 200
            else:
                return jsonify({'error': 'Runner not found'}), 404

        @self.app.route('/api/runners/<runner_id>', methods=['DELETE'])
        @self.require_admin_auth
        def kick_runner(runner_id):
            """Remove/kick a runner."""
            success = self.db.mark_runner_offline(runner_id)

            if success:
                self.broadcast_event('runner_status', {
                    'runner_id': runner_id,
                    'status': 'offline',
                    'timestamp': datetime.now().isoformat()
                })
                return jsonify({'status': 'removed'}), 200
            else:
                return jsonify({'error': 'Runner not found'}), 404

        @self.app.route('/api/challenges', methods=['GET'])
        @self.require_admin_auth
        def get_challenges():
            """Get all challenges."""
            challenges = self.db.get_all_challenges()
            return jsonify({'challenges': challenges}), 200

        @self.app.route('/api/challenges/<challenge_id>', methods=['GET'])
        @self.require_admin_auth
        def get_challenge_details(challenge_id):
            """Get challenge details."""
            challenge = self.db.get_challenge(challenge_id)

            if challenge:
                return jsonify(challenge), 200
            else:
                return jsonify({'error': 'Challenge not found'}), 404

        @self.app.route('/api/challenges/<challenge_id>', methods=['PUT'])
        @self.require_admin_auth
        def update_challenge(challenge_id):
            """Update challenge configuration."""
            data = request.json

            # Validate request body
            if not data:
                return jsonify({'error': 'Missing request body'}), 400

            # Validate config field
            config = data.get('config')
            if config is None:
                return jsonify({'error': 'Missing required field: config'}), 400

            if not isinstance(config, dict):
                return jsonify({'error': 'Field "config" must be a dictionary'}), 400

            success = self.db.update_challenge(challenge_id, config)

            if success:
                return jsonify({'status': 'updated'}), 200
            else:
                return jsonify({'error': 'Challenge not found'}), 404

        @self.app.route('/api/challenges/<challenge_id>/enable', methods=['POST'])
        @self.require_admin_auth
        def enable_challenge(challenge_id):
            """Enable or disable a challenge."""
            data = request.json
            enabled = data.get('enabled', True)

            logger.info(f"Setting challenge {challenge_id} enabled={enabled}")
            success = self.db.enable_challenge(challenge_id, enabled)

            if success:
                logger.info(f"Challenge {challenge_id} {'enabled' if enabled else 'disabled'} successfully")
                return jsonify({'status': 'updated'}), 200
            else:
                return jsonify({'error': 'Challenge not found'}), 404

        @self.app.route('/api/challenges/<challenge_id>/trigger', methods=['POST'])
        @self.require_admin_auth
        def trigger_challenge(challenge_id):
            """Manually trigger a challenge to transmit immediately."""
            challenge = self.db.get_challenge(challenge_id)

            if challenge:
                # Clear timing so it's immediately available
                with self.db.timing_lock:
                    if challenge_id in self.db.challenge_timing:
                        self.db.challenge_timing[challenge_id]['next_tx'] = datetime.now()

                # Update status to queued
                with self.db.get_connection() as conn:
                    conn.execute('''
                        UPDATE challenges
                        SET status = 'queued'
                        WHERE challenge_id = ?
                    ''', (challenge_id,))
                    conn.commit()

                return jsonify({'status': 'triggered'}), 200
            else:
                return jsonify({'error': 'Challenge not found'}), 404

        @self.app.route('/api/challenges/reload', methods=['POST'])
        @self.require_admin_auth
        def reload_challenges():
            """Reload challenges from configuration file."""
            try:
                config = self.load_config(self.config_path)
                challenges_config = config.get('challenges', [])

                added = 0
                for challenge in challenges_config:
                    if isinstance(challenge, dict) and 'name' in challenge:
                        challenge_id = str(uuid.uuid4())
                        if self.db.add_challenge(challenge_id, challenge['name'], challenge):
                            added += 1

                return jsonify({
                    'status': 'reloaded',
                    'added': added
                }), 200
            except Exception as e:
                logger.error(f"Error reloading challenges: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/transmissions', methods=['GET'])
        @self.require_admin_auth
        def get_transmissions():
            """Get transmission history."""
            limit = request.args.get('limit', 50, type=int)
            transmissions = self.db.get_recent_transmissions(limit=limit)
            return jsonify({'transmissions': transmissions}), 200

        @self.app.route('/api/control/pause', methods=['POST'])
        @self.require_admin_auth
        def pause_system():
            """Pause all transmissions."""
            self.db.set_system_state('paused', 'true')

            self.broadcast_event('system_control', {
                'action': 'pause',
                'timestamp': datetime.now().isoformat()
            })

            return jsonify({'status': 'paused'}), 200

        @self.app.route('/api/control/resume', methods=['POST'])
        @self.require_admin_auth
        def resume_system():
            """Resume transmissions."""
            self.db.set_system_state('paused', 'false')

            self.broadcast_event('system_control', {
                'action': 'resume',
                'timestamp': datetime.now().isoformat()
            })

            return jsonify({'status': 'resumed'}), 200

        @self.app.route('/api/control/stop', methods=['POST'])
        @self.require_admin_auth
        def stop_system():
            """Stop all operations."""
            self.db.set_system_state('paused', 'true')

            # Requeue all assigned challenges
            with self.db.get_connection() as conn:
                conn.execute('''
                    UPDATE challenges
                    SET status = 'queued',
                        assigned_to = NULL,
                        assigned_at = NULL,
                        assignment_expires = NULL
                    WHERE status = 'assigned'
                ''')
                conn.commit()

            self.broadcast_event('system_control', {
                'action': 'stop',
                'timestamp': datetime.now().isoformat()
            })

            return jsonify({'status': 'stopped'}), 200

        # File management
        @self.app.route('/api/files/<file_hash>', methods=['GET'])
        @self.require_api_key
        def download_file(file_hash):
            """Download a challenge file."""
            file_info = self.db.get_file(file_hash)

            if file_info and os.path.exists(file_info['file_path']):
                return send_file(
                    file_info['file_path'],
                    mimetype=file_info['mime_type'],
                    as_attachment=True,
                    download_name=file_info['filename']
                )
            else:
                return jsonify({'error': 'File not found'}), 404

        @self.app.route('/api/files/upload', methods=['POST'])
        @self.require_api_key
        def upload_file():
            """Upload a new challenge file."""
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400

            file = request.files['file']

            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400

            try:
                # Read file data
                file_data = file.read()

                # Calculate SHA-256 hash
                file_hash = hashlib.sha256(file_data).hexdigest()

                # Save file
                file_path = os.path.join(self.files_dir, file_hash)
                with open(file_path, 'wb') as f:
                    f.write(file_data)

                # Register in database
                self.db.add_file(
                    file_hash=file_hash,
                    filename=file.filename,
                    size=len(file_data),
                    mime_type=file.content_type or 'application/octet-stream',
                    file_path=file_path
                )

                return jsonify({
                    'status': 'uploaded',
                    'file_hash': file_hash,
                    'filename': file.filename,
                    'size': len(file_data)
                }), 200

            except Exception as e:
                logger.error(f"Error uploading file: {e}")
                return jsonify({'error': str(e)}), 500

        # Serve WebUI (Vue.js SPA)
        # This must be the LAST route to catch all non-API requests
        @self.app.route('/')
        @self.app.route('/<path:path>')
        def serve_frontend(path=''):
            """Serve the Vue.js frontend SPA.

            For SPA routing to work, we serve index.html for all non-file requests.
            Vue Router handles the client-side routing.
            """
            # Check if frontend is built
            if not os.path.exists(self.frontend_dir):
                return jsonify({
                    'message': 'Frontend not built. Run `cd frontend && npm run build`'
                }), 404

            # If path is empty or '/', serve index.html
            if not path or path == '/':
                return send_from_directory(self.frontend_dir, 'index.html')

            # Check if the requested path is an actual file (like CSS, JS, images)
            file_path = os.path.join(self.frontend_dir, path)
            if os.path.isfile(file_path):
                return send_from_directory(self.frontend_dir, path)

            # For all other paths (like /public, /runners, etc.), serve index.html
            # This allows Vue Router to handle the routing
            return send_from_directory(self.frontend_dir, 'index.html')

    def register_socketio_handlers(self):
        """Register WebSocket event handlers."""

        @self.socketio.on('connect')
        def handle_connect():
            logger.info(f"WebSocket client connected: {request.sid}")

            # Send initial state
            stats = self.db.get_dashboard_stats()
            emit('initial_state', {
                'stats': stats,
                'timestamp': datetime.now().isoformat()
            })

        @self.socketio.on('disconnect')
        def handle_disconnect():
            logger.info(f"WebSocket client disconnected: {request.sid}")

    def broadcast_event(self, event_type: str, data: Dict[str, Any]):
        """Broadcast an event to all connected WebSocket clients."""
        try:
            self.socketio.emit('event', {
                'type': event_type,
                **data
            })
        except Exception as e:
            logger.error(f"Error broadcasting event: {e}")

    def run(self, host='0.0.0.0', port=8443, debug=False):
        """Run the API server.

        For production with HTTPS/TLS, use nginx or another reverse proxy
        for TLS termination (see DEPLOYMENT.md).
        """
        logger.info(f"Starting ChallengeCtl API server on http://{host}:{port}")
        logger.info("For production with HTTPS, use nginx reverse proxy")

        # Start server
        self.socketio.run(
            self.app,
            host=host,
            port=port,
            debug=debug,
            allow_unsafe_werkzeug=True
        )


def create_app(config_path='server-config.yml', db_path='challengectl.db', files_dir='files'):
    """Factory function to create the Flask app."""
    db = Database(db_path)
    api = ChallengeCtlAPI(config_path, db, files_dir)
    return api.app, api.socketio
