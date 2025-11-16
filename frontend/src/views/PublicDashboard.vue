<template>
  <div class="public-dashboard">
    <div class="header">
      <h1>Live Challenge Status</h1>
      <p class="subtitle">
        {{ conference.name }}
      </p>
      <div class="header-controls">
        <el-button
          type="primary"
          class="login-button"
          @click="goToLogin"
        >
          Admin Login
        </el-button>
        <el-button
          circle
          :icon="isDark ? Moon : Sunny"
          class="theme-toggle"
          @click="toggleTheme"
        />
      </div>
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
          style="width: 100%"
          stripe
        >
          <el-table-column
            prop="name"
            label="Challenge Name"
            min-width="180"
          />

          <el-table-column
            prop="modulation"
            label="Modulation"
            width="120"
          >
            <template #default="scope">
              <el-tag
                size="small"
                type="info"
              >
                {{ scope.row.modulation.toUpperCase() }}
              </el-tag>
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
              <span v-if="scope.row.last_tx_time">
                {{ formatTime(scope.row.last_tx_time) }}
              </span>
              <span
                v-else
                class="no-data"
              >Never</span>
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

          <el-table-column
            label="Transmissions"
            width="130"
            align="center"
          >
            <template #default="scope">
              <el-badge
                :value="scope.row.transmission_count"
                :max="999"
                class="badge-count"
              >
                <el-icon :size="20">
                  <Promotion />
                </el-icon>
              </el-badge>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- Auto-refresh indicator -->
      <div class="footer-info">
        <el-icon><Refresh /></el-icon>
        <span>Auto-refreshing every {{ refreshInterval / 1000 }} seconds</span>
      </div>
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
import { useRouter } from 'vue-router'
import { api } from '../api'
import { Loading, Refresh, Warning, Promotion, Moon, Sunny } from '@element-plus/icons-vue'

export default {
  name: 'PublicDashboard',
  components: {
    Loading,
    Refresh,
    Warning,
    Promotion,
    Moon,
    Sunny
  },
  setup() {
    const router = useRouter()
    const challenges = ref([])
    const loading = ref(true)
    const error = ref(null)
    const lastUpdateTime = ref('')
    const refreshInterval = ref(30000) // 30 seconds
    let refreshTimer = null
    const isDark = ref(true) // Default to dark theme

    // Conference info (could be loaded from config)
    const conference = ref({
      name: 'RF CTF Challenge Status'
    })

    const goToLogin = () => {
      router.push('/login')
    }

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
        const response = await api.get('/api/public/challenges')
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

    const formatTime = (timestamp) => {
      if (!timestamp) return 'N/A'

      const date = new Date(timestamp)
      const now = new Date()
      const diffMs = now - date
      const diffMins = Math.floor(diffMs / 60000)

      if (diffMins < 1) return 'Just now'
      if (diffMins < 60) return `${diffMins}m ago`

      const diffHours = Math.floor(diffMins / 60)
      if (diffHours < 24) return `${diffHours}h ago`

      const diffDays = Math.floor(diffHours / 24)
      if (diffDays < 7) return `${diffDays}d ago`

      return date.toLocaleDateString()
    }

    const startAutoRefresh = () => {
      refreshTimer = setInterval(() => {
        loadChallenges()
      }, refreshInterval.value)
    }

    const stopAutoRefresh = () => {
      if (refreshTimer) {
        clearInterval(refreshTimer)
        refreshTimer = null
      }
    }

    onMounted(() => {
      initTheme()
      loadChallenges()
      startAutoRefresh()
    })

    onUnmounted(() => {
      stopAutoRefresh()
    })

    return {
      challenges,
      loading,
      error,
      lastUpdateTime,
      refreshInterval,
      conference,
      hasAnyFrequencyVisible,
      hasAnyLastTxVisible,
      hasAnyActiveStatusVisible,
      formatTime,
      isDark,
      Moon,
      Sunny,
      toggleTheme,
      goToLogin
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

.login-button {
  /* Additional styling if needed */
}

.theme-toggle {
  /* Theme toggle is now within header-controls */
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

.badge-count {
  cursor: default;
}

.footer-info {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 20px;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 4px;
  color: #606266;
  font-size: 0.9em;
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
