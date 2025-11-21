# Web Interface Overview

This guide covers the basics of accessing and using the ChallengeCtl web interface.

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

## Navigation

The web interface is organized into several main sections, accessible from the navigation menu:

- **[Dashboard](Web-Interface-Dashboard)**: System overview and statistics
- **[Runners](Web-Interface-Runners)**: Manage runner connections and provisioning
- **[Challenges](Web-Interface-Challenges)**: Monitor, create, and manage challenges
- **[Logs](Web-Interface-Logs)**: Real-time log streaming
- **[Users](Web-Interface-Users)**: User account management
- **[System Controls](Web-Interface-System-Controls)**: Pause/resume and conference settings

## Security Best Practices

1. **Use HTTPS**: Always run behind nginx with TLS in production
2. **Strong passwords**: Enforce strong password requirements
3. **Limit access**: Use firewall rules to restrict web UI access
4. **Regular backups**: Back up the database including user accounts
5. **Monitor logs**: Watch for suspicious login attempts
6. **Logout when done**: Especially on shared computers
7. **Rotate passwords**: Change admin passwords periodically

## Next Steps

- [Dashboard Guide](Web-Interface-Dashboard) - Learn about the dashboard and statistics
- [Runner Management](Web-Interface-Runners) - Manage your RF hardware
- [Challenge Management](Web-Interface-Challenges) - Configure and control challenges
- [User Management](Web-Interface-Users) - Manage admin accounts
- [System Controls](Web-Interface-System-Controls) - System-wide operations
