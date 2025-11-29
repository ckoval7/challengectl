# Implementing New Permissions

This guide walks through the process of adding new permissions to the ChallengeCtl system. Permissions provide granular access control for different features and functionality.

## Overview

ChallengeCtl uses a permission-based access control system where:
- Permissions are stored in the database per-user
- Backend API endpoints validate permissions before allowing operations
- Frontend UI hides/shows features based on user permissions
- Route guards prevent unauthorized navigation

## Permission System Architecture

The permission system has three layers of protection:

1. **UI Layer**: Hide navigation items and UI elements from users without permission
2. **Route Layer**: Prevent direct navigation to protected routes via URL
3. **API Layer**: Validate permissions on all backend operations

This "defense in depth" approach ensures security even if one layer is bypassed.

## Step-by-Step Guide

### 1. Add Permission to Backend Definitions

**File**: `server/api.py`

Add your new permission to the `PERMISSION_DEFINITIONS` structure near the top of the file (~line 38):

```python
# Permission definitions - single source of truth
PERMISSION_DEFINITIONS = [
    {
        'name': 'create_users',
        'description': 'Can create and manage users',
        'category': 'administration'
    },
    {
        'name': 'create_provisioning_key',
        'description': 'Can create provisioning keys for runners',
        'category': 'provisioning'
    },
    {
        'name': 'your_new_permission',
        'description': 'Description of what this permission allows',
        'category': 'your_category'
    }
]

# Helper to get list of valid permission names
VALID_PERMISSIONS = [p['name'] for p in PERMISSION_DEFINITIONS]
```

**That's it!** The permission will automatically be:
- Available in the frontend dropdown (fetched via API)
- Granted to initial admin users (via loop)
- Validated in user creation endpoint
- Validated in permission grant endpoint

**Note**: The `VALID_PERMISSIONS` list is automatically derived from `PERMISSION_DEFINITIONS`, so you don't need to update it separately.

### 2. Add Permission Check to API Endpoints

**File**: `server/api.py`

Add permission checks to any endpoints that require the new permission:

```python
@self.app.route('/api/your-protected-endpoint', methods=['POST'])
@self.require_admin_auth
@self.require_csrf
def your_protected_function():
    """Your endpoint description."""
    # Check permission
    if not self.db.has_permission(request.admin_username, 'your_new_permission'):
        logger.warning(
            f"SECURITY: Operation denied - username='{request.admin_username}' "
            f"missing 'your_new_permission' permission ip={request.remote_addr}"
        )
        return jsonify({'error': 'Permission denied: your_new_permission permission required'}), 403

    # Your endpoint logic here
    # ...

    return jsonify({'status': 'success'}), 200
```

**Key Points**:
- Always check permission at the start of the function
- Use `request.admin_username` (set by `@self.require_admin_auth` decorator)
- Log security warnings when permission is denied
- Return 403 Forbidden status code
- Provide clear error message

### 3. Grant Permission to Initial Admin User

**File**: `server/api.py`

**No action needed!** The initial setup automatically grants all permissions to the first admin user using a loop (~line 1426):

```python
# Grant all permissions to initial admin user
for permission in VALID_PERMISSIONS:
    self.db.grant_permission(username, permission, 'system')
```

Since `VALID_PERMISSIONS` is derived from `PERMISSION_DEFINITIONS`, any new permission you add in Step 1 will automatically be granted to initial admin users. No additional code changes needed!

### 4. Frontend Permission List

**No action needed!** The frontend automatically fetches permission metadata from the backend API.

**How it works**:

The Users.vue component fetches available permissions on mount (~line 786):

```javascript
const fetchPermissionMetadata = async () => {
  loadingPermissions.value = true
  try {
    const response = await api.get('/permissions/metadata')
    availablePermissions.value = response.data.permissions
  } catch (error) {
    console.error('Error fetching permission metadata:', error)
    ElMessage.error('Failed to load available permissions')
  } finally {
    loadingPermissions.value = false
  }
}

onMounted(() => {
  loadUsers()
  fetchPermissionMetadata()  // Fetches permissions from API
})
```

The dropdown dynamically renders options using v-for (~line 433):

```vue
<el-select
  v-model="permissionToGrant"
  placeholder="Select permission"
  :loading="loadingPermissions"
>
  <el-option
    v-for="perm in availablePermissions"
    :key="perm.name"
    :label="`${perm.name} - ${perm.description}`"
    :value="perm.name"
  />
</el-select>
```

