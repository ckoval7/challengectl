# Webhook Management

This guide covers the Webhook Management interface in ChallengeCtl, which enables real-time notifications to Discord channels for system events. Webhooks provide automated alerting for critical events like transmission failures, runner status changes, and security events.

## Table of Contents

- [Overview](#overview)
- [Accessing Webhooks](#accessing-webhooks)
- [Creating a Webhook](#creating-a-webhook)
- [Event Category Subscriptions](#event-category-subscriptions)
- [Managing Webhooks](#managing-webhooks)
- [Testing Webhooks](#testing-webhooks)
- [Discord Embed Format](#discord-embed-format)
- [Troubleshooting](#troubleshooting)

## Overview

Webhooks deliver real-time event notifications from ChallengeCtl to external services like Discord. When subscribed events occur (such as a runner going offline or a transmission failing), the system automatically sends formatted messages to your configured Discord channels.

**Key benefits**:
- **Real-time alerts**: Instant notifications without polling or checking the web interface
- **Category-based filtering**: Subscribe only to events you care about
- **Discord integration**: Rich embed formatting with color-coding and structured fields
- **Delivery tracking**: Monitor webhook deliveries and troubleshoot failures
- **Multiple webhooks**: Configure different webhooks for different event categories or Discord channels

**Use cases**:
- Alert administrators when runners go offline
- Notify teams of transmission failures
- Track security events like failed logins
- Monitor system pause/resume events during multi-day conferences

## Accessing Webhooks

### Permission Requirements

To access webhook management, you must have the `manage_webhooks` permission. This permission allows you to:
- View all configured webhooks
- Create new webhooks
- Edit existing webhooks
- Delete webhooks
- Test webhook delivery

See [Web Interface - User Management](Web-Interface-Users) for information on granting permissions.

### Navigation

Access webhook management from the main navigation:

1. Log in to the ChallengeCtl web interface
2. Click **"Webhooks"** in the main navigation menu (left sidebar)
3. The Webhooks page displays a table of all configured webhooks

## Creating a Webhook

### Step 1: Get a Discord Webhook URL

Before creating a webhook in ChallengeCtl, you need to obtain a webhook URL from Discord:

**In Discord**:

1. Open the Discord server where you want to receive notifications
2. Navigate to the channel where notifications should appear
3. Click the channel settings (gear icon)
4. Select **"Integrations"** from the left menu
5. Click **"Webhooks"** → **"New Webhook"**
6. Configure the webhook:
   - **Name**: Give it a descriptive name (e.g., "ChallengeCtl Alerts")
   - **Channel**: Verify the correct channel is selected
   - **Avatar**: Optionally upload an avatar image
7. Click **"Copy Webhook URL"** to copy the webhook URL to your clipboard
8. Click **"Save Changes"**

The webhook URL will look like: `https://discord.com/api/webhooks/123456789/abcdef...`

**Important**: Keep webhook URLs secure. Anyone with the URL can send messages to your Discord channel.

### Step 2: Create Webhook in ChallengeCtl

**In ChallengeCtl**:

1. Click the **"Create Webhook"** button (top-right of the Webhooks page)
2. Fill in the webhook form:
   - **Name**: Descriptive name for this webhook (e.g., "Production Discord Alerts")
   - **Discord Webhook URL**: Paste the URL you copied from Discord
   - **Description** (optional): Additional notes about this webhook's purpose
   - **Enabled**: Toggle to enable/disable the webhook (default: enabled)
3. Select event categories to subscribe to (see [Event Category Subscriptions](#event-category-subscriptions) below)
4. Click **"Create"** to save the webhook

The webhook will immediately begin receiving events for the selected categories.

## Event Category Subscriptions

When creating or editing a webhook, you can subscribe to specific event categories. Each category groups related events:

### Available Event Categories

| Category | Description | Example Events |
|----------|-------------|----------------|
| **error_logs** | System and runner error messages | Server crashes, database errors, critical failures |
| **server_lifecycle** | Server start, stop, restart events | Server started successfully, server shutting down |
| **agent_status** | Runner/listener online/offline/enabled/disabled | Runner went offline, listener connected, runner disabled by admin |
| **device_changes** | SDR device detection and removal | HackRF detected on runner-1, Device unplugged from runner-2 |
| **challenge_failures** | Failed transmissions and errors | Transmission failed on runner-1, SDR device error during challenge |
| **recording_complete** | Listener recording completions | Waterfall image captured for NBFM_FLAG_1, recording uploaded successfully |
| **security_events** | Authentication failures, enrollment, credential issues | Failed login attempt, API key authentication failed, enrollment token used |
| **user_management** | User creation, deletion, password resets | New user created, password reset for admin, user account disabled |
| **system_control** | Pause/resume, auto-pause events | System paused, system auto-resumed (within daily hours), manual resume |
| **daily_schedule** | Daily start/end events | Day started (auto-resume), day ended (auto-pause) |

### Selecting Categories

Use checkboxes to select which categories should trigger webhook deliveries:

- **Select all**: Subscribe to all event categories (comprehensive monitoring)
- **Select specific categories**: Choose only the events you care about (reduces notification volume)
- **None selected**: Webhook will not deliver any events (useful for testing webhook configuration before enabling)

**Recommendation**: Start with critical categories (`error_logs`, `challenge_failures`, `security_events`) and add others as needed.

## Managing Webhooks

The Webhooks page displays all configured webhooks in a table with the following information:

### Webhook Table Columns

- **Name**: Webhook display name
- **Discord Webhook URL**: Truncated URL preview (hover to see full URL)
- **Status**: Enabled (green) or Disabled (gray)
- **Events**: Number of subscribed event categories (hover to see category list)
- **Deliveries**:
  - Total deliveries count (green badge)
  - Failed deliveries count (red badge, shown only if >0)
- **Last Triggered**: Timestamp of most recent webhook delivery (or "Never" if not yet triggered)
- **Actions**: Dropdown menu with available actions

### Available Actions

Click the **"Actions"** dropdown for each webhook to access these operations:

#### Test Webhook

Sends a test message to the Discord webhook to verify configuration.

**Test message format**:
```
Title: "ChallengeCtl Test Message"
Description: "This is a test message from ChallengeCtl. Your webhook is configured correctly!"
```

**What to check**:
- Message appears in the correct Discord channel
- Formatting displays correctly
- Color and embed structure match expectations

If the test fails, check:
- Webhook URL is correct
- Discord webhook still exists (not deleted in Discord)
- Network connectivity from server to Discord
- Webhook delivery statistics for error details

#### Edit

Opens the edit dialog to modify webhook configuration:

**Editable fields**:
- Name
- Discord Webhook URL
- Description
- Event category subscriptions
- Enabled status

**Note**: You cannot change the webhook URL if there are pending deliveries. Wait for deliveries to complete or create a new webhook.

#### Enable/Disable

Toggles the webhook enabled status:

- **Disable**: Webhook stops receiving events but configuration is preserved
- **Enable**: Webhook resumes receiving events for subscribed categories

**Use cases**:
- Temporarily disable webhook during maintenance
- Disable webhook during testing to avoid notification spam
- Enable webhook only during live events

#### Delete

Permanently removes the webhook from ChallengeCtl.

**Warning**: This action cannot be undone. All webhook configuration and delivery history will be deleted.

**Before deleting**:
- Consider disabling instead of deleting if you might re-enable later
- Ensure no other administrators rely on this webhook's notifications
- Optionally download delivery statistics for record-keeping

## Testing Webhooks

Always test webhooks after creating or modifying them to ensure correct configuration.

### Testing Process

1. Click **"Actions"** → **"Test Webhook"** for the webhook
2. Check the Discord channel for the test message
3. Verify the message appears with correct formatting
4. Check webhook delivery statistics for success confirmation

### Test Message Delivery

Successful test delivery:
- Test message appears in Discord within 2-3 seconds
- "Total deliveries" count increments by 1
- "Last Triggered" timestamp updates
- Success notification appears in ChallengeCtl interface

Failed test delivery:
- Error notification appears in ChallengeCtl interface
- "Failed deliveries" count increments by 1
- Check Troubleshooting section below for common issues

### Automatic Retry

Webhook deliveries automatically retry on failure:
- **Retry attempts**: Up to 3 retries
- **Retry delays**: 5 seconds, 10 seconds, 20 seconds (exponential backoff)
- **After 3 failures**: Delivery marked as failed, webhook remains enabled

## Discord Embed Format

ChallengeCtl sends events to Discord as rich embeds with color-coding and structured fields.

### Embed Structure

Each webhook delivery includes:

**Title**: Event type (e.g., "Transmission Failed", "Runner Offline")

**Description**: Event details and context

**Color**: Category-specific color for quick visual identification

**Fields**: Structured data specific to the event type

**Timestamp**: When the event occurred (server timezone)

### Color Coding by Category

| Category | Color | Hex Code |
|----------|-------|----------|
| error_logs | Red | #E74C3C |
| server_lifecycle | Blue | #3498DB |
| agent_status | Purple | #9B59B6 |
| device_changes | Orange | #F39C12 |
| challenge_failures | Dark Orange | #E67E22 |
| recording_complete | Green | #2ECC71 |
| security_events | Dark Red | #C0392B |
| user_management | Turquoise | #1ABC9C |
| system_control | Yellow | #F1C40F |
| daily_schedule | Gray | #95A5A6 |

### Example Embed: Challenge Failure

```
[Dark Orange] Transmission Failed
Runner: runner-1
Challenge: NBFM_FLAG_1
Frequency: 146.550 MHz
Error: SDR device timeout
Timestamp: 2025-04-05 14:32:15
```

### Example Embed: Runner Status Change

```
[Purple] Runner Offline
Runner: runner-2
Previous Status: online
Last Heartbeat: 2 minutes ago
Timestamp: 2025-04-05 14:35:00
```

## Troubleshooting

### Webhook Not Delivering

**Symptom**: Events occur but no messages appear in Discord

**Checks**:

1. **Webhook enabled**: Verify webhook status is "Enabled" (green tag)
2. **Event subscriptions**: Ensure webhook is subscribed to relevant event categories
3. **Discord webhook valid**: Test the webhook URL directly in Discord settings
4. **Failed deliveries**: Check "Failed deliveries" count in webhook table
5. **Network connectivity**: Verify server can reach Discord API (`discord.com`)

**Common causes**:
- Webhook disabled in ChallengeCtl
- Discord webhook deleted from Discord settings
- Network firewall blocking outbound HTTPS to Discord
- Invalid webhook URL (typo, extra characters)

### Discord Rate Limiting

**Symptom**: Some webhook deliveries fail with "rate limit" errors

**Discord rate limits**:
- 30 messages per minute per webhook URL
- 5 global requests per second

**Solutions**:
- Reduce number of subscribed event categories
- Use multiple webhooks to distribute load
- Configure different webhooks for different event types
- Contact Discord support if legitimate use requires higher limits

**Monitoring**:
- Check "Failed deliveries" count for rate limit errors
- High failed delivery count may indicate rate limiting
- Discord will respond with 429 status code when rate limited

### Invalid Webhook URL

**Symptom**: Test webhook fails immediately with "Invalid URL" error

**Checks**:
1. URL starts with `https://discord.com/api/webhooks/` or `https://discordapp.com/api/webhooks/`
2. URL includes both webhook ID and token (long alphanumeric string)
3. No extra spaces or characters in URL
4. Webhook still exists in Discord (not deleted)

**Fix**: Copy the webhook URL again from Discord settings and update in ChallengeCtl

### High Failed Delivery Count

**Symptom**: "Failed deliveries" count grows over time

**Investigation**:

1. Check webhook "Last Triggered" timestamp - if recent, webhook is receiving events
2. Verify Discord webhook still exists in Discord channel settings
3. Test the webhook using "Test Webhook" action
4. Check server logs for delivery error details
5. Verify webhook URL has not changed in Discord

**Resolution**:
- Update webhook URL if changed in Discord
- Delete and recreate webhook if Discord webhook was deleted
- Investigate network connectivity issues if all webhooks failing
- Contact administrator if delivery errors persist

### Webhook Deliveries Not Updating

**Symptom**: "Total deliveries" and "Last Triggered" not updating

**Checks**:
1. Verify events are actually occurring (check Dashboard, Logs page)
2. Confirm webhook is subscribed to categories for occurring events
3. Check webhook is enabled (green status)
4. Refresh the page to ensure UI is up-to-date

**Note**: Delivery statistics update in real-time but may take a few seconds to refresh in the UI.

## Programmatic Access

Webhooks can also be managed programmatically via the REST API. See [API Reference - Webhook Management](API-Reference#webhook-management) for endpoint documentation.

## Related Guides

- [Implementing Permissions](Implementing-Permissions) - How to grant `manage_webhooks` permission
- [Web Interface - User Management](Web-Interface-Users) - Managing user permissions
- [API Reference](API-Reference) - Webhook API endpoints for automation
- [Architecture Overview](Architecture) - Technical details of webhook dispatcher

## Best Practices

1. **Use descriptive names**: Name webhooks clearly (e.g., "Production Alerts", "Security Events Only")
2. **Test before deploying**: Always test webhooks before enabling for production use
3. **Subscribe selectively**: Only subscribe to event categories you need to reduce notification volume
4. **Monitor delivery statistics**: Periodically check failed delivery counts
5. **Separate webhooks by purpose**: Use different webhooks for different event types or teams
6. **Document webhook purpose**: Use the description field to note webhook purpose and owner
7. **Secure webhook URLs**: Treat webhook URLs as secrets - anyone with the URL can send messages to your Discord channel
8. **Regular testing**: Periodically test webhooks to ensure continued functionality
