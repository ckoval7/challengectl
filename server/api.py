#!/usr/bin/env python3
"""
REST API server for challengectl using Flask and Flask-SocketIO.
Handles runner communication, challenge distribution, and WebUI serving.
"""

from flask import Flask, request, jsonify, send_file, send_from_directory, make_response
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from werkzeug.security import safe_join
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
import random

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

    # File upload security restrictions
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
    ALLOWED_EXTENSIONS = {'.wav', '.bin', '.txt', '.yml', '.yaml', '.py', '.grc'}

    def __init__(self, config_path: str, db: Database, files_dir: str):
        # Don't use Flask's static file serving - we'll handle it manually for SPA routing
        # Configuration
        self.config_path = config_path
        self.config = self.load_config(config_path)
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
        # SECURITY: Use same CORS origins as REST API to prevent unauthorized WebSocket connections
        self.socketio = SocketIO(
            self.app,
            cors_allowed_origins=allowed_origins,
            cookie='session_token'  # Tie to session cookie for additional security
        )

        # Initialize rate limiter with default limits for security
        # SECURITY: Default limits protect against DoS and API abuse
        # Runner endpoints get higher limits (overridden per-endpoint)
        # Authentication endpoints get stricter limits (brute force protection)
        self.limiter = Limiter(
            app=self.app,
            key_func=get_remote_address,
            default_limits=["100 per minute", "1000 per hour"],  # Default for admin/web UI
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

    def get_frequency_ranges(self) -> List[Dict]:
        """Get frequency ranges from config.

        Returns:
            List of frequency range dictionaries with name, description, min_hz, max_hz
        """
        return self.config.get('frequency_ranges', [])

    def select_random_frequency(self, frequency_ranges: List[str]) -> Optional[float]:
        """Select a random frequency from one or more named frequency ranges.

        Args:
            frequency_ranges: List of frequency range names (e.g., ["ham_144", "ham_220"])

        Returns:
            Random frequency in Hz as a float, or None if ranges not found
        """
        if not frequency_ranges:
            return None

        # Select a random range from the list
        selected_range_name = random.choice(frequency_ranges)

        # Find the range configuration
        available_ranges = self.get_frequency_ranges()
        for freq_range in available_ranges:
            if freq_range.get('name') == selected_range_name:
                min_hz = freq_range.get('min_hz')
                max_hz = freq_range.get('max_hz')
                if min_hz is not None and max_hz is not None:
                    # Select random frequency within the range and return as float
                    return float(random.randint(int(min_hz), int(max_hz)))

        logger.warning(f"Frequency range '{selected_range_name}' not found in configuration")
        return None

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
            return {'in_sync': None, 'error': 'Failed to check configuration sync'}

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
        """Decorator to require API key authentication (for runners only).

        Checks database for runner API key with enhanced multi-factor host validation.
        All runners must be enrolled via the secure enrollment process.
        """
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization')

            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({'error': 'Missing or invalid authorization header'}), 401

            api_key = auth_header[7:]  # Remove 'Bearer ' prefix
            current_ip = request.remote_addr

            # Get hostname from request body if available (registration/heartbeat includes it)
            # Otherwise use empty string (will only validate IP)
            current_hostname = ''
            if request.is_json and request.json:
                current_hostname = request.json.get('hostname', '')

            # Get host identifiers from custom headers (sent by runner)
            current_mac = request.headers.get('X-Runner-MAC')
            current_machine_id = request.headers.get('X-Runner-Machine-ID')

            # Find runner_id in database with enhanced host validation (optimized query)
            runner_id = self.db.find_runner_by_api_key(api_key, current_ip, current_hostname,
                                                       current_mac, current_machine_id)

            if not runner_id:
                return jsonify({'error': 'Invalid API key'}), 401

            # Add runner_id to request context
            request.runner_id = runner_id

            return f(*args, **kwargs)

        return decorated_function

    def generate_csrf_token(self) -> str:
        """Generate a random CSRF token."""
        return secrets.token_urlsafe(32)

    def generate_api_key(self) -> str:
        """Generate a secure random API key for runners or provisioning."""
        return secrets.token_urlsafe(48)

    def get_cookie_security_settings(self) -> dict:
        """
        Determine secure cookie settings based on environment.

        Returns dict with 'secure' and 'samesite' settings:
        - In development (HTTP): secure=False, samesite='Lax'
        - In production (HTTPS or behind reverse proxy): secure=True, samesite='Lax'

        Detects HTTPS by checking:
        1. request.is_secure (direct HTTPS)
        2. X-Forwarded-Proto header (nginx reverse proxy with HTTPS termination)
        """
        # Check if we're running on HTTPS (direct or via reverse proxy)
        is_https = request.is_secure or request.headers.get('X-Forwarded-Proto') == 'https'

        return {
            'secure': is_https,
            'samesite': 'Lax'  # Lax allows cookies on top-level navigation (safer than None, works with redirects)
        }

    def set_auth_cookies(self, response, session_token: str, csrf_token: str):
        """Set authentication cookies (session and CSRF tokens) with consistent security settings.

        Args:
            response: Flask response object to set cookies on
            session_token: Session token value
            csrf_token: CSRF token value

        This centralizes cookie configuration to ensure consistency across all auth endpoints.
        """
        # Get security settings (auto-detects HTTP vs HTTPS)
        cookie_settings = self.get_cookie_security_settings()

        # Set secure httpOnly cookie for session token
        response.set_cookie(
            'session_token',
            session_token,
            httponly=True,
            secure=cookie_settings['secure'],
            samesite=cookie_settings['samesite'],
            max_age=86400
        )

        # Set CSRF token cookie (not httpOnly, needs to be readable by JS)
        response.set_cookie(
            'csrf_token',
            csrf_token,
            httponly=False,
            secure=cookie_settings['secure'],
            samesite=cookie_settings['samesite'],
            max_age=86400
        )

    def clear_auth_cookies(self, response):
        """Clear authentication cookies (for logout).

        Args:
            response: Flask response object to clear cookies on

        Cookie attributes must match exactly how they were set during login,
        otherwise browsers won't delete them properly.
        """
        cookie_settings = self.get_cookie_security_settings()

        # Clear session token cookie
        response.set_cookie(
            'session_token',
            '',
            httponly=True,
            secure=cookie_settings['secure'],
            samesite=cookie_settings['samesite'],
            max_age=0
        )

        # Clear CSRF token cookie
        response.set_cookie(
            'csrf_token',
            '',
            httponly=False,
            secure=cookie_settings['secure'],
            samesite=cookie_settings['samesite'],
            max_age=0
        )

    def log_security_event(self, event_type: str, username: str = None, level: str = 'info', **kwargs):
        """Log security-related events with consistent formatting.

        Args:
            event_type: Type of security event (e.g., 'login', 'logout', 'failed_login')
            username: Username associated with the event (if applicable)
            level: Log level ('info', 'warning', 'error')
            **kwargs: Additional context-specific fields to include in log

        This centralizes security logging to ensure consistent format and completeness.
        """
        # Always include IP and user agent for security events
        ip = request.remote_addr
        user_agent = request.headers.get('User-Agent', 'unknown')

        # Build log message
        parts = [f"SECURITY: {event_type}"]
        if username:
            parts.append(f"username='{username}'")
        parts.append(f"ip={ip}")

        # Add additional context fields
        for key, value in kwargs.items():
            parts.append(f"{key}={value}")

        parts.append(f"user_agent='{user_agent}'")

        message = " - ".join(parts) if len(parts) > 1 else parts[0]

        # Log at appropriate level
        if level == 'warning':
            logger.warning(message)
        elif level == 'error':
            logger.error(message)
        else:
            logger.info(message)

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

    def require_provisioning_key(self, f):
        """Decorator to require provisioning API key authentication.

        Provisioning keys have limited permissions - only runner enrollment.
        Uses Bearer token authentication without CSRF (stateless).
        """
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization')

            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({'error': 'Missing or invalid authorization header'}), 401

            api_key = auth_header[7:]  # Remove 'Bearer ' prefix

            # Verify provisioning API key
            key_id = self.db.verify_provisioning_api_key(api_key)

            if not key_id:
                logger.warning(f"Invalid provisioning API key attempt from {request.remote_addr}")
                return jsonify({'error': 'Invalid provisioning API key'}), 401

            # Add key_id to request context for logging
            request.provisioning_key_id = key_id
            logger.info(f"Provisioning API request from key '{key_id}' at {request.remote_addr}")

            return f(*args, **kwargs)

        return decorated_function

    def require_admin_auth(self, f):
        """Decorator to require admin session authentication."""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Use centralized session validation
            username, error_response = self.validate_and_renew_session()

            if error_response:
                return error_response

            # Add username to request context
            request.admin_username = username

            return f(*args, **kwargs)

        return decorated_function

    def require_permission(self, permission_name: str):
        """Decorator factory to require a specific permission.

        Usage: @require_permission('create_users')

        Must be used after @require_admin_auth decorator.
        """
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                # Get username from request context (set by require_admin_auth)
                username = getattr(request, 'admin_username', None)

                if not username:
                    return jsonify({'error': 'Authentication required'}), 401

                # Check if user has the required permission
                if not self.db.has_permission(username, permission_name):
                    self.log_security_event('Permission denied', username, level='warning',
                                           permission=permission_name, path=request.path)
                    return jsonify({'error': f'Permission denied: {permission_name} required'}), 403

                return f(*args, **kwargs)

            return decorated_function
        return decorator

    def create_session(self, username: str, totp_verified: bool = False) -> str:
        """Create a new session token for a user (stored in database).

        SECURITY: Uses UTC timestamps to prevent timezone manipulation issues.
        """
        session_token = secrets.token_urlsafe(32)
        # Use UTC to prevent timezone manipulation
        expires = datetime.utcnow() + timedelta(hours=24)

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

    def renew_session(self, session_token: str) -> bool:
        """Renew session expiry (sliding session).

        SECURITY: Extends session by 24 hours from current time on activity.
        Uses UTC timestamps to prevent timezone manipulation.
        """
        new_expires = datetime.utcnow() + timedelta(hours=24)
        return self.db.update_session_expires(session_token, new_expires.isoformat())

    def validate_and_renew_session(self):
        """Validate session from cookies and renew if valid.

        Returns:
            Tuple of (username, None) if valid, or (None, error_response) if invalid

        This centralizes session validation logic to avoid duplication across endpoints.
        Performs all necessary checks: token presence, validity, expiration, TOTP verification,
        and automatic session renewal.
        """
        session_token = request.cookies.get('session_token')

        if not session_token:
            return None, (jsonify({'error': 'Missing or invalid session'}), 401)

        # Check session validity (from database)
        session = self.db.get_session(session_token)

        if not session:
            return None, (jsonify({'error': 'Invalid or expired session'}), 401)

        # Check if session is expired
        # Note: expires is stored as ISO format string in database
        # SECURITY: Use UTC for consistent timezone handling
        expires = datetime.fromisoformat(session['expires'])
        if datetime.utcnow() > expires:
            self.db.delete_session(session_token)
            return None, (jsonify({'error': 'Session expired'}), 401)

        # Check if TOTP was verified
        if not session.get('totp_verified', False):
            return None, (jsonify({'error': 'TOTP verification required'}), 401)

        # SECURITY: Sliding session - renew expiry on activity
        # Extends session by 24 hours from now
        self.renew_session(session_token)

        # Return username for successful validation
        return session['username'], None

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
                'timestamp': datetime.now(timezone.utc).isoformat()
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
                self.log_security_event('Failed login attempt', username, level='warning', reason=reason)
                return jsonify({'error': 'Invalid credentials'}), 401

            # Check if user is temporary (requires setup)
            is_temporary = user.get('is_temporary', False)

            # Check if user has TOTP configured
            totp_secret = user.get('totp_secret')
            has_totp = totp_secret is not None and totp_secret != ''

            # Temporary users need to complete setup (change password + set up TOTP)
            if is_temporary:
                # Create a limited session for setup (not yet TOTP verified)
                session_token = self.create_session(username, totp_verified=False)

                # Generate CSRF token for this session
                csrf_token = self.generate_csrf_token()

                # Set httpOnly cookie for security (prevents XSS attacks)
                response = make_response(jsonify({
                    'setup_required': True,
                    'username': username,
                    'message': 'Account setup required. Please change your password and set up 2FA.'
                }), 200)

                # Set authentication cookies with consistent security settings
                self.set_auth_cookies(response, session_token, csrf_token)

                self.log_security_event('Temporary user login', username, setup_required='true')

                return response

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

                # Set authentication cookies with consistent security settings
                self.set_auth_cookies(response, session_token, csrf_token)

                # Log successful password verification
                self.log_security_event('Password verified', username, totp_required='true')

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
                self.log_security_event('Successful login', username, totp_required='false')

                # Set httpOnly cookie for security (prevents XSS attacks)
                response = make_response(jsonify({
                    'status': 'authenticated',
                    'totp_required': False,
                    'initial_setup_required': initial_setup_required,
                    'username': username
                }), 200)

                # Set authentication cookies with consistent security settings
                self.set_auth_cookies(response, session_token, csrf_token)

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
            # SECURITY: Use UTC for consistent timezone handling
            expires = datetime.fromisoformat(session['expires'])
            if datetime.utcnow() > expires:
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
                self.log_security_event('TOTP replay attempt', username, level='warning',
                                       code=f"{totp_code[:2]}**")
                return jsonify({'error': 'Invalid TOTP code'}), 401

            # Verify TOTP code
            try:
                totp = pyotp.TOTP(totp_secret)
                if not totp.verify(totp_code, valid_window=1):
                    # Log failed TOTP verification
                    self.log_security_event('Failed TOTP verification', username, level='warning',
                                           code=f"{totp_code[:2]}**")
                    return jsonify({'error': 'Invalid TOTP code'}), 401

                # Mark code as used (only after successful verification)
                if not self.mark_totp_code_used(username, totp_code):
                    # This shouldn't happen due to the check above, but handle it anyway
                    self.log_security_event('TOTP code reuse detected', username, level='warning',
                                           code=f"{totp_code[:2]}**")
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
            self.log_security_event('Successful TOTP verification', username, code=f"{totp_code[:2]}**")

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
            # SECURITY: Use UTC for consistent timezone handling
            expires = datetime.fromisoformat(session['expires'])
            if datetime.utcnow() > expires:
                self.db.delete_session(session_token)
                return jsonify({'authenticated': False, 'error': 'Session expired'}), 401

            # Check if TOTP was verified (required for full authentication)
            if not session.get('totp_verified', False):
                return jsonify({'authenticated': False, 'error': 'TOTP verification required'}), 401

            # SECURITY: Sliding session - renew expiry on session check
            # This is called on page refresh and navigation
            self.renew_session(session_token)

            # Session is valid
            username = session['username']
            user = self.db.get_user(username)

            if not user or not user.get('enabled'):
                return jsonify({'authenticated': False, 'error': 'Account disabled'}), 401

            # Check if initial setup is required
            initial_setup_required = self.db.get_system_state('initial_setup_required', 'false') == 'true'

            # Get user permissions
            permissions = self.db.get_user_permissions(username)

            return jsonify({
                'authenticated': True,
                'username': username,
                'initial_setup_required': initial_setup_required,
                'permissions': permissions
            }), 200

        @self.app.route('/api/auth/logout', methods=['POST'])
        @self.require_csrf
        def logout():
            """Logout and destroy session."""
            # Get session token from httpOnly cookie
            session_token = request.cookies.get('session_token')

            if session_token:
                self.destroy_session(session_token)

            # Clear both session and CSRF cookies with consistent settings
            response = make_response(jsonify({'status': 'logged out'}), 200)
            self.clear_auth_cookies(response)

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

        @self.app.route('/api/auth/complete-setup', methods=['POST'])
        def complete_setup():
            """Step 1: Change password and generate TOTP for temporary users."""
            data = request.json

            if not data:
                return jsonify({'error': 'Missing request body'}), 400

            # Get session token from cookie
            session_token = request.cookies.get('session_token')

            if not session_token:
                return jsonify({'error': 'Missing session token'}), 401

            # Get session from database
            session = self.db.get_session(session_token)

            if not session:
                return jsonify({'error': 'Invalid or expired session'}), 401

            # Check if session is expired
            expires = datetime.fromisoformat(session['expires'])
            if datetime.utcnow() > expires:
                self.db.delete_session(session_token)
                return jsonify({'error': 'Session expired'}), 401

            username = session['username']
            new_password = data.get('new_password')

            if not new_password:
                return jsonify({'error': 'Missing new_password'}), 400

            if len(new_password) < 8:
                return jsonify({'error': 'Password must be at least 8 characters'}), 400

            # Verify user is temporary
            user = self.db.get_user(username)

            if not user:
                return jsonify({'error': 'User not found'}), 404

            if not user.get('is_temporary', False):
                return jsonify({'error': 'This endpoint is only for temporary users'}), 400

            # Hash new password and store in session temporarily
            password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

            # Generate TOTP secret
            totp_secret = pyotp.random_base32()
            totp = pyotp.TOTP(totp_secret)
            conference_name = self.get_conference_name()
            provisioning_uri = totp.provisioning_uri(name=username, issuer_name=conference_name)

            # Store password hash and TOTP secret in session temporarily for verification
            # We'll use a simple in-memory store tied to session token
            if not hasattr(self, '_setup_pending'):
                self._setup_pending = {}

            self._setup_pending[session_token] = {
                'password_hash': password_hash,
                'totp_secret': totp_secret,
                'timestamp': datetime.utcnow()
            }

            self.log_security_event('User setup initiated (step 1)', username)

            return jsonify({
                'status': 'awaiting_verification',
                'username': username,
                'totp_secret': totp_secret,
                'provisioning_uri': provisioning_uri
            }), 200

        @self.app.route('/api/auth/verify-setup', methods=['POST'])
        def verify_setup():
            """Step 2: Verify TOTP code and complete setup for temporary users."""
            data = request.json

            if not data:
                return jsonify({'error': 'Missing request body'}), 400

            # Get session token from cookie
            session_token = request.cookies.get('session_token')

            if not session_token:
                return jsonify({'error': 'Missing session token'}), 401

            # Get session from database
            session = self.db.get_session(session_token)

            if not session:
                return jsonify({'error': 'Invalid or expired session'}), 401

            # Check if session is expired
            expires = datetime.fromisoformat(session['expires'])
            if datetime.utcnow() > expires:
                self.db.delete_session(session_token)
                return jsonify({'error': 'Session expired'}), 401

            username = session['username']
            totp_code = data.get('totp_code')

            if not totp_code:
                return jsonify({'error': 'Missing totp_code'}), 400

            # Get pending setup data
            if not hasattr(self, '_setup_pending') or session_token not in self._setup_pending:
                return jsonify({'error': 'No pending setup found. Please restart setup process.'}), 400

            pending = self._setup_pending[session_token]

            # Check if pending setup is too old (15 minutes)
            if datetime.utcnow() - pending['timestamp'] > timedelta(minutes=15):
                del self._setup_pending[session_token]
                return jsonify({'error': 'Setup session expired. Please restart setup process.'}), 400

            # Verify TOTP code
            totp = pyotp.TOTP(pending['totp_secret'])
            if not totp.verify(totp_code, valid_window=1):
                return jsonify({'error': 'Invalid TOTP code'}), 401

            # Complete user setup
            if not self.db.complete_user_setup(username, pending['password_hash'], pending['totp_secret']):
                return jsonify({'error': 'Failed to complete setup'}), 500

            # Clean up pending setup
            del self._setup_pending[session_token]

            # Mark session as TOTP verified
            self.db.update_session_totp(session_token)

            # Update last login timestamp
            self.db.update_last_login(username)

            self.log_security_event('User setup completed', username)

            return jsonify({
                'status': 'setup_complete',
                'username': username
            }), 200

        # User management endpoints (admin only)
        @self.app.route('/api/users', methods=['GET'])
        @self.require_admin_auth
        def get_users():
            """Get all users."""
            # Get all users with permissions in a single optimized query
            users = self.db.get_all_users_with_permissions()

            return jsonify({'users': users}), 200

        @self.app.route('/api/users', methods=['POST'])
        @self.require_admin_auth
        @self.require_csrf
        def create_user_endpoint():
            """Create a new user (temporary by default, requires setup on first login)."""
            data = request.json

            if not data:
                return jsonify({'error': 'Missing request body'}), 400

            username = data.get('username')
            password = data.get('password')  # Optional - will be auto-generated for temporary users
            permissions = data.get('permissions', [])  # List of permission names to grant

            if not username:
                return jsonify({'error': 'Missing username'}), 400

            # Check if this is initial setup (special case - no permission check needed)
            initial_setup_required = self.db.get_system_state('initial_setup_required', 'false') == 'true'

            # For initial setup, password is required
            if initial_setup_required:
                if not password:
                    return jsonify({'error': 'Missing password'}), 400
                if len(password) < 8:
                    return jsonify({'error': 'Password must be at least 8 characters'}), 400

            # For normal user creation (not initial setup), check create_users permission
            if not initial_setup_required:
                creator_username = request.admin_username
                if not self.db.has_permission(creator_username, 'create_users'):
                    self.log_security_event('User creation denied', creator_username, level='warning',
                                           missing_permission='create_users')
                    return jsonify({'error': 'Permission denied: create_users permission required'}), 403

                # Auto-generate temporary password if not provided
                if not password:
                    password = secrets.token_urlsafe(12)  # Generates ~16 character password

            # Hash password
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

            # Create temporary user (no TOTP, must complete setup on first login)
            # Note: For initial setup, we create a full user with TOTP
            if initial_setup_required:
                # Initial setup creates a full admin user with TOTP
                totp_secret = pyotp.random_base32()
                if not self.db.create_user(username, password_hash, totp_secret, is_temporary=False):
                    return jsonify({'error': 'User already exists'}), 409

                # Mark initial setup as complete
                self.db.set_system_state('initial_setup_required', 'false')
                # Disable the default admin account for security
                self.db.disable_user('admin')
                logger.info("Initial setup completed - default admin account disabled")

                # Grant full permissions to first user
                self.db.grant_permission(username, 'create_users', 'system')
                self.db.grant_permission(username, 'create_provisioning_key', 'system')

                # Generate TOTP provisioning URI
                totp = pyotp.TOTP(totp_secret)
                conference_name = self.get_conference_name()
                provisioning_uri = totp.provisioning_uri(name=username, issuer_name=conference_name)

                logger.info(f"Initial admin user {username} created during setup")

                return jsonify({
                    'status': 'created',
                    'username': username,
                    'totp_secret': totp_secret,
                    'provisioning_uri': provisioning_uri,
                    'is_temporary': False
                }), 201
            else:
                # Normal user creation - create temporary user
                if not self.db.create_user(username, password_hash, totp_secret=None, is_temporary=True):
                    return jsonify({'error': 'User already exists'}), 409

                # Grant requested permissions to the new user
                creator_username = request.admin_username
                for permission in permissions:
                    if permission in ['create_users', 'create_provisioning_key']:  # Whitelist of valid permissions
                        self.db.grant_permission(username, permission, creator_username)
                        logger.info(f"Granted permission '{permission}' to new user {username}")

                logger.info(
                    f"Temporary user {username} created by {creator_username} "
                    f"(must complete setup within 24 hours)"
                )

                return jsonify({
                    'status': 'created',
                    'username': username,
                    'is_temporary': True,
                    'setup_deadline_hours': 24,
                    'temporary_password': password  # Return temp password so admin can share it
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
            # Don't allow resetting your own password (use change password instead)
            if username == request.admin_username:
                return jsonify({'error': 'Cannot reset your own password. Use change password instead.'}), 400

            # Check user exists
            user = self.db.get_user(username)
            if not user:
                return jsonify({'error': 'User not found'}), 404

            # Auto-generate a temporary password
            new_password = secrets.token_urlsafe(12)  # Generates ~16 character password

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

            return jsonify({
                'status': 'password_reset',
                'username': username,
                'temporary_password': new_password  # Return temp password so admin can share it
            }), 200

        # Permission management endpoints
        @self.app.route('/api/users/<username>/permissions', methods=['GET'])
        @self.require_admin_auth
        def get_user_permissions_endpoint(username):
            """Get permissions for a specific user."""
            # Check user exists
            user = self.db.get_user(username)
            if not user:
                return jsonify({'error': 'User not found'}), 404

            permissions = self.db.get_user_permissions(username)

            return jsonify({
                'username': username,
                'permissions': permissions
            }), 200

        @self.app.route('/api/users/<username>/permissions', methods=['POST'])
        @self.require_admin_auth
        @self.require_csrf
        @self.require_permission('create_users')  # Only users with create_users can manage permissions
        def grant_permission_endpoint(username):
            """Grant a permission to a user."""
            data = request.json

            if not data:
                return jsonify({'error': 'Missing request body'}), 400

            permission_name = data.get('permission')

            if not permission_name:
                return jsonify({'error': 'Missing permission field'}), 400

            # Whitelist of valid permissions
            valid_permissions = ['create_users', 'create_provisioning_key']

            if permission_name not in valid_permissions:
                return jsonify({'error': f'Invalid permission: {permission_name}'}), 400

            # Check user exists
            user = self.db.get_user(username)
            if not user:
                return jsonify({'error': 'User not found'}), 404

            # Grant permission
            if not self.db.grant_permission(username, permission_name, request.admin_username):
                return jsonify({'error': 'Failed to grant permission'}), 500

            logger.info(f"Permission '{permission_name}' granted to user {username} by {request.admin_username}")

            return jsonify({'status': 'permission_granted', 'permission': permission_name}), 200

        @self.app.route('/api/users/<username>/permissions/<permission_name>', methods=['DELETE'])
        @self.require_admin_auth
        @self.require_csrf
        @self.require_permission('create_users')  # Only users with create_users can manage permissions
        def revoke_permission_endpoint(username, permission_name):
            """Revoke a permission from a user."""
            # Check user exists
            user = self.db.get_user(username)
            if not user:
                return jsonify({'error': 'User not found'}), 404

            # Don't allow revoking your own permissions
            if username == request.admin_username:
                return jsonify({'error': 'Cannot revoke your own permissions'}), 400

            # Revoke permission
            if not self.db.revoke_permission(username, permission_name):
                return jsonify({'error': 'Failed to revoke permission'}), 500

            logger.info(f"Permission '{permission_name}' revoked from user {username} by {request.admin_username}")

            return jsonify({'status': 'permission_revoked', 'permission': permission_name}), 200

        # Public dashboard endpoint (no auth required)
        @self.app.route('/api/public/challenges', methods=['GET'])
        def get_public_challenges():
            """Get public view of enabled challenges with configurable visibility."""
            try:
                public_challenges = self.get_public_challenges_data()

                return jsonify({
                    'challenges': public_challenges,
                    'count': len(public_challenges),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }), 200

            except Exception as e:
                logger.error(f"Error getting public challenges: {e}")
                return jsonify({'error': 'Internal server error'}), 500

        # Conference info endpoint (no auth required)
        @self.app.route('/api/conference', methods=['GET'])
        def get_conference_info():
            """Get conference information including name and start/stop times."""
            try:
                conference = self.config.get('conference', {})

                # Get day_start and end_of_day from system_state (runtime config) or fallback to config file
                day_start = self.db.get_system_state('day_start', conference.get('day_start'))
                end_of_day = self.db.get_system_state('end_of_day', conference.get('end_of_day'))
                auto_pause_daily = self.db.get_system_state('auto_pause_daily', 'false') == 'true'

                return jsonify({
                    'name': conference.get('name', 'ChallengeCtl'),
                    'start': conference.get('start'),
                    'stop': conference.get('stop'),
                    'day_start': day_start,
                    'end_of_day': end_of_day,
                    'auto_pause_daily': auto_pause_daily
                }), 200

            except Exception as e:
                logger.error(f"Error getting conference info: {e}")
                return jsonify({'error': 'Internal server error'}), 500

        @self.app.route('/api/frequency-ranges', methods=['GET'])
        def get_frequency_ranges():
            """Get available named frequency ranges from configuration.

            Returns:
                List of frequency range objects with name, description, min_hz, max_hz
            """
            try:
                frequency_ranges = self.get_frequency_ranges()
                return jsonify(frequency_ranges), 200
            except Exception as e:
                logger.error(f"Error getting frequency ranges: {e}")
                return jsonify({'error': 'Internal server error'}), 500

        @self.app.route('/api/frequency-ranges/reload', methods=['POST'])
        @self.require_admin_auth
        @self.require_csrf
        def reload_frequency_ranges():
            """Reload configuration file to pick up new frequency ranges.

            This reloads the entire server configuration from disk, making any
            new frequency ranges immediately available without restarting the server.
            """
            try:
                # Reload config from disk
                self.config = self.load_config(self.config_path)
                logger.info(f"Configuration reloaded from {self.config_path}")

                # Get updated frequency ranges
                frequency_ranges = self.get_frequency_ranges()

                return jsonify({
                    'status': 'reloaded',
                    'count': len(frequency_ranges),
                    'ranges': frequency_ranges
                }), 200
            except Exception as e:
                logger.error(f"Error reloading configuration: {e}")
                return jsonify({'error': 'Failed to reload configuration'}), 500

        # Conference settings endpoints (admin only)
        @self.app.route('/api/conference/day-times', methods=['PUT'])
        @self.require_admin_auth
        @self.require_csrf
        def update_day_times():
            """Update the day start and end of day times."""
            try:
                data = request.json
                if not data:
                    return jsonify({'error': 'Missing request body'}), 400

                import re
                time_pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'

                # Update day_start if provided
                if 'day_start' in data:
                    day_start = data['day_start']
                    if day_start and not re.match(time_pattern, day_start):
                        return jsonify({'error': 'Invalid day_start format. Use HH:MM (e.g., 09:00)'}), 400
                    self.db.set_system_state('day_start', day_start)
                    logger.info(f"Day start updated to '{day_start}' by {request.admin_username}")

                # Update end_of_day if provided
                if 'end_of_day' in data:
                    end_of_day = data['end_of_day']
                    if end_of_day and not re.match(time_pattern, end_of_day):
                        return jsonify({'error': 'Invalid end_of_day format. Use HH:MM (e.g., 17:00)'}), 400
                    self.db.set_system_state('end_of_day', end_of_day)
                    logger.info(f"End of day updated to '{end_of_day}' by {request.admin_username}")

                return jsonify({
                    'status': 'updated',
                    'day_start': data.get('day_start'),
                    'end_of_day': data.get('end_of_day')
                }), 200

            except Exception as e:
                logger.error(f"Error updating day times: {e}")
                return jsonify({'error': 'Internal server error'}), 500

        # Backward compatibility endpoint
        @self.app.route('/api/conference/end-of-day', methods=['PUT'])
        @self.require_admin_auth
        @self.require_csrf
        def update_end_of_day_legacy():
            """Update the end of day time (legacy endpoint)."""
            return update_day_times()

        # Auto-pause settings endpoint
        @self.app.route('/api/conference/auto-pause', methods=['PUT'])
        @self.require_admin_auth
        @self.require_csrf
        def update_auto_pause():
            """Update the auto-pause daily setting."""
            try:
                data = request.json
                if not data or 'auto_pause_daily' not in data:
                    return jsonify({'error': 'Missing auto_pause_daily field'}), 400

                auto_pause = data['auto_pause_daily']

                # Validate boolean
                if not isinstance(auto_pause, bool):
                    return jsonify({'error': 'auto_pause_daily must be a boolean'}), 400

                # Store in system_state
                self.db.set_system_state('auto_pause_daily', 'true' if auto_pause else 'false')

                logger.info(f"Auto-pause daily updated to {auto_pause} by {request.admin_username}")

                return jsonify({
                    'status': 'updated',
                    'auto_pause_daily': auto_pause
                }), 200

            except Exception as e:
                logger.error(f"Error updating auto-pause: {e}")
                return jsonify({'error': 'Internal server error'}), 500

        # Runner endpoints
        # SECURITY: Runner endpoints have liberal rate limits due to frequent polling/heartbeats
        @self.app.route('/api/runners/register', methods=['POST'])
        @self.require_api_key
        @self.limiter.limit("100 per minute")  # Registration not frequent
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

            # Get host identifiers from custom headers (sent by runner)
            mac_address = request.headers.get('X-Runner-MAC')
            machine_id = request.headers.get('X-Runner-Machine-ID')

            success = self.db.register_runner(runner_id, hostname, ip_address, devices,
                                             mac_address=mac_address, machine_id=machine_id)

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
        @self.limiter.limit("1000 per minute")  # High limit for frequent heartbeats (every 30s)
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
        @self.limiter.limit("100 per minute")  # Signout not frequent
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
        @self.limiter.limit("1000 per minute")  # High limit for frequent task polling
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
                # Process frequency_ranges or manual_frequency_range if present
                config = challenge['config'].copy()  # Make a copy to avoid modifying stored config
                frequency_ranges = config.get('frequency_ranges')
                manual_frequency_range = config.get('manual_frequency_range')

                if frequency_ranges:
                    # Select random frequency from named ranges
                    selected_frequency = self.select_random_frequency(frequency_ranges)
                    if selected_frequency:
                        # Replace frequency_ranges with selected frequency
                        config['frequency'] = selected_frequency
                        # Remove frequency_ranges from config sent to runner
                        config.pop('frequency_ranges', None)
                        logger.info(f"Selected random frequency {selected_frequency} Hz from ranges {frequency_ranges}")
                    else:
                        logger.error(f"Failed to select frequency from ranges: {frequency_ranges}")
                        return jsonify({'error': 'Invalid frequency range configuration'}), 500
                elif manual_frequency_range:
                    # Select random frequency from manual range
                    min_hz = manual_frequency_range.get('min_hz')
                    max_hz = manual_frequency_range.get('max_hz')
                    if min_hz and max_hz:
                        selected_frequency = float(random.randint(int(min_hz), int(max_hz)))
                        config['frequency'] = selected_frequency
                        # Remove manual_frequency_range from config sent to runner
                        config.pop('manual_frequency_range', None)
                        logger.info(f"Selected random frequency {selected_frequency} Hz from manual range {min_hz}-{max_hz}")
                    else:
                        logger.error(f"Invalid manual frequency range: {manual_frequency_range}")
                        return jsonify({'error': 'Invalid manual frequency range configuration'}), 500
                elif 'frequency' in config:
                    # Ensure existing frequency is a float
                    config['frequency'] = float(config['frequency'])

                # Broadcast assignment event
                self.broadcast_event('challenge_assigned', {
                    'runner_id': runner_id,
                    'challenge_id': challenge['challenge_id'],
                    'challenge_name': challenge['name'],
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })

                return jsonify({
                    'task': {
                        'challenge_id': challenge['challenge_id'],
                        'name': challenge['name'],
                        'config': config
                    }
                }), 200
            else:
                return jsonify({'task': None, 'message': 'No challenges available'}), 200

        @self.app.route('/api/runners/<runner_id>/complete', methods=['POST'])
        @self.require_api_key
        @self.limiter.limit("1000 per minute")  # High limit for frequent task completions
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
            timestamp = datetime.now(timezone.utc).isoformat()
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
        @self.limiter.limit("1000 per minute")  # High limit for frequent logging
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

        # Unified Agent endpoints (support both runners and listeners)
        @self.app.route('/api/agents/register', methods=['POST'])
        @self.require_api_key
        @self.limiter.limit("100 per minute")
        def register_agent():
            """Register an agent (runner or listener) with the server."""
            data = request.json

            # Validate request body
            if not data:
                return jsonify({'error': 'Missing request body'}), 400

            agent_id = request.runner_id  # Note: Uses same authentication mechanism

            # Validate required fields
            agent_type = data.get('agent_type', 'runner')  # Default to runner for backward compatibility
            if agent_type not in ['runner', 'listener']:
                return jsonify({'error': 'Invalid agent_type. Must be "runner" or "listener"'}), 400

            hostname = data.get('hostname')
            if not hostname or not hostname.strip():
                return jsonify({'error': 'Missing required field: hostname'}), 400

            devices = data.get('devices')
            if devices is None:
                return jsonify({'error': 'Missing required field: devices'}), 400

            if not isinstance(devices, list):
                return jsonify({'error': 'Field "devices" must be a list'}), 400

            ip_address = request.remote_addr

            # Get host identifiers from custom headers
            mac_address = request.headers.get('X-Runner-MAC') or request.headers.get('X-Agent-MAC')
            machine_id = request.headers.get('X-Runner-Machine-ID') or request.headers.get('X-Agent-Machine-ID')

            success = self.db.register_agent(agent_id, agent_type, hostname, ip_address, devices,
                                            mac_address=mac_address, machine_id=machine_id)

            if success:
                # Broadcast agent online event
                event_name = 'runner_status' if agent_type == 'runner' else 'listener_status'
                self.broadcast_event(event_name, {
                    'agent_id': agent_id,
                    'runner_id': agent_id if agent_type == 'runner' else None,  # Backward compat
                    'listener_id': agent_id if agent_type == 'listener' else None,
                    'status': 'online',
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })

                return jsonify({
                    'status': 'registered',
                    'agent_id': agent_id,
                    'agent_type': agent_type
                }), 200
            else:
                return jsonify({'error': 'Registration failed'}), 500

        @self.app.route('/api/agents/<agent_id>/heartbeat', methods=['POST'])
        @self.require_api_key
        @self.limiter.limit("1000 per minute")
        def agent_heartbeat(agent_id):
            """Update agent heartbeat (runner or listener)."""
            if request.runner_id != agent_id:
                return jsonify({'error': 'Unauthorized'}), 403

            success, previous_status = self.db.update_agent_heartbeat(agent_id)

            if success:
                # Get agent details to determine type
                agent = self.db.get_agent(agent_id)
                if agent:
                    agent_type = agent['agent_type']
                    heartbeat_time = datetime.now(timezone.utc).isoformat()

                    # Broadcast with appropriate event name for backward compatibility
                    event_name = 'runner_status' if agent_type == 'runner' else 'listener_status'
                    self.broadcast_event(event_name, {
                        'agent_id': agent_id,
                        'runner_id': agent_id if agent_type == 'runner' else None,
                        'listener_id': agent_id if agent_type == 'listener' else None,
                        'status': 'online',
                        'last_heartbeat': heartbeat_time,
                        'timestamp': heartbeat_time
                    })

                return jsonify({'status': 'ok'}), 200
            else:
                return jsonify({'error': 'Agent not found'}), 404

        @self.app.route('/api/agents/<agent_id>/signout', methods=['POST'])
        @self.require_api_key
        @self.limiter.limit("100 per minute")
        def agent_signout(agent_id):
            """Agent graceful signout."""
            if request.runner_id != agent_id:
                return jsonify({'error': 'Unauthorized'}), 403

            # Get agent details before marking offline
            agent = self.db.get_agent(agent_id)
            if not agent:
                return jsonify({'error': 'Agent not found'}), 404

            agent_type = agent['agent_type']

            # Mark agent as offline
            success = self.db.mark_agent_offline(agent_id)

            if success:
                # Broadcast offline status
                event_name = 'runner_status' if agent_type == 'runner' else 'listener_status'
                self.broadcast_event(event_name, {
                    'agent_id': agent_id,
                    'runner_id': agent_id if agent_type == 'runner' else None,
                    'listener_id': agent_id if agent_type == 'listener' else None,
                    'status': 'offline',
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
                logger.info(f"{agent_type.capitalize()} {agent_id} signed out gracefully")
                return jsonify({'status': 'signed_out'}), 200
            else:
                return jsonify({'error': 'Failed to sign out'}), 500

        @self.app.route('/api/agents/<agent_id>/task', methods=['GET'])
        @self.require_api_key
        @self.limiter.limit("1000 per minute")
        def agent_get_task(agent_id):
            """Get next challenge assignment for runner agent (HTTP polling).
            Note: Listener agents use WebSocket push instead of polling."""
            if request.runner_id != agent_id:
                return jsonify({'error': 'Unauthorized'}), 403

            # Verify this is a runner agent
            agent = self.db.get_agent(agent_id)
            if not agent:
                return jsonify({'error': 'Agent not found'}), 404

            if agent['agent_type'] != 'runner':
                return jsonify({'error': 'Only runner agents can poll for tasks. Listeners use WebSocket.'}), 400

            # Check if system is paused
            if self.db.get_system_state('paused', 'false') == 'true':
                return jsonify({'task': None, 'message': 'System paused'}), 200

            # Assign challenge (same logic as old /api/runners/{id}/task)
            challenge = self.db.assign_challenge(agent_id)

            if challenge:
                # Process frequency_ranges or manual_frequency_range if present
                config = challenge['config'].copy()
                frequency_ranges = config.get('frequency_ranges')
                manual_frequency_range = config.get('manual_frequency_range')

                if frequency_ranges:
                    selected_frequency = self.select_random_frequency(frequency_ranges)
                    if selected_frequency:
                        config['frequency'] = selected_frequency
                        config.pop('frequency_ranges', None)
                        logger.info(f"Selected random frequency {selected_frequency} Hz from ranges {frequency_ranges}")
                    else:
                        logger.error(f"Failed to select frequency from ranges: {frequency_ranges}")
                        return jsonify({'error': 'Invalid frequency range configuration'}), 500
                elif manual_frequency_range:
                    min_hz = manual_frequency_range.get('min_hz')
                    max_hz = manual_frequency_range.get('max_hz')
                    if min_hz and max_hz:
                        selected_frequency = float(random.randint(int(min_hz), int(max_hz)))
                        config['frequency'] = selected_frequency
                        config.pop('manual_frequency_range', None)
                        logger.info(f"Selected random frequency {selected_frequency} Hz from manual range {min_hz}-{max_hz}")
                    else:
                        logger.error(f"Invalid manual frequency range: {manual_frequency_range}")
                        return jsonify({'error': 'Invalid manual frequency range configuration'}), 500
                elif 'frequency' in config:
                    config['frequency'] = float(config['frequency'])

                # Broadcast assignment event
                self.broadcast_event('challenge_assigned', {
                    'runner_id': agent_id,
                    'agent_id': agent_id,
                    'challenge_id': challenge['challenge_id'],
                    'challenge_name': challenge['name'],
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })

                # TODO: Check if we should assign a listener to record this transmission
                # This will be implemented in the coordinated assignment logic

                return jsonify({
                    'task': {
                        'challenge_id': challenge['challenge_id'],
                        'name': challenge['name'],
                        'config': config
                    }
                }), 200
            else:
                return jsonify({'task': None, 'message': 'No challenges available'}), 200

        @self.app.route('/api/agents/<agent_id>/complete', methods=['POST'])
        @self.require_api_key
        @self.limiter.limit("1000 per minute")
        def agent_complete_task(agent_id):
            """Mark challenge as completed by runner agent."""
            if request.runner_id != agent_id:
                return jsonify({'error': 'Unauthorized'}), 403

            data = request.json
            if not data:
                return jsonify({'error': 'Missing request body'}), 400

            challenge_id = data.get('challenge_id')
            if not challenge_id:
                return jsonify({'error': 'Missing required field: challenge_id'}), 400

            success = data.get('success', False)
            if not isinstance(success, bool):
                return jsonify({'error': 'Field "success" must be a boolean'}), 400

            error_message = data.get('error_message')

            # Get challenge info
            challenge = self.db.get_challenge(challenge_id)
            challenge_name = challenge['name'] if challenge else challenge_id

            config = self.db.complete_challenge(challenge_id, agent_id, success, error_message)
            if not config:
                return jsonify({'error': 'Challenge not found'}), 404

            # Add to in-memory transmission buffer
            timestamp = datetime.now(timezone.utc).isoformat()
            transmission = {
                'started_at': timestamp,
                'runner_id': agent_id,
                'agent_id': agent_id,
                'challenge_id': challenge_id,
                'challenge_name': challenge_name,
                'frequency': config.get('frequency', 0),
                'status': 'success' if success else 'failed',
                'error_message': error_message
            }

            with self.transmission_lock:
                self.transmission_buffer.appendleft(transmission)

            # Broadcast completion event
            self.broadcast_event('transmission_complete', {
                'runner_id': agent_id,
                'agent_id': agent_id,
                'challenge_id': challenge_id,
                'challenge_name': challenge_name,
                'frequency': config.get('frequency', 0),
                'status': 'success' if success else 'failed',
                'error_message': error_message,
                'timestamp': timestamp
            })

            # Broadcast updated public challenges
            self.broadcast_public_challenges()

            return jsonify({'status': 'recorded'}), 200

        @self.app.route('/api/agents/<agent_id>/log', methods=['POST'])
        @self.require_api_key
        @self.limiter.limit("1000 per minute")
        def agent_upload_log(agent_id):
            """Receive log entries from agent (runner or listener)."""
            if request.runner_id != agent_id:
                return jsonify({'error': 'Unauthorized'}), 403

            data = request.json
            log_entry = data.get('log', {})

            # Create structured log event
            log_event = {
                'type': 'log',
                'source': agent_id,
                'level': log_entry.get('level', 'INFO'),
                'message': log_entry.get('message', ''),
                'timestamp': log_entry.get('timestamp', datetime.now(timezone.utc).isoformat())
            }

            # Store in log buffer
            if len(self.log_buffer) >= 1000:
                self.log_buffer.pop(0)
            self.log_buffer.append(log_event)

            # Broadcast log event to WebUI
            self.broadcast_event('log', log_event)

            return jsonify({'status': 'received'}), 200

        # Recording endpoints (for listener agents)
        @self.app.route('/api/agents/<agent_id>/recording/start', methods=['POST'])
        @self.require_api_key
        @self.limiter.limit("100 per minute")
        def recording_start(agent_id):
            """Listener reports recording has started."""
            if request.runner_id != agent_id:
                return jsonify({'error': 'Unauthorized'}), 403

            # Verify this is a listener agent
            agent = self.db.get_agent(agent_id)
            if not agent or agent['agent_type'] != 'listener':
                return jsonify({'error': 'Only listener agents can start recordings'}), 400

            data = request.json
            if not data:
                return jsonify({'error': 'Missing request body'}), 400

            challenge_id = data.get('challenge_id')
            transmission_id = data.get('transmission_id')
            frequency = data.get('frequency')
            sample_rate = data.get('sample_rate', 2000000)
            expected_duration = data.get('expected_duration', 30.0)

            if not all([challenge_id, transmission_id, frequency]):
                return jsonify({'error': 'Missing required fields'}), 400

            # Create recording entry
            recording_id = self.db.create_recording(
                challenge_id=challenge_id,
                agent_id=agent_id,
                transmission_id=transmission_id,
                frequency=int(frequency),
                sample_rate=int(sample_rate),
                expected_duration=float(expected_duration)
            )

            if recording_id > 0:
                # Broadcast recording started event
                self.broadcast_event('recording_started', {
                    'recording_id': recording_id,
                    'agent_id': agent_id,
                    'listener_id': agent_id,
                    'challenge_id': challenge_id,
                    'transmission_id': transmission_id,
                    'frequency': frequency,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })

                return jsonify({
                    'status': 'recording',
                    'recording_id': recording_id
                }), 200
            else:
                return jsonify({'error': 'Failed to create recording'}), 500

        @self.app.route('/api/agents/<agent_id>/recording/<int:recording_id>/complete', methods=['POST'])
        @self.require_api_key
        @self.limiter.limit("100 per minute")
        def recording_complete(agent_id, recording_id):
            """Listener reports recording has completed."""
            if request.runner_id != agent_id:
                return jsonify({'error': 'Unauthorized'}), 403

            data = request.json
            if not data:
                return jsonify({'error': 'Missing request body'}), 400

            success = data.get('success', False)
            error_message = data.get('error_message')
            duration = data.get('duration')
            image_width = data.get('image_width')
            image_height = data.get('image_height')

            # Note: image_path will be set after upload
            recording = self.db.get_recording(recording_id)
            if not recording:
                return jsonify({'error': 'Recording not found'}), 404

            if recording['agent_id'] != agent_id:
                return jsonify({'error': 'Unauthorized - recording belongs to different agent'}), 403

            # Update recording status
            updated = self.db.update_recording_complete(
                recording_id=recording_id,
                success=success,
                image_path=None,  # Will be set on upload
                image_width=image_width,
                image_height=image_height,
                duration=duration,
                error_message=error_message
            )

            if updated:
                # Broadcast recording completed event
                self.broadcast_event('recording_complete', {
                    'recording_id': recording_id,
                    'agent_id': agent_id,
                    'listener_id': agent_id,
                    'challenge_id': recording['challenge_id'],
                    'status': 'completed' if success else 'failed',
                    'error_message': error_message,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })

                return jsonify({'status': 'updated'}), 200
            else:
                return jsonify({'error': 'Failed to update recording'}), 500

        @self.app.route('/api/agents/<agent_id>/recording/<int:recording_id>/upload', methods=['POST'])
        @self.require_api_key
        @self.limiter.limit("20 per minute")  # Lower limit for file uploads
        def recording_upload(agent_id, recording_id):
            """Upload waterfall image for a recording."""
            if request.runner_id != agent_id:
                return jsonify({'error': 'Unauthorized'}), 403

            # Verify recording exists and belongs to this agent
            recording = self.db.get_recording(recording_id)
            if not recording:
                return jsonify({'error': 'Recording not found'}), 404

            if recording['agent_id'] != agent_id:
                return jsonify({'error': 'Unauthorized - recording belongs to different agent'}), 403

            # Check if file was uploaded
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400

            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400

            # Validate file type (PNG images only)
            if not file.filename.lower().endswith('.png'):
                return jsonify({'error': 'Only PNG images are allowed'}), 400

            # Create recordings directory if it doesn't exist
            import os
            recordings_dir = os.path.join(os.path.dirname(__file__), '..', 'recordings')
            os.makedirs(recordings_dir, exist_ok=True)

            # Save file with recording ID as filename
            filename = f"recording_{recording_id}.png"
            file_path = os.path.join(recordings_dir, filename)

            try:
                file.save(file_path)

                # Get image dimensions
                from PIL import Image
                with Image.open(file_path) as img:
                    width, height = img.size

                # Update recording with image path and dimensions
                self.db.update_recording_complete(
                    recording_id=recording_id,
                    success=True,
                    image_path=file_path,
                    image_width=width,
                    image_height=height,
                    duration=recording.get('duration_seconds')
                )

                logger.info(f"Uploaded waterfall image for recording {recording_id}: {width}x{height}px")

                return jsonify({
                    'status': 'uploaded',
                    'filename': filename,
                    'width': width,
                    'height': height
                }), 200

            except Exception as e:
                logger.error(f"Error saving recording image: {e}")
                return jsonify({'error': 'Failed to save image'}), 500

        # Recording query endpoints (admin)
        @self.app.route('/api/recordings', methods=['GET'])
        @self.require_admin_auth
        def get_recordings():
            """Get all recordings."""
            limit = request.args.get('limit', 100, type=int)
            recordings = self.db.get_all_recordings(limit=min(limit, 500))
            return jsonify({'recordings': recordings}), 200

        @self.app.route('/api/recordings/<int:recording_id>', methods=['GET'])
        @self.require_admin_auth
        def get_recording(recording_id):
            """Get specific recording details."""
            recording = self.db.get_recording(recording_id)
            if recording:
                return jsonify(recording), 200
            else:
                return jsonify({'error': 'Recording not found'}), 404

        @self.app.route('/api/recordings/<int:recording_id>/image', methods=['GET'])
        @self.require_admin_auth
        def get_recording_image(recording_id):
            """Serve waterfall image for a recording."""
            recording = self.db.get_recording(recording_id)
            if not recording:
                return jsonify({'error': 'Recording not found'}), 404

            image_path = recording.get('image_path')
            if not image_path:
                return jsonify({'error': 'No image available for this recording'}), 404

            import os
            from flask import send_file
            if os.path.exists(image_path):
                return send_file(image_path, mimetype='image/png')
            else:
                return jsonify({'error': 'Image file not found'}), 404

        @self.app.route('/api/challenges/<challenge_id>/recordings', methods=['GET'])
        @self.require_admin_auth
        def get_challenge_recordings(challenge_id):
            """Get recordings for a specific challenge."""
            limit = request.args.get('limit', 50, type=int)
            recordings = self.db.get_recordings_for_challenge(challenge_id, limit=min(limit, 200))
            return jsonify({'recordings': recordings}), 200

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

        # Enrollment token endpoints
        @self.app.route('/api/enrollment/token', methods=['POST'])
        @self.require_admin_auth
        @self.require_csrf
        def create_enrollment_token():
            """Generate a new enrollment token for runner registration.

            Request body:
                runner_name: Descriptive name for the runner
                expires_hours: Hours until token expires (default 24)

            Returns:
                token: The one-time enrollment token
                api_key: The API key to be used by the runner
                expires_at: When the token expires
            """
            data = request.json

            if not data or 'runner_name' not in data:
                return jsonify({'error': 'Missing runner_name'}), 400

            runner_name = data['runner_name']
            expires_hours = data.get('expires_hours', 24)

            # Generate a secure enrollment token
            enrollment_token = secrets.token_urlsafe(32)

            # Generate a secure API key for the runner
            api_key = secrets.token_urlsafe(48)

            # Calculate expiration time
            expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)

            # Get current user from session
            session_token = request.cookies.get('session_token')
            session = self.db.get_session(session_token)
            created_by = session['username'] if session else 'unknown'

            # Store the token in database
            success = self.db.create_enrollment_token(
                token=enrollment_token,
                runner_name=runner_name,
                created_by=created_by,
                expires_at=expires_at
            )

            if not success:
                return jsonify({'error': 'Failed to create enrollment token'}), 500

            logger.info(f"Created enrollment token for runner: {runner_name} by {created_by}")

            return jsonify({
                'token': enrollment_token,
                'api_key': api_key,
                'runner_name': runner_name,
                'expires_at': expires_at.isoformat(),
                'expires_hours': expires_hours
            }), 201

        @self.app.route('/api/enrollment/enroll', methods=['POST'])
        @self.limiter.limit("10 per hour")  # Limit enrollment attempts
        def enroll_runner():
            """Enroll a new runner using an enrollment token.

            Request body:
                enrollment_token: The enrollment token
                api_key: The API key provided with the token
                runner_id: Unique identifier for this runner
                hostname: Hostname of the runner
                mac_address: Optional MAC address of the runner
                machine_id: Optional machine ID of the runner
                devices: List of SDR devices

            Returns:
                success: Boolean indicating enrollment success
                runner_id: The enrolled runner ID
            """
            data = request.json

            if not data:
                return jsonify({'error': 'Missing request body'}), 400

            required_fields = ['enrollment_token', 'api_key', 'runner_id', 'hostname', 'devices']
            for field in required_fields:
                if field not in data:
                    return jsonify({'error': f'Missing required field: {field}'}), 400

            enrollment_token = data['enrollment_token']
            api_key = data['api_key']
            runner_id = data['runner_id']
            hostname = data['hostname']
            mac_address = data.get('mac_address')
            machine_id = data.get('machine_id')
            devices = data['devices']

            # Verify the enrollment token
            is_valid, runner_name = self.db.verify_enrollment_token(enrollment_token)

            if not is_valid:
                logger.warning(f"Invalid or expired enrollment token used from {request.remote_addr}")
                return jsonify({'error': 'Invalid or expired enrollment token'}), 401

            # Get token details to check if this is a re-enrollment
            token_details = self.db.get_enrollment_token(enrollment_token)
            is_re_enrollment = token_details and token_details.get('re_enrollment_for')

            # Check if runner_id already exists
            existing_runner = self.db.get_runner(runner_id)
            if existing_runner and existing_runner.get('api_key_hash') and not is_re_enrollment:
                return jsonify({'error': 'Runner ID already enrolled'}), 409

            # For re-enrollment, verify the runner_id matches
            if is_re_enrollment and is_re_enrollment != runner_id:
                logger.warning(f"Re-enrollment token for {is_re_enrollment} used with wrong runner_id {runner_id}")
                return jsonify({'error': 'Re-enrollment token does not match runner ID'}), 400

            # Register or update the runner with the API key and host identifiers
            success = self.db.register_runner(
                runner_id=runner_id,
                hostname=hostname,
                ip_address=request.remote_addr,
                mac_address=mac_address,
                machine_id=machine_id,
                devices=devices,
                api_key=api_key
            )

            if not success:
                return jsonify({'error': 'Failed to register runner'}), 500

            # Mark the token as used
            self.db.mark_token_used(enrollment_token, runner_id)

            logger.info(f"Runner {runner_id} ({runner_name}) enrolled successfully from {request.remote_addr} "
                       f"(MAC: {mac_address}, Machine ID: {machine_id})")

            # Broadcast event to WebUI
            self.broadcast_event('runner_enrolled', {
                'runner_id': runner_id,
                'runner_name': runner_name,
                'hostname': hostname,
                'mac_address': mac_address,
                'machine_id': machine_id,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })

            return jsonify({
                'success': True,
                'runner_id': runner_id,
                'message': f'Runner {runner_name} enrolled successfully'
            }), 201

        @self.app.route('/api/enrollment/tokens', methods=['GET'])
        @self.require_admin_auth
        def get_enrollment_tokens():
            """Get all enrollment tokens (for admin view)."""
            tokens = self.db.get_all_enrollment_tokens()
            return jsonify({'tokens': tokens}), 200

        @self.app.route('/api/enrollment/token/<token>', methods=['DELETE'])
        @self.require_admin_auth
        @self.require_csrf
        def delete_enrollment_token(token):
            """Delete an enrollment token."""
            success = self.db.delete_enrollment_token(token)

            if success:
                return jsonify({'status': 'deleted'}), 200
            else:
                return jsonify({'error': 'Token not found'}), 404

        @self.app.route('/api/enrollment/re-enroll/<runner_id>', methods=['POST'])
        @self.require_admin_auth
        @self.require_csrf
        def re_enroll_runner(runner_id):
            """Generate a fresh enrollment token for an existing runner.

            This allows re-enrollment of a runner on a different host or after
            the original credentials are compromised. Generates new enrollment
            token and API key.

            Args:
                runner_id: The runner ID to re-enroll
            Request body:
                expires_hours: Optional hours until token expires (default: 24)

            Returns:
                token: New enrollment token
                api_key: New API key
                expires_at: Token expiration timestamp
            """
            # Check if runner exists
            existing_runner = self.db.get_runner(runner_id)
            if not existing_runner:
                return jsonify({'error': 'Runner not found'}), 404

            data = request.json or {}
            expires_hours = data.get('expires_hours', 24)

            # Get current user from session
            session_token = request.cookies.get('session_token')
            session = self.db.get_session(session_token)
            username = session['username'] if session else 'unknown'

            # Generate new credentials
            new_api_key = self.generate_api_key()
            enrollment_token = secrets.token_urlsafe(32)
            expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)

            # Create enrollment token marked for re-enrollment
            success = self.db.create_enrollment_token(
                token=enrollment_token,
                runner_name=runner_id,  # Use runner_id as name for re-enrollment
                created_by=username,
                expires_at=expires_at,
                re_enrollment_for=runner_id  # Mark this as a re-enrollment token
            )

            if not success:
                return jsonify({'error': 'Failed to create enrollment token'}), 500

            logger.info(f"Re-enrollment token generated for runner {runner_id} by {username}")

            return jsonify({
                'token': enrollment_token,
                'api_key': new_api_key,
                'runner_id': runner_id,
                'expires_at': expires_at.isoformat(),
                'expires_hours': expires_hours
            }), 201

        # Provisioning API key management endpoints (admin only)
        @self.app.route('/api/provisioning/keys', methods=['POST'])
        @self.require_admin_auth
        @self.require_csrf
        def create_provisioning_key():
            """Create a new provisioning API key.

            Request body:
                key_id: Unique identifier for this key
                description: Human-readable description

            Returns:
                key_id: The key identifier
                api_key: The generated API key (only shown once!)
            """
            # Check create_provisioning_key permission
            if not self.db.has_permission(request.admin_username, 'create_provisioning_key'):
                self.log_security_event('Provisioning key creation denied', request.admin_username,
                                       level='warning', missing_permission='create_provisioning_key')
                return jsonify({'error': 'Permission denied: create_provisioning_key permission required'}), 403

            data = request.json or {}

            key_id = data.get('key_id')
            description = data.get('description', '')

            if not key_id:
                return jsonify({'error': 'Missing required field: key_id'}), 400

            # Validate key_id format (alphanumeric, hyphens, underscores)
            import re
            if not re.match(r'^[a-zA-Z0-9_-]+$', key_id):
                return jsonify({'error': 'key_id must contain only alphanumeric characters, hyphens, and underscores'}), 400

            # Get current user
            username = request.admin_username

            # Generate API key
            api_key = self.generate_api_key()

            # Create in database
            success = self.db.create_provisioning_api_key(key_id, api_key, description, username)

            if not success:
                return jsonify({'error': 'Failed to create provisioning key (key_id may already exist)'}), 409

            logger.info(f"Provisioning API key created: {key_id} by {username}")

            return jsonify({
                'key_id': key_id,
                'api_key': api_key,
                'description': description
            }), 201

        @self.app.route('/api/provisioning/keys', methods=['GET'])
        @self.require_admin_auth
        def list_provisioning_keys():
            """List all provisioning API keys (without the actual keys)."""
            keys = self.db.get_all_provisioning_api_keys()
            return jsonify({'keys': keys}), 200

        @self.app.route('/api/provisioning/keys/<key_id>', methods=['DELETE'])
        @self.require_admin_auth
        @self.require_csrf
        def delete_provisioning_key(key_id):
            """Delete a provisioning API key."""
            # Check create_provisioning_key permission
            if not self.db.has_permission(request.admin_username, 'create_provisioning_key'):
                self.log_security_event('Provisioning key deletion denied', request.admin_username,
                                       level='warning', missing_permission='create_provisioning_key')
                return jsonify({'error': 'Permission denied: create_provisioning_key permission required'}), 403

            success = self.db.delete_provisioning_api_key(key_id)

            if success:
                return jsonify({'status': 'deleted'}), 200
            else:
                return jsonify({'error': 'Key not found'}), 404

        @self.app.route('/api/provisioning/keys/<key_id>/toggle', methods=['POST'])
        @self.require_admin_auth
        @self.require_csrf
        def toggle_provisioning_key(key_id):
            """Enable or disable a provisioning API key."""
            # Check create_provisioning_key permission
            if not self.db.has_permission(request.admin_username, 'create_provisioning_key'):
                self.log_security_event('Provisioning key toggle denied', request.admin_username,
                                       level='warning', missing_permission='create_provisioning_key')
                return jsonify({'error': 'Permission denied: create_provisioning_key permission required'}), 403

            data = request.json or {}
            enabled = data.get('enabled', True)

            success = self.db.toggle_provisioning_api_key(key_id, enabled)

            if success:
                status = 'enabled' if enabled else 'disabled'
                return jsonify({'status': status}), 200
            else:
                return jsonify({'error': 'Key not found'}), 404

        # Provisioning endpoint (uses provisioning API key, no CSRF)
        @self.app.route('/api/provisioning/provision', methods=['POST'])
        @self.require_provisioning_key
        @self.limiter.limit("100 per hour")
        def provision_runner():
            """Provision a new runner - generates credentials and returns YAML config.

            This endpoint uses provisioning API key authentication (Bearer token).
            It generates enrollment credentials and returns a complete runner config.

            Request body:
                runner_name: Name for the runner
                runner_id: Unique ID for the runner (optional, defaults to runner_name)
                expires_hours: Hours until enrollment token expires (default: 24)
                server_url: Server URL for the config (optional, uses request origin)
                verify_ssl: SSL verification setting (default: true)
                devices: List of device configurations (optional)

            Returns:
                enrollment_token: Token for enrollment
                api_key: API key for authentication
                config_yaml: Complete runner configuration as YAML string
            """
            data = request.json or {}

            runner_name = data.get('runner_name')
            if not runner_name:
                return jsonify({'error': 'Missing required field: runner_name'}), 400

            runner_id = data.get('runner_id', runner_name)
            expires_hours = data.get('expires_hours', 24)
            server_url = data.get('server_url', request.host_url.rstrip('/'))
            verify_ssl = data.get('verify_ssl', True)
            devices = data.get('devices', [])

            # Get the provisioning key ID from request context
            created_by = f"provisioning:{request.provisioning_key_id}"

            # Generate credentials
            api_key = self.generate_api_key()
            enrollment_token = secrets.token_urlsafe(32)
            expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)

            # Create enrollment token
            success = self.db.create_enrollment_token(
                token=enrollment_token,
                runner_name=runner_name,
                created_by=created_by,
                expires_at=expires_at
            )

            if not success:
                return jsonify({'error': 'Failed to create enrollment token'}), 500

            # Generate complete YAML config
            config_yaml = f"""---
# ChallengeCtl Runner Configuration
# Provisioned for: {runner_name}
# Provisioned by: {request.provisioning_key_id}
# Generated: {datetime.now(timezone.utc).isoformat()}

runner:
  # Runner identification
  runner_id: "{runner_id}"

  # Server connection
  server_url: "{server_url}"

  # Enrollment credentials
  # Note: enrollment_token can be left in config, it will be ignored once enrolled
  enrollment_token: "{enrollment_token}"
  api_key: "{api_key}"

  # TLS/SSL Configuration
  ca_cert: ""
  verify_ssl: {str(verify_ssl).lower()}

  # Intervals
  heartbeat_interval: 30
  poll_interval: 10

  # Cache
  cache_dir: "cache"

  # Spectrum paint before challenges
  spectrum_paint_before_challenge: true

# Radio/SDR Device Configuration
radios:
  # Model defaults
  models:
  - model: hackrf
    rf_gain: 14
    if_gain: 32
    bias_t: true
    rf_samplerate: 2000000
    ppm: 0

  - model: bladerf
    rf_gain: 43
    bias_t: true
    rf_samplerate: 2000000
    ppm: 0

  - model: usrp
    rf_gain: 20
    bias_t: false
    rf_samplerate: 2000000
    ppm: 0

  # Individual devices
  devices:
"""

            # Add device configurations
            if devices:
                for device in devices:
                    config_yaml += f"  - name: {device.get('name', '0')}\n"
                    config_yaml += f"    model: {device.get('model', 'hackrf')}\n"
                    config_yaml += f"    rf_gain: {device.get('rf_gain', 14)}\n"

                    if device.get('model') == 'hackrf' and 'if_gain' in device:
                        config_yaml += f"    if_gain: {device.get('if_gain')}\n"

                    freq_limits = device.get('frequency_limits', [])
                    if freq_limits:
                        config_yaml += "    frequency_limits:\n"
                        for limit in freq_limits:
                            config_yaml += f"      - \"{limit}\"\n"
            else:
                # Default device if none specified
                config_yaml += """  - name: 0
    model: hackrf
    rf_gain: 14
    if_gain: 32
    frequency_limits:
      - "144000000-148000000"  # 2m ham band
      - "420000000-450000000"  # 70cm ham band
"""

            logger.info(f"Provisioned runner '{runner_name}' via key '{request.provisioning_key_id}'")

            return jsonify({
                'runner_name': runner_name,
                'runner_id': runner_id,
                'enrollment_token': enrollment_token,
                'api_key': api_key,
                'expires_at': expires_at.isoformat(),
                'config_yaml': config_yaml
            }), 201

        @self.app.route('/api/challenges', methods=['GET'])
        @self.require_admin_auth
        def get_challenges():
            """Get all challenges."""
            challenges = self.db.get_all_challenges()
            return jsonify({'challenges': challenges}), 200

        @self.app.route('/api/challenges', methods=['POST'])
        @self.require_admin_auth
        @self.require_csrf
        def create_challenge():
            """Create a new challenge."""
            data = request.json

            # Validate request body
            if not data:
                return jsonify({'error': 'Missing request body'}), 400

            # Validate required fields
            name = data.get('name')
            if not name:
                return jsonify({'error': 'Missing required field: name'}), 400

            config = data.get('config', {})
            if not isinstance(config, dict):
                return jsonify({'error': 'Field "config" must be a dictionary'}), 400

            # Validate required fields in config
            modulation = config.get('modulation')
            if not modulation:
                return jsonify({'error': 'Missing required field: modulation'}), 400

            # Validate timing configuration
            min_delay = config.get('min_delay')
            max_delay = config.get('max_delay')

            if min_delay is None:
                return jsonify({'error': 'Missing required field: min_delay'}), 400
            if max_delay is None:
                return jsonify({'error': 'Missing required field: max_delay'}), 400

            if min_delay > max_delay:
                return jsonify({'error': 'min_delay must be less than or equal to max_delay'}), 400

            # Validate frequency specification - exactly one required
            frequency = config.get('frequency')
            frequency_ranges = config.get('frequency_ranges')
            manual_frequency_range = config.get('manual_frequency_range')

            freq_specs_present = sum([
                frequency is not None,
                frequency_ranges is not None,
                manual_frequency_range is not None
            ])

            if freq_specs_present == 0:
                return jsonify({
                    'error': 'Missing frequency specification. Must provide one of: frequency, frequency_ranges, or manual_frequency_range'
                }), 400

            if freq_specs_present > 1:
                return jsonify({
                    'error': 'Multiple frequency specifications provided. Must provide exactly one of: frequency, frequency_ranges, or manual_frequency_range'
                }), 400

            # Validate frequency_ranges if provided
            if frequency_ranges is not None:
                if not isinstance(frequency_ranges, list) or len(frequency_ranges) == 0:
                    return jsonify({'error': 'frequency_ranges must be a non-empty array'}), 400

                # Validate that all ranges exist in configuration
                available_ranges = self.get_frequency_ranges()
                available_names = {r.get('name') for r in available_ranges}
                for range_name in frequency_ranges:
                    if range_name not in available_names:
                        return jsonify({
                            'error': f'Unknown frequency range: {range_name}. Available ranges: {", ".join(sorted(available_names))}'
                        }), 400

            # Validate manual_frequency_range if provided
            if manual_frequency_range is not None:
                if not isinstance(manual_frequency_range, dict):
                    return jsonify({'error': 'manual_frequency_range must be an object with min_hz and max_hz'}), 400

                min_hz = manual_frequency_range.get('min_hz')
                max_hz = manual_frequency_range.get('max_hz')

                if min_hz is None:
                    return jsonify({'error': 'manual_frequency_range.min_hz is required'}), 400
                if max_hz is None:
                    return jsonify({'error': 'manual_frequency_range.max_hz is required'}), 400

                if min_hz >= max_hz:
                    return jsonify({'error': 'manual_frequency_range.min_hz must be less than max_hz'}), 400

            # Ensure name is in config
            config['name'] = name

            # Generate challenge ID
            challenge_id = str(uuid.uuid4())

            # Add challenge to database
            success = self.db.add_challenge(challenge_id, name, config)

            if success:
                # Broadcast updated challenges to public dashboard
                self.broadcast_public_challenges()
                return jsonify({
                    'status': 'created',
                    'challenge_id': challenge_id
                }), 201
            else:
                return jsonify({'error': 'Challenge name already exists'}), 409

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

            # Validate timing configuration
            min_delay = config.get('min_delay')
            max_delay = config.get('max_delay')
            if min_delay is not None and max_delay is not None:
                if min_delay > max_delay:
                    return jsonify({'error': 'min_delay must be less than or equal to max_delay'}), 400

            success = self.db.update_challenge(challenge_id, config)

            if success:
                # Broadcast updated challenges to public dashboard
                self.broadcast_public_challenges()
                return jsonify({'status': 'updated'}), 200
            else:
                return jsonify({'error': 'Challenge not found'}), 404

        @self.app.route('/api/challenges/<challenge_id>', methods=['DELETE'])
        @self.require_admin_auth
        @self.require_csrf
        def delete_challenge(challenge_id):
            """Delete a challenge."""
            success = self.db.delete_challenge(challenge_id)

            if success:
                # Broadcast updated challenges to public dashboard
                self.broadcast_public_challenges()
                return jsonify({'status': 'deleted'}), 200
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

        @self.app.route('/api/challenges/import', methods=['POST'])
        @self.require_admin_auth
        @self.require_csrf
        def import_challenges():
            """Import challenges from uploaded YAML file with optional challenge files."""
            try:
                # Get YAML file from request
                if 'yaml_file' not in request.files:
                    return jsonify({'error': 'Missing yaml_file in request'}), 400

                yaml_file = request.files['yaml_file']
                if yaml_file.filename == '':
                    return jsonify({'error': 'No file selected'}), 400

                # Validate YAML file extension
                if not yaml_file.filename.lower().endswith(('.yml', '.yaml')):
                    return jsonify({'error': 'File must be a YAML file (.yml or .yaml)'}), 400

                # Parse YAML content
                yaml_content = yaml_file.read().decode('utf-8')
                try:
                    import yaml as yaml_lib
                    challenges_data = yaml_lib.safe_load(yaml_content)
                except Exception as e:
                    logger.error(f"Error parsing YAML: {e}")
                    return jsonify({'error': f'Invalid YAML format: {str(e)}'}), 400

                # Handle both list format and dict with 'challenges' key
                if isinstance(challenges_data, dict) and 'challenges' in challenges_data:
                    challenges_config = challenges_data['challenges']
                elif isinstance(challenges_data, list):
                    challenges_config = challenges_data
                else:
                    return jsonify({'error': 'YAML must contain a list of challenges or a dict with "challenges" key'}), 400

                # Process uploaded challenge files
                uploaded_files = {}
                for key in request.files:
                    if key != 'yaml_file':
                        file = request.files[key]
                        if file.filename:
                            # Save file using existing file upload mechanism
                            file_data = file.read()
                            file_hash = hashlib.sha256(file_data).hexdigest()

                            # Check file extension
                            allowed_extensions = {'.wav', '.bin', '.txt', '.yml', '.yaml', '.py', '.grc'}
                            file_ext = os.path.splitext(file.filename)[1].lower()
                            if file_ext not in allowed_extensions:
                                logger.warning(f"Skipping file with disallowed extension: {file.filename}")
                                continue

                            # Save file
                            file_path = os.path.join(self.files_dir, file_hash)
                            with open(file_path, 'wb') as f:
                                f.write(file_data)

                            # Register in database
                            self.db.add_file(file_hash, file.filename, len(file_data),
                                           file.content_type or 'application/octet-stream', file_path)

                            # Map original filename to hash for path substitution
                            uploaded_files[file.filename] = file_hash
                            logger.info(f"Uploaded file: {file.filename} -> {file_hash}")

                # Get existing challenges by name
                existing_challenges = {c['name']: c for c in self.db.get_all_challenges()}

                added = 0
                updated = 0
                errors = []

                for challenge in challenges_config:
                    if isinstance(challenge, dict) and 'name' in challenge:
                        name = challenge['name']

                        # Update file paths in challenge config if files were uploaded
                        if 'flag' in challenge and challenge['flag'] in uploaded_files:
                            # Store as file hash reference
                            challenge['flag_file_hash'] = uploaded_files[challenge['flag']]

                        # Validate timing configuration
                        min_delay = challenge.get('min_delay')
                        max_delay = challenge.get('max_delay')
                        if min_delay is not None and max_delay is not None:
                            if min_delay > max_delay:
                                errors.append(f"Challenge {name}: min_delay must be less than or equal to max_delay")
                                continue

                        try:
                            if name in existing_challenges:
                                # Update existing challenge
                                challenge_id = existing_challenges[name]['challenge_id']
                                if self.db.update_challenge(challenge_id, challenge):
                                    updated += 1
                                    logger.info(f"Updated challenge: {name}")
                                else:
                                    errors.append(f"Failed to update challenge: {name}")
                            else:
                                # Add new challenge
                                challenge_id = str(uuid.uuid4())
                                if self.db.add_challenge(challenge_id, name, challenge):
                                    added += 1
                                    logger.info(f"Added challenge: {name}")
                                else:
                                    errors.append(f"Failed to add challenge: {name}")
                        except Exception as e:
                            logger.error(f"Error processing challenge {name}: {e}")
                            errors.append(f"Error processing {name}: {str(e)}")

                # Broadcast updated challenges to public dashboard
                self.broadcast_public_challenges()

                response = {
                    'status': 'imported',
                    'added': added,
                    'updated': updated,
                    'files_uploaded': len(uploaded_files)
                }

                if errors:
                    response['errors'] = errors

                return jsonify(response), 200

            except Exception as e:
                logger.error(f"Error importing challenges: {e}", exc_info=True)
                return jsonify({'error': f'Failed to import challenges: {str(e)}'}), 500

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
                return jsonify({'error': 'Failed to reload challenges'}), 500

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
            # Clear auto_paused flag when manually pausing (manual override)
            self.db.set_system_state('auto_paused', 'false')

            self.broadcast_event('system_control', {
                'action': 'pause',
                'auto': False,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })

            return jsonify({'status': 'paused'}), 200

        @self.app.route('/api/control/resume', methods=['POST'])
        @self.require_admin_auth
        @self.require_csrf
        def resume_system():
            """Resume transmissions."""
            self.db.set_system_state('paused', 'false')
            # Clear auto_paused flag when manually resuming (manual override)
            self.db.set_system_state('auto_paused', 'false')

            self.broadcast_event('system_control', {
                'action': 'resume',
                'auto': False,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })

            return jsonify({'status': 'resumed'}), 200

        @self.app.route('/api/control/status', methods=['GET'])
        @self.require_admin_auth
        def get_control_status():
            """Get current system control status."""
            is_paused = self.db.get_system_state('paused', 'false') == 'true'
            return jsonify({'paused': is_paused}), 200

        # File management
        @self.app.route('/api/files/<file_hash>', methods=['GET'])
        @self.require_api_key
        @self.limiter.limit("500 per minute")  # Liberal limit for runner file downloads
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
        @self.limiter.limit("100 per minute")  # Moderate limit for file uploads
        def upload_file():
            """Upload a new challenge file with security restrictions.

            Supports both admin session authentication and runner API key authentication.
            """
            # Check authentication - accept either admin session or API key
            auth_valid = False

            # Try admin session auth first
            if 'session' in request.cookies:
                session_token = request.cookies.get('session')
                if session_token:
                    user_data = self.db.get_session(session_token)
                    if user_data:
                        auth_valid = True

            # If not authenticated via session, try API key
            if not auth_valid:
                auth_header = request.headers.get('Authorization')
                if auth_header and auth_header.startswith('Bearer '):
                    api_key = auth_header[7:]
                    runner = self.db.get_runner_by_api_key(api_key)
                    if runner:
                        auth_valid = True

            if not auth_valid:
                return jsonify({'error': 'Authentication required'}), 401

            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400

            file = request.files['file']

            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400

            # SECURITY: Validate file extension
            file_ext = os.path.splitext(file.filename)[1].lower()
            if file_ext not in self.ALLOWED_EXTENSIONS:
                self.log_security_event('File upload rejected', request.admin_username, level='warning',
                                       extension=file_ext, filename=file.filename)
                return jsonify({
                    'error': f'Invalid file type. Allowed: {", ".join(sorted(self.ALLOWED_EXTENSIONS))}'
                }), 400

            try:
                # SECURITY: Validate file size before reading entire file
                # Seek to end to get size, then back to beginning
                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)

                if file_size > self.MAX_FILE_SIZE:
                    max_mb = self.MAX_FILE_SIZE / (1024 * 1024)
                    actual_mb = file_size / (1024 * 1024)
                    self.log_security_event('File upload rejected', request.admin_username, level='warning',
                                           reason=f'size {actual_mb:.1f}MB exceeds limit {max_mb:.0f}MB',
                                           filename=file.filename)
                    return jsonify({
                        'error': f'File too large. Maximum size: {max_mb:.0f}MB'
                    }), 413

                # Read file data (now we know it's safe size)
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

                logger.info(
                    f"File uploaded successfully - hash={file_hash[:12]}... "
                    f"name={file.filename} size={file_size} from {request.remote_addr}"
                )

                return jsonify({
                    'status': 'uploaded',
                    'file_hash': file_hash,
                    'filename': file.filename,
                    'size': len(file_data)
                }), 200

            except Exception as e:
                logger.error(f"Error uploading file: {e}")
                return jsonify({'error': 'Internal server error'}), 500

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
            # SECURITY: Use safe_join to prevent path traversal attacks
            file_path = safe_join(self.frontend_dir, path)
            if file_path and os.path.isfile(file_path):
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
            # SECURITY: Use UTC for consistent timezone handling
            expires = datetime.fromisoformat(session['expires'])
            if datetime.utcnow() > expires:
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
                    'timestamp': datetime.now(timezone.utc).isoformat()
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
            # Support both new public_view format and old public_fields array format
            public_view = config.get('public_view')

            # Backwards compatibility: convert old public_fields array to public_view object
            if public_view is None and 'public_fields' in config:
                public_fields = config.get('public_fields', [])
                public_view = {
                    'show_modulation': 'modulation' in public_fields,
                    'show_frequency': 'frequency' in public_fields,
                    'show_last_tx_time': 'last_tx_time' in public_fields,
                    'show_active_status': 'status' in public_fields
                }
            elif public_view is None:
                # No visibility settings at all - default to showing all fields
                # for backwards compatibility with old challenges
                public_view = {
                    'show_modulation': True,
                    'show_frequency': True,
                    'show_last_tx_time': True,
                    'show_active_status': True
                }

            # Show modulation if enabled (default: True)
            if public_view.get('show_modulation', True):
                public_challenge['modulation'] = config.get('modulation', 'unknown')

            # Show frequency if enabled (default: True)
            if public_view.get('show_frequency', True):
                frequency = config.get('frequency')
                frequency_ranges = config.get('frequency_ranges')
                manual_frequency_range = config.get('manual_frequency_range')

                if frequency:
                    # Format frequency in MHz for readability
                    freq_mhz = frequency / 1_000_000
                    public_challenge['frequency'] = frequency
                    public_challenge['frequency_display'] = f"{freq_mhz:.3f} MHz"
                elif frequency_ranges:
                    # Show named frequency ranges with display names
                    public_challenge['frequency_ranges'] = frequency_ranges
                    # Get display names for the ranges
                    display_names = []
                    for range_name in frequency_ranges:
                        # Look up the display name from config
                        freq_range_config = next(
                            (r for r in self.get_frequency_ranges() if r.get('name') == range_name),
                            None
                        )
                        if freq_range_config and 'display_name' in freq_range_config:
                            display_names.append(freq_range_config['display_name'])
                        else:
                            display_names.append(range_name)
                    public_challenge['frequency_display'] = ', '.join(display_names)
                elif manual_frequency_range:
                    # Show manual frequency range
                    min_hz = manual_frequency_range.get('min_hz')
                    max_hz = manual_frequency_range.get('max_hz')
                    if min_hz and max_hz:
                        min_mhz = min_hz / 1_000_000
                        max_mhz = max_hz / 1_000_000
                        public_challenge['manual_frequency_range'] = manual_frequency_range
                        public_challenge['frequency_display'] = f"{min_mhz:.3f}-{max_mhz:.3f} MHz"

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
                'timestamp': datetime.now(timezone.utc).isoformat()
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
