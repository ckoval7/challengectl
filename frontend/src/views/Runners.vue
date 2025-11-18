<template>
  <div class="runners">
    <div class="header">
      <h1>Runners</h1>
      <el-button type="primary" @click="showAddRunnerDialog">
        Add Runner
      </el-button>
    </div>

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

    <!-- Add Runner Dialog -->
    <el-dialog
      v-model="addRunnerDialogVisible"
      title="Add Runner"
      width="600px"
      :close-on-click-modal="false"
    >
      <div v-if="!enrollmentData">
        <!-- Step 1: Enter runner name -->
        <el-form :model="addRunnerForm" label-width="120px">
          <el-form-item label="Runner Name">
            <el-input
              v-model="addRunnerForm.runnerName"
              placeholder="e.g., sdr-station-1"
              @keyup.enter="generateEnrollmentToken"
            />
          </el-form-item>
          <el-form-item label="Token Expiry">
            <el-select v-model="addRunnerForm.expiresHours" placeholder="Select expiry time">
              <el-option label="1 hour" :value="1" />
              <el-option label="6 hours" :value="6" />
              <el-option label="24 hours (default)" :value="24" />
              <el-option label="7 days" :value="168" />
            </el-select>
          </el-form-item>
        </el-form>
      </div>

      <div v-else class="enrollment-data">
        <!-- Step 2: Display token and API key -->
        <el-alert
          title="Important: Save these credentials now!"
          type="warning"
          description="The enrollment token and API key will only be shown once. Copy them to your runner configuration."
          :closable="false"
          show-icon
          style="margin-bottom: 20px"
        />

        <div class="credential-block">
          <h4>Runner Name:</h4>
          <div class="credential-value">
            <code>{{ enrollmentData.runner_name }}</code>
          </div>
        </div>

        <div class="credential-block">
          <h4>Enrollment Token:</h4>
          <div class="credential-value">
            <code>{{ enrollmentData.token }}</code>
            <el-button
              size="small"
              @click="copyToClipboard(enrollmentData.token, 'Enrollment token')"
            >
              Copy
            </el-button>
          </div>
        </div>

        <div class="credential-block">
          <h4>API Key:</h4>
          <div class="credential-value">
            <code>{{ enrollmentData.api_key }}</code>
            <el-button
              size="small"
              @click="copyToClipboard(enrollmentData.api_key, 'API key')"
            >
              Copy
            </el-button>
          </div>
        </div>

        <div class="credential-block">
          <h4>Expires:</h4>
          <div class="credential-value">
            <code>{{ formatTimestamp(enrollmentData.expires_at) }}</code>
          </div>
        </div>

        <el-divider />

        <div class="setup-instructions">
          <h4>Setup Instructions:</h4>
          <ol>
            <li>Copy the Enrollment Token and API Key above</li>
            <li>On your runner machine, create/edit <code>runner-config.yml</code></li>
            <li>Add the following configuration:
              <pre style="background: #f5f5f5; padding: 10px; border-radius: 4px; margin-top: 10px;">
server:
  url: {{ serverUrl }}
  enrollment_token: {{ enrollmentData.token }}
  api_key: {{ enrollmentData.api_key }}
runner:
  id: &lt;unique-runner-id&gt;
  # ... rest of config
              </pre>
            </li>
            <li>Start the runner with: <code>python runner.py</code></li>
          </ol>
        </div>
      </div>

      <template #footer>
        <span class="dialog-footer">
          <el-button v-if="!enrollmentData" @click="addRunnerDialogVisible = false">
            Cancel
          </el-button>
          <el-button
            v-if="!enrollmentData"
            type="primary"
            :disabled="!addRunnerForm.runnerName"
            @click="generateEnrollmentToken"
          >
            Generate Token
          </el-button>
          <el-button v-else type="primary" @click="closeAddRunnerDialog">
            Done
          </el-button>
        </span>
      </template>
    </el-dialog>
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
    const addRunnerDialogVisible = ref(false)
    const addRunnerForm = ref({
      runnerName: '',
      expiresHours: 24
    })
    const enrollmentData = ref(null)
    const serverUrl = ref(window.location.origin)

    const loadRunners = async () => {
      try {
        const response = await api.get('/runners')
        runners.value = response.data.runners || []
      } catch (error) {
        console.error('Error loading runners:', error)
        ElMessage.error('Failed to load runners')
      }
    }

    const showAddRunnerDialog = () => {
      addRunnerDialogVisible.value = true
      enrollmentData.value = null
      addRunnerForm.value = {
        runnerName: '',
        expiresHours: 24
      }
    }

    const generateEnrollmentToken = async () => {
      if (!addRunnerForm.value.runnerName) {
        ElMessage.warning('Please enter a runner name')
        return
      }

      try {
        const response = await api.post('/enrollment/token', {
          runner_name: addRunnerForm.value.runnerName,
          expires_hours: addRunnerForm.value.expiresHours
        })

        enrollmentData.value = response.data
        ElMessage.success('Enrollment token generated')
      } catch (error) {
        console.error('Error generating enrollment token:', error)
        ElMessage.error('Failed to generate enrollment token')
      }
    }

    const closeAddRunnerDialog = () => {
      addRunnerDialogVisible.value = false
      enrollmentData.value = null
      addRunnerForm.value = {
        runnerName: '',
        expiresHours: 24
      }
    }

    const copyToClipboard = async (text, label) => {
      try {
        await navigator.clipboard.writeText(text)
        ElMessage.success(`${label} copied to clipboard`)
      } catch (error) {
        console.error('Failed to copy:', error)
        ElMessage.error('Failed to copy to clipboard')
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
      addRunnerDialogVisible,
      addRunnerForm,
      enrollmentData,
      serverUrl,
      showAddRunnerDialog,
      generateEnrollmentToken,
      closeAddRunnerDialog,
      copyToClipboard,
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

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.enrollment-data {
  padding: 10px;
}

.credential-block {
  margin-bottom: 20px;
}

.credential-block h4 {
  margin: 0 0 8px 0;
  color: #333;
  font-size: 14px;
}

.credential-value {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #f5f5f5;
  padding: 12px;
  border-radius: 4px;
  border: 1px solid #ddd;
}

.credential-value code {
  flex: 1;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  word-break: break-all;
  color: #2c3e50;
}

.setup-instructions {
  margin-top: 20px;
}

.setup-instructions h4 {
  margin: 0 0 10px 0;
  color: #333;
}

.setup-instructions ol {
  padding-left: 20px;
}

.setup-instructions li {
  margin-bottom: 10px;
  line-height: 1.6;
}

.setup-instructions code {
  background: #e7f3ff;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

.setup-instructions pre {
  overflow-x: auto;
}
</style>
