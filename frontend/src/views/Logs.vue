<template>
  <div class="logs">
    <h1>Live Logs</h1>

    <div style="margin-bottom: 20px">
      <el-space>
        <el-select
          v-model="levelFilter"
          placeholder="Filter by level"
          style="width: 150px"
        >
          <el-option
            label="All"
            value=""
          />
          <el-option
            label="DEBUG"
            value="DEBUG"
          />
          <el-option
            label="INFO"
            value="INFO"
          />
          <el-option
            label="WARNING"
            value="WARNING"
          />
          <el-option
            label="ERROR"
            value="ERROR"
          />
        </el-select>

        <el-button @click="clearLogs">
          Clear
        </el-button>

        <el-checkbox v-model="autoScroll">
          Auto-scroll
        </el-checkbox>
      </el-space>
    </div>

    <el-card>
      <div
        ref="logContainer"
        class="log-container"
      >
        <div
          v-for="(log, index) in filteredLogs"
          :key="index"
          :class="['log-entry', `log-${log.level.toLowerCase()}`]"
        >
          <span class="log-timestamp">{{ formatTime(log.timestamp) }}</span>
          <span class="log-source">[{{ log.source }}]</span>
          <span :class="`log-level log-level-${log.level.toLowerCase()}`">{{ log.level }}</span>
          <span class="log-message">{{ log.message }}</span>
        </div>

        <div
          v-if="filteredLogs.length === 0"
          class="log-empty"
        >
          No logs yet. Waiting for events...
        </div>
      </div>
    </el-card>

    <div style="margin-top: 10px; color: #909399; font-size: 12px">
      Showing {{ filteredLogs.length }} of {{ logs.length }} log entries
    </div>
  </div>
</template>

<script>
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { websocket } from '../websocket'
import { api } from '../api'
import { formatTime } from '../utils/time'

export default {
  name: 'Logs',
  setup() {
    const logs = ref([])
    const levelFilter = ref('')
    const autoScroll = ref(true)
    const logContainer = ref(null)
    const loading = ref(false)

    const filteredLogs = computed(() => {
      if (!levelFilter.value) {
        return logs.value
      }
      return logs.value.filter(log => log.level === levelFilter.value)
    })

    const fetchLogs = async () => {
      loading.value = true
      try {
        const response = await api.get('/logs')
        const fetchedLogs = response.data.logs || []

        // Add fetched logs in reverse order (newest first)
        logs.value = fetchedLogs.map(log => ({
          timestamp: log.timestamp || new Date().toISOString(),
          source: log.source || 'server',
          level: log.level || 'INFO',
          message: log.message || ''
        })).reverse()
      } catch (error) {
        console.error('Failed to fetch logs:', error)
      } finally {
        loading.value = false
      }
    }

    const handleLogEvent = (event) => {
      logs.value.unshift({
        timestamp: event.timestamp || new Date().toISOString(),
        source: event.source || 'server',
        level: event.level || 'INFO',
        message: event.message || ''
      })

      // Keep only last 500 logs
      if (logs.value.length > 500) {
        logs.value.pop()
      }

      // Auto-scroll to top if enabled
      if (autoScroll.value) {
        nextTick(() => {
          if (logContainer.value) {
            logContainer.value.scrollTop = 0
          }
        })
      }
    }

    const clearLogs = () => {
      logs.value = []
    }

    onMounted(async () => {
      // Fetch historical logs first
      await fetchLogs()

      // Then connect to WebSocket for real-time updates
      websocket.connect()
      websocket.on('log', handleLogEvent)
    })

    onUnmounted(() => {
      websocket.off('log', handleLogEvent)
    })

    return {
      logs,
      filteredLogs,
      levelFilter,
      autoScroll,
      logContainer,
      loading,
      clearLogs,
      formatTime
    }
  }
}
</script>

<style scoped>
.logs {
  padding: 20px;
}

.log-container {
  max-height: 600px;
  overflow-y: auto;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  background: #f5f7fa;
  padding: 10px;
  border-radius: 4px;
}

.log-entry {
  padding: 4px 0;
  border-bottom: 1px solid #e4e7ed;
}

.log-timestamp {
  color: #909399;
  margin-right: 10px;
}

.log-source {
  color: #606266;
  margin-right: 10px;
  font-weight: bold;
}

.log-level {
  display: inline-block;
  width: 70px;
  text-align: center;
  margin-right: 10px;
  padding: 2px 4px;
  border-radius: 2px;
  font-size: 11px;
  font-weight: bold;
}

.log-level-debug {
  background: #e4e7ed;
  color: #606266;
}

.log-level-info {
  background: #d9ecff;
  color: #409eff;
}

.log-level-warning {
  background: #fdf6ec;
  color: #e6a23c;
}

.log-level-error {
  background: #fef0f0;
  color: #f56c6c;
}

.log-message {
  color: #303133;
}

.log-empty {
  text-align: center;
  padding: 40px;
  color: #909399;
}
</style>
