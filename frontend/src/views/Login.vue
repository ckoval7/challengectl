<template>
  <div class="login-container">
    <el-card class="login-card">
      <template #header>
        <div class="card-header">
          <h2>ChallengeCtl Admin Login</h2>
        </div>
      </template>

      <!-- Step 1: Username and Password -->
      <el-form
        v-if="!showTotpStep"
        ref="formRef"
        :model="form"
        label-position="top"
        @submit.prevent="handleLogin"
      >
        <el-form-item
          label="Username"
          prop="username"
          :rules="[
            { required: true, message: 'Please enter your username', trigger: 'blur' }
          ]"
        >
          <el-input
            v-model="form.username"
            placeholder="Enter your username"
            size="large"
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-form-item
          label="Password"
          prop="password"
          :rules="[
            { required: true, message: 'Please enter your password', trigger: 'blur' }
          ]"
        >
          <el-input
            v-model="form.password"
            type="password"
            placeholder="Enter your password"
            show-password
            size="large"
            @keyup.enter="handleLogin"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            style="width: 100%"
            :loading="loading"
            @click="handleLogin"
          >
            Continue
          </el-button>
        </el-form-item>
      </el-form>

      <!-- Step 2: TOTP Verification -->
      <el-form
        v-else
        ref="totpFormRef"
        :model="form"
        label-position="top"
        @submit.prevent="handleVerifyTotp"
      >
        <el-alert
          type="info"
          :closable="false"
          style="margin-bottom: 20px"
        >
          <template #title>
            Enter the 6-digit code from your authenticator app
          </template>
        </el-alert>

        <el-form-item
          label="TOTP Code"
          prop="totpCode"
          :rules="[
            { required: true, message: 'Please enter your TOTP code', trigger: 'blur' },
            { pattern: /^\d{6}$/, message: 'TOTP code must be 6 digits', trigger: 'blur' }
          ]"
        >
          <el-input
            v-model="form.totpCode"
            placeholder="000000"
            maxlength="6"
            size="large"
            @keyup.enter="handleVerifyTotp"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            style="width: 100%"
            :loading="loading"
            @click="handleVerifyTotp"
          >
            Login
          </el-button>
        </el-form-item>

        <el-form-item>
          <el-button
            size="large"
            style="width: 100%"
            @click="goBackToLogin"
          >
            Back
          </el-button>
        </el-form-item>
      </el-form>

      <div class="login-footer">
        <el-link
          type="primary"
          @click="goToPublicDashboard"
        >
          View Public Dashboard
        </el-link>
      </div>
    </el-card>
  </div>
</template>

<script>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { login } from '../auth'
import { api } from '../api'
import { ElMessage } from 'element-plus'

export default {
  name: 'Login',
  setup() {
    const router = useRouter()
    const formRef = ref(null)
    const totpFormRef = ref(null)
    const form = ref({
      username: '',
      password: '',
      totpCode: ''
    })
    const loading = ref(false)
    const showTotpStep = ref(false)
    const sessionToken = ref(null)

    const handleLogin = async () => {
      if (!formRef.value) return

      try {
        await formRef.value.validate()
      } catch (error) {
        return
      }

      loading.value = true

      try {
        // Step 1: Login with username and password
        const response = await api.post('/auth/login', {
          username: form.value.username,
          password: form.value.password
        })

        // Check if TOTP is required
        if (response.data.totp_required) {
          // Save session token and move to TOTP step
          sessionToken.value = response.data.session_token
          showTotpStep.value = true
          ElMessage.success('Password verified. Please enter your TOTP code.')
        } else {
          // No TOTP required - user logged in directly
          login(response.data.session_token)

          // Check if initial setup is required
          if (response.data.initial_setup_required) {
            ElMessage.info('Please create your admin account')
            router.push('/initial-setup')
          } else {
            ElMessage.success('Login successful')
            router.push('/admin')
          }
        }
      } catch (error) {
        if (error.response?.status === 401) {
          ElMessage.error('Invalid username or password')
        } else if (error.response?.status === 403) {
          ElMessage.error('Account disabled')
        } else {
          ElMessage.error('Login failed. Please try again.')
        }
      } finally {
        loading.value = false
      }
    }

    const handleVerifyTotp = async () => {
      if (!totpFormRef.value) return

      try {
        await totpFormRef.value.validate()
      } catch (error) {
        return
      }

      loading.value = true

      try {
        // Step 2: Verify TOTP code
        const response = await api.post('/auth/verify-totp', {
          session_token: sessionToken.value,
          totp_code: form.value.totpCode
        })

        // Save the authenticated session token
        login(response.data.session_token)

        // Check if password change is required
        if (response.data.password_change_required) {
          ElMessage.warning('Password change required')
          router.push('/change-password')
        } else {
          ElMessage.success('Login successful')
          router.push('/admin')
        }
      } catch (error) {
        if (error.response?.status === 401) {
          ElMessage.error('Invalid TOTP code. Please try again.')
          form.value.totpCode = '' // Clear the code field
        } else {
          ElMessage.error('TOTP verification failed. Please try again.')
        }
      } finally {
        loading.value = false
      }
    }

    const goBackToLogin = () => {
      showTotpStep.value = false
      sessionToken.value = null
      form.value.totpCode = ''
    }

    const goToPublicDashboard = () => {
      router.push('/public')
    }

    return {
      formRef,
      totpFormRef,
      form,
      loading,
      showTotpStep,
      handleLogin,
      handleVerifyTotp,
      goBackToLogin,
      goToPublicDashboard
    }
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.login-card {
  width: 100%;
  max-width: 400px;
}

.card-header h2 {
  margin: 0;
  text-align: center;
  color: var(--el-text-color-primary);
}

.login-footer {
  text-align: center;
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid var(--el-border-color);
}
</style>
