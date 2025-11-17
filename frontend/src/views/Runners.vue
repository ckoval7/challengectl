<template>
  <div class="runners">
    <h1>Runners</h1>

    <el-table
      :data="runners"
      style="width: 100%"
    >
      <el-table-column
        prop="runner_id"
        label="Runner ID"
        width="180"
      />
      <el-table-column
        prop="hostname"
        label="Hostname"
        width="200"
      />
      <el-table-column
        prop="ip_address"
        label="IP Address"
        width="150"
      />
      <el-table-column
        label="Status"
        width="150"
      >
        <template #default="scope">
          <el-space>
            <el-tag
              :type="scope.row.status === 'online' ? 'success' : 'info'"
              size="small"
            >
              {{ scope.row.status }}
            </el-tag>
            <el-tag
              v-if="!scope.row.enabled"
              type="warning"
              size="small"
            >
              disabled
            </el-tag>
          </el-space>
        </template>
      </el-table-column>
      <el-table-column
        label="Devices"
        width="100"
      >
        <template #default="scope">
          {{ scope.row.devices?.length || 0 }}
        </template>
      </el-table-column>
      <el-table-column
        label="Last Heartbeat"
        width="180"
      >
        <template #default="scope">
          {{ formatTimestamp(scope.row.last_heartbeat) }}
        </template>
      </el-table-column>
      <el-table-column
        label="Actions"
        width="220"
      >
        <template #default="scope">
          <el-space>
            <el-button
              v-if="scope.row.enabled"
              size="small"
              type="warning"
              @click="disableRunner(scope.row.runner_id)"
            >
              Disable
            </el-button>
            <el-button
              v-else
              size="small"
              type="success"
              @click="enableRunner(scope.row.runner_id)"
            >
              Enable
            </el-button>
            <el-button
              size="small"
              type="danger"
              @click="kickRunner(scope.row.runner_id)"
            >
              Kick
            </el-button>
          </el-space>
        </template>
      </el-table-column>
      <el-table-column type="expand">
        <template #default="scope">
          <div style="padding: 20px">
            <h4>Devices:</h4>
            <el-table
              :data="scope.row.devices || []"
              style="width: 100%"
            >
              <el-table-column
                prop="device_id"
                label="ID"
                width="80"
              />
              <el-table-column
                prop="model"
                label="Model"
                width="150"
              />
              <el-table-column
                prop="name"
                label="Name/Serial"
              />
              <el-table-column label="Frequency Limits">
                <template #default="devScope">
                  {{ devScope.row.frequency_limits?.join(', ') || 'Any' }}
                </template>
              </el-table-column>
            </el-table>
          </div>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'
import { api } from '../api'
import { websocket } from '../websocket'
import { ElMessage, ElMessageBox } from 'element-plus'
import { formatDateTime } from '../utils/time'

export default {
  name: 'Runners',
  setup() {
    const runners = ref([])

    const loadRunners = async () => {
      try {
        const response = await api.get('/runners')
        runners.value = response.data.runners || []
      } catch (error) {
        console.error('Error loading runners:', error)
        ElMessage.error('Failed to load runners')
      }
    }

    const enableRunner = async (runnerId) => {
      try {
        await api.post(`/runners/${runnerId}/enable`)
        ElMessage.success('Runner enabled')
        // WebSocket will update the UI automatically
      } catch (error) {
        console.error('Error enabling runner:', error)
        ElMessage.error('Failed to enable runner')
      }
    }

    const disableRunner = async (runnerId) => {
      try {
        await api.post(`/runners/${runnerId}/disable`)
        ElMessage.success('Runner disabled')
        // WebSocket will update the UI automatically
      } catch (error) {
        console.error('Error disabling runner:', error)
        ElMessage.error('Failed to disable runner')
      }
    }

    const kickRunner = async (runnerId) => {
      try {
        await ElMessageBox.confirm(
          `Remove runner ${runnerId}?`,
          'Confirm',
          {
            confirmButtonText: 'Remove',
            cancelButtonText: 'Cancel',
            type: 'warning'
          }
        )

        await api.delete(`/runners/${runnerId}`)
        ElMessage.success('Runner removed')
        loadRunners()
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error('Failed to remove runner')
        }
      }
    }

    const handleRunnerStatusEvent = (event) => {
      console.log('Runners page received runner_status event:', event)

      const runner = runners.value.find(r => r.runner_id === event.runner_id)

      if (event.status === 'online') {
        if (!runner) {
          // New runner registered, reload full list to get all details
          console.log('New runner detected, reloading list')
          loadRunners()
        } else {
          // Update existing runner status
          console.log('Updating runner to online:', event.runner_id)
          runner.status = 'online'
          if (event.last_heartbeat) {
            runner.last_heartbeat = event.last_heartbeat
          }
        }
      } else if (event.status === 'offline') {
        if (runner) {
          // Mark runner as offline
          console.log('Updating runner to offline:', event.runner_id)
          runner.status = 'offline'
        }
      }
    }

    const handleRunnerEnabledEvent = (event) => {
      console.log('Runners page received runner_enabled event:', event)

      const runner = runners.value.find(r => r.runner_id === event.runner_id)
      if (runner) {
        runner.enabled = event.enabled
        console.log(`Updated runner ${event.runner_id} enabled status to:`, event.enabled)
      }
    }

    onMounted(() => {
      loadRunners()

      // Connect WebSocket for real-time updates
      websocket.connect()
      websocket.on('runner_status', handleRunnerStatusEvent)
      websocket.on('runner_enabled', handleRunnerEnabledEvent)
    })

    onUnmounted(() => {
      websocket.off('runner_status', handleRunnerStatusEvent)
      websocket.off('runner_enabled', handleRunnerEnabledEvent)
    })

    return {
      runners,
      enableRunner,
      disableRunner,
      kickRunner,
      formatTimestamp: formatDateTime
    }
  }
}
</script>

<style scoped>
.runners {
  padding: 20px;
}
</style>