**Result**: Any permission added to `PERMISSION_DEFINITIONS` in the backend will automatically appear in the frontend dropdown. No frontend code changes needed!

### 5. Hide UI Elements Based on Permission

**File**: `frontend/src/App.vue` (or relevant component)

Use conditional rendering to hide navigation items:

```vue
<!-- In sidebar menu -->
<el-menu-item
  v-if="userPermissions.includes('your_new_permission')"
  index="/your-route"
>
  <el-icon><YourIcon /></el-icon>
  <span>Your Feature</span>
</el-menu-item>
```

For other UI elements:

```vue
<!-- Hide buttons -->
<el-button
  v-if="userPermissions.includes('your_new_permission')"
  @click="yourAction"
>
  Protected Action
</el-button>

<!-- Hide entire sections -->
<div v-if="userPermissions.includes('your_new_permission')">
  <!-- Protected content -->
</div>

<!-- Hide tabs -->
<el-tab-pane
  v-if="userPermissions.includes('your_new_permission')"
  label="Protected Tab"
  name="protected"
>
  <!-- Tab content -->
</el-tab-pane>
```

**Don't forget to import userPermissions**:

```javascript
import { userPermissions } from '../auth'
// or from './auth' depending on file location
```

And expose it in the component's return statement:

```javascript
return {
  // ... other properties
  userPermissions
}
```

### 6. Add Route Guard (Optional)

**File**: `frontend/src/router.js`

If you want to protect an entire route, add the permission requirement:

```javascript
{
  path: '/your-route',
  name: 'YourRoute',
  component: YourComponent,
  meta: { requiresAuth: true, requiresPermission: 'your_new_permission' }
}
```

The existing route guard logic will automatically:
- Check if the user has the required permission
- Redirect to `/admin` with error message if permission is missing
- Show error: "You do not have permission to access this page."

**Note**: Only add route guards if the entire page requires the permission. For granular control (like hiding individual features), use UI-level conditional rendering instead.

## Complete Example: create_provisioning_key Permission

Here's a real example of the `create_provisioning_key` permission implementation:

### Backend: Permission Definitions
```python
# server/api.py, line 38
PERMISSION_DEFINITIONS = [
    {
        'name': 'create_users',
        'description': 'Can create and manage users',
        'category': 'administration'
    },
    {
        'name': 'create_provisioning_key',
        'description': 'Can create provisioning keys for runners',
        'category': 'provisioning'
    }
]

# Helper to get list of valid permission names
VALID_PERMISSIONS = [p['name'] for p in PERMISSION_DEFINITIONS]
```

### Backend: API Protection
```python
# server/api.py, line 2200
@self.app.route('/api/provisioning/keys', methods=['POST'])
@self.require_admin_auth
@self.require_csrf
def create_provisioning_key():
    """Create a new provisioning API key."""
    # Check create_provisioning_key permission
    if not self.db.has_permission(request.admin_username, 'create_provisioning_key'):
        logger.warning(
            f"SECURITY: Provisioning key creation denied - username='{request.admin_username}' "
            f"missing 'create_provisioning_key' permission ip={request.remote_addr}"
        )
        return jsonify({'error': 'Permission denied: create_provisioning_key permission required'}), 403

    # ... rest of function
```

### Backend: Initial Admin Grant
```python
# server/api.py, line 1426
# Grant all permissions to initial admin user
for permission in VALID_PERMISSIONS:
    self.db.grant_permission(username, permission, 'system')
```

**Note**: All permissions in `VALID_PERMISSIONS` are automatically granted, including `create_provisioning_key`.

### Backend: Permission Metadata API
```python
# server/api.py, line 1686
@self.app.route('/api/permissions/metadata', methods=['GET'])
@self.require_admin_auth
def get_permission_metadata():
    """Return all available permissions with their metadata."""
    return jsonify({
        'permissions': PERMISSION_DEFINITIONS
    }), 200
```

### Frontend: Permission Fetching
```javascript
// frontend/src/views/Users.vue, line 786
const fetchPermissionMetadata = async () => {
  const response = await api.get('/permissions/metadata')
  availablePermissions.value = response.data.permissions
}

onMounted(() => {
  loadUsers()
  fetchPermissionMetadata()  // Automatically fetches all permissions
})
```

