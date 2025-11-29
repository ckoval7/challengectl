# User Management

The Users page allows you to manage admin accounts with username and password authentication combined with TOTP two-factor authentication. User management includes comprehensive permission controls to determine who can create and manage other users within the system.

!["Screenshot of User Management Page"](/docs/images/user_management.png "Users List")

## User List

The user list displays all admin users with comprehensive information about each account. The Username column shows the login name for each account. The Status column displays the account status, indicating whether accounts are enabled or disabled and whether they are temporary or permanent. The Created column shows the account creation timestamp for reference. The Last Login column displays when the user last successfully authenticated to the system. The Permissions column lists assigned permissions such as create_users or create_provisioning_key. The Actions column provides access to account management operations including enable, disable, reset password, reset TOTP, manage permissions, and delete.

## User Operations

### Add User

Creating new users requires the `create_users` permission, ensuring that only authorized administrators can provision accounts. To create a new user, click the "Add User" button and enter the desired username in the dialog. The system automatically generates a secure password for the account, eliminating the risk of weak initial credentials. Optionally grant permissions such as `create_users` if the new account should have user management capabilities. Click "Create User" to provision the account.

After creation, the system displays the initial password only once for security reasons. Share the username and initial password with the new user through a secure channel, ensuring credentials are not exposed through insecure communication methods. The new user must complete account setup within 24 hours of creation, including changing their password and configuring TOTP two-factor authentication.

The new user workflow follows a structured process. Upon first login with the initial credentials, the system automatically requires the user to change their password to a secure value of their choosing. Next, the system requires TOTP configuration by displaying a QR code for scanning or a manual entry code. The user must complete both steps or face automatic account disable after 24 hours for security reasons.

### User Account Types

The system supports two distinct types of user accounts. New users created through the web UI must complete setup on first login, making this approach ideal for onboarding new administrators. These accounts are automatically disabled after 24 hours if setup is not completed, and they have no TOTP configured initially.

Initial admin accounts created during server setup differ significantly. These accounts already have TOTP configured and are ready to use immediately, requiring no additional setup steps before first use.

### Enable/Disable User

The disable operation prevents a user from logging in without deleting their account and associated data. When you disable a user, all of their sessions are immediately invalidated and they cannot create new sessions. This proves useful for temporarily suspending access without losing account configuration.

The enable operation re-activates a disabled account, allowing the user to log in again with their existing credentials. This restores full access without requiring any account reconfiguration.

### Manage Permissions

Permission management provides fine-grained control over user capabilities. The grant permission operation gives a user specific capabilities within the system. Currently supported permissions include `create_users`, which allows creating and managing user accounts, and `create_provisioning_key`, which allows creating and managing provisioning API keys for automated agent deployment. The permission system is extensible, allowing additional permissions to be added for future capabilities.

The revoke permission operation removes a permission from a user, causing them to immediately lose that capability. The view permissions operation shows all permissions assigned to a user, providing visibility into their current authorization level.

### Delete User

The delete operation permanently removes an account from the system. This immediately logs out the user if they are currently authenticated and invalidates all of their sessions. The system prevents you from deleting your own account to avoid accidental lockout. All permissions are automatically removed when an account is deleted.

### User Actions Menu

All user management actions including enable, disable, manage permissions, reset password, reset TOTP, and delete are available through the Actions dropdown button in the user table. This provides a clean and organized interface for user management operations without cluttering the display with numerous individual buttons.

### Reset TOTP

The reset TOTP operation generates a new TOTP secret for a user account. Use this function when a user loses access to their authenticator app or needs to reconfigure two-factor authentication on a new device. After reset, the system displays a new QR code for setup using any TOTP-compatible authenticator application. Old TOTP codes immediately become invalid, preventing use of the previous configuration. All user sessions are invalidated for security, requiring the user to log in again with their password and new TOTP code.

### Reset Password

The reset password operation generates a new temporary password for a user account. The system automatically generates this password for security rather than allowing manual selection, ensuring strong credentials. The temporary password is displayed only once for the administrator to share with the user. The system sets a password change required flag, forcing the user to change the password on their next login. All user sessions are invalidated for security, preventing continued access with the old credentials. Share the new temporary password with the user through a secure channel to maintain credential confidentiality.

