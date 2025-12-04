<template>
  <div class="dashboard">
    <h1>Dashboard</h1>

    <!-- Statistics Cards -->
    <el-row
      :gutter="20"
      class="mb-xl"
    >
      <el-col
        :xs="24"
        :sm="12"
        :md="6"
      >
        <el-card>
          <div class="stat-card">
            <div class="stat-value">
              {{ stats.runners_online || 0 }} / {{ stats.listeners_online || 0 }}
            </div>
            <div class="stat-label">
              Runners / Listeners
            </div>
            <div class="stat-sublabel">
              {{ stats.runners_total || 0 }} / {{ stats.listeners_total || 0 }} Total
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col
        :xs="24"
        :sm="12"
        :md="6"
      >
        <el-card>
          <div class="stat-card">
            <div class="stat-value">
              {{ stats.challenges_queued || 0 }} / {{ stats.challenges_waiting || 0 }}
            </div>
            <div class="stat-label">
              Queued / Waiting
            </div>
            <div class="stat-sublabel">
              {{ stats.challenges_total || 0 }} Total
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col
        :xs="24"
        :sm="12"
        :md="6"
      >
        <el-card>
          <div class="stat-card">
            <div class="stat-value">
              {{ stats.total_transmissions || 0 }}
            </div>
            <div class="stat-label">
              Total Transmissions
            </div>
            <div class="stat-sublabel">
              All Time
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col
        :xs="24"
        :sm="12"
        :md="6"
      >
        <el-card>
          <div class="stat-card">
            <div class="stat-value">
              {{ stats.success_rate?.toFixed(1) || 0 }}%
            </div>
            <div class="stat-label">
              Success Rate
            </div>
            <div class="stat-sublabel">
              Recent Transmissions
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Runners and Activity -->
    <el-row :gutter="20">
      <el-col
        :xs="24"
        :md="12"
      >
        <el-card class="mb-xl">
          <template #header>
            <div class="card-header">
              <span>Runners</span>
            </div>
          </template>

          <el-table
            :data="runners"
            class="w-full"
            max-height="400"
          >
            <el-table-column
              v-if="!isMobile"
              prop="runner_id"
              label="Runner ID"
              width="150"
            />
            <el-table-column
              prop="hostname"
              label="Hostname"
              :width="isMobile ? undefined : '180'"
            />
            <el-table-column
              label="Status"
              :width="isMobile ? '100' : '100'"
            >
              <template #default="scope">
                <el-tag
                  :type="getRunnerStatusType(scope.row)"
                  size="small"
                >
                  {{ scope.row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column
              v-if="!isMobile"
              label="Devices"
              width="80"
            >
              <template #default="scope">
                {{ scope.row.devices?.length || 0 }}
              </template>
            </el-table-column>
            <el-table-column
              v-if="!isMobile"
              label="Last Heartbeat"
            >
              <template #default="scope">
                {{ formatTime(scope.row.last_heartbeat) }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <!-- Conference Settings -->
        <el-card>
          <template #header>
            <div class="card-header">
              <span>Conference Settings</span>
            </div>
          </template>
          <el-form label-width="150px">
            <el-form-item label="Day Start Time">
              <el-time-select
                v-model="dayStartTime"
                :clearable="true"
                start="00:00"
                step="00:15"
                end="23:45"
                placeholder="Select time"
                format="HH:mm"
                style="width: 150px"
              />
              <div class="info-box">
                Daily start time for countdown cycle
              </div>
            </el-form-item>
            <el-form-item label="End of Day Time">
              <el-time-select
                v-model="endOfDayTime"
                :clearable="true"
                start="00:00"
                step="00:15"
                end="23:45"
                placeholder="Select time"
                format="HH:mm"
                style="width: 150px"
              />
              <div class="info-box">
                Daily end time for countdown cycle
              </div>
            </el-form-item>
            <el-form-item>
              <el-button
                type="primary"
                :loading="savingDayTimes"
                @click="saveDayTimes"
              >
                Save
              </el-button>
              <el-button
                :loading="savingDayTimes"
                @click="clearDayTimes"
              >
                Clear Both
              </el-button>
            </el-form-item>
            <el-form-item label="Auto-Pause Daily">
              <el-switch
                v-model="autoPauseDaily"
                :loading="savingAutoPause"
                @change="toggleAutoPause"
              />
              <div class="info-box">
                Automatically pause transmissions outside daily hours
              </div>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col
        :xs="24"
        :md="12"
      >
        <el-card>
          <template #header>
            <div class="card-header">
              <span>Recent Transmissions</span>
            </div>
          </template>

          <el-table
            :data="recentTransmissions"
            class="w-full"
            max-height="400"
          >
            <el-table-column
              v-if="!isMobile"
              label="Time"
              width="100"
            >
              <template #default="scope">
                {{ formatTime(scope.row.started_at) }}
              </template>
            </el-table-column>
            <el-table-column
              v-if="!isMobile"
              prop="runner_id"
              label="Runner"
              width="120"
            />
            <el-table-column
              prop="challenge_name"
              label="Challenge"
            />
            <el-table-column
              v-if="!isMobile"
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
import { formatTime } from '../utils/time'
import { ElMessage } from 'element-plus'
import { useBreakpoint } from '../composables/useBreakpoint'

export default {
  name: 'Dashboard',
  setup() {
    const stats = ref({})
    const runners = ref([])
    const recentTransmissions = ref([])
    const dayStartTime = ref('')
    const endOfDayTime = ref('')
    const savingDayTimes = ref(false)
    const autoPauseDaily = ref(false)
    const savingAutoPause = ref(false)

    // Breakpoint detection for responsive design
    const { isMobile } = useBreakpoint()

    // Helper to determine runner status tag type
    // Returns 'warning' if runner is online but has offline devices
    const getRunnerStatusType = (runner) => {
      if (runner.status !== 'online') {
        return 'info'  // Offline runner = gray
      }

      // Runner is online - check if any devices are offline
      if (runner.devices && runner.devices.length > 0) {
        const hasOfflineDevice = runner.devices.some(d => d.status === 'offline')
        if (hasOfflineDevice) {
          return 'warning'  // Online runner with offline device(s) = yellow
        }
      }

      return 'success'  // Online runner with all devices online = green
    }

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
          if (event.last_heartbeat) {
            runner.last_heartbeat = event.last_heartbeat
          }
        } else {
          loadDashboard()  // Reload if new runner
        }
      } else if (event.type === 'transmission_complete') {
        // Add to recent transmissions
        recentTransmissions.value.unshift({
          started_at: event.timestamp,
          runner_id: event.runner_id,
          challenge_name: event.challenge_name,
          status: event.status,
          frequency: event.frequency
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

    const loadConferenceSettings = async () => {
      try {
        const response = await api.get('/conference')
        dayStartTime.value = response.data.day_start || ''
        endOfDayTime.value = response.data.end_of_day || ''
        autoPauseDaily.value = response.data.auto_pause_daily || false
      } catch (error) {
        console.error('Error loading conference settings:', error)
      }
    }

    const toggleAutoPause = async () => {
      savingAutoPause.value = true
      try {
        await api.put('/conference/auto-pause', {
          auto_pause_daily: autoPauseDaily.value
        })
        ElMessage.success(`Auto-pause ${autoPauseDaily.value ? 'enabled' : 'disabled'}`)
      } catch (error) {
        console.error('Error toggling auto-pause:', error)
        ElMessage.error(error.response?.data?.error || 'Failed to toggle auto-pause')
        // Revert the toggle on error
        autoPauseDaily.value = !autoPauseDaily.value
      } finally {
        savingAutoPause.value = false
      }
    }

    const saveDayTimes = async () => {
      if (!dayStartTime.value && !endOfDayTime.value) {
        ElMessage.warning('Please select at least one time or use Clear Both to remove')
        return
      }

      savingDayTimes.value = true
      try {
        await api.put('/conference/day-times', {
          day_start: dayStartTime.value,
          end_of_day: endOfDayTime.value
        })
        ElMessage.success('Day times updated successfully')
      } catch (error) {
        console.error('Error saving day times:', error)
        ElMessage.error(error.response?.data?.error || 'Failed to save day times')
      } finally {
        savingDayTimes.value = false
      }
    }

    const clearDayTimes = async () => {
      savingDayTimes.value = true
      try {
        await api.put('/conference/day-times', {
          day_start: '',
          end_of_day: ''
        })
        dayStartTime.value = ''
        endOfDayTime.value = ''
        ElMessage.success('Day times cleared')
      } catch (error) {
        console.error('Error clearing day times:', error)
        ElMessage.error(error.response?.data?.error || 'Failed to clear day times')
      } finally {
        savingDayTimes.value = false
      }
    }

    onMounted(() => {
      loadDashboard()
      loadConferenceSettings()

      // Connect WebSocket
      websocket.connect()
      websocket.on('runner_status', handleWebSocketEvent)
      websocket.on('transmission_complete', handleWebSocketEvent)
    })

    onUnmounted(() => {
      websocket.off('runner_status', handleWebSocketEvent)
      websocket.off('transmission_complete', handleWebSocketEvent)
    })

    const formatFrequency = (hz) => {
      if (!hz) return 'N/A'
      return (hz / 1e6).toFixed(3) + ' MHz'
    }

    return {
      stats,
      runners,
      recentTransmissions,
      dayStartTime,
      endOfDayTime,
      savingDayTimes,
      autoPauseDaily,
      savingAutoPause,
      isMobile,
      saveDayTimes,
      clearDayTimes,
      toggleAutoPause,
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

/* All other styles (.stat-card, .stat-value, .stat-label, .stat-sublabel, .card-header)
   are now defined globally in /src/styles/utilities.css */
</style>
