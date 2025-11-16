<template>
  <div class="logs">
    <h1>Live Logs</h1>

    <div style="margin-bottom: 20px">
      <el-space wrap>
        <el-select
          v-model="levelFilter"
          placeholder="Filter by level"
          style="width: 200px"
          multiple
          collapse-tags
          collapse-tags-tooltip
        >
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
          <el-option
            label="CRITICAL"
            value="CRITICAL"
          />
        </el-select>

        <el-select
          v-model="sourceFilter"
          placeholder="Filter by source"
          style="width: 220px"
          multiple
          collapse-tags
          collapse-tags-tooltip
        >
          <el-option
            v-for="source in uniqueSources"
            :key="source"
            :label="source"
            :value="source"
          />
        </el-select>

        <el-input
          v-model="searchFilter"
          placeholder="Search logs..."
          style="width: 250px"
          clearable
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>

        <el-button @click="clearFilters">
          Clear Filters
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

    <div style="margin-top: 10px; display: flex; justify-content: space-between; align-items: center">
      <div style="color: #909399; font-size: 12px">
        Showing {{ filteredLogs.length }} of {{ logs.length }} log entries
      </div>
      <el-button @click="clearLogs" type="danger" plain>
        Clear Logs
      </el-button>
    </div>
  </div>
</template>

<script>
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { websocket } from '../websocket'
import { api } from '../api'
import { formatTime } from '../utils/time'

export default {
  name: 'Logs',
  components: {
    Search
  },
  setup() {
    const logs = ref([])
    const levelFilter = ref([])
    const sourceFilter = ref([])
    const searchFilter = ref('')
    const autoScroll = ref(true)
    const logContainer = ref(null)
    const loading = ref(false)

    const uniqueSources = computed(() => {
      const sources = new Set()
      logs.value.forEach(log => {
        if (log.source) {
          sources.add(log.source)
        }
      })
      return Array.from(sources).sort()
    })

    const filteredLogs = computed(() => {
      let result = logs.value

      // Filter by log levels
      if (levelFilter.value && levelFilter.value.length > 0) {
        result = result.filter(log => levelFilter.value.includes(log.level))
      }

      // Filter by sources (server/runners)
      if (sourceFilter.value && sourceFilter.value.length > 0) {
        result = result.filter(log => sourceFilter.value.includes(log.source))
      }

      // Filter by search text
      if (searchFilter.value && searchFilter.value.trim()) {
        const search = searchFilter.value.toLowerCase()
        result = result.filter(log =>
          log.message.toLowerCase().includes(search) ||
          log.source.toLowerCase().includes(search)
        )
      }

      return result
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
      console.debug('handleLogEvent called:', event)
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

    const clearFilters = () => {
      levelFilter.value = []
      sourceFilter.value = []
      searchFilter.value = ''
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
      uniqueSources,
      levelFilter,
      sourceFilter,
      searchFilter,
      autoScroll,
      logContainer,
      loading,
      clearLogs,
      clearFilters,
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
  padding: 10px;
  border-radius: 4px;
  background: #f5f7fa;
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

.log-level-critical {
  background: #f0e0e0;
  color: #c03030;
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

<style>
/* Dark theme overrides - unscoped to access html.dark class */
html.dark .log-container {
  background: #1a1a1a;
}

html.dark .log-entry {
  border-bottom-color: #333;
}

html.dark .log-timestamp {
  color: #8a8a8a;
}

html.dark .log-source {
  color: #b0b0b0;
}

html.dark .log-message {
  color: #d0d0d0;
}

html.dark .log-empty {
  color: #8a8a8a;
}

html.dark .log-level-debug {
  background: #2a2a2a;
  color: #909399;
}

html.dark .log-level-info {
  background: #1a3a5a;
  color: #66b3ff;
}

html.dark .log-level-warning {
  background: #3a2e1a;
  color: #f0c040;
}

html.dark .log-level-error {
  background: #3a1a1a;
  color: #ff8888;
}

html.dark .log-level-critical {
  background: #4a0000;
  color: #ffaaaa;
}
</style>
