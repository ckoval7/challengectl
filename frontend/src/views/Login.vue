<template>
  <div class="login-container">
    <el-card class="login-card">
      <template #header>
        <div class="card-header">
          <h2>ChallengeCtl Admin Login</h2>
        </div>
      </template>

      <el-form
        ref="formRef"
        :model="form"
        label-position="top"
        @submit.prevent="handleLogin"
      >
        <el-form-item
          label="Admin API Key"
          prop="apiKey"
          :rules="[
            { required: true, message: 'Please enter your API key', trigger: 'blur' }
          ]"
        >
          <el-input
            v-model="form.apiKey"
            type="password"
            placeholder="Enter your admin API key"
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
            Login
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
    const form = ref({
      apiKey: ''
    })
    const loading = ref(false)

    const handleLogin = async () => {
      if (!formRef.value) return

      try {
        await formRef.value.validate()
      } catch (error) {
        return
      }

      loading.value = true

      try {
        // Test the API key by making a request
        const testApi = api.create()
        testApi.defaults.headers.common['Authorization'] = `Bearer ${form.value.apiKey}`

        await testApi.get('/dashboard')

        // If successful, save the API key and redirect
        login(form.value.apiKey)
        ElMessage.success('Login successful')
        router.push('/')
      } catch (error) {
        if (error.response?.status === 401) {
          ElMessage.error('Invalid API key')
        } else {
          ElMessage.error('Login failed. Please try again.')
        }
      } finally {
        loading.value = false
      }
    }

    const goToPublicDashboard = () => {
      router.push('/public')
    }

    return {
      formRef,
      form,
      loading,
      handleLogin,
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