### Frontend: Dynamic Permission Dropdown
```vue
<!-- frontend/src/views/Users.vue, line 433 -->
<el-select v-model="permissionToGrant" :loading="loadingPermissions">
  <el-option
    v-for="perm in availablePermissions"
    :key="perm.name"
    :label="`${perm.name} - ${perm.description}`"
    :value="perm.name"
  />
</el-select>
```

**Note**: The dropdown automatically includes `create_provisioning_key` and all other permissions from the API.

### Frontend: UI Conditional Rendering
```vue
<!-- frontend/src/views/Runners.vue, line 501 -->
<el-tab-pane
  v-if="userPermissions.includes('create_provisioning_key')"
  label="Provisioning Keys"
  name="provisioning"
>
  <!-- Tab content -->
</el-tab-pane>
```

## Permission Naming Conventions

Follow these conventions when naming permissions:

- Use **snake_case**: `create_users`, `manage_challenges`
- Use **verb_noun** format: `create_provisioning_key`, `delete_runners`
- Be specific: `create_provisioning_key` not just `provisioning`
- Keep it concise: shorter names are easier to work with

## Testing New Permissions

After implementing a new permission:

1. **Test as admin** (with permission):
   - Verify UI elements are visible
   - Verify API endpoints work
   - Verify route navigation works

2. **Test as user without permission**:
   - Verify UI elements are hidden
   - Verify API returns 403 Forbidden
   - Verify route redirects with error message

3. **Test permission granting**:
   - Grant permission via Users page
   - Verify user immediately gets access (may need to refresh)
   - Revoke permission and verify access is removed

## Granting Permissions to Existing Users

If you add a new permission and need to grant it to existing admin users:

### Via Web UI
1. Navigate to Users page
2. Click "Actions" → "Manage Permissions" for the user
3. Select your new permission from dropdown
4. Click "Grant Permission"

### Via Database (Direct)
```bash
sqlite3 data/challengectl.db "INSERT INTO user_permissions (username, permission_name, granted_by, granted_at) VALUES ('admin_username', 'your_new_permission', 'system', datetime('now'));"
```

### Via API
```bash
curl -X POST https://your-server/api/users/username/permissions \
  -H "Content-Type: application/json" \
  -d '{"permission_name": "your_new_permission"}'
```

## Database Schema

Permissions are stored in the `user_permissions` table:

```sql
CREATE TABLE user_permissions (
    username TEXT NOT NULL,
    permission_name TEXT NOT NULL,
    granted_by TEXT NOT NULL,
    granted_at TEXT NOT NULL,
    PRIMARY KEY (username, permission_name),
    FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
);
```

## Common Patterns

### Pattern 1: Feature Permission
Protect an entire feature (e.g., user management):
- Permission: `create_users`
- Protects: User CRUD operations, permission management
- UI: Hide Users menu item, hide all user management UI

### Pattern 2: Action Permission
Protect specific actions within a feature (e.g., provisioning keys):
- Permission: `create_provisioning_key`
- Protects: Creating/deleting provisioning keys
- UI: Show feature, hide specific actions (Provisioning Keys tab)

### Pattern 3: Read vs Write
Separate read and write permissions:
- Permission: `view_logs` and `manage_logs`
- Protects: Viewing vs clearing/exporting logs
- UI: Show logs to all, hide management buttons

## Security Best Practices

1. **Always validate on backend**: Never trust frontend-only restrictions
2. **Log permission denials**: Help detect unauthorized access attempts
3. **Use descriptive error messages**: Help legitimate users understand restrictions
4. **Check permissions early**: Fail fast before performing expensive operations
5. **Grant least privilege**: Only give users permissions they need
6. **Document permissions**: Keep this wiki updated with new permissions

## Troubleshooting

### Permission not working after adding to whitelist
- Restart the server to reload the permission whitelist
- Verify the permission name matches exactly (case-sensitive)

### UI still shows after revoking permission
- User may need to refresh the page
- Check browser console for errors
- Verify `userPermissions` is properly imported and exposed

### API returns 403 even with permission
- Check database: `SELECT * FROM user_permissions WHERE username='your_user';`
- Verify permission name spelling in database matches code
- Check server logs for the specific error message

### Route guard not working
- Verify `requiresPermission` is spelled correctly in route meta
- Check that route guard logic includes permission checking
- Import and use `hasPermission` from auth module

## Related Documentation

- [Web Interface Guide](Web-Interface-Guide) - Managing users and permissions via UI
- [API Reference](API-Reference) - API endpoints and authentication
- [Architecture](Architecture) - System design and security model
