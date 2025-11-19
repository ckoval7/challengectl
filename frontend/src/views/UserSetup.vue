<template>
  <div class="setup-container">
    <el-card class="setup-card">
      <template #header>
        <div class="card-header">
          <h2>Complete Your Account Setup</h2>
        </div>
      </template>

      <el-alert
        type="warning"
        :closable="false"
        style="margin-bottom: 20px"
      >
        <template #title>
          Set up your account within 24 hours
        </template>
        <p>Your account is temporary. Complete setup by changing your password and enabling 2FA.</p>
      </el-alert>

      <el-form
        v-if="!showTotpDialog"
        ref="formRef"
        :model="form"
        label-position="top"
        @submit.prevent="handleCompleteSetup"
      >
        <el-form-item
          label="New Password"
          prop="newPassword"
          :rules="[
            { required: true, message: 'Please enter new password', trigger: 'blur' },
            { min: 8, message: 'Password must be at least 8 characters', trigger: 'blur' }
          ]"
        >
          <el-input
            v-model="form.newPassword"
            type="password"
            placeholder="Minimum 8 characters"
            show-password
            size="large"
          />
        </el-form-item>

        <el-form-item
          label="Confirm New Password"
          prop="confirmPassword"
          :rules="[
            { required: true, message: 'Please confirm password', trigger: 'blur' },
            { validator: validatePasswordMatch, trigger: 'blur' }
          ]"
        >
          <el-input
            v-model="form.confirmPassword"
            type="password"
            placeholder="Confirm new password"
            show-password
            size="large"
            @keyup.enter="handleCompleteSetup"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            style="width: 100%"
            :loading="loading"
            @click="handleCompleteSetup"
          >
            Continue to 2FA Setup
          </el-button>
        </el-form-item>
      </el-form>

      <!-- TOTP Setup Form -->
      <div v-if="showTotpDialog" class="totp-setup">
        <el-alert
          type="success"
          :closable="false"
          style="margin-bottom: 20px"
        >
          <template #title>
            Set up two-factor authentication
          </template>
        </el-alert>

        <p><strong>Step 1:</strong> Scan this QR code with your authenticator app (Google Authenticator, Authy, etc.):</p>

        <div
          v-if="totpInfo.qrCode"
          class="qr-code"
        >
          <img
            :src="totpInfo.qrCode"
            alt="QR Code"
          >
        </div>

        <p><strong>Step 2:</strong> Or manually enter this secret:</p>
        <el-input
          :model-value="totpInfo.totp_secret"
          readonly
          style="margin-bottom: 20px"
        >
          <template #append>
            <el-button @click="copyToClipboard(totpInfo.totp_secret)">
              Copy
            </el-button>
          </template>
        </el-input>

        <p><strong>Step 3:</strong> Enter a code from your authenticator app to verify:</p>
        <el-input
          v-model="totpVerifyCode"
          placeholder="000000"
          maxlength="6"
          size="large"
          style="margin-bottom: 20px"
          @keyup.enter="handleFinishSetup"
        />

        <el-button
          type="primary"
          size="large"
          style="width: 100%"
          :loading="loading"
          @click="handleFinishSetup"
        >
          Complete Setup
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { ElMessage } from 'element-plus'
import QRCode from 'qrcode'

export default {
  name: 'UserSetup',
  setup() {
    const router = useRouter()
    const formRef = ref(null)
    const form = ref({
      newPassword: '',
      confirmPassword: ''
    })
    const loading = ref(false)
    const showTotpDialog = ref(false)
    const totpInfo = ref({
      totp_secret: '',
      provisioning_uri: '',
      qrCode: ''
    })
    const totpVerifyCode = ref('')

    const validatePasswordMatch = (rule, value, callback) => {
      if (value !== form.value.newPassword) {
        callback(new Error('Passwords do not match'))
      } else {
        callback()
      }
    }

    const handleCompleteSetup = async () => {
      if (!formRef.value) return

      try {
        await formRef.value.validate()
      } catch (error) {
        return
      }

      loading.value = true

      try {
        // Call backend to change password and generate TOTP secret
        const response = await api.post('/auth/complete-setup', {
          new_password: form.value.newPassword
        })

        // Backend returns TOTP secret and provisioning URI
        const { totp_secret, provisioning_uri } = response.data

        // Generate QR code from provisioning URI
        const qrCode = await QRCode.toDataURL(provisioning_uri)

        totpInfo.value = {
          totp_secret: totp_secret,
          provisioning_uri: provisioning_uri,
          qrCode: qrCode
        }

        // Show TOTP setup dialog
        showTotpDialog.value = true
      } catch (error) {
        if (error.response?.status === 401) {
          ElMessage.error('Session expired. Please login again.')
          router.push('/login')
        } else {
          ElMessage.error(error.response?.data?.error || 'Failed to initiate setup')
        }
      } finally {
        loading.value = false
      }
    }

    const handleFinishSetup = async () => {
      if (!totpVerifyCode.value) {
        ElMessage.error('Please enter a TOTP code')
        return
      }

      if (!/^\d{6}$/.test(totpVerifyCode.value)) {
        ElMessage.error('TOTP code must be 6 digits')
        return
      }

      loading.value = true

      try {
        // Verify TOTP code and complete setup
        await api.post('/auth/verify-setup', {
          totp_code: totpVerifyCode.value
        })

        ElMessage.success('Account setup complete! You can now access the system.')
        router.push('/admin')
      } catch (error) {
        if (error.response?.status === 401) {
          const errorMsg = error.response?.data?.error || 'Authentication failed'
          if (errorMsg.includes('Invalid TOTP code')) {
            ElMessage.error('Invalid TOTP code. Please try again.')
          } else if (errorMsg.includes('Session expired')) {
            ElMessage.error('Session expired. Please login again.')
            router.push('/login')
          } else {
            ElMessage.error(errorMsg)
          }
        } else if (error.response?.status === 400) {
          ElMessage.error(error.response?.data?.error || 'Setup failed. Please restart the setup process.')
        } else {
          ElMessage.error('Failed to complete setup. Please try again.')
        }
      } finally {
        loading.value = false
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

    return {
      formRef,
      form,
      loading,
      showTotpDialog,
      totpInfo,
      totpVerifyCode,
      validatePasswordMatch,
      handleCompleteSetup,
      handleFinishSetup,
      copyToClipboard
    }
  }
}
</script>

<style scoped>
.setup-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: #f5f5f5;
  padding: 20px;
}

.setup-card {
  width: 100%;
  max-width: 500px;
}

.card-header {
  text-align: center;
}

.card-header h2 {
  margin: 0;
  color: #303133;
}

.totp-setup {
  text-align: center;
}

.totp-setup p {
  margin-bottom: 15px;
  text-align: left;
}

.qr-code {
  display: flex;
  justify-content: center;
  margin: 20px 0;
}

.qr-code img {
  max-width: 250px;
  height: auto;
}
</style>
