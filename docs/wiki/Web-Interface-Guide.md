# Web Interface Guide

This guide covers the ChallengeCtl web interface, explaining how to monitor system status, manage challenges and runners, and control system operation through the browser-based dashboard.

## Table of Contents

- [Overview](#overview)
- [Accessing the Web Interface](#accessing-the-web-interface)
- [Dashboard](#dashboard)
- [Runners Management](#runners-management)
- [Challenges Management](#challenges-management)
- [Logs Viewer](#logs-viewer)
- [User Management](#user-management)
- [System Controls](#system-controls)
- [Real-Time Updates](#real-time-updates)

## Overview

The ChallengeCtl web interface provides a comprehensive view of your RF challenge distribution system. It allows administrators to monitor system health, manage runners and challenges, view real-time logs, and control system operation without needing to edit configuration files or restart services.

### Key Features

- **Real-time monitoring**: Live updates via WebSocket connections
- **Challenge management**: Enable, disable, and manually trigger challenges
- **Runner control**: Monitor runner status and manage connections
- **Log streaming**: Real-time logs from server and all runners
- **User administration**: Manage admin accounts and credentials
- **System controls**: Pause, resume, and stop operations

## Accessing the Web Interface

### Login Process

1. **Navigate to the server URL** in your web browser:
   ```
   http://your-server-ip:8443
   ```
   Or for production deployments:
   ```
   https://challengectl.example.com
   ```

2. **Enter your credentials**:
   - Username: Your admin username
   - Password: Your admin password

3. **Complete two-factor authentication**:
   - Enter the 6-digit TOTP code from your authenticator app
   - The code refreshes every 30 seconds

4. **Access the dashboard**:
   - Upon successful authentication, you'll be directed to the main dashboard

### Session Management

- **Session duration**: Sessions remain active for 24 hours
- **Auto-logout**: Sessions expire after 24 hours of inactivity
- **Manual logout**: Click the "Logout" button in the navigation bar
- **Multiple sessions**: You can be logged in from multiple browsers/devices simultaneously

## Dashboard

The dashboard provides an overview of system status and recent activity.

### Statistics Panel

The top section displays key metrics:

**Total Runners**: Number of registered runners (includes online and offline)

**Active Runners**: Number of runners currently online and available
- Green indicator: Healthy system
- Yellow indicator: Some runners offline
- Red indicator: No runners available

**Total Challenges**: Number of configured challenges in the system

**Enabled Challenges**: Number of challenges currently active
- Shows how many challenges are eligible for transmission

**Total Transmissions**: Cumulative count of all completed transmissions since server start

### Recent Transmissions Feed

The lower section shows real-time transmission activity:

**Columns**:
- **Challenge**: Name of the transmitted challenge
- **Runner**: Which runner executed the transmission
- **Frequency**: Transmission frequency in Hz (displayed as MHz)
- **Modulation**: Type of modulation used
- **Status**: Success or failure indicator
- **Timestamp**: When the transmission completed

**Status Indicators**:
- Green checkmark: Successful transmission
- Red X: Failed transmission (hover for error details)

**Auto-refresh**: The feed updates automatically as transmissions complete via WebSocket events.

## Runners Management

The Runners page displays all registered runners and their current status.

### Runner List

Each runner shows:

**Runner ID**: Unique identifier for the runner

**Status**: Current connection state
- **Online** (green): Runner is active and sending heartbeats
- **Busy** (yellow): Runner is currently executing a transmission
- **Offline** (red): Runner has stopped sending heartbeats or disconnected

**Last Heartbeat**: Timestamp of the most recent heartbeat
- Updates in real-time
- Shows "Never" if runner registered but never sent a heartbeat

**Frequency Limits**: Supported frequency ranges
- Displayed as frequency ranges in Hz
- Determines which challenges this runner can accept

**Current Task**: Name of challenge currently being executed
- Shows "None" when idle
- Shows challenge name when busy

### Runner Actions

**Enable Runner**: Allow the runner to receive task assignments
- Enabled runners will be included in task distribution
- Button shows "Enabled" when active

**Disable Runner**: Prevent the runner from receiving new tasks
- Disabled runners remain connected but won't receive assignments
- Currently executing tasks continue to completion
- Use this for maintenance or troubleshooting
- Button shows "Disabled" when inactive

**Kick Runner**: Forcibly disconnect the runner
- Immediately removes the runner from the system
- Any assigned tasks are requeued
- The runner can re-register automatically
- Use this to resolve stuck runners or force a reconnection

### When to Disable vs Kick

**Disable a runner when**:
- Performing maintenance on the SDR hardware
- Troubleshooting signal quality issues
- Temporarily taking the device offline
- Testing with a subset of runners

**Kick a runner when**:
- The runner appears stuck or unresponsive
- Forcing a clean reconnection
- The runner's configuration has changed
- Clearing a stuck state

**Key difference**: Disabled runners stay connected but idle. Kicked runners are forcibly disconnected and must re-register.

## Challenges Management

The Challenges page allows you to control which challenges are active and manually trigger transmissions.

### Challenge List

Each challenge displays:

**Challenge Name**: Unique identifier

**Frequency**: Transmission frequency in Hz (displayed as MHz)

**Modulation**: Modulation type (CW, NBFM, SSB, FHSS, etc.)

**State**: Current challenge state
- **Queued**: Waiting for delay period to elapse before marking as waiting
- **Waiting**: Ready to be assigned to a runner
- **Assigned**: Currently being executed by a runner
- **Disabled**: Challenge is not active

**Last Run**: Timestamp of most recent transmission
- Shows "Never" if challenge hasn't been transmitted yet
- Updates in real-time as transmissions complete

**Delays**: Min and max delay between transmissions in seconds
- Format: "60-90s" means 60 to 90 seconds between transmissions

### Challenge Actions

**Enable Challenge**: Activate the challenge for automatic transmission
- Enabled challenges will be queued for transmission
- The system randomly waits between min_delay and max_delay before transmitting
- Button shows "Enabled" when active

**Disable Challenge**: Deactivate the challenge
- Disabled challenges will not be queued
- If currently assigned, the transmission completes before disabling
- Use this to remove challenges from rotation
- Button shows "Disabled" when inactive

**Trigger Now**: Manually queue the challenge for immediate transmission
- Bypasses the delay timer
- Queues the challenge as "waiting" immediately
- The next available compatible runner will execute it
- Use this for testing or demonstrations
- Does not affect the regular scheduling cycle

**Edit Challenge**: Modify challenge parameters (if supported)
- Adjust min/max delays
- Enable/disable public visibility settings
- Changes take effect immediately

### Challenge Workflow

1. **Disabled**: Challenge exists in configuration but is inactive
2. **Enabled**: Challenge is activated and enters the queue
3. **Queued**: Waiting for random delay period (between min_delay and max_delay)
4. **Waiting**: Ready for assignment, available to compatible runners
5. **Assigned**: A runner has claimed the task and is executing
6. **Completed**: Transmission finished, returns to queued state

**Note**: The cycle repeats continuously for enabled challenges.

## Logs Viewer

The Logs page provides real-time log streaming from the server and all connected runners.

### Log Display

**Columns**:
- **Timestamp**: When the log entry was created
- **Source**: Where the log originated (server or runner ID)
- **Level**: Log severity (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **Message**: The log message content

**Color Coding**:
- **Gray**: DEBUG messages
- **White**: INFO messages
- **Yellow**: WARNING messages
- **Red**: ERROR and CRITICAL messages

### Filtering Logs

**By Source**:
- **All**: Show logs from server and all runners
- **Server**: Show only server logs
- **Runner ID**: Show logs from a specific runner

**By Level**:
- **All**: Show all log levels
- **INFO and above**: Hide DEBUG messages
- **WARNING and above**: Show only warnings and errors
- **ERROR only**: Show only errors

### Log Features

**Auto-scroll**: Automatically scroll to newest entries
- Toggle on/off with the auto-scroll button
- Disable to review historical logs

**Search**: Filter logs by text search
- Searches across all columns
- Case-insensitive
- Updates in real-time

**Export**: Download logs for offline analysis
- Exports currently filtered logs
- CSV format
- Includes timestamp, source, level, and message

### Common Log Patterns

**Normal Operation**:
```
[INFO] Runner runner-1 registered successfully
[INFO] Challenge NBFM_FLAG_1 assigned to runner-1
[INFO] Challenge NBFM_FLAG_1 completed successfully
```

**Warning Signs**:
```
[WARNING] Runner runner-1 heartbeat timeout warning
[WARNING] No runners available for challenge assignment
```

**Errors**:
```
[ERROR] Challenge transmission failed: Device not found
[ERROR] Database lock timeout
[ERROR] File not found: challenges/missing.wav
```

## User Management

The Users page allows you to manage admin accounts with username/password and TOTP authentication.

### User List

Displays all admin users with:
- **Username**: Login name
- **Created**: Account creation timestamp
- **Actions**: Add, edit, delete buttons

### User Operations

**Add User**:
1. Click "Add User" button
2. Enter username and password
3. Save to create the account
4. A TOTP secret is generated automatically
5. Display the QR code to the user for authenticator app setup
6. Store the TOTP secret securely

**Edit User**:
- Change password
- The user's current session remains active

**Delete User**:
- Permanently removes the account
- User is immediately logged out
- Cannot delete your own account (prevents lockout)

**Reset TOTP**:
- Generates a new TOTP secret
- Use when a user loses access to their authenticator app
- Displays a new QR code for setup
- Old TOTP codes immediately become invalid

**Reset Password**:
- Set a new password for a user
- User is not automatically logged out
- User should log out and log back in with new password

### User Security

**Password Requirements**:
- Minimum 8 characters
- Should include uppercase, lowercase, numbers, and symbols
- Passwords are bcrypt hashed (never stored in plaintext)

**TOTP Requirements**:
- Required for all admin accounts
- 6-digit codes rotate every 30 seconds
- Use any TOTP-compatible authenticator app
- Secrets are encrypted in the database

## System Controls

System controls affect the entire ChallengeCtl server and all runners.

### Accessing System Controls

System control buttons are located in the **header bar** at the top of every page:

- **Pause button**: Visible when system is running normally
- **Resume button**: Visible when system is paused (replaces Pause button)

### Pause vs Disable

Understanding the differences between these operations is critical:

#### Pause System

**What it does**:
- Stops queuing new challenges
- Allows currently executing transmissions to complete
- Runners remain connected and send heartbeats
- Web interface remains accessible
- No data is lost

**When to use**:
- Taking a break during a CTF event
- Waiting for an issue to be resolved
- Coordinating with CTF participants
- Performing non-invasive maintenance

**How to resume**:
- Click "Resume" button
- Challenge queueing resumes immediately
- System returns to normal operation

**Effect on**:
- **Active transmissions**: Continue to completion
- **Waiting challenges**: Remain in waiting state (not reassigned)
- **Queued challenges**: Stop advancing to waiting state
- **Runners**: Stay connected and idle
- **Web UI**: Fully functional

**Note**: To shut down the ChallengeCtl server, use `Ctrl+C` in the terminal or `systemctl stop challengectl` if running as a service.

#### Disable (Runner-specific)

**What it does**:
- Prevents a specific runner from receiving new tasks
- Runner remains connected
- Runner continues sending heartbeats
- Active transmission on that runner completes
- Other runners are unaffected

**When to use**:
- Troubleshooting a specific runner
- SDR hardware maintenance
- Adjusting antenna or device settings
- Testing with subset of runners

**How to resume**:
- Click "Enable" on the runner

**Effect on**:
- **This runner's active transmission**: Completes normally
- **This runner's new tasks**: None assigned
- **Other runners**: Unaffected
- **System**: Continues normal operation

### Comparison Table

| Operation | New Tasks | Active Tasks | Runners Connected | Web UI | Restart Required |
|-----------|-----------|--------------|-------------------|--------|------------------|
| **Pause** | Stopped | Complete | Yes | Yes | No |
| **Stop** | Stopped | Requeued | Yes | Yes | No |
| **Disable Runner** | Stopped (1 runner) | Complete | Yes | Yes | No |

### Reload Configuration

**What it does**:
- Reloads `server-config.yml` from disk
- Updates challenge definitions
- Adds new challenges
- Updates parameters for existing challenges
- Does not require server restart

**When to use**:
- Adding new challenges during an event
- Adjusting min/max delays
- Enabling/disabling challenges via config file
- Fixing challenge file paths

**What it doesn't affect**:
- Runner connections
- Active transmissions
- Server settings (port, CORS, etc.)
- Database state
- User accounts

**Limitations**:
- Cannot change server port or binding
- Cannot change database location
- Cannot modify API keys (requires restart)

## Real-Time Updates

The web interface uses WebSocket connections for real-time updates without page refreshes.

### What Updates in Real-Time

**Dashboard**:
- Statistics counters
- Recent transmissions feed
- Runner online/offline status

**Runners Page**:
- Runner status (online, busy, offline)
- Last heartbeat timestamps
- Current task assignments

**Challenges Page**:
- Challenge state changes (queued, waiting, assigned)
- Last run timestamps
- Enable/disable status

**Logs Page**:
- New log entries from server and runners
- Continuous log streaming

### WebSocket Connection Status

**Connected**: Green indicator in the top-right corner
- Updates flow normally
- No action needed

**Disconnected**: Red indicator in the top-right corner
- Updates stop
- Page data becomes stale
- Browser automatically attempts to reconnect

**Reconnecting**: Yellow indicator
- Connection lost, attempting to restore
- Wait a few seconds for automatic reconnection

### If WebSocket Fails

1. **Check your network connection**: Ensure you're connected to the network
2. **Refresh the page**: Force reconnection by reloading
3. **Check server logs**: Look for WebSocket errors
4. **Verify reverse proxy**: If using nginx, ensure WebSocket proxying is configured
5. **Manual refresh**: You can still use the interface, but you'll need to manually refresh pages

## Tips and Best Practices

### Event Management

**Before the event**:
- Test all challenges with "Trigger Now"
- Verify all runners are online and enabled
- Set up log filtering to reduce noise
- Create backup admin accounts

**During the event**:
- Monitor the dashboard for anomalies
- Watch logs for errors
- Use pause (not stop) for short breaks
- Disable problematic runners rather than kicking them
- Use manual trigger for demonstrations

**After the event**:
- Export logs for analysis
- Review transmission history
- Disable all challenges or stop the server
- Back up the database

### Troubleshooting Through the UI

**Runner won't go online**:
1. Check the Runners page for the runner
2. If listed but offline, check last heartbeat time
3. Check Logs page for connection errors from that runner ID
4. Consider kicking and letting it re-register

**Challenge won't transmit**:
1. Check Challenges page for the challenge state
2. Verify at least one runner is online and enabled
3. Check runner frequency limits include the challenge frequency
4. Look for errors in Logs page
5. Try manual trigger to test

**System slow or unresponsive**:
1. Check number of active runners (too many?)
2. Review recent transmissions for high failure rate
3. Check Logs for database lock errors
4. Consider pausing system temporarily
5. Check server resource usage externally

### Security Best Practices

1. **Use HTTPS**: Always run behind nginx with TLS in production
2. **Strong passwords**: Enforce strong password requirements
3. **Limit access**: Use firewall rules to restrict web UI access
4. **Regular backups**: Back up the database including user accounts
5. **Monitor logs**: Watch for suspicious login attempts
6. **Logout when done**: Especially on shared computers
7. **Rotate passwords**: Change admin passwords periodically

## Next Steps

Now that you understand the web interface, you can:

- [Review the API Reference](API-Reference) for programmatic access
- [Read the Architecture Overview](Architecture) to understand how the UI interacts with the backend
- [Check the Troubleshooting Guide](Troubleshooting) for common issues
- [Explore Configuration Reference](Configuration-Reference) for advanced setup options
