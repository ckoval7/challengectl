<template>
  <div class="users-container">
    <div class="header">
      <h1>User Management</h1>
      <el-button
        type="primary"
        @click="showCreateDialog = true"
      >
        <el-icon><Plus /></el-icon>
        Create User
      </el-button>
    </div>

    <el-table
      v-loading="loading"
      :data="users"
      style="width: 100%"
    >
      <el-table-column
        prop="username"
        label="Username"
      />
      <el-table-column
        label="Status"
        width="120"
      >
        <template #default="scope">
          <el-tag :type="scope.row.enabled ? 'success' : 'danger'">
            {{ scope.row.enabled ? 'Enabled' : 'Disabled' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        label="Password Status"
        width="150"
      >
        <template #default="scope">
          <el-tag
            v-if="scope.row.password_change_required"
            type="warning"
          >
            Change Required
          </el-tag>
          <el-tag
            v-else
            type="success"
          >
            OK
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        prop="created_at"
        label="Created"
        width="180"
      />
      <el-table-column
        prop="last_login"
        label="Last Login"
        width="180"
      >
        <template #default="scope">
          {{ scope.row.last_login || 'Never' }}
        </template>
      </el-table-column>
      <el-table-column
        label="Permissions"
        width="150"
      >
        <template #default="scope">
          <el-tag
            v-for="perm in (scope.row.permissions || [])"
            :key="perm"
            size="small"
            style="margin: 2px"
          >
            {{ perm }}
          </el-tag>
          <el-tag
            v-if="!scope.row.permissions || scope.row.permissions.length === 0"
            size="small"
            type="info"
          >
            None
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        label="Actions"
        width="120"
        align="center"
      >
        <template #default="scope">
          <el-dropdown @command="(command) => handleUserAction(command, scope.row)">
            <el-button size="small" type="primary">
              Actions
              <el-icon style="margin-left: 5px;"><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item :command="scope.row.enabled ? 'disable' : 'enable'">
                  <el-icon><Switch /></el-icon>
                  {{ scope.row.enabled ? 'Disable User' : 'Enable User' }}
                </el-dropdown-item>
                <el-dropdown-item command="permissions">
                  <el-icon><Key /></el-icon>
                  Manage Permissions
                </el-dropdown-item>
                <el-dropdown-item command="reset-password" divided>
                  <el-icon><Lock /></el-icon>
                  Reset Password
                </el-dropdown-item>
                <el-dropdown-item command="reset-totp">
                  <el-icon><Unlock /></el-icon>
                  Reset TOTP
                </el-dropdown-item>
                <el-dropdown-item command="delete" divided>
                  <el-icon><Delete /></el-icon>
                  <span style="color: var(--el-color-danger);">Delete User</span>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
      </el-table-column>
    </el-table>

    <!-- Create User Dialog -->
    <el-dialog
      v-model="showCreateDialog"
      title="Create New User"
      width="500px"
    >
      <el-form
        ref="createFormRef"
        :model="createForm"
        label-width="140px"
        @submit.prevent="createUser"
      >
        <el-form-item
          label="Username"
          prop="username"
          :rules="[{ required: true, message: 'Please enter username' }]"
        >
          <el-input
            v-model="createForm.username"
            placeholder="Enter username"
            @keyup.enter="createUser"
          />
        </el-form-item>
        <el-alert
          type="info"
          :closable="false"
          show-icon
          style="margin-bottom: 20px"
        >
          An initial password will be automatically generated. The new user will be required to change their password and set up two-factor authentication on first login.
        </el-alert>
      </el-form>

      <template #footer>
        <el-button @click="showCreateDialog = false">
          Cancel
        </el-button>
        <el-button
          type="primary"
          :loading="creating"
          @click="createUser"
        >
          Create
        </el-button>
      </template>
    </el-dialog>

    <!-- New User Created Dialog -->
    <el-dialog
      v-model="showTempUserDialog"
      title="User Created"
      width="600px"
    >
      <el-alert
        type="success"
        :closable="false"
        style="margin-bottom: 20px"
      >
        <template #title>
          User created successfully! Share these credentials:
        </template>
      </el-alert>

      <div class="user-info">
        <el-form label-width="180px">
          <el-form-item label="Username:">
            <el-input
              :model-value="tempUserInfo.username"
              readonly
            >
              <template #append>
                <el-button @click="copyToClipboard(tempUserInfo.username)">
                  Copy
                </el-button>
              </template>
            </el-input>
          </el-form-item>
          <el-form-item label="Initial Password:">
            <el-input
              :model-value="tempUserInfo.password"
              readonly
              type="text"
            >
              <template #append>
                <el-button @click="copyToClipboard(tempUserInfo.password)">
                  Copy
                </el-button>
              </template>
            </el-input>
          </el-form-item>
        </el-form>

        <el-alert
          type="warning"
          :closable="false"
          show-icon
          style="margin-top: 20px"
        >
          <template #title>
            {{ tempUserInfo.username }} must set up their account within 24 hours.
          </template>
          <p style="margin: 10px 0 0 0">They must log in and complete the following steps:</p>
          <ul style="margin: 5px 0 0 20px; padding: 0">
            <li>Change their password.</li>
            <li>Set up two-factor authentication (2FA).</li>
          </ul>
          <p style="margin: 10px 0 0 0">If setup is not completed within 24 hours, the account will be automatically disabled.</p>
        </el-alert>
      </div>

      <template #footer>
        <el-button
          type="primary"
          @click="showTempUserDialog = false"
        >
          Done
        </el-button>
      </template>
    </el-dialog>

    <!-- Password Reset Dialog -->
    <el-dialog
      v-model="showPasswordResetDialog"
      title="Password Reset"
      width="600px"
    >
      <el-alert
        type="success"
        :closable="false"
        style="margin-bottom: 20px"
      >
        <template #title>
          Password reset successfully! Share these credentials:
        </template>
      </el-alert>

      <div class="user-info">
        <el-form label-width="180px">
          <el-form-item label="Username:">
            <el-input
              :model-value="resetPasswordInfo.username"
              readonly
            >
              <template #append>
                <el-button @click="copyToClipboard(resetPasswordInfo.username)">
                  Copy
                </el-button>
              </template>
            </el-input>
          </el-form-item>
          <el-form-item label="New Password:">
            <el-input
              :model-value="resetPasswordInfo.password"
              readonly
              type="text"
            >
              <template #append>
                <el-button @click="copyToClipboard(resetPasswordInfo.password)">
                  Copy
                </el-button>
              </template>
            </el-input>
          </el-form-item>
        </el-form>

        <el-alert
          type="warning"
          :closable="false"
          show-icon
          style="margin-top: 20px"
        >
          <template #title>
            {{ resetPasswordInfo.username }} must change their password on next login.
          </template>
          <p style="margin: 10px 0 0 0">The user will be required to change this temporary password when they log in. All existing sessions for this user have been invalidated.</p>
        </el-alert>
      </div>

      <template #footer>
        <el-button
          type="primary"
          @click="showPasswordResetDialog = false"
        >
          Done
        </el-button>
      </template>
    </el-dialog>

    <!-- TOTP Secret Dialog (for Reset TOTP feature) -->
    <el-dialog
      v-model="showTotpDialog"
      title="TOTP Secret"
      width="600px"
    >
      <el-alert
        type="success"
        :closable="false"
        style="margin-bottom: 20px"
      >
        <template #title>
          TOTP reset successfully! Save these details:
        </template>
      </el-alert>

      <div class="totp-info">
        <p><strong>Username:</strong> {{ totpInfo.username }}</p>
        <p><strong>TOTP Secret:</strong></p>
        <el-input
          :model-value="totpInfo.totp_secret"
          readonly
          style="margin-bottom: 10px"
        >
          <template #append>
            <el-button @click="copyToClipboard(totpInfo.totp_secret)">
              Copy
            </el-button>
          </template>
        </el-input>

        <p><strong>Setup Instructions:</strong></p>
        <ol>
          <li>Scan this QR code with an authenticator app (Google Authenticator, Authy, etc.)</li>
          <li>Or manually enter the TOTP secret above</li>
          <li>Save the credentials securely and share them with the user</li>
        </ol>

        <div
          v-if="totpInfo.qrCode"
          class="qr-code"
        >
          <img
            :src="totpInfo.qrCode"
            alt="QR Code"
          >
        </div>
      </div>

      <template #footer>
        <el-button
          type="primary"
          @click="showTotpDialog = false"
        >
          Done
        </el-button>
      </template>
    </el-dialog>

    <!-- Manage Permissions Dialog -->
    <el-dialog
      v-model="showPermissionsDialog"
      title="Manage Permissions"
      width="500px"
    >
      <div v-if="selectedUser">
        <h3>User: {{ selectedUser.username }}</h3>

        <h4 style="margin-top: 20px">Current Permissions:</h4>
        <div v-if="userPermissions.length > 0" style="margin-bottom: 20px">
          <el-tag
            v-for="perm in userPermissions"
            :key="perm"
            closable
            @close="revokePermission(perm)"
            style="margin: 5px"
          >
            {{ perm }}
          </el-tag>
        </div>
        <el-tag v-else type="info" style="margin-bottom: 20px">
          No permissions granted
        </el-tag>

        <h4>Grant Permission:</h4>
        <el-select
          v-model="permissionToGrant"
          placeholder="Select permission"
          style="width: 100%; margin-bottom: 10px"
        >
          <el-option
            label="create_users - Can create and manage users"
            value="create_users"
          />
          <el-option
            label="create_provisioning_key - Can create provisioning keys for runners"
            value="create_provisioning_key"
          />
        </el-select>
        <el-button
          type="primary"
          :disabled="!permissionToGrant"
          @click="grantPermission"
          style="width: 100%"
        >
          Grant Permission
        </el-button>
      </div>

      <template #footer>
        <el-button @click="showPermissionsDialog = false">
          Close
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { Plus, ArrowDown, Switch, Key, Lock, Unlock, Delete } from '@element-plus/icons-vue'
import { api } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import QRCode from 'qrcode'

export default {
  name: 'Users',
  components: {
    Plus,
    ArrowDown,
    Switch,
    Key,
    Lock,
    Unlock,
    Delete
  },
  setup() {
    const users = ref([])
    const loading = ref(false)
    const showCreateDialog = ref(false)
    const showTotpDialog = ref(false)
    const showTempUserDialog = ref(false)
    const showPasswordResetDialog = ref(false)
    const showPermissionsDialog = ref(false)
    const creating = ref(false)
    const createFormRef = ref(null)
    const createForm = ref({
      username: ''
    })
    const tempUserInfo = ref({
      username: '',
      password: ''
    })
    const resetPasswordInfo = ref({
      username: '',
      password: ''
    })
    const totpInfo = ref({
      username: '',
      totp_secret: '',
      provisioning_uri: '',
      qrCode: null
    })
    const selectedUser = ref(null)
    const userPermissions = ref([])
    const permissionToGrant = ref('')

    const loadUsers = async () => {
      loading.value = true
      try {
        const response = await api.get('/users')
        users.value = response.data.users
      } catch (error) {
        ElMessage.error('Failed to load users')
      } finally {
        loading.value = false
      }
    }

    const createUser = async () => {
      if (!createFormRef.value) return

      try {
        await createFormRef.value.validate()
      } catch (error) {
        return
      }

      creating.value = true

      try {
        const response = await api.post('/users', {
          username: createForm.value.username
        })

        showCreateDialog.value = false

        // Check if this is a new user requiring setup or initial setup
        if (response.data.is_temporary) {
          // New user - show initial password
          tempUserInfo.value = {
            username: response.data.username,
            password: response.data.temporary_password
          }
          showTempUserDialog.value = true
        } else {
          // Initial setup - show TOTP QR code
          const qrCodeDataUrl = await QRCode.toDataURL(response.data.provisioning_uri)

          totpInfo.value = {
            username: response.data.username,
            totp_secret: response.data.totp_secret,
            provisioning_uri: response.data.provisioning_uri,
            qrCode: qrCodeDataUrl
          }
          showTotpDialog.value = true
        }

        createForm.value.username = ''

        loadUsers()
      } catch (error) {
        if (error.response?.status === 409) {
          ElMessage.error('Username already exists')
        } else if (error.response?.data?.error) {
          ElMessage.error(error.response.data.error)
        } else {
          ElMessage.error('Failed to create user')
        }
      } finally {
        creating.value = false
      }
    }

    const toggleUserStatus = async (user) => {
      try {
        await api.put(`/users/${user.username}`, {
          enabled: !user.enabled
        })

        ElMessage.success(`User ${user.enabled ? 'disabled' : 'enabled'} successfully`)
        loadUsers()
      } catch (error) {
        if (error.response?.data?.error) {
          ElMessage.error(error.response.data.error)
        } else {
          ElMessage.error('Failed to update user status')
        }
      }
    }

    const showResetTotpDialog = async (user) => {
      try {
        await ElMessageBox.confirm(
          `This will reset the TOTP secret for user "${user.username}". The user will need to reconfigure their authenticator app. Continue?`,
          'Reset TOTP',
          {
            confirmButtonText: 'Reset',
            cancelButtonText: 'Cancel',
            type: 'warning'
          }
        )

        const response = await api.post(`/users/${user.username}/reset-totp`)

        // Generate QR code
        const qrCodeDataUrl = await QRCode.toDataURL(response.data.provisioning_uri)

        totpInfo.value = {
          username: user.username,
          totp_secret: response.data.totp_secret,
          provisioning_uri: response.data.provisioning_uri,
          qrCode: qrCodeDataUrl
        }

        showTotpDialog.value = true
        ElMessage.success('TOTP reset successfully')
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error('Failed to reset TOTP')
        }
      }
    }

    const resetUserPassword = async (user) => {
      try {
        await ElMessageBox.confirm(
          `This will reset the password for user "${user.username}". A new temporary password will be generated and all existing sessions will be invalidated. The user will be required to change their password on next login. Continue?`,
          'Reset Password',
          {
            confirmButtonText: 'Reset',
            cancelButtonText: 'Cancel',
            type: 'warning'
          }
        )

        const response = await api.post(`/users/${user.username}/reset-password`)

        resetPasswordInfo.value = {
          username: user.username,
          password: response.data.temporary_password
        }

        showPasswordResetDialog.value = true
        ElMessage.success('Password reset successfully')
        loadUsers()
      } catch (error) {
        if (error !== 'cancel') {
          if (error.response?.data?.error) {
            ElMessage.error(error.response.data.error)
          } else {
            ElMessage.error('Failed to reset password')
          }
        }
      }
    }

    const confirmDelete = async (user) => {
      try {
        await ElMessageBox.confirm(
          `Are you sure you want to delete user "${user.username}"? This action cannot be undone.`,
          'Delete User',
          {
            confirmButtonText: 'Delete',
            cancelButtonText: 'Cancel',
            type: 'error'
          }
        )

        await api.delete(`/users/${user.username}`)

        ElMessage.success('User deleted successfully')
        loadUsers()
      } catch (error) {
        if (error !== 'cancel') {
          if (error.response?.data?.error) {
            ElMessage.error(error.response.data.error)
          } else {
            ElMessage.error('Failed to delete user')
          }
        }
      }
    }

    const handleUserAction = (command, user) => {
      switch (command) {
        case 'enable':
        case 'disable':
          toggleUserStatus(user)
          break
        case 'permissions':
          showManagePermissionsDialog(user)
          break
        case 'reset-password':
          resetUserPassword(user)
          break
        case 'reset-totp':
          showResetTotpDialog(user)
          break
        case 'delete':
          confirmDelete(user)
          break
      }
    }

    const copyToClipboard = async (text) => {
      try {
        await navigator.clipboard.writeText(text)
        ElMessage.success('Copied to clipboard')
      } catch (error) {
        ElMessage.error('Failed to copy to clipboard')
      }
    }

    const showManagePermissionsDialog = async (user) => {
      selectedUser.value = user
      permissionToGrant.value = ''
      await loadUserPermissions(user.username)
      showPermissionsDialog.value = true
    }

    const loadUserPermissions = async (username) => {
      try {
        const response = await api.get(`/users/${username}/permissions`)
        userPermissions.value = response.data.permissions || []
      } catch (error) {
        ElMessage.error('Failed to load permissions')
        userPermissions.value = []
      }
    }

    const grantPermission = async () => {
      if (!permissionToGrant.value || !selectedUser.value) return

      try {
        await api.post(`/users/${selectedUser.value.username}/permissions`, {
          permission_name: permissionToGrant.value
        })

        ElMessage.success(`Granted permission: ${permissionToGrant.value}`)
        permissionToGrant.value = ''
        await loadUserPermissions(selectedUser.value.username)
        await loadUsers() // Refresh user list to update permissions column
      } catch (error) {
        if (error.response?.data?.error) {
          ElMessage.error(error.response.data.error)
        } else {
          ElMessage.error('Failed to grant permission')
        }
      }
    }

    const revokePermission = async (permission) => {
      if (!selectedUser.value) return

      try {
        await ElMessageBox.confirm(
          `Revoke "${permission}" permission from user "${selectedUser.value.username}"?`,
          'Revoke Permission',
          {
            confirmButtonText: 'Revoke',
            cancelButtonText: 'Cancel',
            type: 'warning'
          }
        )

        await api.delete(`/users/${selectedUser.value.username}/permissions/${permission}`)

        ElMessage.success(`Revoked permission: ${permission}`)
        await loadUserPermissions(selectedUser.value.username)
        await loadUsers() // Refresh user list to update permissions column
      } catch (error) {
        if (error !== 'cancel') {
          if (error.response?.data?.error) {
            ElMessage.error(error.response.data.error)
          } else {
            ElMessage.error('Failed to revoke permission')
          }
        }
      }
    }

    onMounted(() => {
      loadUsers()
    })

    return {
      users,
      loading,
      showCreateDialog,
      showTotpDialog,
      showTempUserDialog,
      showPasswordResetDialog,
      showPermissionsDialog,
      creating,
      createFormRef,
      createForm,
      totpInfo,
      tempUserInfo,
      resetPasswordInfo,
      selectedUser,
      userPermissions,
      permissionToGrant,
      loadUsers,
      createUser,
      toggleUserStatus,
      showManagePermissionsDialog,
      showResetTotpDialog,
      resetUserPassword,
      confirmDelete,
      handleUserAction,
      copyToClipboard,
      grantPermission,
      revokePermission
    }
  }
}
</script>

<style scoped>
.users-container {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header h1 {
  margin: 0;
}

.totp-info {
  padding: 10px;
}

.totp-info p {
  margin: 10px 0;
}

.totp-info strong {
  color: var(--el-text-color-primary);
}

.totp-info ol {
  margin: 10px 0;
  padding-left: 20px;
}

.qr-code {
  display: flex;
  justify-content: center;
  padding: 20px;
  background: white;
  border-radius: 8px;
  margin-top: 20px;
}

.qr-code img {
  max-width: 300px;
}
</style>
