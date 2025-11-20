<template>
  <div class="public-dashboard">
    <div class="header">
      <h1>Live Challenge Status</h1>
      <div class="countdown-wrapper">
        <ConferenceCountdown />
      </div>
      <div class="header-controls">
        <el-button
          circle
          :icon="isDark ? Moon : Sunny"
          class="theme-toggle"
          @click="toggleTheme"
        />
      </div>
    </div>

    <!-- WebSocket status indicator -->
    <div
      class="ws-status"
      :class="{ connected: wsConnected, disconnected: !wsConnected }"
      :title="wsConnected ? 'Live updates active' : 'Disconnected - attempting to reconnect'"
    >
      <div class="ws-dot" />
    </div>

    <!-- Loading State -->
    <div
      v-if="loading"
      class="loading-container"
    >
      <el-icon
        class="is-loading"
        :size="40"
      >
        <Loading />
      </el-icon>
      <p>Loading challenges...</p>
    </div>

    <!-- Error State -->
    <div
      v-else-if="error"
      class="error-container"
    >
      <el-alert
        title="Error Loading Challenges"
        :description="error"
        type="error"
        :closable="false"
      />
    </div>

    <!-- Challenges Table -->
    <div v-else-if="challenges.length > 0">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>Active Challenges ({{ challenges.length }})</span>
            <span class="last-update">Last updated: {{ lastUpdateTime }}</span>
          </div>
        </template>

        <el-table
          :data="challenges"
          class="w-full"
          stripe
        >
          <el-table-column
            prop="name"
            label="Challenge Name"
            min-width="180"
          />

          <el-table-column
            v-if="hasAnyModulationVisible"
            label="Modulation"
            width="120"
          >
            <template #default="scope">
              <span v-if="scope.row.modulation">
                <el-tag
                  size="small"
                  type="info"
                >
                  {{ scope.row.modulation.toUpperCase() }}
                </el-tag>
              </span>
              <span
                v-else
                class="hidden-field"
              >—</span>
            </template>
          </el-table-column>

          <el-table-column
            v-if="hasAnyFrequencyVisible"
            label="Frequency"
            width="140"
          >
            <template #default="scope">
              <span v-if="scope.row.frequency_display">
                {{ scope.row.frequency_display }}
              </span>
              <span
                v-else
                class="hidden-field"
              >—</span>
            </template>
          </el-table-column>

          <el-table-column
            v-if="hasAnyLastTxVisible"
            label="Last Transmission"
            width="180"
          >
            <template #default="scope">
              <span v-if="scope.row.last_tx_time !== undefined">
                <span v-if="scope.row.last_tx_time">
                  {{ formatTime(scope.row.last_tx_time) }}
                </span>
                <span
                  v-else
                  class="no-data"
                >Never</span>
              </span>
              <span
                v-else
                class="hidden-field"
              >—</span>
            </template>
          </el-table-column>

          <el-table-column
            v-if="hasAnyActiveStatusVisible"
            label="Status"
            width="120"
          >
            <template #default="scope">
              <span v-if="scope.row.is_active !== undefined">
                <el-tag
                  :type="scope.row.is_active ? 'success' : 'info'"
                  size="small"
                >
                  {{ scope.row.is_active ? 'ACTIVE' : 'IDLE' }}
                </el-tag>
              </span>
              <span
                v-else
                class="hidden-field"
              >—</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <!-- Empty State -->
    <div
      v-else
      class="empty-state"
    >
      <el-empty description="No active challenges at this time">
        <template #image>
          <el-icon
            :size="100"
            color="#909399"
          >
            <Warning />
          </el-icon>
        </template>
      </el-empty>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { io } from 'socket.io-client'
import { api } from '../api'
import config from '../config'
import { Loading, Warning, Moon, Sunny } from '@element-plus/icons-vue'
import { formatTime } from '../utils/time'
import ConferenceCountdown from '../components/ConferenceCountdown.vue'

