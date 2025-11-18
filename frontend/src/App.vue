<template>
  <div id="app">
    <!-- Admin layout (only shown for authenticated routes) -->
    <el-container
      v-if="showAdminLayout"
      style="height: 100vh"
    >
      <el-header
        height="60px"
        style="background: #409EFF; color: white; display: flex; align-items: center; padding: 0 20px;"
      >
        <h2 style="margin: 0">
          ChallengeCtl Control Center
        </h2>
        <div style="flex: 1" />
        <el-button
          circle
          :icon="isDark ? Moon : Sunny"
          style="margin-right: 10px"
          @click="toggleTheme"
        />
        <el-button
          v-if="systemPaused"
          type="success"
          style="margin-right: 10px"
          @click="resumeSystem"
        >
          Resume
        </el-button>
        <el-button
          v-else
          type="warning"
          style="margin-right: 10px"
          @click="pauseSystem"
        >
          Pause
        </el-button>
        <el-button
          @click="handleLogout"
        >
          Logout
        </el-button>
      </el-header>

      <el-container>
        <el-aside
          width="200px"
          class="sidebar"
        >
          <el-menu
            :default-active="$route.path"
            router
            class="sidebar-menu"
          >
            <el-menu-item index="/admin">
              <el-icon><Monitor /></el-icon>
              <span>Dashboard</span>
            </el-menu-item>
            <el-menu-item index="/runners">
              <el-icon><Connection /></el-icon>
              <span>Runners</span>
            </el-menu-item>
            <el-menu-item index="/challenges">
              <el-icon><Document /></el-icon>
              <span>Challenges</span>
            </el-menu-item>
            <el-menu-item index="/challenge-config">
              <el-icon><Setting /></el-icon>
              <span>Configure Challenges</span>
            </el-menu-item>
            <el-menu-item index="/logs">
              <el-icon><Notebook /></el-icon>
              <span>Logs</span>
            </el-menu-item>
            <el-menu-item index="/users">
              <el-icon><User /></el-icon>
              <span>Users</span>
            </el-menu-item>
          </el-menu>
        </el-aside>

        <el-main>
          <router-view />
        </el-main>
      </el-container>
    </el-container>

    <!-- Public/unauthenticated layout (just the router view) -->
    <router-view v-else />
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Monitor, Connection, Document, Notebook, User, Moon, Sunny, Setting } from '@element-plus/icons-vue'
import { api } from './api'
import { logout, checkAuth } from './auth'
import { ElMessage } from 'element-plus'

export default {
  name: 'App',
  components: {
    Monitor,
    Connection,
    Document,
    Notebook,
    User,
    Setting
  },
  setup() {
    const route = useRoute()
    const router = useRouter()
    const systemPaused = ref(false)
    const isDark = ref(true) // Default to dark theme

    // Show admin layout for authenticated routes
    const showAdminLayout = computed(() => {
      return checkAuth() && route.meta.requiresAuth
    })

    // Initialize theme from localStorage or default to dark
    onMounted(() => {
      const savedTheme = localStorage.getItem('theme')
      if (savedTheme) {
        isDark.value = savedTheme === 'dark'
      }
      applyTheme()
    })

    const applyTheme = () => {
      if (isDark.value) {
        document.documentElement.classList.add('dark')
      } else {
        document.documentElement.classList.remove('dark')
      }
    }

    const toggleTheme = () => {
      isDark.value = !isDark.value
      localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
      applyTheme()
    }

    const handleLogout = async () => {
      try {
        // Call backend logout API to destroy session
        await api.post('/auth/logout')
        // Clear local auth state
        logout()
        ElMessage.success('Logged out successfully')
        router.push('/public')
      } catch (error) {
        // Even if API call fails, clear local state
        logout()
        ElMessage.warning('Logged out (session may still be active)')
        router.push('/public')
      }
    }

    const pauseSystem = async () => {
      try {
        await api.post('/control/pause')
        systemPaused.value = true
        ElMessage.success('System paused')
      } catch (error) {
        ElMessage.error('Failed to pause system')
      }
    }

    const resumeSystem = async () => {
      try {
        await api.post('/control/resume')
        systemPaused.value = false
        ElMessage.success('System resumed')
      } catch (error) {
        ElMessage.error('Failed to resume system')
      }
    }

    return {
      showAdminLayout,
      systemPaused,
      isDark,
      Moon,
      Sunny,
      toggleTheme,
      handleLogout,
      pauseSystem,
      resumeSystem
    }
  }
}
</script>

<style>
body {
  margin: 0;
  padding: 0;
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
}

#app {
  height: 100vh;
}

.sidebar {
  background: var(--el-bg-color-page);
  padding: 20px;
  border-right: 1px solid var(--el-border-color);
}

.sidebar-menu {
  border: none;
  background: transparent;
}

/* Dark mode adjustments */
html.dark {
  color-scheme: dark;
}

html.dark body {
  background-color: var(--el-bg-color);
  color: var(--el-text-color-primary);
}
</style>
