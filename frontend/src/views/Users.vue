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
        label="Actions"
        width="300"
      >
        <template #default="scope">
          <el-button
            size="small"
            :type="scope.row.enabled ? 'warning' : 'success'"
            @click="toggleUserStatus(scope.row)"
          >
            {{ scope.row.enabled ? 'Disable' : 'Enable' }}
          </el-button>
          <el-button
            size="small"
            @click="showResetTotpDialog(scope.row)"
          >
            Reset TOTP
          </el-button>
          <el-button
            size="small"
            type="danger"
            @click="confirmDelete(scope.row)"
          >
            Delete
          </el-button>
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
      >
        <el-form-item
          label="Username"
          prop="username"
          :rules="[{ required: true, message: 'Please enter username' }]"
        >
          <el-input
            v-model="createForm.username"
            placeholder="Enter username"
          />
        </el-form-item>
        <el-form-item
          label="Password"
          prop="password"
          :rules="[
            { required: true, message: 'Please enter password' },
            { min: 8, message: 'Password must be at least 8 characters' }
          ]"
        >
          <el-input
            v-model="createForm.password"
            type="password"
            placeholder="Minimum 8 characters"
            show-password
          />
        </el-form-item>
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

    <!-- TOTP Secret Dialog -->
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
          User created successfully! Save these details:
        </template>
      </el-alert>

      <div class="totp-info">
        <p><strong>Username:</strong> {{ totpInfo.username }}</p>
        <p><strong>Password:</strong> (as entered)</p>
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
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { api } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import QRCode from 'qrcode'

export default {
  name: 'Users',
  components: {
    Plus
  },
  setup() {
    const users = ref([])
    const loading = ref(false)
    const showCreateDialog = ref(false)
    const showTotpDialog = ref(false)
    const creating = ref(false)
    const createFormRef = ref(null)
    const createForm = ref({
      username: '',
      password: ''
    })
    const totpInfo = ref({
      username: '',
      totp_secret: '',
      provisioning_uri: '',
      qrCode: null
    })

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
          username: createForm.value.username,
          password: createForm.value.password
        })

        // Generate QR code
        const qrCodeDataUrl = await QRCode.toDataURL(response.data.provisioning_uri)

        totpInfo.value = {
          username: response.data.username,
          totp_secret: response.data.totp_secret,
          provisioning_uri: response.data.provisioning_uri,
          qrCode: qrCodeDataUrl
        }

        showCreateDialog.value = false
        showTotpDialog.value = true

        createForm.value.username = ''
        createForm.value.password = ''

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

    const copyToClipboard = async (text) => {
      try {
        await navigator.clipboard.writeText(text)
        ElMessage.success('Copied to clipboard')
      } catch (error) {
        ElMessage.error('Failed to copy to clipboard')
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
      creating,
      createFormRef,
      createForm,
      totpInfo,
      loadUsers,
      createUser,
      toggleUserStatus,
      showResetTotpDialog,
      confirmDelete,
      copyToClipboard
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