export default {
  name: 'PublicDashboard',
  components: {
    Loading,
    Warning,
    ConferenceCountdown
  },
  setup() {
    const challenges = ref([])
    const loading = ref(true)
    const error = ref(null)
    const lastUpdateTime = ref('')
    const isDark = ref(true) // Default to dark theme
    const wsConnected = ref(false)
    let socket = null

    // Conference info (could be loaded from config)
    const conference = ref({
      name: 'RF CTF Challenge Status'
    })

    // Initialize theme from localStorage or default to dark
    const initTheme = () => {
      const savedTheme = localStorage.getItem('theme')
      if (savedTheme) {
        isDark.value = savedTheme === 'dark'
      }
      applyTheme()
    }

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

    // Computed properties to determine which columns to show
    const hasAnyModulationVisible = computed(() => {
      return challenges.value.some(c => c.modulation !== undefined)
    })

    const hasAnyFrequencyVisible = computed(() => {
      return challenges.value.some(c => c.frequency_display !== undefined)
    })

    const hasAnyLastTxVisible = computed(() => {
      return challenges.value.some(c => c.last_tx_time !== undefined)
    })

    const hasAnyActiveStatusVisible = computed(() => {
      return challenges.value.some(c => c.is_active !== undefined)
    })

    const loadChallenges = async () => {
      try {
        // Public endpoint - no authentication required
        // Note: baseURL is already '/api', so we just need '/public/challenges'
        const response = await api.get('/public/challenges')
        challenges.value = response.data.challenges || []
        lastUpdateTime.value = new Date().toLocaleTimeString()
        error.value = null
        loading.value = false
      } catch (err) {
        console.error('Error loading public challenges:', err)
        error.value = err.response?.data?.error || 'Failed to load challenges'
        loading.value = false
      }
    }

    const connectWebSocket = () => {
      // Connect to public WebSocket namespace (no authentication required)
      const wsUrl = config.websocket?.url || window.location.origin

      socket = io(`${wsUrl}/public`, {
        transports: ['websocket', 'polling']
      })

      socket.on('connect', () => {
        console.log('Public WebSocket connected')
        wsConnected.value = true
        error.value = null
      })

      socket.on('disconnect', (reason) => {
        console.log('Public WebSocket disconnected. Reason:', reason)
        wsConnected.value = false
      })

      socket.on('connect_error', (error) => {
        console.error('Public WebSocket connection error:', error.message)
        wsConnected.value = false
        // Fall back to loading from API on connection error
        if (challenges.value.length === 0) {
          loadChallenges()
        }
      })

      socket.on('challenges_update', (data) => {
        console.log('Challenges update received:', data)
        challenges.value = data.challenges || []
        lastUpdateTime.value = new Date().toLocaleTimeString()
        loading.value = false
      })
    }

    const disconnectWebSocket = () => {
      if (socket) {
        socket.disconnect()
        socket = null
      }
    }

    onMounted(() => {
      initTheme()
      loadChallenges() // Initial load
      connectWebSocket() // Connect to real-time updates
    })

    onUnmounted(() => {
      disconnectWebSocket()
    })

    return {
      challenges,
      loading,
      error,
      lastUpdateTime,
      conference,
      hasAnyModulationVisible,
      hasAnyFrequencyVisible,
      hasAnyLastTxVisible,
      hasAnyActiveStatusVisible,
      formatTime,
      isDark,
      wsConnected,
      Moon,
      Sunny,
      toggleTheme
    }
  }
}
</script>

<style scoped>
.public-dashboard {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.header {
  text-align: center;
  margin-bottom: 30px;
  padding: 20px 0;
  border-bottom: 2px solid #409eff;
  position: relative;
}

.header-controls {
  position: absolute;
  top: 20px;
  right: 20px;
  display: flex;
  gap: 10px;
  align-items: center;
}

.header h1 {
  margin: 0;
  font-size: 2.5em;
  color: var(--el-text-color-primary);
}

.subtitle {
  margin: 10px 0 0 0;
  font-size: 1.2em;
  color: var(--el-text-color-regular);
}

.countdown-wrapper {
  margin: 15px 0;
  font-size: 1.3em;
  color: var(--el-text-color-primary);
  font-weight: 500;
}

.loading-container,
.error-container,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
}

.loading-container p {
  margin-top: 20px;
  color: #909399;
  font-size: 1.1em;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.last-update {
  font-size: 0.9em;
  color: #909399;
}

.hidden-field,
.no-data {
  color: #c0c4cc;
  font-style: italic;
}

/* WebSocket status indicator */
.ws-status {
  position: fixed;
  bottom: 20px;
  right: 20px;
  padding: 8px 12px;
  border-radius: 20px;
  background: var(--el-bg-color);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: help;
  transition: all 0.3s ease;
  z-index: 1000;
}

.ws-status:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.ws-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  transition: background-color 0.3s ease;
}

.ws-status.connected .ws-dot {
  background-color: #67c23a;
  box-shadow: 0 0 8px rgba(103, 194, 58, 0.5);
}

.ws-status.disconnected .ws-dot {
  background-color: #909399;
}

/* Mobile responsiveness */
@media (max-width: 768px) {
  .public-dashboard {
    padding: 10px;
  }

  .header h1 {
    font-size: 1.8em;
  }

  .subtitle {
    font-size: 1em;
  }
}
</style>
