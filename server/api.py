#!/usr/bin/env python3
"""
REST API server for challengectl using Flask and Flask-SocketIO.
Handles runner communication, challenge distribution, and WebUI serving.
"""

from flask import Flask, request, jsonify, send_file, send_from_directory, make_response
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from functools import wraps
import logging
import os
import hashlib
import yaml
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
import uuid
from collections import deque
import threading
import secrets
import bcrypt
import pyotp

from database import Database
from crypto import encrypt_totp_secret

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
                'timestamp': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
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
        # Configuration
        self.config_path = config_path
        self.config = self.load_config(config_path)
        self.api_keys = self.config.get('server', {}).get('api_keys', {})
        self.files_dir = files_dir

        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = os.urandom(24)

        # Store frontend directory path
        self.frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend/dist'))

        # Enable CORS with restricted origins (SECURITY: prevents CSRF attacks)
        # Allow only configured origins when using credentials
        # Configuration priority: 1) config file, 2) environment variable, 3) localhost defaults
        allowed_origins = self.config.get('server', {}).get('cors_origins')

        # Fallback to environment variable if not in config
        if not allowed_origins:
            cors_origins_env = os.environ.get('CHALLENGECTL_CORS_ORIGINS')
            if cors_origins_env:
                allowed_origins = [origin.strip() for origin in cors_origins_env.split(',')]

        # Fallback to localhost defaults for development
        if not allowed_origins:
            allowed_origins = [
                'http://localhost:5173',  # Vite dev server
                'http://localhost:5000',  # Flask dev server
                'http://127.0.0.1:5173',
                'http://127.0.0.1:5000'
            ]
            logger.warning("No CORS origins configured. Using localhost defaults for development only!")

        logger.info(f"CORS allowed origins: {allowed_origins}")

        CORS(
            self.app,
            supports_credentials=True,
            origins=allowed_origins,
            allow_headers=['Content-Type', 'X-CSRF-Token'],  # Allow CSRF token header
            methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
        )

        # Initialize SocketIO for real-time updates
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")

        # Initialize rate limiter for authentication endpoints
        # Note: No default limits - only specific endpoints (login, TOTP) are rate-limited
        # to prevent brute force attacks. Runner endpoints need high frequency access.
        self.limiter = Limiter(
            app=self.app,
            key_func=get_remote_address,
            default_limits=[],  # No default limits
            storage_uri="memory://",
            strategy="fixed-window"
        )

        # Use provided database instance
        self.db = db

        # # Configuration
        # self.config_path = config_path
        # self.config = self.load_config(config_path)
        # self.api_keys = self.config.get('server', {}).get('api_keys', {})
        # self.files_dir = files_dir

        # In-memory log buffer for recent logs (last 500)
        self.log_buffer = deque(maxlen=500)
        self.buffer_lock = threading.Lock()

        # In-memory transmission buffer for recent transmissions (last 50)
        self.transmission_buffer = deque(maxlen=50)
        self.transmission_lock = threading.Lock()

        # Note: Sessions are now stored persistently in the database (sessions table)
        # This allows sessions to survive server restarts

        # In-memory TOTP code tracking for replay protection
        # Format: {(username, totp_code): timestamp}
        self.used_totp_codes = {}
        self.totp_codes_lock = threading.Lock()

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
        ws_handler.setLevel(logging.DEBUG)  # Forward all log levels, filtering happens in UI
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

    def get_conference_name(self) -> str:
        """Get the conference name from config."""
        return self.config.get('conference', {}).get('name', 'ChallengeCtl')

    def check_config_sync(self) -> Dict:
        """Check if database challenges are in sync with config file.

        Returns:
            Dict with 'in_sync' boolean and details about differences
        """
        try:
            # Load challenges from config
            config_challenges = {}
            for challenge in self.config.get('challenges', []):
                if isinstance(challenge, dict) and 'name' in challenge:
                    config_challenges[challenge['name']] = challenge

            # Get challenges from database
            db_challenges = {c['name']: c for c in self.db.get_all_challenges()}

            # Find differences
            new_in_config = set(config_challenges.keys()) - set(db_challenges.keys())
            removed_from_config = set(db_challenges.keys()) - set(config_challenges.keys())

            # Check for updated challenges (same name but different config)
            updated = []
            for name in set(config_challenges.keys()) & set(db_challenges.keys()):
                if config_challenges[name] != db_challenges[name]['config']:
                    updated.append(name)

            in_sync = not (new_in_config or removed_from_config or updated)

            return {
                'in_sync': in_sync,
                'new': sorted(new_in_config),
                'removed': sorted(removed_from_config),
                'updated': sorted(updated),
                'total_config': len(config_challenges),
                'total_db': len(db_challenges)
            }
        except Exception as e:
            logger.error(f"Error checking config sync: {e}")
            return {'in_sync': None, 'error': str(e)}

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

    def generate_csrf_token(self) -> str:
        """Generate a random CSRF token."""
        return secrets.token_urlsafe(32)

    def require_csrf(self, f):
        """Decorator to require CSRF token validation for state-changing operations."""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Skip CSRF check for GET, HEAD, OPTIONS (safe methods)
            if request.method in ['GET', 'HEAD', 'OPTIONS']:
                return f(*args, **kwargs)

            # Get CSRF token from header
            csrf_header = request.headers.get('X-CSRF-Token')
            # Get CSRF token from cookie
            csrf_cookie = request.cookies.get('csrf_token')

            # Both must be present and match
            if not csrf_header or not csrf_cookie:
                logger.warning(f"CSRF token missing from {request.remote_addr} for {request.path}")
                return jsonify({'error': 'CSRF token missing'}), 403

            if csrf_header != csrf_cookie:
                logger.warning(f"CSRF token mismatch from {request.remote_addr} for {request.path}")
                return jsonify({'error': 'CSRF token invalid'}), 403

            return f(*args, **kwargs)

        return decorated_function

    def require_admin_auth(self, f):
        """Decorator to require admin session authentication."""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get session token from httpOnly cookie (more secure than localStorage)
            session_token = request.cookies.get('session_token')

            if not session_token:
                return jsonify({'error': 'Missing or invalid session'}), 401

            # Check session validity (from database)
            session = self.db.get_session(session_token)

            if not session:
                return jsonify({'error': 'Invalid or expired session'}), 401

            # Check if session is expired
            # Note: expires is stored as ISO format string in database
            expires = datetime.fromisoformat(session['expires'])
            if datetime.now() > expires:
                self.db.delete_session(session_token)
                return jsonify({'error': 'Session expired'}), 401

            # Check if TOTP was verified
            if not session.get('totp_verified', False):
                return jsonify({'error': 'TOTP verification required'}), 401

            # Add username to request context
            request.admin_username = session['username']

            return f(*args, **kwargs)

        return decorated_function

    def create_session(self, username: str, totp_verified: bool = False) -> str:
        """Create a new session token for a user (stored in database)."""
        session_token = secrets.token_urlsafe(32)
        expires = datetime.now() + timedelta(hours=24)

        # Store session in database instead of memory
        self.db.create_session(
            session_token=session_token,
            username=username,
            expires=expires.isoformat(),
            totp_verified=totp_verified
        )

        return session_token

    def update_session_totp(self, session_token: str) -> bool:
        """Mark session as TOTP verified (in database)."""
        return self.db.update_session_totp(session_token)

    def destroy_session(self, session_token: str) -> bool:
        """Destroy a session (from database)."""
        return self.db.delete_session(session_token)

    def cleanup_expired_sessions(self):
        """Remove expired sessions from database (called periodically)."""
        count = self.db.cleanup_expired_sessions()
        if count > 0:
            logger.info(f"Cleaned up {count} expired session(s)")

    def invalidate_user_sessions(self, username: str, except_token: Optional[str] = None) -> int:
        """
        Invalidate all sessions for a specific user (in database).

        Args:
            username: The username whose sessions should be invalidated
            except_token: Optional session token to exclude from invalidation (e.g., current session)

        Returns:
            Number of sessions invalidated
        """
        return self.db.delete_user_sessions(username, except_token)

    def is_totp_code_used(self, username: str, totp_code: str) -> bool:
        """
        Check if a TOTP code has already been used (in-memory tracking).

        Args:
            username: The username
            totp_code: The TOTP code to check

        Returns:
            True if code was already used, False otherwise
        """
        with self.totp_codes_lock:
            key = (username, totp_code)
            return key in self.used_totp_codes

    def mark_totp_code_used(self, username: str, totp_code: str) -> bool:
        """
        Mark a TOTP code as used (in-memory tracking).

        Args:
            username: The username
            totp_code: The TOTP code to mark as used

        Returns:
            True if successfully marked, False if already used
        """
        with self.totp_codes_lock:
            key = (username, totp_code)
            if key in self.used_totp_codes:
                return False
            self.used_totp_codes[key] = datetime.now()
            return True

    def cleanup_expired_totp_codes(self):
        """
        Remove expired TOTP codes from in-memory tracking.
        TOTP codes are valid for 30 seconds with a window of ±1 period (90 seconds total).
        This is called periodically by the background scheduler.
        """
        with self.totp_codes_lock:
            # Remove codes older than 2 minutes (well beyond the 90 second validity window)
            threshold = datetime.now() - timedelta(seconds=120)
            expired_keys = [key for key, timestamp in self.used_totp_codes.items() if timestamp < threshold]

            for key in expired_keys:
                del self.used_totp_codes[key]

            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired TOTP code(s) from memory")

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
        @self.limiter.limit("5 per 15 minutes")
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

            # Always perform bcrypt check to prevent timing attacks that reveal user existence
            # Use a dummy hash if user doesn't exist to maintain constant time
            if user:
                password_hash = user['password_hash']
            else:
                # Dummy hash to compare against (prevents timing attack on user enumeration)
                # This ensures bcrypt work is done even for non-existent users
                password_hash = '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYuZx3U6jpe'

            # Verify password (always runs regardless of user existence)
            try:
                password_valid = bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
            except Exception as e:
                logger.error(f"Password verification error: {e}")
                return jsonify({'error': 'Invalid credentials'}), 401

            # Check authentication after constant-time operations complete
            # Return generic error for: user not found, wrong password, OR disabled account
            # This prevents username enumeration
            if not user or not password_valid or not user.get('enabled'):
                # Log failed login attempt for security monitoring
                reason = 'user_not_found' if not user else ('wrong_password' if not password_valid else 'account_disabled')
                logger.warning(
                    f"SECURITY: Failed login attempt - username='{username}' ip={request.remote_addr} "
                    f"reason={reason} user_agent='{request.headers.get('User-Agent', 'unknown')}'"
                )
                return jsonify({'error': 'Invalid credentials'}), 401

            # Check if user has TOTP configured
            totp_secret = user.get('totp_secret')
            has_totp = totp_secret is not None and totp_secret != ''

            if has_totp:
                # Create session (not yet TOTP verified)
                session_token = self.create_session(username, totp_verified=False)

                # Generate CSRF token for this session
                csrf_token = self.generate_csrf_token()

                # Set httpOnly cookie for security (prevents XSS attacks)
                response = make_response(jsonify({
                    'totp_required': True,
                    'username': username
                }), 200)

                # Set secure httpOnly cookie for session token
                # NOTE: Using samesite=None to allow WebSocket connections
                # In production, set secure=True when using HTTPS
                response.set_cookie(
                    'session_token',
                    session_token,
                    httponly=True,  # Prevents JavaScript access (XSS protection)
                    secure=False,   # Set to True in production with HTTPS
                    samesite=None,  # Allow WebSocket connections (was 'Lax')
                    max_age=86400   # 24 hours (matches session expiry)
                )

                # Set CSRF token cookie (NOT httpOnly - JavaScript needs to read it)
                response.set_cookie(
                    'csrf_token',
                    csrf_token,
                    httponly=False,  # JavaScript can read to send in header
                    secure=False,    # Set to True in production with HTTPS
                    samesite=None,   # Match session cookie setting
                    max_age=86400    # 24 hours
                )

                # Log successful password verification
                logger.info(
                    f"SECURITY: Password verified - username='{username}' ip={request.remote_addr} "
                    f"totp_required=true user_agent='{request.headers.get('User-Agent', 'unknown')}'"
                )

                return response
            else:
                # No TOTP configured - complete login immediately
                session_token = self.create_session(username, totp_verified=True)

                # Generate CSRF token for this session
                csrf_token = self.generate_csrf_token()

                # Update last login timestamp
                self.db.update_last_login(username)

                # Check if initial setup is required
                initial_setup_required = self.db.get_system_state('initial_setup_required', 'false') == 'true'

                # Log successful login
                logger.info(
                    f"SECURITY: Successful login - username='{username}' ip={request.remote_addr} "
                    f"totp_required=false user_agent='{request.headers.get('User-Agent', 'unknown')}'"
                )

                # Set httpOnly cookie for security (prevents XSS attacks)
                response = make_response(jsonify({
                    'status': 'authenticated',
                    'totp_required': False,
                    'initial_setup_required': initial_setup_required,
                    'username': username
                }), 200)

                # Set secure httpOnly cookie for session token
                # NOTE: Using samesite=None to allow WebSocket connections
                # In production, set secure=True when using HTTPS
                response.set_cookie(
                    'session_token',
                    session_token,
                    httponly=True,  # Prevents JavaScript access (XSS protection)
                    secure=False,   # Set to True in production with HTTPS
                    samesite=None,  # Allow WebSocket connections (was 'Lax')
                    max_age=86400   # 24 hours (matches session expiry)
                )

                # Set CSRF token cookie (NOT httpOnly - JavaScript needs to read it)
                response.set_cookie(
                    'csrf_token',
                    csrf_token,
                    httponly=False,  # JavaScript can read to send in header
                    secure=False,    # Set to True in production with HTTPS
                    samesite=None,   # Match session cookie setting
                    max_age=86400    # 24 hours
                )

                return response

        @self.app.route('/api/auth/verify-totp', methods=['POST'])
        @self.limiter.limit("5 per 15 minutes")
        def verify_totp():
            """Verify TOTP code and fully authenticate the session."""
            data = request.json

            if not data:
                return jsonify({'error': 'Missing request body'}), 400

            # Get session token from httpOnly cookie (set during login)
            session_token = request.cookies.get('session_token')
            totp_code = data.get('totp_code')

            if not session_token or not totp_code:
                return jsonify({'error': 'Missing session or totp_code'}), 400

            # Get session from database
            session = self.db.get_session(session_token)

            if not session:
                return jsonify({'error': 'Invalid or expired session'}), 401

            # Check if session is expired
            expires = datetime.fromisoformat(session['expires'])
            if datetime.now() > expires:
                self.db.delete_session(session_token)
                return jsonify({'error': 'Session expired'}), 401

            username = session['username']

            # Get user's TOTP secret
            user = self.db.get_user(username)

            if not user:
                return jsonify({'error': 'Invalid session'}), 401

            totp_secret = user.get('totp_secret')

            if not totp_secret:
                return jsonify({'error': 'Invalid session'}), 401

            # Check if TOTP code was already used (replay protection)
            if self.is_totp_code_used(username, totp_code):
                logger.warning(
                    f"SECURITY: TOTP replay attempt - username='{username}' ip={request.remote_addr} "
                    f"code={totp_code[:2]}** user_agent='{request.headers.get('User-Agent', 'unknown')}'"
                )
                return jsonify({'error': 'Invalid TOTP code'}), 401

            # Verify TOTP code
            try:
                totp = pyotp.TOTP(totp_secret)
                if not totp.verify(totp_code, valid_window=1):
                    # Log failed TOTP verification
                    logger.warning(
                        f"SECURITY: Failed TOTP verification - username='{username}' ip={request.remote_addr} "
                        f"code={totp_code[:2]}** user_agent='{request.headers.get('User-Agent', 'unknown')}'"
                    )
                    return jsonify({'error': 'Invalid TOTP code'}), 401

                # Mark code as used (only after successful verification)
                if not self.mark_totp_code_used(username, totp_code):
                    # This shouldn't happen due to the check above, but handle it anyway
                    logger.warning(
                        f"SECURITY: TOTP code reuse detected - username='{username}' ip={request.remote_addr} "
                        f"code={totp_code[:2]}** user_agent='{request.headers.get('User-Agent', 'unknown')}'"
                    )
                    return jsonify({'error': 'Invalid TOTP code'}), 401

            except Exception as e:
                logger.error(f"TOTP verification error: {e}")
                return jsonify({'error': 'TOTP verification failed'}), 500

            # Mark session as TOTP verified
            if not self.update_session_totp(session_token):
                return jsonify({'error': 'Failed to update session'}), 500

            # Update last login timestamp
            self.db.update_last_login(username)

            # Log successful TOTP verification and login
            logger.info(
                f"SECURITY: Successful TOTP verification - username='{username}' ip={request.remote_addr} "
                f"code={totp_code[:2]}** user_agent='{request.headers.get('User-Agent', 'unknown')}'"
            )

            # Check if password change is required
            password_change_required = user.get('password_change_required', False)

            # Session token already in httpOnly cookie (set during login)
            # No need to return it in response (security: prevents XSS)
            return jsonify({
                'status': 'authenticated',
                'password_change_required': bool(password_change_required),
                'username': username
            }), 200

        @self.app.route('/api/auth/session', methods=['GET'])
        def check_session():
            """Check if current session is valid (for page refresh and router guards)."""
            # Get session token from httpOnly cookie
            session_token = request.cookies.get('session_token')

            if not session_token:
                return jsonify({'authenticated': False, 'error': 'No session token'}), 401

            # Check session validity (from database)
            session = self.db.get_session(session_token)

            if not session:
                return jsonify({'authenticated': False, 'error': 'Invalid session'}), 401

            # Check if session is expired
            expires = datetime.fromisoformat(session['expires'])
            if datetime.now() > expires:
                self.db.delete_session(session_token)
                return jsonify({'authenticated': False, 'error': 'Session expired'}), 401

            # Check if TOTP was verified (required for full authentication)
            if not session.get('totp_verified', False):
                return jsonify({'authenticated': False, 'error': 'TOTP verification required'}), 401

            # Session is valid
            username = session['username']
            user = self.db.get_user(username)

            if not user or not user.get('enabled'):
                return jsonify({'authenticated': False, 'error': 'Account disabled'}), 401

            return jsonify({
                'authenticated': True,
                'username': username
            }), 200

        @self.app.route('/api/auth/logout', methods=['POST'])
        @self.require_csrf
        def logout():
            """Logout and destroy session."""
            # Get session token from httpOnly cookie
            session_token = request.cookies.get('session_token')

            if session_token:
                self.destroy_session(session_token)

            # Clear both session and CSRF cookies
            # NOTE: Cookie attributes must match exactly how they were set during login
            # Otherwise browsers won't delete them
            response = make_response(jsonify({'status': 'logged out'}), 200)
            response.set_cookie(
                'session_token',
                '',
                httponly=True,
                secure=False,    # Must match login cookie setting
                samesite=None,
                max_age=0        # Use max_age=0 to delete cookie (matches login style)
            )
            response.set_cookie(
                'csrf_token',
                '',
                httponly=False,
                secure=False,    # Must match login cookie setting
                samesite=None,
                max_age=0        # Use max_age=0 to delete cookie (matches login style)
            )

            return response

        @self.app.route('/api/auth/change-password', methods=['POST'])
        @self.require_admin_auth
        @self.require_csrf
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

            # Invalidate all other sessions except the current one (for security)
            auth_header = request.headers.get('Authorization')
            current_token = auth_header[7:] if auth_header and auth_header.startswith('Bearer ') else None
            invalidated_count = self.invalidate_user_sessions(username, except_token=current_token)

            logger.info(f"User {username} changed their password (invalidated {invalidated_count} other session(s))")

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
        @self.require_csrf
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
            conference_name = self.get_conference_name()
            provisioning_uri = totp.provisioning_uri(name=username, issuer_name=conference_name)

            logger.info(f"User {username} created by {request.admin_username}")

            return jsonify({
                'status': 'created',
                'username': username,
                'totp_secret': totp_secret,
                'provisioning_uri': provisioning_uri
            }), 201

        @self.app.route('/api/users/<username>', methods=['PUT'])
        @self.require_admin_auth
        @self.require_csrf
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
        @self.require_csrf
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
        @self.require_csrf
        def reset_user_totp(username):
            """Reset TOTP secret for a user."""
            # Check user exists
            user = self.db.get_user(username)
            if not user:
                return jsonify({'error': 'User not found'}), 404

            # Generate new TOTP secret
            totp_secret = pyotp.random_base32()

            # Encrypt TOTP secret before storing
            encrypted_totp_secret = encrypt_totp_secret(totp_secret)

            # Update user
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users
                    SET totp_secret = ?
                    WHERE username = ?
                ''', (encrypted_totp_secret, username))
                conn.commit()

            # Generate TOTP provisioning URI
            totp = pyotp.TOTP(totp_secret)
            conference_name = self.get_conference_name()
            provisioning_uri = totp.provisioning_uri(name=username, issuer_name=conference_name)

            logger.info(f"TOTP reset for user {username} by {request.admin_username}")

            return jsonify({
                'status': 'totp_reset',
                'totp_secret': totp_secret,
                'provisioning_uri': provisioning_uri
            }), 200

        @self.app.route('/api/users/<username>/reset-password', methods=['POST'])
        @self.require_admin_auth
        @self.require_csrf
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

            # Invalidate ALL sessions for this user (security: admin-initiated password reset)
            invalidated_count = self.invalidate_user_sessions(username)

            logger.info(f"Password reset for user {username} by {request.admin_username} (invalidated {invalidated_count} session(s))")

            return jsonify({'status': 'password_reset'}), 200

        # Public dashboard endpoint (no auth required)
        @self.app.route('/api/public/challenges', methods=['GET'])
        def get_public_challenges():
            """Get public view of enabled challenges with configurable visibility."""
            try:
                public_challenges = self.get_public_challenges_data()

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
                    'timestamp': datetime.now(timezone.utc).isoformat()
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

            success, previous_status = self.db.update_heartbeat(runner_id)

            if success:
                # Always broadcast heartbeat to update last_heartbeat timestamp in UI
                heartbeat_time = datetime.now(timezone.utc).isoformat()
                self.broadcast_event('runner_status', {
                    'runner_id': runner_id,
                    'status': 'online',
                    'last_heartbeat': heartbeat_time,
                    'timestamp': heartbeat_time
                })

                return jsonify({'status': 'ok'}), 200
            else:
                return jsonify({'error': 'Runner not found'}), 404

        @self.app.route('/api/runners/<runner_id>/signout', methods=['POST'])
        @self.require_api_key
        def signout(runner_id):
            """Runner graceful signout."""
            if request.runner_id != runner_id:
                return jsonify({'error': 'Unauthorized'}), 403

            # Mark runner as offline
            success = self.db.mark_runner_offline(runner_id)

            if success:
                # Broadcast offline status
                self.broadcast_event('runner_status', {
                    'runner_id': runner_id,
                    'status': 'offline',
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
                logger.info(f"Runner {runner_id} signed out gracefully")
                return jsonify({'status': 'signed_out'}), 200
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
                logger.debug(f"Added transmission to buffer. Buffer size: {len(self.transmission_buffer)}")

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

            # Broadcast updated public challenges to public dashboard
            self.broadcast_public_challenges()

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
                'timestamp': log_entry.get('timestamp', datetime.now(timezone.utc).isoformat())
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
        @self.require_csrf
        def kick_runner(runner_id):
            """Remove/kick a runner."""
            success = self.db.mark_runner_offline(runner_id)

            if success:
                self.broadcast_event('runner_status', {
                    'runner_id': runner_id,
                    'status': 'offline',
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
                return jsonify({'status': 'removed'}), 200
            else:
                return jsonify({'error': 'Runner not found'}), 404

        @self.app.route('/api/runners/<runner_id>/enable', methods=['POST'])
        @self.require_admin_auth
        @self.require_csrf
        def enable_runner(runner_id):
            """Enable a runner to receive task assignments."""
            success = self.db.enable_runner(runner_id)

            if success:
                self.broadcast_event('runner_enabled', {
                    'runner_id': runner_id,
                    'enabled': True,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
                return jsonify({'status': 'enabled'}), 200
            else:
                return jsonify({'error': 'Runner not found'}), 404

        @self.app.route('/api/runners/<runner_id>/disable', methods=['POST'])
        @self.require_admin_auth
        @self.require_csrf
        def disable_runner(runner_id):
            """Disable a runner from receiving task assignments."""
            success = self.db.disable_runner(runner_id)

            if success:
                self.broadcast_event('runner_enabled', {
                    'runner_id': runner_id,
                    'enabled': False,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
                return jsonify({'status': 'disabled'}), 200
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
        @self.require_csrf
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
        @self.require_csrf
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
        @self.require_csrf
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
        @self.require_csrf
        def reload_challenges():
            """Reload challenges from configuration file."""
            try:
                config = self.load_config(self.config_path)
                challenges_config = config.get('challenges', [])

                # Get existing challenges by name
                existing_challenges = {c['name']: c for c in self.db.get_all_challenges()}

                added = 0
                updated = 0
                for challenge in challenges_config:
                    if isinstance(challenge, dict) and 'name' in challenge:
                        name = challenge['name']

                        if name in existing_challenges:
                            # Update existing challenge
                            challenge_id = existing_challenges[name]['challenge_id']
                            if self.db.update_challenge(challenge_id, challenge):
                                updated += 1
                                logger.info(f"Updated challenge: {name}")
                        else:
                            # Add new challenge
                            challenge_id = str(uuid.uuid4())
                            if self.db.add_challenge(challenge_id, name, challenge):
                                added += 1

                # Broadcast updated challenges to public dashboard
                self.broadcast_public_challenges()

                return jsonify({
                    'status': 'reloaded',
                    'added': added,
                    'updated': updated
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
        @self.require_csrf
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
        @self.require_csrf
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
        @self.require_csrf
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
            """Handle WebSocket connection with authentication validation."""
            # Validate session authentication before allowing WebSocket connection
            session_token = request.cookies.get('session_token')

            # Debug logging to help diagnose cookie issues
            logger.debug(f"WebSocket connection attempt from {request.remote_addr}")
            logger.debug(f"Cookies received: {list(request.cookies.keys())}")

            if not session_token:
                logger.warning(f"WebSocket connection rejected: No session token from {request.remote_addr} (cookies: {list(request.cookies.keys())})")
                return False  # Reject connection

            # Validate session
            session = self.db.get_session(session_token)

            if not session:
                logger.warning(f"WebSocket connection rejected: Invalid session token from {request.remote_addr}")
                return False  # Reject connection

            # Check if session is expired
            expires = datetime.fromisoformat(session['expires'])
            if datetime.now() > expires:
                self.db.delete_session(session_token)
                logger.warning(f"WebSocket connection rejected: Expired session from {request.remote_addr}")
                return False  # Reject connection

            # Check if TOTP was verified (full authentication required)
            totp_verified = session.get('totp_verified', False)
            logger.debug(f"Session totp_verified value: {totp_verified} (type: {type(totp_verified)})")
            if not totp_verified:
                logger.warning(f"WebSocket connection rejected: TOTP not verified (value={totp_verified}) from {request.remote_addr}")
                return False  # Reject connection

            # Authentication successful
            username = session['username']
            logger.info(f"WebSocket client connected: {request.sid} (user: {username})")

            # Send initial state to authenticated client
            stats = self.db.get_dashboard_stats()
            emit('initial_state', {
                'stats': stats,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })

        @self.socketio.on('disconnect')
        def handle_disconnect():
            logger.info(f"WebSocket client disconnected: {request.sid}")

        # Public namespace - no authentication required
        @self.socketio.on('connect', namespace='/public')
        def handle_public_connect():
            """Handle public WebSocket connection (no authentication required)."""
            logger.info(f"Public WebSocket client connected: {request.sid} from {request.remote_addr}")

            # Send initial public challenge data
            try:
                challenges = self.get_public_challenges_data()
                emit('challenges_update', {
                    'challenges': challenges,
                    'timestamp': datetime.now().isoformat()
                }, namespace='/public')
            except Exception as e:
                logger.error(f"Error sending initial public challenges: {e}")

        @self.socketio.on('disconnect', namespace='/public')
        def handle_public_disconnect():
            logger.info(f"Public WebSocket client disconnected: {request.sid}")

    def broadcast_event(self, event_type: str, data: Dict[str, Any]):
        """Broadcast an event to all connected WebSocket clients."""
        try:
            self.socketio.emit('event', {
                'type': event_type,
                **data
            })
        except Exception as e:
            logger.error(f"Error broadcasting event: {e}")

    def get_public_challenges_data(self):
        """Build public challenges data with configurable visibility."""
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
            }

            # Conditionally add fields based on public view settings
            public_view = config.get('public_view', {})

            # Show modulation if enabled (default: True)
            if public_view.get('show_modulation', True):
                public_challenge['modulation'] = config.get('modulation', 'unknown')

            # Show frequency if enabled (default: True)
            if public_view.get('show_frequency', True):
                frequency = config.get('frequency')
                if frequency:
                    # Format frequency in MHz for readability
                    freq_mhz = frequency / 1_000_000
                    public_challenge['frequency'] = frequency
                    public_challenge['frequency_display'] = f"{freq_mhz:.3f} MHz"

            # Show last transmission time if enabled (default: True)
            if public_view.get('show_last_tx_time', True):
                # Always include the field if it should be shown (even if null)
                # This allows frontend to distinguish between "never" and "hidden"
                public_challenge['last_tx_time'] = challenge.get('last_tx_time')

            # Show active status if enabled (default: True)
            if public_view.get('show_active_status', True):
                # Check if currently assigned (actively transmitting)
                is_active = (challenge.get('status') == 'assigned' and
                             challenge.get('assigned_to') is not None)
                public_challenge['is_active'] = is_active

            public_challenges.append(public_challenge)

        # Sort by name
        public_challenges.sort(key=lambda x: x['name'])
        return public_challenges

    def broadcast_public_challenges(self):
        """Broadcast updated public challenge data to all public WebSocket clients."""
        try:
            challenges = self.get_public_challenges_data()
            self.socketio.emit('challenges_update', {
                'challenges': challenges,
                'timestamp': datetime.now().isoformat()
            }, namespace='/public')
        except Exception as e:
            logger.error(f"Error broadcasting public challenges: {e}")

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
