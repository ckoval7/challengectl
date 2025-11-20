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
        class="mb-xl"
      >
        <template #title>
          You must set up your account within 24 hours.
        </template>
        <p>Please complete the setup process by changing your password and enabling two-factor authentication. If setup is not completed within 24 hours, your account will be automatically disabled.</p>
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
            class="w-full"
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
          class="mb-xl"
        >
          <template #title>
            Set up two-factor authentication.
          </template>
        </el-alert>

        <p><strong>Step 1:</strong> Scan this QR code with your authenticator app (such as Google Authenticator or Authy).</p>

        <div
          v-if="totpInfo.qrCode"
          class="qr-code"
        >
          <img
            :src="totpInfo.qrCode"
            alt="QR Code"
          >
        </div>

        <p><strong>Step 2:</strong> Alternatively, you can manually enter this secret into your authenticator app.</p>
        <el-input
          :model-value="totpInfo.totp_secret"
          readonly
          class="mb-xl"
        >
          <template #append>
            <el-button @click="copyToClipboard(totpInfo.totp_secret)">
              Copy
            </el-button>
          </template>
        </el-input>

        <p><strong>Step 3:</strong> Enter the 6-digit code from your authenticator app to verify the setup.</p>
        <el-input
          v-model="totpVerifyCode"
          placeholder="000000"
          maxlength="6"
          size="large"
          class="mb-xl"
          @keyup.enter="handleFinishSetup"
        />

        <el-button
          type="primary"
          size="large"
          class="w-full"
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
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.setup-card {
  width: 100%;
  max-width: 400px;
}

.card-header h2 {
  margin: 0;
  text-align: center;
  color: var(--el-text-color-primary);
}

.totp-setup {
  text-align: center;
}

.totp-setup p {
  margin-bottom: 15px;
  text-align: left;
  color: var(--el-text-color-regular);
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
