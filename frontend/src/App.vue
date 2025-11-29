<template>
  <div id="app">
    <!-- Admin layout (only shown for authenticated routes) -->
    <el-container
      v-if="showAdminLayout"
      style="height: 100vh"
    >
      <el-header
        height="80px"
        class="app-header"
      >
        <!-- Hamburger menu button (mobile only) -->
        <el-button
          v-if="isMobile"
          circle
          :icon="MenuIcon"
          class="hamburger-button"
          @click="toggleSidebar"
        />

        <!-- Title and countdown -->
        <div class="header-title">
          <h2 class="title-text">
            Challengectlv2 Orchestrator<span
              v-if="conferenceName"
              class="conference-name"
            > - {{ conferenceName }}</span>
          </h2>
          <div class="countdown-wrapper">
            <ConferenceCountdown />
          </div>
        </div>

        <div style="flex: 1" />

        <!-- Header actions -->
        <div class="header-actions">
          <el-button
            circle
            :icon="isDark ? Moon : Sunny"
            class="action-button mobile-hidden"
            @click="toggleTheme"
          />
          <el-button
            v-if="systemPaused"
            type="success"
            class="action-button mobile-hidden"
            @click="resumeSystem"
          >
            Resume
          </el-button>
          <el-button
            v-else
            type="warning"
            class="action-button mobile-hidden"
            @click="pauseSystem"
          >
            Pause
          </el-button>
          <el-dropdown @command="handleUserMenuCommand">
            <span class="user-menu-trigger">
              <el-avatar
                :size="isMobile ? 28 : 32"
                style="background-color: #409EFF; margin-right: 8px;"
              >
                <el-icon><UserFilled /></el-icon>
              </el-avatar>
              <span class="mobile-hidden">{{ username }}</span>
              <el-icon
                class="mobile-hidden"
                style="margin-left: 8px;"
              ><ArrowDown /></el-icon>
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
        </div>
      </el-header>

      <el-container>
        <!-- Mobile Drawer Sidebar -->
        <el-drawer
          v-if="isMobile"
          v-model="sidebarOpen"
          direction="ltr"
          :size="280"
          :with-header="false"
          class="mobile-sidebar-drawer"
        >
          <el-menu
            :default-active="$route.path"
            router
            class="sidebar-menu"
            @select="closeSidebar"
          >
            <el-menu-item index="/admin">
              <el-icon><House /></el-icon>
              <span>Dashboard</span>
            </el-menu-item>
            <el-menu-item index="/runners">
              <el-icon><Connection /></el-icon>
              <span>Agents</span>
            </el-menu-item>
            <el-menu-item index="/challenge-config">
              <el-icon><Flag /></el-icon>
              <span>Challenges</span>
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
            <el-menu-item index="/public">
              <el-icon><Monitor /></el-icon>
              <span>Public Dashboard</span>
            </el-menu-item>
          </el-menu>
        </el-drawer>

        <!-- Desktop Sidebar -->
        <el-aside
          v-if="!isMobile"
          width="200px"
          class="sidebar"
        >
          <el-menu
            :default-active="$route.path"
            router
            class="sidebar-menu"
          >
            <el-menu-item index="/admin">
              <el-icon><House /></el-icon>
              <span>Dashboard</span>
            </el-menu-item>
            <el-menu-item index="/runners">
              <el-icon><Connection /></el-icon>
              <span>Agents</span>
            </el-menu-item>
            <el-menu-item index="/challenge-config">
              <el-icon><Flag /></el-icon>
              <span>Challenges</span>
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
            <el-menu-item index="/public">
              <el-icon><Monitor /></el-icon>
              <span>Public Dashboard</span>
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
import { House, Monitor, Connection, Notebook, User, Moon, Sunny, Flag, UserFilled, ArrowDown, EditPen, SwitchButton, Menu as MenuIcon } from '@element-plus/icons-vue'
import { api } from './api'
import { logout, checkAuth, currentUsername, userPermissions } from './auth'
import { ElMessage } from 'element-plus'
import { websocket } from './websocket'
import ConferenceCountdown from './components/ConferenceCountdown.vue'
import { useBreakpoint } from './composables/useBreakpoint'

