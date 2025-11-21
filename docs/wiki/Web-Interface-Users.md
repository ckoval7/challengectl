# User Management

The Users page allows you to manage admin accounts with username/password and TOTP authentication. User management includes permission controls to determine who can create and manage other users.

## User List

Displays all admin users with:
- **Username**: Login name
- **Status**: Account status (enabled/disabled, temporary/permanent)
- **Created**: Account creation timestamp
- **Last Login**: When the user last successfully logged in
- **Permissions**: Assigned permissions (e.g., create_users)
- **Actions**: Enable/disable, reset password, reset TOTP, manage permissions, delete

## User Operations

### Add User

**Requires**: `create_users` permission

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

### User Account Types

- **New users** (created via web UI): Must complete setup on first login
  - Ideal for onboarding new administrators
  - Auto-disabled after 24 hours if setup not completed
  - No TOTP configured initially
- **Initial admin**: Created during initial server setup
  - Already has TOTP configured
  - Ready to use immediately

### Enable/Disable User

- **Disable**: Prevent user from logging in without deleting the account
  - All user sessions are invalidated
  - User cannot create new sessions
  - Useful for temporarily suspending access
- **Enable**: Re-activate a disabled account
  - User can login again with their existing credentials

### Manage Permissions

- **Grant Permission**: Give a user specific capabilities
  - Currently supported: `create_users` (allows creating and managing users)
  - Future permissions can be added (extensible system)
- **Revoke Permission**: Remove a permission from a user
  - User immediately loses that capability
- **View Permissions**: See all permissions assigned to a user

### Delete User

- Permanently removes the account
- User is immediately logged out
- All user sessions are invalidated
- Cannot delete your own account (prevents lockout)
- All permissions are automatically removed

### User Actions Menu

All user actions (Enable/Disable, Manage Permissions, Reset Password, Reset TOTP, Delete) are available through the "Actions" dropdown button in the user table. This provides a clean, organized interface for user management operations.

### Reset TOTP

- Generates a new TOTP secret
- Use when a user loses access to their authenticator app
- Displays a new QR code for setup
- Old TOTP codes immediately become invalid
- All user sessions are invalidated for security

### Reset Password

- Generate a new temporary password for a user (password is auto-generated for security)
- The temporary password is displayed once for you to share with the user
- Sets `password_change_required` flag
- User must change password on next login
- All user sessions are invalidated for security
- Share the new temporary password securely

## Permission System

ChallengeCtl uses a scalable permission system to control user capabilities:

### Available Permissions

- **`create_users`**: Allows user to:
  - Create new user accounts
  - Manage permissions for other users
  - View all users and their permissions
  - Cannot be used to grant permissions the user doesn't have
- **`create_provisioning_key`**: Allows user to:
  - Create provisioning API keys for automated runner deployment
  - Manage (enable/disable/delete) provisioning keys
  - Access the Provisioning Keys tab in the Runners page

### Permission Inheritance

- The first user created during initial setup automatically receives all permissions
- New users have no permissions by default unless granted during creation
- Permissions can be granted/revoked at any time by users with `create_users` permission

### Permission Checks

- Attempting to create a user without `create_users` permission returns an error
- Users can view their own permissions in their profile
- Cannot revoke your own permissions (prevents lockout)

## User Security

### Password Requirements

- Minimum 8 characters
- Should include uppercase, lowercase, numbers, and symbols
- Passwords are bcrypt hashed (never stored in plaintext)
- Temporary passwords must be changed on first login

### TOTP Requirements

- Required for all admin accounts
- 6-digit codes rotate every 30 seconds
- Use any TOTP-compatible authenticator app (Google Authenticator, Authy, etc.)
- Secrets are encrypted in the database using Fernet encryption

### Account Security Features

- **24-hour setup deadline**: New accounts must complete setup within 24 hours or are auto-disabled
- **Session invalidation**: Password/TOTP resets immediately log out all user sessions
- **Permission-based access control**: Users can only perform actions they're authorized for
- **Audit logging**: All permission grants/revokes are logged with granting administrator

## Common User Management Workflows

### Onboarding a New Administrator

1. Click "Add User" with your account (must have `create_users` permission)
2. Enter username (initial password auto-generated)
3. Grant `create_users` permission if they should manage users
4. Share credentials securely with the new admin
5. New admin logs in and completes setup within 24 hours

### Temporarily Suspending a User

1. Find the user in the list
2. Click "Disable"
3. User is immediately logged out and cannot login
4. To restore access, click "Enable"

### Rotating Security Credentials

- **Password**: Use "Reset Password" to set a temporary password, user must change on next login
- **TOTP**: Use "Reset TOTP" to generate new secret, user must scan new QR code
- Both operations invalidate all existing sessions for security

### Granting Additional Permissions

1. Find the user in the list
2. Click "Manage Permissions"
3. Select permission to grant (e.g., `create_users`)
4. Click "Grant Permission"
5. Changes take effect immediately

## Related Guides

- [Web Interface Overview](Web-Interface-Overview) - Learn about authentication and login
- [Security Best Practices](Web-Interface-Overview#security-best-practices) - General security guidelines
- [Logs](Web-Interface-Logs) - Monitor user login attempts and actions
