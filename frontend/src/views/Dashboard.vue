<template>
  <div class="dashboard">
    <h1>Dashboard</h1>

    <!-- Statistics Cards -->
    <el-row
      :gutter="20"
      style="margin-bottom: 20px"
    >
      <el-col :span="6">
        <el-card>
          <div class="stat-card">
            <div class="stat-value">
              {{ stats.runners_online || 0 }}
            </div>
            <div class="stat-label">
              Runners Online
            </div>
            <div class="stat-sublabel">
              {{ stats.runners_total || 0 }} Total
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card>
          <div class="stat-card">
            <div class="stat-value">
              {{ stats.challenges_queued || 0 }}
            </div>
            <div class="stat-label">
              Challenges Queued
            </div>
            <div class="stat-sublabel">
              {{ stats.challenges_total || 0 }} Total
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card>
          <div class="stat-card">
            <div class="stat-value">
              {{ stats.total_transmissions || 0 }}
            </div>
            <div class="stat-label">
              Total Transmissions
            </div>
            <div class="stat-sublabel">
              {{ stats.transmissions_last_hour || 0 }} Last Hour
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card>
          <div class="stat-card">
            <div class="stat-value">
              {{ stats.success_rate?.toFixed(1) || 0 }}%
            </div>
            <div class="stat-label">
              Success Rate
            </div>
            <div class="stat-sublabel">
              Last Hour
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Runners and Activity -->
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>Runners</span>
            </div>
          </template>

          <el-table
            :data="runners"
            style="width: 100%"
            max-height="400"
          >
            <el-table-column
              prop="runner_id"
              label="Runner ID"
              width="150"
            />
            <el-table-column
              prop="hostname"
              label="Hostname"
              width="180"
            />
            <el-table-column
              label="Status"
              width="100"
            >
              <template #default="scope">
                <el-tag
                  :type="scope.row.status === 'online' ? 'success' : 'info'"
                  size="small"
                >
                  {{ scope.row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column
              label="Devices"
              width="80"
            >
              <template #default="scope">
                {{ scope.row.devices?.length || 0 }}
              </template>
            </el-table-column>
            <el-table-column label="Last Heartbeat">
              <template #default="scope">
                {{ formatTime(scope.row.last_heartbeat) }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>Recent Transmissions</span>
            </div>
          </template>

          <el-table
            :data="recentTransmissions"
            style="width: 100%"
            max-height="400"
          >
            <el-table-column
              label="Time"
              width="100"
            >
              <template #default="scope">
                {{ formatTime(scope.row.started_at) }}
              </template>
            </el-table-column>
            <el-table-column
              prop="runner_id"
              label="Runner"
              width="120"
            />
            <el-table-column
              prop="challenge_name"
              label="Challenge"
            />
            <el-table-column
              label="Frequency"
              width="120"
            >
              <template #default="scope">
                {{ formatFrequency(scope.row.frequency) }}
              </template>
            </el-table-column>
            <el-table-column
              label="Status"
              width="100"
            >
              <template #default="scope">
                <el-tag
                  :type="scope.row.status === 'success' ? 'success' : (scope.row.status === 'failed' ? 'danger' : 'warning')"
                  size="small"
                >
                  {{ scope.row.status }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'
import { api } from '../api'
import { websocket } from '../websocket'

export default {
  name: 'Dashboard',
  setup() {
    const stats = ref({})
    const runners = ref([])
    const recentTransmissions = ref([])

    const loadDashboard = async () => {
      try {
        const response = await api.get('/dashboard')
        const data = response.data

        stats.value = data.stats || {}
        runners.value = data.runners || []
        recentTransmissions.value = data.recent_transmissions || []
      } catch (error) {
        console.error('Error loading dashboard:', error)
      }
    }

    const handleWebSocketEvent = (event) => {
      console.log('Dashboard received event:', event.type)

      if (event.type === 'runner_status') {
        // Update runner status
        const runner = runners.value.find(r => r.runner_id === event.runner_id)
        if (runner) {
          runner.status = event.status
        } else {
          loadDashboard()  // Reload if new runner
        }
      } else if (event.type === 'transmission_complete') {
        // Add to recent transmissions
        recentTransmissions.value.unshift({
          started_at: event.timestamp,
          runner_id: event.runner_id,
          challenge_name: event.challenge_id,
          status: event.status,
          frequency: 0
        })

        // Keep only last 20
        if (recentTransmissions.value.length > 20) {
          recentTransmissions.value.pop()
        }

        // Update stats
        if (event.status === 'success') {
          stats.value.total_transmissions = (stats.value.total_transmissions || 0) + 1
        }
      }
    }

    onMounted(() => {
      loadDashboard()

      // Connect WebSocket
      websocket.connect()
      websocket.on('runner_status', handleWebSocketEvent)
      websocket.on('transmission_complete', handleWebSocketEvent)

      // Refresh dashboard periodically
      const interval = setInterval(loadDashboard, 30000)  // Every 30 seconds

      onUnmounted(() => {
        clearInterval(interval)
        websocket.off('runner_status', handleWebSocketEvent)
        websocket.off('transmission_complete', handleWebSocketEvent)
      })
    })

    const formatTime = (timestamp) => {
      if (!timestamp) return 'Never'
      const date = new Date(timestamp)
      return date.toLocaleTimeString()
    }

    const formatFrequency = (hz) => {
      if (!hz) return 'N/A'
      return (hz / 1e6).toFixed(3) + ' MHz'
    }

    return {
      stats,
      runners,
      recentTransmissions,
      formatTime,
      formatFrequency
    }
  }
}
</script>

<style scoped>
.dashboard {
  padding: 20px;
}

.stat-card {
  text-align: center;
  padding: 20px 0;
}

.stat-value {
  font-size: 36px;
  font-weight: bold;
  color: #409EFF;
}

.stat-label {
  font-size: 14px;
  color: #606266;
  margin-top: 8px;
}

.stat-sublabel {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.card-header {
  font-weight: bold;
  font-size: 16px;
}
</style>
