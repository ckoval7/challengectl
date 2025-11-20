<template>
  <div class="setup-container">
    <el-card class="setup-card">
      <template #header>
        <div class="card-header">
          <h2>Welcome to ChallengeCtl</h2>
        </div>
      </template>

      <el-alert
        type="info"
        :closable="false"
        style="margin-bottom: 20px"
      >
        <template #title>
          Create your admin account with TOTP 2FA
        </template>
      </el-alert>

      <p style="margin-bottom: 20px">
        You've logged in with the default admin account. Create your personal admin account
        with TOTP two-factor authentication for secure access.
      </p>

      <el-form
        ref="formRef"
        :model="form"
        label-position="top"
        @submit.prevent="handleCreate"
      >
        <el-form-item
          label="Username"
          prop="username"
          :rules="[
            { required: true, message: 'Please enter username', trigger: 'blur' },
            { min: 3, message: 'Username must be at least 3 characters', trigger: 'blur' }
          ]"
        >
          <el-input
            v-model="form.username"
            placeholder="Enter your username"
            size="large"
          />
        </el-form-item>

        <el-form-item
          label="Password"
          prop="password"
          :rules="[
            { required: true, message: 'Please enter password', trigger: 'blur' },
            { min: 8, message: 'Password must be at least 8 characters', trigger: 'blur' }
          ]"
        >
          <el-input
            v-model="form.password"
            type="password"
            placeholder="Minimum 8 characters"
            show-password
            size="large"
          />
        </el-form-item>

        <el-form-item
          label="Confirm Password"
          prop="confirmPassword"
          :rules="[
            { required: true, message: 'Please confirm password', trigger: 'blur' },
            { validator: validatePasswordMatch, trigger: 'blur' }
          ]"
        >
          <el-input
            v-model="form.confirmPassword"
            type="password"
            placeholder="Confirm password"
            show-password
            size="large"
            @keyup.enter="handleCreate"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            style="width: 100%"
            :loading="loading"
            @click="handleCreate"
          >
            Create Account
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- TOTP Setup Dialog -->
    <el-dialog
      v-model="showTotpDialog"
      title="Set Up Two-Factor Authentication"
      width="600px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="false"
    >
      <el-alert
        type="success"
        :closable="false"
        style="margin-bottom: 20px"
      >
        <template #title>
          Account created! Set up TOTP to complete setup.
        </template>
      </el-alert>

      <div class="totp-setup">
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
          @keyup.enter="handleVerifyAndLogin"
        />

        <el-button
          type="primary"
          size="large"
          style="width: 100%"
          :loading="verifying"
          @click="handleVerifyAndLogin"
        >
          Verify and Continue
        </el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { login } from '../auth'
import { api } from '../api'
import { ElMessage } from 'element-plus'
import QRCode from 'qrcode'

export default {
  name: 'InitialSetup',
  setup() {
    const router = useRouter()
    const formRef = ref(null)
    const form = ref({
      username: '',
      password: '',
      confirmPassword: ''
    })
    const loading = ref(false)
    const showTotpDialog = ref(false)
    const totpInfo = ref({
      username: '',
      password: '',
      totp_secret: '',
      provisioning_uri: '',
      qrCode: null
    })
    const totpVerifyCode = ref('')
    const verifying = ref(false)

    const validatePasswordMatch = (rule, value, callback) => {
      if (value !== form.value.password) {
        callback(new Error('Passwords do not match'))
      } else {
        callback()
      }
    }

    const handleCreate = async () => {
      if (!formRef.value) return

      try {
        await formRef.value.validate()
      } catch (error) {
        return
      }

      loading.value = true

      try {
        const response = await api.post('/users', {
          username: form.value.username,
          password: form.value.password
        })

        // Generate QR code
        const qrCodeDataUrl = await QRCode.toDataURL(response.data.provisioning_uri)

        totpInfo.value = {
          username: form.value.username,
          password: form.value.password,
          totp_secret: response.data.totp_secret,
          provisioning_uri: response.data.provisioning_uri,
          qrCode: qrCodeDataUrl
        }

        showTotpDialog.value = true
        ElMessage.success('Account created! Set up TOTP to continue.')
      } catch (error) {
        if (error.response?.status === 409) {
          ElMessage.error('Username already exists')
        } else if (error.response?.data?.error) {
          ElMessage.error(error.response.data.error)
        } else {
          ElMessage.error('Failed to create account')
        }
      } finally {
        loading.value = false
      }
    }

    const handleVerifyAndLogin = async () => {
      if (!totpVerifyCode.value || totpVerifyCode.value.length !== 6) {
        ElMessage.error('Please enter a 6-digit TOTP code')
        return
      }

      verifying.value = true

      try {
        // Log in with the new account
        const loginResponse = await api.post('/auth/login', {
          username: totpInfo.value.username,
          password: totpInfo.value.password
        })

        // Verify TOTP (should be required for new account)
        if (loginResponse.data.totp_required) {
          const verifyResponse = await api.post('/auth/verify-totp', {
            totp_code: totpVerifyCode.value
          })

          login(false) // Initial setup is complete
          ElMessage.success('Setup complete! Welcome to ChallengeCtl.')
          router.push('/admin')
        } else {
          // Shouldn't happen, but handle it
          login(false) // Initial setup is complete
          ElMessage.success('Setup complete! Welcome to ChallengeCtl.')
          router.push('/admin')
        }
      } catch (error) {
        if (error.response?.status === 401) {
          ElMessage.error('Invalid TOTP code. Please try again.')
          totpVerifyCode.value = ''
        } else if (error.response?.data?.error) {
          ElMessage.error(error.response.data.error)
        } else {
          ElMessage.error('Verification failed. Please try again.')
        }
      } finally {
        verifying.value = false
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
      verifying,
      validatePasswordMatch,
      handleCreate,
      handleVerifyAndLogin,
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

.totp-setup p {
  margin: 15px 0;
}

.totp-setup strong {
  color: var(--el-text-color-primary);
}

.qr-code {
  display: flex;
  justify-content: center;
  padding: 20px;
  background: white;
  border-radius: 8px;
  margin: 20px 0;
}

.qr-code img {
  max-width: 250px;
}
</style>
