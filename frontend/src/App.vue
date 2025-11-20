<template>
  <div id="app">
    <!-- Admin layout (only shown for authenticated routes) -->
    <el-container
      v-if="showAdminLayout"
      style="height: 100vh"
    >
      <el-header
        height="80px"
        style="background: #409EFF; color: white; display: flex; align-items: center; padding: 0 20px;"
      >
        <div style="display: flex; flex-direction: column; align-items: flex-start; margin-right: 20px;">
          <h2 style="margin: 0; line-height: 1.3; font-size: 1.5em;">
            ChallengeCtl Control Center<span v-if="conferenceName"> - {{ conferenceName }}</span>
          </h2>
          <div style="font-size: 0.9em; margin-top: 5px; opacity: 0.95;">
            <ConferenceCountdown />
          </div>
        </div>
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
        <el-dropdown @command="handleUserMenuCommand">
          <span class="user-menu-trigger">
            <el-avatar
              :size="32"
              style="background-color: #409EFF; margin-right: 8px;"
            >
              <el-icon><UserFilled /></el-icon>
            </el-avatar>
            {{ username }}
            <el-icon style="margin-left: 8px;"><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="change-password">
                <el-icon><EditPen /></el-icon>
                Change Password
              </el-dropdown-item>
              <el-dropdown-item
                command="logout"
                divided
              >
                <el-icon><SwitchButton /></el-icon>
                Logout
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
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
            <el-menu-item index="/challenge-config">
              <el-icon><Setting /></el-icon>
              <span>Manage Challenges</span>
            </el-menu-item>
            <el-menu-item index="/logs">
              <el-icon><Notebook /></el-icon>
              <span>Logs</span>
            </el-menu-item>
            <el-menu-item
              v-if="userPermissions.includes('create_users')"
              index="/users"
            >
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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Monitor, Connection, Notebook, User, Moon, Sunny, Setting, UserFilled, ArrowDown, EditPen, SwitchButton } from '@element-plus/icons-vue'
import { api } from './api'
import { logout, checkAuth, currentUsername, userPermissions } from './auth'
import { ElMessage } from 'element-plus'
import { websocket } from './websocket'
import ConferenceCountdown from './components/ConferenceCountdown.vue'

export default {
  name: 'App',
  components: {
    Monitor,
    Connection,
    Notebook,
    User,
    Setting,
    ConferenceCountdown
  },
  setup() {
    const route = useRoute()
    const router = useRouter()
    const systemPaused = ref(false)
    const isDark = ref(true) // Default to dark theme
    const conferenceName = ref('')

    // Show admin layout for authenticated routes (but not during initial setup or user setup)
    const showAdminLayout = computed(() => {
      return checkAuth() && route.meta.requiresAuth && !route.meta.hideLayout
    })

    // Get current username
    const username = computed(() => currentUsername.value || 'User')

    // Load conference name
    const loadConferenceName = async () => {
      try {
        const response = await api.get('/conference')
        conferenceName.value = response.data.name
      } catch (error) {
        console.error('Failed to load conference name:', error)
      }
    }

    // Load initial pause state
    const loadPauseState = async () => {
      try {
        const response = await api.get('/control/status')
        systemPaused.value = response.data.paused
      } catch (error) {
        console.error('Failed to load pause state:', error)
      }
    }

    // Handle system control WebSocket events
    const handleSystemControl = (event) => {
      if (event.action === 'pause') {
        systemPaused.value = true
        if (event.auto) {
          ElMessage.info('System auto-paused (outside daily hours)')
        }
      } else if (event.action === 'resume') {
        systemPaused.value = false
        if (event.auto) {
          ElMessage.info('System auto-resumed (within daily hours)')
        }
      }
    }

    // Initialize theme from localStorage or default to dark
    onMounted(() => {
      const savedTheme = localStorage.getItem('theme')
      if (savedTheme) {
        isDark.value = savedTheme === 'dark'
      }
      applyTheme()
      loadConferenceName()

      // Connect WebSocket if authenticated
      if (checkAuth()) {
        loadPauseState()
        websocket.connect()
        websocket.on('system_control', handleSystemControl)
      }
    })

    onUnmounted(() => {
      websocket.off('system_control', handleSystemControl)
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

    const handleUserMenuCommand = (command) => {
      if (command === 'logout') {
        handleLogout()
      } else if (command === 'change-password') {
        router.push('/change-password')
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
      conferenceName,
      username,
      Moon,
      Sunny,
      UserFilled,
      ArrowDown,
      EditPen,
      SwitchButton,
      toggleTheme,
      handleLogout,
      handleUserMenuCommand,
      pauseSystem,
      resumeSystem,
      userPermissions
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

/* User menu styling */
.user-menu-trigger {
  display: flex;
  align-items: center;
  cursor: pointer;
  padding: 8px 12px;
  border-radius: 4px;
  transition: background-color 0.3s;
  color: white;
  font-size: 14px;
}

.user-menu-trigger:hover {
  background-color: rgba(255, 255, 255, 0.1);
}
</style>
