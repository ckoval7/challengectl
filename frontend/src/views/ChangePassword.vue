<template>
  <div class="change-password-container">
    <el-card class="change-password-card">
      <template #header>
        <div class="card-header">
          <h2>Change Password Required</h2>
        </div>
      </template>

      <el-alert
        type="warning"
        :closable="false"
        class="mb-xl"
      >
        <template #title>
          You must change your password before continuing
        </template>
      </el-alert>

      <el-form
        ref="formRef"
        :model="form"
        label-position="top"
        @submit.prevent="handleChangePassword"
      >
        <el-form-item
          label="Current Password"
          prop="currentPassword"
          :rules="[
            { required: true, message: 'Please enter your current password', trigger: 'blur' }
          ]"
        >
          <el-input
            v-model="form.currentPassword"
            type="password"
            placeholder="Enter your current password"
            show-password
            size="large"
          />
        </el-form-item>

        <el-form-item
          label="New Password"
          prop="newPassword"
          :rules="[
            { required: true, message: 'Please enter a new password', trigger: 'blur' },
            { min: 8, message: 'Password must be at least 8 characters', trigger: 'blur' }
          ]"
        >
          <el-input
            v-model="form.newPassword"
            type="password"
            placeholder="Enter new password (min 8 characters)"
            show-password
            size="large"
          />
        </el-form-item>

        <el-form-item
          label="Confirm New Password"
          prop="confirmPassword"
          :rules="[
            { required: true, message: 'Please confirm your new password', trigger: 'blur' },
            { validator: validatePasswordMatch, trigger: 'blur' }
          ]"
        >
          <el-input
            v-model="form.confirmPassword"
            type="password"
            placeholder="Confirm new password"
            show-password
            size="large"
            @keyup.enter="handleChangePassword"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            class="w-full"
            :loading="loading"
            @click="handleChangePassword"
          >
            Change Password
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { ElMessage } from 'element-plus'

export default {
  name: 'ChangePassword',
  setup() {
    const router = useRouter()
    const formRef = ref(null)
    const form = ref({
      currentPassword: '',
      newPassword: '',
      confirmPassword: ''
    })
    const loading = ref(false)

    const validatePasswordMatch = (rule, value, callback) => {
      if (value !== form.value.newPassword) {
        callback(new Error('Passwords do not match'))
      } else {
        callback()
      }
    }

    const handleChangePassword = async () => {
      if (!formRef.value) return

      try {
        await formRef.value.validate()
      } catch (error) {
        return
      }

      loading.value = true

      try {
        await api.post('/auth/change-password', {
          current_password: form.value.currentPassword,
          new_password: form.value.newPassword
        })

        ElMessage.success('Password changed successfully')
        router.push('/admin')
      } catch (error) {
        if (error.response?.status === 401) {
          ElMessage.error('Current password is incorrect')
        } else if (error.response?.data?.error) {
          ElMessage.error(error.response.data.error)
        } else {
          ElMessage.error('Failed to change password. Please try again.')
        }
      } finally {
        loading.value = false
      }
    }

    return {
      formRef,
      form,
      loading,
      validatePasswordMatch,
      handleChangePassword
    }
  }
}
</script>

<style scoped>
.change-password-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.change-password-card {
  width: 100%;
  max-width: 400px;
}

.card-header h2 {
  margin: 0;
  text-align: center;
  color: var(--el-text-color-primary);
}
</style>
