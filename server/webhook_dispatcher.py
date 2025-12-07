#!/usr/bin/env python3
"""
Webhook dispatcher for Discord notifications.
Handles asynchronous webhook delivery with retry logic and auto-disable on repeated failures.
"""

import logging
import threading
import queue
import time
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# Discord embed color scheme
DISCORD_COLORS = {
    'error_logs': 0xE74C3C,        # Red
    'server_lifecycle': 0x3498DB,  # Blue
    'agent_status': 0x9B59B6,      # Purple
    'device_changes': 0xF39C12,    # Orange
    'challenge_failures': 0xE67E22, # Dark Orange
    'recording_complete': 0x2ECC71, # Green
    'security_events': 0xC0392B,    # Dark Red
    'user_management': 0x1ABC9C,    # Turquoise
    'system_control': 0xF1C40F,     # Yellow
    'daily_schedule': 0x95A5A6      # Gray
}


class WebhookDispatcher:
    """Manages asynchronous webhook delivery to Discord."""

    def __init__(self, db, max_retries=3, retry_delay=5):
        """Initialize webhook dispatcher.

        Args:
            db: Database instance
            max_retries: Maximum retry attempts per webhook
            retry_delay: Base delay in seconds between retries (exponential backoff)
        """
        self.db = db
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Thread-safe queue for webhook events
        self.event_queue = queue.Queue(maxsize=1000)

        # Track if worker is currently processing an event
        self._processing = False
        self._processing_lock = threading.Lock()

        # Start background worker thread
        self.worker_thread = threading.Thread(target=self._worker, daemon=True, name="WebhookDispatcher")
        self.worker_thread.start()
        logger.info("Webhook dispatcher worker thread started")

    def dispatch_event(self, event_type: str, event_data: Dict[str, Any], category: str):
        """Queue an event for webhook delivery.

        Args:
            event_type: System event type (e.g., 'transmission_complete', 'log')
            event_data: Event payload
            category: Event category for subscription filtering (e.g., 'challenge_failures')
        """
        try:
            self.event_queue.put_nowait({
                'event_type': event_type,
                'event_data': event_data,
                'category': category,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            logger.debug(f"Queued webhook event: category={category}, type={event_type}")
        except queue.Full:
            logger.warning(f"Webhook event queue full, dropping event: {category}/{event_type}")

    def flush(self, timeout=10):
        """Wait for all queued webhook events to be delivered.

        This method waits for both:
        1. The queue to be empty (all events dequeued)
        2. The worker to finish processing the current event

        Args:
            timeout: Maximum time to wait in seconds (default: 10)
        """
        logger.info("Flushing webhook queue...")
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                remaining = self.event_queue.qsize()
                with self._processing_lock:
                    processing = self._processing
                if remaining > 0 or processing:
                    logger.warning(f"Webhook flush timeout - {remaining} events queued, processing={processing}")
                break

            # Check if queue is empty AND worker is not processing
            queue_empty = self.event_queue.empty()
            with self._processing_lock:
                processing = self._processing

            if queue_empty and not processing:
                break

            time.sleep(0.1)

        logger.info("Webhook queue flushed")

    def _worker(self):
        """Background worker thread to process webhook deliveries."""
        logger.info("Webhook dispatcher worker started")
        while True:
            try:
                event = self.event_queue.get(timeout=1)

                # Mark as processing
                with self._processing_lock:
                    self._processing = True

                try:
                    self._process_event(event)
                finally:
                    # Mark as done processing
                    with self._processing_lock:
                        self._processing = False

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in webhook worker: {e}", exc_info=True)
                # Ensure processing flag is cleared even on error
                with self._processing_lock:
                    self._processing = False

    def _process_event(self, event: Dict[str, Any]):
        """Process a single event and deliver to subscribed webhooks.

        Args:
            event: Event dictionary with type, data, category, timestamp
        """
        category = event['category']

        # Get all enabled webhooks subscribed to this category
        webhooks = self.db.get_webhooks_for_category(category)

        if not webhooks:
            logger.debug(f"No webhooks subscribed to category: {category}")
            return

        logger.debug(f"Delivering webhook event to {len(webhooks)} webhook(s): {category}")

        # Build Discord embed
        embed = self._build_discord_embed(event)

        # Deliver to each webhook
        for webhook in webhooks:
            self._deliver_webhook(webhook, embed, event)

    def _deliver_webhook(self, webhook: Dict[str, Any], embed: Dict[str, Any], event: Dict[str, Any]):
        """Deliver webhook with retry logic.

        Args:
            webhook: Webhook configuration dictionary
            embed: Discord embed payload
            event: Event data for logging
        """
        webhook_id = webhook['webhook_id']
        url = webhook['url']

        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    url,
                    json={"embeds": [embed]},
                    timeout=10,
                    headers={'Content-Type': 'application/json'}
                )

                # Discord returns 204 No Content on success
                if response.status_code == 204:
                    # Record success
                    self.db.record_webhook_success(webhook_id)
                    logger.debug(f"Webhook {webhook_id} ({webhook['name']}) delivered successfully")
                    return
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.warning(f"Webhook {webhook_id} delivery failed: {error_msg}")

                    if attempt < self.max_retries - 1:
                        # Exponential backoff
                        sleep_time = self.retry_delay * (attempt + 1)
                        time.sleep(sleep_time)
                    else:
                        # Record failure (max retries exhausted)
                        self.db.record_webhook_failure(webhook_id, error_msg)
                        logger.error(f"Webhook {webhook_id} delivery failed after {self.max_retries} attempts")

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Webhook {webhook_id} delivery error (attempt {attempt + 1}): {error_msg}")

                if attempt < self.max_retries - 1:
                    sleep_time = self.retry_delay * (attempt + 1)
                    time.sleep(sleep_time)
                else:
                    # Record failure (max retries exhausted)
                    self.db.record_webhook_failure(webhook_id, error_msg)

    def _build_discord_embed(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Build Discord embed from event data.

        Args:
            event: Event dictionary with category, event_type, event_data, timestamp

        Returns:
            Discord embed dictionary
        """
        category = event['category']
        event_type = event['event_type']
        data = event['event_data']
        timestamp = event['timestamp']

        # Get color for category
        color = DISCORD_COLORS.get(category, 0x95A5A6)  # Default to gray

        # Build embed based on category
        if category == 'error_logs':
            return self._build_error_log_embed(data, color, timestamp)
        elif category == 'server_lifecycle':
            return self._build_server_lifecycle_embed(data, color, timestamp)
        elif category == 'agent_status':
            return self._build_agent_status_embed(data, color, timestamp)
        elif category == 'device_changes':
            return self._build_device_changes_embed(data, event_type, color, timestamp)
        elif category == 'challenge_failures':
            return self._build_challenge_failure_embed(data, color, timestamp)
        elif category == 'recording_complete':
            return self._build_recording_complete_embed(data, color, timestamp)
        elif category == 'security_events':
            return self._build_security_event_embed(data, color, timestamp)
        elif category == 'user_management':
            return self._build_user_management_embed(data, event_type, color, timestamp)
        elif category == 'system_control':
            return self._build_system_control_embed(data, color, timestamp)
        elif category == 'daily_schedule':
            return self._build_daily_schedule_embed(data, color, timestamp)
        else:
            # Generic fallback
            return {
                "title": f"System Event: {event_type}",
                "description": str(data),
                "color": color,
                "timestamp": timestamp,
                "footer": {"text": "ChallengeCtl v2"}
            }

    def _build_error_log_embed(self, data: Dict[str, Any], color: int, timestamp: str) -> Dict[str, Any]:
        """Build Discord embed for error logs."""
        level = data.get('level', 'ERROR')
        message = data.get('message', '')
        source = data.get('source', 'server')

        # Extract challenge/agent info if present
        fields = [
            {"name": "Source", "value": source, "inline": True},
            {"name": "Level", "value": level, "inline": True}
        ]

        # Add message
        if len(message) > 1000:
            message = message[:997] + "..."

        fields.append({"name": "Message", "value": message, "inline": False})

        return {
            "title": f"⚠️ {level} Log",
            "description": f"{level} level event detected",
            "color": color,
            "fields": fields,
            "timestamp": timestamp,
            "footer": {"text": "ChallengeCtl v2"}
        }

    def _build_server_lifecycle_embed(self, data: Dict[str, Any], color: int, timestamp: str) -> Dict[str, Any]:
        """Build Discord embed for server startup/shutdown."""
        action = data.get('action', 'unknown')

        if action == 'startup':
            return {
                "title": "🚀 Server Started",
                "description": "ChallengeCtl server is now online",
                "color": color,
                "timestamp": timestamp,
                "footer": {"text": "ChallengeCtl v2"}
            }
        elif action == 'shutdown':
            return {
                "title": "🛑 Server Stopped",
                "description": "ChallengeCtl server is shutting down",
                "color": color,
                "timestamp": timestamp,
                "footer": {"text": "ChallengeCtl v2"}
            }
        else:
            return {
                "title": "Server Event",
                "description": f"Server {action}",
                "color": color,
                "timestamp": timestamp,
                "footer": {"text": "ChallengeCtl v2"}
            }

    def _build_agent_status_embed(self, data: Dict[str, Any], color: int, timestamp: str) -> Dict[str, Any]:
        """Build Discord embed for agent status changes."""
        agent_id = data.get('agent_id', 'unknown')
        status = data.get('status', 'unknown')
        agent_type = data.get('agent_type', 'agent')

        status_emoji = {
            'online': '🟢',
            'offline': '🔴',
            'busy': '🟡'
        }.get(status, '⚪')

        fields = [
            {"name": "Agent", "value": agent_id, "inline": True},
            {"name": "Type", "value": agent_type.capitalize(), "inline": True},
            {"name": "Status", "value": status.capitalize(), "inline": True}
        ]

        return {
            "title": f"{status_emoji} {agent_type.capitalize()} {agent_id} {status.capitalize()}",
            "description": f"{agent_type.capitalize()} {agent_id} is now {status}",
            "color": color,
            "fields": fields,
            "timestamp": timestamp,
            "footer": {"text": "ChallengeCtl v2"}
        }

    def _build_device_changes_embed(self, data: Dict[str, Any], event_type: str, color: int, timestamp: str) -> Dict[str, Any]:
        """Build Discord embed for device changes."""
        device_id = data.get('device_id', 'unknown')
        agent_id = data.get('agent_id', 'unknown')
        model = data.get('model', 'unknown')

        if event_type == 'device_detected':
            return {
                "title": "🔌 Device Detected",
                "description": f"New device detected on {agent_id}",
                "color": color,
                "fields": [
                    {"name": "Device", "value": device_id, "inline": True},
                    {"name": "Model", "value": model, "inline": True},
                    {"name": "Agent", "value": agent_id, "inline": True}
                ],
                "timestamp": timestamp,
                "footer": {"text": "ChallengeCtl v2"}
            }
        elif event_type == 'device_status':
            status = data.get('status', 'unknown')
            return {
                "title": "📡 Device Status Changed",
                "description": f"Device {device_id} status updated",
                "color": color,
                "fields": [
                    {"name": "Device", "value": device_id, "inline": True},
                    {"name": "Status", "value": status, "inline": True},
                    {"name": "Agent", "value": agent_id, "inline": True}
                ],
                "timestamp": timestamp,
                "footer": {"text": "ChallengeCtl v2"}
            }
        else:
            return {
                "title": "⚙️ Device Configuration Updated",
                "description": f"Device {device_id} configuration changed",
                "color": color,
                "fields": [
                    {"name": "Device", "value": device_id, "inline": True},
                    {"name": "Agent", "value": agent_id, "inline": True}
                ],
                "timestamp": timestamp,
                "footer": {"text": "ChallengeCtl v2"}
            }

    def _build_challenge_failure_embed(self, data: Dict[str, Any], color: int, timestamp: str) -> Dict[str, Any]:
        """Build Discord embed for challenge transmission failures."""
        challenge_name = data.get('challenge_name', 'unknown')
        agent_id = data.get('agent_id', 'unknown')
        frequency = data.get('frequency', 0)
        device_id = data.get('device_id', 'unknown')
        error = data.get('error_message', 'Unknown error')

        # Format frequency
        freq_mhz = frequency / 1_000_000 if frequency else 0

        fields = [
            {"name": "Challenge", "value": challenge_name, "inline": True},
            {"name": "Frequency", "value": f"{freq_mhz:.3f} MHz", "inline": True},
            {"name": "Agent", "value": agent_id, "inline": True},
            {"name": "Device", "value": device_id, "inline": True},
            {"name": "Error", "value": error[:1000], "inline": False}
        ]

        return {
            "title": "❌ Challenge Transmission Failed",
            "description": f"{challenge_name} failed on {agent_id}",
            "color": color,
            "fields": fields,
            "timestamp": timestamp,
            "footer": {"text": "ChallengeCtl v2"}
        }

    def _build_recording_complete_embed(self, data: Dict[str, Any], color: int, timestamp: str) -> Dict[str, Any]:
        """Build Discord embed for recording completion."""
        challenge_name = data.get('challenge_name', 'unknown')
        frequency = data.get('frequency', 0)
        agent_id = data.get('agent_id', 'unknown')
        duration = data.get('duration', 0)

        # Format frequency
        freq_mhz = frequency / 1_000_000 if frequency else 0

        fields = [
            {"name": "Challenge", "value": challenge_name, "inline": True},
            {"name": "Frequency", "value": f"{freq_mhz:.3f} MHz", "inline": True},
            {"name": "Listener", "value": agent_id, "inline": True},
            {"name": "Duration", "value": f"{duration:.1f}s", "inline": True}
        ]

        return {
            "title": "📷 New Recording Available",
            "description": f"Waterfall recording completed for {challenge_name}",
            "color": color,
            "fields": fields,
            "timestamp": timestamp,
            "footer": {"text": "ChallengeCtl v2"}
        }

    def _build_security_event_embed(self, data: Dict[str, Any], color: int, timestamp: str) -> Dict[str, Any]:
        """Build Discord embed for security events."""
        message = data.get('message', '')

        # Extract security event type from message
        if 'Failed login' in message or 'failed login' in message.lower():
            title = "🔒 Security Alert: Failed Login"
        elif 'Permission denied' in message:
            title = "🔒 Security Alert: Permission Denied"
        elif 'TOTP' in message:
            title = "🔒 Security Alert: 2FA Issue"
        else:
            title = "🔒 Security Alert"

        # Try to extract details from message
        fields = []
        if 'username' in data:
            fields.append({"name": "Username", "value": data['username'], "inline": True})

        return {
            "title": title,
            "description": message[:1000],
            "color": color,
            "fields": fields,
            "timestamp": timestamp,
            "footer": {"text": "ChallengeCtl v2 • Security"}
        }

    def _build_user_management_embed(self, data: Dict[str, Any], event_type: str, color: int, timestamp: str) -> Dict[str, Any]:
        """Build Discord embed for user management events."""
        username = data.get('username', 'unknown')

        if event_type == 'user_created':
            changed_by = data.get('created_by', 'unknown')
            return {
                "title": "👤 User Created",
                "description": f"New user account created: {username}",
                "color": color,
                "fields": [
                    {"name": "Username", "value": username, "inline": True},
                    {"name": "Created By", "value": changed_by, "inline": True}
                ],
                "timestamp": timestamp,
                "footer": {"text": "ChallengeCtl v2"}
            }
        elif event_type == 'user_deleted':
            changed_by = data.get('deleted_by', 'unknown')
            return {
                "title": "👤 User Deleted",
                "description": f"User account deleted: {username}",
                "color": color,
                "fields": [
                    {"name": "Username", "value": username, "inline": True},
                    {"name": "Deleted By", "value": changed_by, "inline": True}
                ],
                "timestamp": timestamp,
                "footer": {"text": "ChallengeCtl v2"}
            }
        elif event_type == 'user_enabled':
            changed_by = data.get('changed_by', 'unknown')
            return {
                "title": "✅ User Enabled",
                "description": f"User account enabled: {username}",
                "color": color,
                "fields": [
                    {"name": "Username", "value": username, "inline": True},
                    {"name": "Changed By", "value": changed_by, "inline": True}
                ],
                "timestamp": timestamp,
                "footer": {"text": "ChallengeCtl v2"}
            }
        elif event_type == 'user_disabled':
            changed_by = data.get('changed_by', 'unknown')
            return {
                "title": "🚫 User Disabled",
                "description": f"User account disabled: {username}",
                "color": color,
                "fields": [
                    {"name": "Username", "value": username, "inline": True},
                    {"name": "Changed By", "value": changed_by, "inline": True}
                ],
                "timestamp": timestamp,
                "footer": {"text": "ChallengeCtl v2"}
            }
        elif event_type == 'permission_granted':
            permission = data.get('permission', 'unknown')
            granted_by = data.get('granted_by', 'unknown')
            return {
                "title": "🔑 Permission Granted",
                "description": f"Permission granted to {username}",
                "color": color,
                "fields": [
                    {"name": "Username", "value": username, "inline": True},
                    {"name": "Permission", "value": permission, "inline": True},
                    {"name": "Granted By", "value": granted_by, "inline": True}
                ],
                "timestamp": timestamp,
                "footer": {"text": "ChallengeCtl v2"}
            }
        elif event_type == 'permission_revoked':
            permission = data.get('permission', 'unknown')
            revoked_by = data.get('revoked_by', 'unknown')
            return {
                "title": "🔓 Permission Revoked",
                "description": f"Permission revoked from {username}",
                "color": color,
                "fields": [
                    {"name": "Username", "value": username, "inline": True},
                    {"name": "Permission", "value": permission, "inline": True},
                    {"name": "Revoked By", "value": revoked_by, "inline": True}
                ],
                "timestamp": timestamp,
                "footer": {"text": "ChallengeCtl v2"}
            }
        else:
            return {
                "title": "👥 User Management Event",
                "description": f"User management action: {event_type}",
                "color": color,
                "timestamp": timestamp,
                "footer": {"text": "ChallengeCtl v2"}
            }

    def _build_system_control_embed(self, data: Dict[str, Any], color: int, timestamp: str) -> Dict[str, Any]:
        """Build Discord embed for system pause/resume."""
        action = data.get('action', 'unknown')
        # Support both 'username' (from manual actions) and 'changed_by' (legacy)
        changed_by = data.get('username') or data.get('changed_by', 'system')
        is_auto = data.get('auto', False)

        if action == 'pause':
            reason = "Automatic" if is_auto else "Manual"
            return {
                "title": "⏸️ System Paused",
                "description": "Challenge transmissions have been paused",
                "color": color,
                "fields": [
                    {"name": "Paused By", "value": changed_by, "inline": True},
                    {"name": "Reason", "value": reason, "inline": True}
                ],
                "timestamp": timestamp,
                "footer": {"text": "ChallengeCtl v2"}
            }
        elif action == 'resume':
            reason = "Automatic" if is_auto else "Manual"
            fields = [
                {"name": "Resumed By", "value": changed_by, "inline": True},
                {"name": "Reason", "value": reason, "inline": True}
            ]
            return {
                "title": "▶️ System Resumed",
                "description": "Challenge transmissions have been resumed",
                "color": color,
                "fields": fields,
                "timestamp": timestamp,
                "footer": {"text": "ChallengeCtl v2"}
            }
        else:
            return {
                "title": "⚙️ System Control",
                "description": f"System {action}",
                "color": color,
                "timestamp": timestamp,
                "footer": {"text": "ChallengeCtl v2"}
            }

    def _build_daily_schedule_embed(self, data: Dict[str, Any], color: int, timestamp: str) -> Dict[str, Any]:
        """Build Discord embed for daily schedule auto-pause/resume."""
        action = data.get('action', 'unknown')

        if action == 'auto_pause':
            return {
                "title": "🌙 End of Day Reached",
                "description": "System automatically paused based on daily schedule",
                "color": color,
                "timestamp": timestamp,
                "footer": {"text": "ChallengeCtl v2 • Auto-Pause"}
            }
        elif action == 'auto_resume':
            return {
                "title": "🌅 Start of Day Reached",
                "description": "System automatically resumed based on daily schedule",
                "color": color,
                "timestamp": timestamp,
                "footer": {"text": "ChallengeCtl v2 • Auto-Resume"}
            }
        else:
            return {
                "title": "📅 Daily Schedule Event",
                "description": f"Daily schedule {action}",
                "color": color,
                "timestamp": timestamp,
                "footer": {"text": "ChallengeCtl v2"}
            }

    def test_webhook(self, url: str) -> Dict[str, Any]:
        """Test a webhook URL by sending a test message.

        Args:
            url: Discord webhook URL

        Returns:
            Dict with 'status', 'http_status', and optional 'error'
        """
        embed = {
            "title": "🧪 Test Message",
            "description": "This is a test message from ChallengeCtl",
            "color": 0x3498DB,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "footer": {"text": "ChallengeCtl v2 • Test"}
        }

        try:
            response = requests.post(
                url,
                json={"embeds": [embed]},
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )

            if response.status_code == 204:
                return {
                    'status': 'success',
                    'http_status': 204,
                    'message': 'Test message delivered successfully'
                }
            else:
                return {
                    'status': 'failed',
                    'http_status': response.status_code,
                    'error': response.text[:500]
                }
        except Exception as e:
            return {
                'status': 'failed',
                'http_status': 0,
                'error': str(e)
            }
