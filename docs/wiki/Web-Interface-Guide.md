# Web Interface Guide

This guide covers the ChallengeCtl web interface, explaining how to monitor system status, manage challenges and runners, and control system operation through the browser-based dashboard.

## Table of Contents

- [Overview](#overview)
- [Accessing the Web Interface](#accessing-the-web-interface)
- [Dashboard](#dashboard)
- [Runners Management](#runners-management)
- [Manage Challenges](#manage-challenges)
- [Logs Viewer](#logs-viewer)
- [User Management](#user-management)
- [System Controls](#system-controls)
- [Conference Settings](#conference-settings)
- [Real-Time Updates](#real-time-updates)

## Overview

The ChallengeCtl web interface provides a comprehensive view of your RF challenge distribution system. It allows administrators to monitor system health, manage runners and challenges, view real-time logs, and control system operation without needing to edit configuration files or restart services.

### Key Features

- **Real-time monitoring**: Live updates via WebSocket connections
- **Challenge management**: Enable, disable, and manually trigger challenges
- **Challenge configuration**: Create, import, edit, and delete challenges via Web UI
- **Runner control**: Monitor runner status and manage connections
- **Log streaming**: Real-time logs from server and all runners
- **User administration**: Manage admin accounts and credentials
- **System controls**: Pause and resume operations
- **Conference countdown**: Live countdown timers with daily hour cycling
- **Auto-pause scheduling**: Automatically pause/resume based on daily hours

## Accessing the Web Interface

### Login Process

The login process differs based on whether you're an existing user or a newly created user requiring setup.

#### Existing User Login

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

#### New User First Login

If an administrator created your account, you must complete setup on first login:

1. **Navigate to the server URL** and enter your initial credentials:
   - Username: Provided by your administrator
   - Password: Initial password provided by administrator

2. **Account Setup Screen**:
   - You'll be automatically redirected to the setup page
   - **Important**: You must complete this within 24 hours or your account will be disabled

3. **Change Your Password**:
   - Enter a new secure password (minimum 8 characters)
   - Confirm the new password
   - Click "Continue to 2FA Setup"

4. **Set Up Two-Factor Authentication**:
   - After submitting your password, the server generates a TOTP secret
   - Scan the QR code with your authenticator app (Google Authenticator, Authy, etc.)
   - Or manually enter the secret if QR code scanning isn't available
   - Enter the 6-digit code from your app to verify setup
   - Click "Complete Setup"

5. **Access the dashboard**:
   - Your account is now fully activated
   - You can access all features based on your permissions
   - Future logins will use your new password and TOTP

**Important Notes**:
- New users **must complete setup within 24 hours** of account creation
- Accounts not set up in time are automatically disabled for security
- If your account is disabled, contact your administrator to create a new one
- You cannot skip TOTP setup - all users must have 2FA enabled

### Session Management

- **Session duration**: Sessions remain active for 24 hours
- **Auto-logout**: Sessions expire after 24 hours of inactivity
- **Manual logout**: Click your username in the header, then select "Logout"
- **Multiple sessions**: You can be logged in from multiple browsers/devices simultaneously

### User Menu

The user menu in the header provides quick access to your account options:

**Accessing the User Menu**:
- Click on your username (with avatar icon) in the top-right corner of the header
- A dropdown menu appears with available options

**Available Options**:
- **Change Password**: Update your current password
  - Requires your current password for verification
  - Enter new password twice to confirm
  - Session remains active after password change
  - Use this to regularly rotate your credentials
- **Logout**: Sign out and invalidate your current session
  - Ends your session immediately
  - Returns you to the login page
  - Other sessions on different devices remain active

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

The Runners page displays all registered runners and their current status. The page includes two tabs:

1. **Runners**: View and manage runner connections (available to all users)
2. **Provisioning Keys**: Create and manage provisioning API keys for automated runner deployment (requires `create_provisioning_key` permission)

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

## Manage Challenges

The Manage Challenges page provides a unified interface for monitoring, creating, importing, editing, and controlling your challenges. This combines real-time monitoring with configuration management in a single location.

### Overview

The Manage Challenges page has four tabs:

1. **Live Status**: Monitor and control active challenges in real-time
2. **Create Challenge**: Form-based interface for creating individual challenges
3. **Import from YAML**: Batch import challenges from YAML files with file uploads
4. **Manage Challenges**: View, edit, and delete existing challenges

**When to use each tab**:
- **Live Status**: For monitoring challenge execution, enabling/disabling, and triggering transmissions
- **Create Challenge**: For adding one challenge at a time with guided validation
- **Import from YAML**: For batch operations, migration, or automation
- **Manage Challenges**: For editing existing challenges or removing old ones

For comprehensive documentation on challenge configuration, see the [Challenge Management Guide](Challenge-Management).

### Live Status Tab

**Purpose**: Real-time monitoring and control of challenge execution.

**Key Features**:
- Auto-refresh every 15 seconds
- Enable/disable toggle switches
- Manual trigger controls
- Real-time status updates
- Transmission count tracking
- Reload from config functionality

**Displayed Information**:

**Challenge Name**: Unique identifier

**Modulation**: Modulation type (CW, NBFM, SSB, FHSS, etc.)

**Frequency**: Transmission frequency in Hz (displayed as MHz)

**Status**: Current challenge state with color-coded tags
- **Queued** (green): Waiting for delay period to elapse
- **Waiting** (orange): Ready to be assigned to a runner
- **Assigned** (default): Currently being executed by a runner
- **Disabled** (gray): Challenge is not active

**Enabled**: Toggle switch to activate/deactivate the challenge
- Enabled challenges will be queued for transmission
- Disabled challenges will not be queued

**TX Count**: Number of times the challenge has been transmitted
- Updates in real-time as transmissions complete

**Last TX**: Timestamp of most recent transmission
- Shows relative time (e.g., "2 minutes ago")
- Updates automatically

**Actions Available**:

**Reload from Config**:
- Reloads challenges from server-config.yml
- Adds new challenges from config file
- Does not affect database-stored challenges
- Use when adding challenges via config file

**Enable/Disable Toggle**:
- Click switch to activate or deactivate a challenge
- Enabled challenges enter the transmission queue
- Disabled challenges are skipped
- Changes take effect immediately

**Trigger Now**:
- Manually queue the challenge for immediate transmission
- Bypasses the delay timer
- Queues the challenge as "waiting" immediately
- The next available compatible runner will execute it
- Use this for testing or demonstrations
- Does not affect the regular scheduling cycle

**Challenge Workflow**:

1. **Disabled**: Challenge exists but is inactive
2. **Enabled**: Challenge is activated and enters the queue
3. **Queued**: Waiting for random delay period (between min_delay and max_delay)
4. **Waiting**: Ready for assignment, available to compatible runners
5. **Assigned**: A runner has claimed the task and is executing
6. **Completed**: Transmission finished, returns to queued state

**Note**: The cycle repeats continuously for enabled challenges.

### Create Challenge Tab

**Purpose**: Create a single challenge using a guided form interface.

**Key Features**:
- Dynamic form fields based on modulation type
- Built-in validation for required fields
- File upload for audio and binary files
- Modulation-specific parameter configuration
- Public field visibility configuration

**Workflow**:
1. Enter basic information (name, modulation, frequency)
2. Configure challenge content (flag text or file upload)
3. Set timing parameters (min/max delay, priority)
4. Configure public dashboard visibility (select which fields are visible on public dashboard)
5. Configure modulation-specific settings (if applicable)
6. Click "Create Challenge"

**Priority Field**:
- Priority range: 0-100
- Higher number = higher priority
- Higher priority challenges are transmitted first
- Default: 0 (normal priority)
- Use for time-sensitive or important challenges

**Public Dashboard Visibility**:
- Select which fields are visible on the public dashboard
- Available fields: name, modulation, frequency, status, last TX time
- Default: name, modulation, frequency, status
- Allows you to control what information participants can see

**Example Use Case**:
- Creating a new NBFM challenge during a CTF event
- Testing different CW speeds to find the right difficulty
- Quickly adding a challenge without editing YAML files

### Import from YAML Tab

**Purpose**: Batch import multiple challenges from a YAML configuration file.

**Key Features**:
- Upload YAML file with challenge definitions
- Upload associated media files (WAV, binary, etc.)
- Automatic file path mapping
- Import statistics and error reporting
- API documentation for automation

**Workflow**:
1. Prepare a YAML file with your challenges
2. Click "Select YAML File" and choose your file
3. (Optional) Click "Add Files" to upload media files
4. Click "Import Challenges"
5. Review import results (added, updated, errors)

**File Handling**:
- Files are uploaded and stored by SHA-256 hash
- System automatically maps uploaded files to challenge configs
- If YAML references `example.wav` and you upload `example.wav`, it's linked automatically

**Example Use Case**:
- Migrating challenges from server config to database
- Sharing challenge sets between ChallengeCtl instances
- Version-controlling challenges in git and importing
- Restoring from backup

### Manage Challenges Tab

**Purpose**: View, edit, and delete existing challenges.

**Key Features**:
- Table view of all configured challenges
- Filter and search capabilities
- JSON editor for advanced configuration
- Delete with confirmation dialog

**Displayed Information**:
- Challenge name
- Modulation type
- Frequency (formatted as MHz/GHz)
- Status (Enabled/Disabled)
- Transmission count

**Actions Available**:

**Refresh List**:
- Reloads challenges from database
- Use after importing or creating challenges elsewhere

**Edit**:
- Opens JSON editor dialog
- Shows complete challenge configuration
- Make changes directly to JSON
- Click "Save" to apply changes
- Validates JSON syntax before saving

**Delete**:
- Removes challenge permanently
- Confirmation dialog prevents accidental deletion
- Deletes challenge config and transmission history
- Does NOT delete referenced media files (other challenges may use them)

**Example Use Case**:
- Adjusting min/max delays during an event
- Changing frequency after testing
- Removing old or unused challenges
- Copying configuration to create similar challenges

### API Automation

The Import from YAML tab includes documentation for API-based automation:

**cURL Example**:
```bash
curl -X POST http://localhost:8080/api/challenges/import \
  -H "X-CSRF-Token: YOUR_CSRF_TOKEN" \
  -b "session=YOUR_SESSION_COOKIE" \
  -F "yaml_file=@challenges.yml" \
  -F "example_voice.wav=@/path/to/example_voice.wav"
```

**Python Example**:
```python
import requests

url = "http://localhost:8080/api/challenges/import"
files = {
    'yaml_file': open('challenges.yml', 'rb'),
    'example_voice.wav': open('example_voice.wav', 'rb'),
}
cookies = {'session': 'YOUR_SESSION_COOKIE'}
headers = {'X-CSRF-Token': 'YOUR_CSRF_TOKEN'}

response = requests.post(url, files=files, cookies=cookies, headers=headers)
print(response.json())
```

**Use Cases for API Automation**:
- CI/CD pipeline integration
- Automated challenge rotation
- Dynamic challenge generation from scripts
- Remote challenge management

### Best Practices

**Creating Challenges**:
- Use descriptive names (e.g., `NBFM_EASY_1` not `FLAG1`)
- Start disabled, test with "Trigger Now", then enable
- Set appropriate delays based on event duration
- Verify frequency is within runner limits

**Importing Challenges**:
- Test YAML file syntax before importing
- Keep YAML files under version control
- Upload all referenced media files together
- Review import results for errors

**Managing Challenges**:
- Disable rather than delete during events
- Back up configuration before bulk edits
- Use JSON validation tools when editing directly
- Test changes with "Trigger Now" before re-enabling

**File Management**:
- Use meaningful filenames (e.g., `flag_morse_slow.wav`)
- Keep media files organized in directories
- Don't delete files that might be used by multiple challenges
- Track file hashes for deduplication

### Typical Workflow

The unified Manage Challenges interface streamlines challenge management:

1. **Create/Import**: Use the **Create Challenge** or **Import from YAML** tabs to add challenges
2. **Configure**: Set up timing, priority, and public visibility settings
3. **Monitor**: Switch to **Live Status** tab to monitor execution
4. **Control**: Use **Live Status** to enable/disable or trigger challenges
5. **Edit**: Use **Manage Challenges** tab to edit or delete existing challenges

This unified approach eliminates the need to switch between separate pages for configuration and monitoring.

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

The Users page allows you to manage admin accounts with username/password and TOTP authentication. User management includes permission controls to determine who can create and manage other users.

### User List

Displays all admin users with:
- **Username**: Login name
- **Status**: Account status (enabled/disabled, temporary/permanent)
- **Created**: Account creation timestamp
- **Last Login**: When the user last successfully logged in
- **Permissions**: Assigned permissions (e.g., create_users)
- **Actions**: Enable/disable, reset password, reset TOTP, manage permissions, delete

### User Operations

**Add User** (Requires `create_users` permission):

Creating a new user:

1. Click "Add User" button
2. Enter username (password is auto-generated)
3. (Optional) Grant permissions like `create_users`
4. Click "Create User"
5. **Important**: The initial password is displayed only once
6. Share the username and initial password with the new user securely
7. The new user must complete setup within 24 hours

The new user will:
- Login with the initial credentials
- Be required to change their password
- Be required to set up TOTP 2FA
- Complete setup or have their account auto-disabled after 24 hours

**User Account Types**:
- **New users** (created via web UI): Must complete setup on first login
  - Ideal for onboarding new administrators
  - Auto-disabled after 24 hours if setup not completed
  - No TOTP configured initially
- **Initial admin**: Created during initial server setup
  - Already has TOTP configured
  - Ready to use immediately

**Enable/Disable User**:
- **Disable**: Prevent user from logging in without deleting the account
  - All user sessions are invalidated
  - User cannot create new sessions
  - Useful for temporarily suspending access
- **Enable**: Re-activate a disabled account
  - User can login again with their existing credentials

**Manage Permissions**:
- **Grant Permission**: Give a user specific capabilities
  - Currently supported: `create_users` (allows creating and managing users)
  - Future permissions can be added (extensible system)
- **Revoke Permission**: Remove a permission from a user
  - User immediately loses that capability
- **View Permissions**: See all permissions assigned to a user

**Delete User**:
- Permanently removes the account
- User is immediately logged out
- All user sessions are invalidated
- Cannot delete your own account (prevents lockout)
- All permissions are automatically removed

**User Actions Menu**:

All user actions (Enable/Disable, Manage Permissions, Reset Password, Reset TOTP, Delete) are available through the "Actions" dropdown button in the user table. This provides a clean, organized interface for user management operations.

**Reset TOTP**:
- Generates a new TOTP secret
- Use when a user loses access to their authenticator app
- Displays a new QR code for setup
- Old TOTP codes immediately become invalid
- All user sessions are invalidated for security

**Reset Password**:
- Generate a new temporary password for a user (password is auto-generated for security)
- The temporary password is displayed once for you to share with the user
- Sets `password_change_required` flag
- User must change password on next login
- All user sessions are invalidated for security
- Share the new temporary password securely

### Permission System

ChallengeCtl uses a scalable permission system to control user capabilities:

**Available Permissions**:
- **`create_users`**: Allows user to:
  - Create new user accounts
  - Manage permissions for other users
  - View all users and their permissions
  - Cannot be used to grant permissions the user doesn't have
- **`create_provisioning_key`**: Allows user to:
  - Create provisioning API keys for automated runner deployment
  - Manage (enable/disable/delete) provisioning keys
  - Access the Provisioning Keys tab in the Runners page

**Permission Inheritance**:
- The first user created during initial setup automatically receives all permissions
- New users have no permissions by default unless granted during creation
- Permissions can be granted/revoked at any time by users with `create_users` permission

**Permission Checks**:
- Attempting to create a user without `create_users` permission returns an error
- Users can view their own permissions in their profile
- Cannot revoke your own permissions (prevents lockout)

### User Security

**Password Requirements**:
- Minimum 8 characters
- Should include uppercase, lowercase, numbers, and symbols
- Passwords are bcrypt hashed (never stored in plaintext)
- Temporary passwords must be changed on first login

**TOTP Requirements**:
- Required for all admin accounts
- 6-digit codes rotate every 30 seconds
- Use any TOTP-compatible authenticator app (Google Authenticator, Authy, etc.)
- Secrets are encrypted in the database using Fernet encryption

**Account Security Features**:
- **24-hour setup deadline**: New accounts must complete setup within 24 hours or are auto-disabled
- **Session invalidation**: Password/TOTP resets immediately log out all user sessions
- **Permission-based access control**: Users can only perform actions they're authorized for
- **Audit logging**: All permission grants/revokes are logged with granting administrator

### Common User Management Workflows

**Onboarding a New Administrator**:
1. Click "Add User" with your account (must have `create_users` permission)
2. Enter username (initial password auto-generated)
3. Grant `create_users` permission if they should manage users
4. Share credentials securely with the new admin
5. New admin logs in and completes setup within 24 hours

**Temporarily Suspending a User**:
1. Find the user in the list
2. Click "Disable"
3. User is immediately logged out and cannot login
4. To restore access, click "Enable"

**Rotating Security Credentials**:
- **Password**: Use "Reset Password" to set a temporary password, user must change on next login
- **TOTP**: Use "Reset TOTP" to generate new secret, user must scan new QR code
- Both operations invalidate all existing sessions for security

**Granting Additional Permissions**:
1. Find the user in the list
2. Click "Manage Permissions"
3. Select permission to grant (e.g., `create_users`)
4. Click "Grant Permission"
5. Changes take effect immediately

## System Controls

System controls affect the entire ChallengeCtl server and all runners.

### Accessing System Controls

System control buttons are located in the **header bar** at the top of every page:

- **Pause button**: Visible when system is running normally (yellow)
- **Resume button**: Visible when system is paused (green, replaces Pause button)
- Button state syncs in real-time across all connected admin sessions via WebSocket
- Initial state is loaded when the page loads to show correct button

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

## Conference Settings

The Conference Settings card on the Dashboard allows you to configure conference-specific features including daily operating hours, countdown timers, and automatic pause/resume.

### Accessing Conference Settings

Conference Settings are located on the **Dashboard** page in a dedicated card below the Runners table (left column).

### Conference Name and Countdown

The conference name and countdown timer appear in both the admin and public page headers:

**Admin Header**:
```
ChallengeCtl Control Center - ExampleCon
Ends in: 1d 12h 30m 45s
```

**Public Dashboard Header**:
```
Live Challenge Status
Starts in: 2d 5h 30m 45s
```

The countdown displays different states based on the conference timeline:

**Before Conference Start**:
- Shows: `Starts in: X`
- Counts down to conference start time from config

**During Conference**:
- Shows: `Ends in: X`
- Counts down to conference end time
- Additional timer when within daily hours (see below)

**After Conference**:
- Shows: `ExampleCon RFCTF has ended`
- Red text indicating event completion

### Daily Operating Hours

Configure daily start and end times to create a countdown cycle for multi-day conferences.

#### Day Start Time

**Purpose**: When the daily operating hours begin each day.

**Configuration**:
- Use the time picker to select a time (15-minute intervals)
- Format: HH:MM (e.g., "09:00")
- Timezone: Conference timezone (from config.yml)

**Example**: Set to "09:00" for a 9 AM daily start

#### End of Day Time

**Purpose**: When the daily operating hours end each day.

**Configuration**:
- Use the time picker to select a time (15-minute intervals)
- Format: HH:MM (e.g., "17:00")
- Timezone: Conference timezone (from config.yml)

**Example**: Set to "17:00" for a 5 PM daily end

#### Daily Countdown Cycle

When both day start and end times are configured, the countdown changes based on time of day:

**During Daily Hours** (e.g., 9 AM - 5 PM):
```
Ends in: 1d 12h 30m | Day ends: 4h 30m 15s
```
- Main countdown: Time until conference ends
- Secondary countdown: Time until end of day

**Outside Daily Hours** (e.g., 5 PM - 9 AM):
```
Day starts in: 15h 30m 45s
```
- Countdown to when the next day begins
- Only shown during conference (not before/after)

**Overnight Support**:
- Handles overnight ranges (e.g., 10:00 PM - 6:00 AM)
- Automatically calculates correct countdown

#### Saving Daily Times

**Save Button**:
- Click to apply both day start and end of day times
- Changes take effect immediately
- Updates countdown for all users in real-time
- No server restart required

**Clear Both Button**:
- Removes both day start and end of day settings
- Disables the daily countdown cycle
- Reverts to simple conference-wide countdown

**Validation**:
- Times must be in HH:MM format
- Invalid times show an error message
- Both times can be set independently

### Auto-Pause Daily

Automatically pause and resume the system based on daily operating hours.

#### How Auto-Pause Works

**When Enabled**:
1. System automatically pauses at end of day time
2. System automatically resumes at day start time
3. Runs in background every 30 seconds
4. Works across multiple days during conference

**Timezone Handling**:
- Auto-pause uses the **conference timezone** from config.yml
- Timezone offset is extracted from conference start time (e.g., `-5` from `"2024-04-05 09:00:00 -5"`)
- Daily times (e.g., 09:00, 17:00) are interpreted in this conference timezone
- System correctly handles pause/resume regardless of server's local timezone

**Requirements**:
- Both day start and end of day times must be set
- Auto-pause toggle must be enabled
- Conference timezone must be specified in config.yml start time

#### Enabling Auto-Pause

**Toggle Switch**:
- Located below the day time pickers
- Click to enable or disable
- Changes save immediately
- Shows "Automatically pause transmissions outside daily hours" description

**When Enabled**:
- System pauses at end of day (e.g., 5:00 PM)
- System resumes at day start (e.g., 9:00 AM)
- Live UI updates via WebSocket
- All connected admins see notifications

**When Disabled**:
- System runs continuously (24/7)
- Manual pause/resume still works
- Daily countdown still functions

#### Manual Override

The manual Pause/Resume button in the header **always works** and overrides auto-pause:

**Manual Pause**:
- Click "Pause" button at any time
- System pauses immediately
- Auto-pause will **not** auto-resume (respects manual override)
- Click "Resume" to start transmissions again

**Manual Resume**:
- Click "Resume" button during auto-pause period
- System resumes immediately
- Auto-pause will pause again at next end of day (if still outside hours)

**Auto-Pause Behavior**:
- Only auto-resumes if it was the one that paused
- Won't override manual pause with auto-resume
- Manual resume during off-hours is allowed (for testing, etc.)

#### WebSocket Notifications and State Sync

All connected admin users receive real-time notifications and button state updates:

**Auto-Pause Event**:
```
ℹ System auto-paused (outside daily hours)
```
- Appears when auto-pause triggers
- Pause button changes to Resume button for **all connected admins**
- Blue info notification

**Auto-Resume Event**:
```
ℹ System auto-resumed (within daily hours)
```
- Appears when auto-resume triggers
- Resume button changes to Pause button for **all connected admins**
- Blue info notification

**Manual Pause/Resume**:
- Uses standard success messages (green)
- No "auto" prefix in notification
- Button state syncs across all connected admin sessions via WebSocket
- If one admin pauses, all admins see the Resume button immediately

**Initial State Loading**:
- When you load the page, the pause button state is fetched from the server
- Ensures the button always shows the correct state (Pause or Resume)
- No refresh needed to see current system state

### Configuration Workflow

**Typical Setup**:

1. **Set Conference Times** (in config.yml):
   ```yaml
   conference:
     name: ExampleCon
     start: "2024-04-05 09:00:00 -5"
     stop: "2024-04-07 17:00:00 -5"
   ```

2. **Configure Daily Hours** (in Dashboard):
   - Day Start: 09:00
   - End of Day: 17:00
   - Click "Save"

3. **Enable Auto-Pause** (optional):
   - Toggle "Auto-Pause Daily" on
   - System will pause/resume automatically

4. **Monitor**:
   - Check countdown in header
   - Watch for auto-pause notifications
   - Use manual pause/resume as needed

### Runtime Configuration

All conference settings are **runtime configurable**:

**No Restart Required**:
- Change day start/end times anytime
- Toggle auto-pause on/off instantly
- Updates apply immediately
- All users see changes in real-time

**Persistent Storage**:
- Settings stored in database (system_state table)
- Survive server restarts
- Can be changed during live events
- Config.yml values serve as defaults

**Override Order**:
1. Database setting (from web UI)
2. Config.yml setting (fallback)
3. No setting (feature disabled)

### Best Practices

**Setting Daily Hours**:
- Match your event schedule (e.g., 9 AM - 5 PM)
- Account for setup/teardown time
- Consider participant time zones
- Test with manual trigger before enabling

**Using Auto-Pause**:
- Enable for multi-day events with defined hours
- Reduces power consumption overnight
- Prevents confusion about "dead air" periods
- Use manual override for testing outside hours

**During Events**:
- Don't change times during active hours (wait for breaks)
- Manual pause/resume always available
- Monitor WebSocket notifications
- Check countdown shows correct times

**Testing**:
1. Set day times (e.g., current time + 2 minutes)
2. Enable auto-pause
3. Wait for auto-pause notification
4. Test manual resume override
5. Adjust times to actual schedule

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
1. Check **Manage Challenges > Live Status** tab for the challenge state
2. Verify at least one runner is online and enabled
3. Check runner frequency limits include the challenge frequency
4. Look for errors in Logs page
5. Try manual trigger from Live Status tab to test

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

- [Read the Challenge Management Guide](Challenge-Management) for detailed challenge configuration
- [Review the API Reference](API-Reference) for programmatic access
- [Read the Architecture Overview](Architecture) to understand how the UI interacts with the backend
- [Check the Troubleshooting Guide](Troubleshooting) for common issues
- [Explore Configuration Reference](Configuration-Reference) for advanced setup options