export default {
  name: 'App',
  components: {
    House,
    Monitor,
    Connection,
    Notebook,
    User,
    Flag,
    ConferenceCountdown
  },
  setup() {
    const route = useRoute()
    const router = useRouter()
    const systemPaused = ref(false)
    const isDark = ref(true) // Default to dark theme
    const conferenceName = ref('')
    const sidebarOpen = ref(false) // Mobile sidebar state

    // Breakpoint detection
    const { isMobile, isDesktop } = useBreakpoint()

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
      console.log('[App.vue] Received system_control event:', event)
      console.log('[App.vue] Current systemPaused value:', systemPaused.value)
      if (event.action === 'pause') {
        console.log('[App.vue] Setting systemPaused = true')
        systemPaused.value = true
        if (event.auto) {
          ElMessage.info('System auto-paused (outside daily hours)')
        }
      } else if (event.action === 'resume') {
        console.log('[App.vue] Setting systemPaused = false')
        systemPaused.value = false
        if (event.auto) {
          ElMessage.info('System auto-resumed (within daily hours)')
        }
      }
      console.log('[App.vue] New systemPaused value:', systemPaused.value)
    }

    // Handle initial state from WebSocket
    const handleInitialState = (data) => {
      console.log('[App.vue] Received initial_state from WebSocket:', data)
      if (data.stats && typeof data.stats.paused !== 'undefined') {
        console.log('[App.vue] Setting systemPaused from initial_state:', data.stats.paused)
        systemPaused.value = data.stats.paused
      }
    }

    // Handle WebSocket reconnection
    const handleWebSocketReconnect = () => {
      console.log('WebSocket reconnected, reloading pause state')
      loadPauseState()
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
        websocket.on('initial_state', handleInitialState)

        // Reload pause state on WebSocket reconnection to sync with server
        websocket.socket?.on('connect', handleWebSocketReconnect)
      }
    })

    onUnmounted(() => {
      websocket.off('system_control', handleSystemControl)
      websocket.off('initial_state', handleInitialState)
      websocket.socket?.off('connect', handleWebSocketReconnect)
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
      } catch {
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
        console.log('[App.vue] Sending pause request to server')
        await api.post('/control/pause')
        systemPaused.value = true
        console.log('[App.vue] Pause successful, systemPaused =', systemPaused.value)
        ElMessage.success('System paused')
      } catch (error) {
        console.error('[App.vue] Failed to pause system:', error)
        ElMessage.error('Failed to pause system')
      }
    }

    const resumeSystem = async () => {
      try {
        console.log('[App.vue] Sending resume request to server')
        await api.post('/control/resume')
        systemPaused.value = false
        console.log('[App.vue] Resume successful, systemPaused =', systemPaused.value)
        ElMessage.success('System resumed')
      } catch (error) {
        console.error('[App.vue] Failed to resume system:', error)
        ElMessage.error('Failed to resume system')
      }
    }

    const toggleSidebar = () => {
      sidebarOpen.value = !sidebarOpen.value
    }

    const closeSidebar = () => {
      sidebarOpen.value = false
    }

    return {
      showAdminLayout,
      systemPaused,
      isDark,
      conferenceName,
      username,
      sidebarOpen,
      isMobile,
      isDesktop,
      Moon,
      Sunny,
      MenuIcon,
      UserFilled,
      ArrowDown,
      EditPen,
      SwitchButton,
      toggleTheme,
      handleLogout,
      handleUserMenuCommand,
      pauseSystem,
      resumeSystem,
      toggleSidebar,
      closeSidebar,
      userPermissions
    }
  }
}
</script>

<style scoped>
/* ============================================
   RESPONSIVE HEADER STYLES
   ============================================ */

.app-header {
  background: #409EFF;
  color: white;
  display: flex;
  align-items: center;
  padding: 0 20px;
}

.hamburger-button {
  margin-right: 12px;
  flex-shrink: 0;
}

.header-title {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  margin-right: 20px;
  min-width: 0; /* Allow flex item to shrink */
}

.title-text {
  margin: 0;
  line-height: 1.3;
  font-size: 1.5em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.conference-name {
  white-space: nowrap;
}

.countdown-wrapper {
  font-size: 0.9em;
  margin-top: 5px;
  opacity: 0.95;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.action-button {
  flex-shrink: 0;
}

.user-menu-trigger {
  display: flex;
  align-items: center;
  cursor: pointer;
  color: white;
}

/* Mobile Responsive Adjustments */
@media (max-width: 767px) {
  .app-header {
    padding: 0 10px;
    height: 60px !important;
  }

  .header-title {
    margin-right: 10px;
    flex: 1;
    min-width: 0;
  }

  .title-text {
    font-size: 1em;
    line-height: 1.2;
  }

  .conference-name {
    display: none; /* Hide conference name on very small screens */
  }

  .countdown-wrapper {
    font-size: 0.75em;
    margin-top: 2px;
  }

  .header-actions {
    gap: 5px;
  }
}

@media (min-width: 768px) and (max-width: 1024px) {
  .title-text {
    font-size: 1.2em;
  }

  .countdown-wrapper {
    font-size: 0.85em;
  }
}

/* ============================================
   MOBILE SIDEBAR DRAWER STYLES
   ============================================ */

.mobile-sidebar-drawer :deep(.el-drawer__body) {
  padding: 0;
}

.mobile-sidebar-drawer .sidebar-menu {
  border-right: none;
  height: 100%;
}
</style>