## Permission System

ChallengeCtl implements a scalable permission system to control user capabilities with fine granularity.

### Available Permissions

The `create_users` permission allows a user to create new user accounts, manage permissions for other users, and view all users and their assigned permissions. This permission cannot be used to grant permissions the user does not themselves possess, preventing privilege escalation.

The `create_provisioning_key` permission allows a user to create provisioning API keys for automated runner deployment, manage provisioning keys by enabling, disabling, or deleting them, and access the Provisioning Keys tab in the Runners page.

### Permission Inheritance

The permission system follows clear rules for initial permission assignment. The first user created during initial server setup automatically receives all available permissions, ensuring administrative access is available. New users have no permissions by default unless explicitly granted during account creation. Permissions can be granted or revoked at any time by users who possess the `create_users` permission.

### Permission Checks

The system enforces permission requirements consistently throughout the interface. Attempting to create a user without the `create_users` permission results in an error preventing the operation. Users can view their own permissions through their profile interface. The system prevents users from revoking their own permissions to avoid accidental lockout situations.

## User Security

### Password Requirements

The system enforces password security through several requirements and best practices. Passwords must contain a minimum of eight characters to ensure adequate complexity. Passwords should include uppercase letters, lowercase letters, numbers, and symbols for maximum strength. All passwords are stored using bcrypt hashing, ensuring they are never stored in plaintext. Temporary passwords generated for new or reset accounts must be changed on first login to ensure each user has unique credentials.

### TOTP Requirements

Two-factor authentication using TOTP is mandatory for all admin accounts without exception. The system uses six-digit codes that rotate every 30 seconds, providing time-limited authentication. Any TOTP-compatible authenticator app works with the system, including Google Authenticator, Authy, and others. TOTP secrets are encrypted in the database using Fernet encryption with a server master key, protecting them even if the database is compromised.

### Account Security Features

Several security features protect accounts from unauthorized access and ensure proper account lifecycle management. The 24-hour setup deadline requires new accounts to complete setup within 24 hours or face automatic disable, preventing abandoned accounts from remaining active. Session invalidation immediately logs out all user sessions when passwords or TOTP secrets are reset, preventing unauthorized continued access. Permission-based access control ensures users can only perform actions they are explicitly authorized to perform. Audit logging records all permission grants and revocations along with the identity of the granting administrator, providing accountability and traceability for authorization changes.

## Common User Management Workflows

### Onboarding a New Administrator

To onboard a new administrator, begin by clicking "Add User" with an account that has the `create_users` permission. Enter the desired username, as the initial password will be auto-generated for security. Grant the `create_users` permission if the new administrator should have the ability to manage other users. Share the generated credentials securely with the new admin through an encrypted channel or in person. The new admin must then log in and complete setup within 24 hours by changing their password and configuring TOTP authentication.

### Temporarily Suspending a User

To temporarily suspend a user account, locate the user in the list and click the "Disable" action. The user is immediately logged out and cannot log in until re-enabled. When you need to restore access, click the "Enable" action to allow the user to authenticate again.

### Rotating Security Credentials

Security credential rotation helps maintain account security over time. To rotate a password, use the "Reset Password" function to set a temporary password which the user must change on next login. To rotate TOTP configuration, use the "Reset TOTP" function to generate a new secret which the user must scan with their authenticator app. Both operations invalidate all existing sessions for security, requiring the user to authenticate again with the new credentials.

### Granting Additional Permissions

To grant additional permissions to a user, find the user in the list and click "Manage Permissions". Select the permission to grant from the available options, such as `create_users` or `create_provisioning_key`. Click "Grant Permission" to apply the change. The permission change takes effect immediately without requiring the user to log out and back in.

## Related Guides

For information about authentication and login procedures, see the Web Interface Overview guide. For general security guidelines applicable to user management, consult the Security Best Practices section of the Overview guide. To monitor user login attempts and account management actions, refer to the Logs guide for analysis techniques.
