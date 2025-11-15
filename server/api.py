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
from datetime import datetime
from typing import Dict, Any
import uuid

from database import Database

logger = logging.getLogger(__name__)


class ChallengeCtlAPI:
    """Main API server for challengectl."""

    def __init__(self, config_path: str, db_path: str, files_dir: str):
        self.app = Flask(__name__, static_folder='../frontend/dist', static_url_path='')
        self.app.config['SECRET_KEY'] = os.urandom(24)

        # Enable CORS for development
        CORS(self.app)

        # Initialize SocketIO for real-time updates
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")

        # Database
        self.db = Database(db_path)

        # Configuration
        self.config = self.load_config(config_path)
        self.api_keys = self.config.get('server', {}).get('api_keys', {})
        self.files_dir = files_dir

        # Ensure files directory exists
        os.makedirs(self.files_dir, exist_ok=True)

        # Register routes
        self.register_routes()
        self.register_socketio_handlers()

        logger.info("ChallengeCtl API initialized")

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

    def require_api_key(self, f):
        """Decorator to require API key authentication."""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization')

            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({'error': 'Missing or invalid authorization header'}), 401

            api_key = auth_header[7:]  # Remove 'Bearer ' prefix

            # Find runner_id or role for this API key
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

    def register_routes(self):
        """Register all API routes."""

        # Health check (no auth required)
        @self.app.route('/api/health', methods=['GET'])
        def health_check():
            return jsonify({
                'status': 'ok',
                'timestamp': datetime.now().isoformat()
            })

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
            runner_id = request.runner_id

            hostname = data.get('hostname', '')
            ip_address = request.remote_addr
            devices = data.get('devices', [])

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
            challenge_id = data.get('challenge_id')
            success = data.get('success', False)
            error_message = data.get('error_message')
            # device_id and frequency are logged but not currently used
            # device_id = data.get('device_id', '')
            # frequency = data.get('frequency', 0)

            # Record transmission in history
            if success:
                self.db.complete_challenge(challenge_id, runner_id, success, error_message)

            # Broadcast completion event
            self.broadcast_event('transmission_complete', {
                'runner_id': runner_id,
                'challenge_id': challenge_id,
                'status': 'success' if success else 'failed',
                'error_message': error_message,
                'timestamp': datetime.now().isoformat()
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

            # Broadcast log event to WebUI
            self.broadcast_event('log', {
                'source': runner_id,
                'level': log_entry.get('level', 'INFO'),
                'message': log_entry.get('message', ''),
                'timestamp': log_entry.get('timestamp', datetime.now().isoformat())
            })

            return jsonify({'status': 'received'}), 200

        # Admin/WebUI endpoints
        @self.app.route('/api/dashboard', methods=['GET'])
        @self.require_api_key
        def get_dashboard():
            """Get dashboard statistics and data."""
            stats = self.db.get_dashboard_stats()
            runners = self.db.get_all_runners()
            recent_transmissions = self.db.get_recent_transmissions(limit=20)

            # Parse runner devices JSON
            for runner in runners:
                if runner.get('devices'):
                    import json
                    runner['devices'] = json.loads(runner['devices'])

            return jsonify({
                'stats': stats,
                'runners': runners,
                'recent_transmissions': recent_transmissions
            }), 200

        @self.app.route('/api/runners', methods=['GET'])
        @self.require_api_key
        def get_runners():
            """Get all registered runners."""
            runners = self.db.get_all_runners()

            # Parse devices JSON
            for runner in runners:
                if runner.get('devices'):
                    import json
                    runner['devices'] = json.loads(runner['devices'])

            return jsonify({'runners': runners}), 200

        @self.app.route('/api/runners/<runner_id>', methods=['GET'])
        @self.require_api_key
        def get_runner_details(runner_id):
            """Get details for a specific runner."""
            runner = self.db.get_runner(runner_id)

            if runner:
                if runner.get('devices'):
                    import json
                    runner['devices'] = json.loads(runner['devices'])
                return jsonify(runner), 200
            else:
                return jsonify({'error': 'Runner not found'}), 404

        @self.app.route('/api/runners/<runner_id>', methods=['DELETE'])
        @self.require_api_key
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
        @self.require_api_key
        def get_challenges():
            """Get all challenges."""
            challenges = self.db.get_all_challenges()
            return jsonify({'challenges': challenges}), 200

        @self.app.route('/api/challenges/<challenge_id>', methods=['GET'])
        @self.require_api_key
        def get_challenge_details(challenge_id):
            """Get challenge details."""
            challenge = self.db.get_challenge(challenge_id)

            if challenge:
                return jsonify(challenge), 200
            else:
                return jsonify({'error': 'Challenge not found'}), 404

        @self.app.route('/api/challenges/<challenge_id>', methods=['PUT'])
        @self.require_api_key
        def update_challenge(challenge_id):
            """Update challenge configuration."""
            data = request.json
            config = data.get('config', {})

            success = self.db.update_challenge(challenge_id, config)

            if success:
                return jsonify({'status': 'updated'}), 200
            else:
                return jsonify({'error': 'Challenge not found'}), 404

        @self.app.route('/api/challenges/<challenge_id>/enable', methods=['POST'])
        @self.require_api_key
        def enable_challenge(challenge_id):
            """Enable or disable a challenge."""
            data = request.json
            enabled = data.get('enabled', True)

            success = self.db.enable_challenge(challenge_id, enabled)

            if success:
                return jsonify({'status': 'updated'}), 200
            else:
                return jsonify({'error': 'Challenge not found'}), 404

        @self.app.route('/api/challenges/<challenge_id>/trigger', methods=['POST'])
        @self.require_api_key
        def trigger_challenge(challenge_id):
            """Manually trigger a challenge to transmit immediately."""
            # Update next_tx_time to now
            challenge = self.db.get_challenge(challenge_id)

            if challenge:
                with self.db.get_connection() as conn:
                    conn.execute('''
                        UPDATE challenges
                        SET next_tx_time = CURRENT_TIMESTAMP,
                            status = 'queued'
                        WHERE challenge_id = ?
                    ''', (challenge_id,))
                    conn.commit()

                return jsonify({'status': 'triggered'}), 200
            else:
                return jsonify({'error': 'Challenge not found'}), 404

        @self.app.route('/api/challenges/reload', methods=['POST'])
        @self.require_api_key
        def reload_challenges():
            """Reload challenges from configuration file."""
            try:
                config = self.load_config('server-config.yml')
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
        @self.require_api_key
        def get_transmissions():
            """Get transmission history."""
            limit = request.args.get('limit', 50, type=int)
            transmissions = self.db.get_recent_transmissions(limit=limit)
            return jsonify({'transmissions': transmissions}), 200

        @self.app.route('/api/control/pause', methods=['POST'])
        @self.require_api_key
        def pause_system():
            """Pause all transmissions."""
            self.db.set_system_state('paused', 'true')

            self.broadcast_event('system_control', {
                'action': 'pause',
                'timestamp': datetime.now().isoformat()
            })

            return jsonify({'status': 'paused'}), 200

        @self.app.route('/api/control/resume', methods=['POST'])
        @self.require_api_key
        def resume_system():
            """Resume transmissions."""
            self.db.set_system_state('paused', 'false')

            self.broadcast_event('system_control', {
                'action': 'resume',
                'timestamp': datetime.now().isoformat()
            })

            return jsonify({'status': 'resumed'}), 200

        @self.app.route('/api/control/emergency-stop', methods=['POST'])
        @self.require_api_key
        def emergency_stop():
            """Emergency stop all operations."""
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
                'action': 'emergency_stop',
                'timestamp': datetime.now().isoformat()
            })

            return jsonify({'status': 'emergency_stopped'}), 200

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
        @self.app.route('/')
        @self.app.route('/<path:path>')
        def serve_frontend(path='index.html'):
            """Serve the Vue.js frontend."""
            frontend_dir = os.path.join(self.app.static_folder)

            # If frontend is built, serve it
            if os.path.exists(frontend_dir):
                if path and os.path.exists(os.path.join(frontend_dir, path)):
                    return send_from_directory(frontend_dir, path)
                else:
                    return send_from_directory(frontend_dir, 'index.html')
            else:
                return jsonify({
                    'message': 'Frontend not built. Run `cd frontend && npm run build`'
                }), 404

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

    def run(self, host='0.0.0.0', port=8443, debug=False, ssl_cert=None, ssl_key=None):
        """Run the API server.

        Note: Direct SSL support with eventlet is not reliable. For production,
        use nginx or another reverse proxy for TLS termination.
        """

        if ssl_cert or ssl_key:
            logger.warning("Direct SSL/TLS not supported with eventlet backend")
            logger.warning("For TLS, use nginx or a reverse proxy (see DEPLOYMENT.md)")

        logger.info(f"Starting ChallengeCtl API server on http://{host}:{port}")
        logger.info("For production with TLS, use nginx reverse proxy")

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
    api = ChallengeCtlAPI(config_path, db_path, files_dir)
    return api.app, api.socketio
