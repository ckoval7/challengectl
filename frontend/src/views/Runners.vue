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
        width="300"
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
              type="primary"
              @click="showReEnrollDialog(scope.row.runner_id)"
            >
              Re-enroll
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
      width="800px"
      :close-on-click-modal="false"
    >
      <div v-if="!enrollmentData">
        <!-- Step 1: Enter runner name and configuration -->
        <el-form :model="addRunnerForm" label-width="150px">
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
          <el-form-item label="Verify SSL">
            <el-switch
              v-model="addRunnerForm.verifySsl"
              active-text="Enabled"
              inactive-text="Disabled"
            />
            <div style="font-size: 12px; color: #909399; margin-top: 5px;">
              Disable only for development with self-signed certificates
            </div>
          </el-form-item>
        </el-form>
      </div>

      <div v-else class="enrollment-data">
        <!-- Step 2: Display complete configuration -->
        <el-alert
          title="Important: Save this configuration now!"
          type="warning"
          description="The enrollment token and API key will only be shown once. Download or copy the complete configuration below."
          :closable="false"
          show-icon
          style="margin-bottom: 20px"
        />

        <div style="margin-bottom: 15px;">
          <el-space>
            <el-button
              type="primary"
              @click="copyToClipboard(generatedConfig, 'Configuration')"
            >
              Copy Full Config
            </el-button>
            <el-button
              type="success"
              @click="downloadConfig"
            >
              Download runner-config.yml
            </el-button>
          </el-space>
        </div>

        <div class="config-display">
          <h4>Complete Runner Configuration:</h4>
          <pre class="config-content">{{ generatedConfig }}</pre>
        </div>

        <el-divider />

        <div class="setup-instructions">
          <h4>Setup Instructions:</h4>
          <ol>
            <li>Download or copy the complete configuration above</li>
            <li>On your runner machine, save as <code>runner-config.yml</code></li>
            <li>Customize the <code>radios</code> section for your SDR devices</li>
            <li>Start the runner with: <code>python -m challengectl.runner.runner</code></li>
            <li>After successful enrollment, remove the <code>enrollment_token</code> line from the config</li>
          </ol>
        </div>

        <el-divider />

        <div class="credential-block">
          <h4>Token Expires:</h4>
          <div class="credential-value">
            <code>{{ formatTimestamp(enrollmentData.expires_at) }}</code>
          </div>
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

    <!-- Re-enroll Runner Dialog -->
    <el-dialog
      v-model="reEnrollDialogVisible"
      title="Re-enroll Runner"
      width="800px"
      :close-on-click-modal="false"
    >
      <div v-if="!reEnrollData">
        <el-alert
          title="Re-enrollment Process"
          type="info"
          description="Generate fresh credentials to migrate this runner to a different host or update compromised credentials."
          :closable="false"
          show-icon
          style="margin-bottom: 20px"
        />
        <p><strong>Runner ID:</strong> {{ reEnrollRunnerId }}</p>
        <p>This will generate new enrollment credentials. The old API key will remain valid until the runner re-enrolls with the new credentials.</p>
      </div>

      <div v-else class="enrollment-data">
        <el-alert
          title="Important: Save this configuration now!"
          type="warning"
          description="The enrollment token and API key will only be shown once. Download or copy the complete configuration below."
          :closable="false"
          show-icon
          style="margin-bottom: 20px"
        />

        <div style="margin-bottom: 15px;">
          <el-space>
            <el-button
              type="primary"
              @click="copyToClipboard(reEnrollGeneratedConfig, 'Configuration')"
            >
              Copy Full Config
            </el-button>
            <el-button
              type="success"
              @click="downloadReEnrollConfig"
            >
              Download runner-config.yml
            </el-button>
          </el-space>
        </div>

        <div class="config-display">
          <h4>Complete Runner Configuration:</h4>
          <pre class="config-content">{{ reEnrollGeneratedConfig }}</pre>
        </div>

        <el-divider />

        <div class="setup-instructions">
          <h4>Re-enrollment Instructions:</h4>
          <ol>
            <li>Download or copy the complete configuration above</li>
            <li>On the NEW runner machine, save as <code>runner-config.yml</code></li>
            <li>Customize the <code>radios</code> section for your SDR devices</li>
            <li>Start the runner with: <code>python -m challengectl.runner.runner</code></li>
            <li>After successful re-enrollment, remove the <code>enrollment_token</code> line from the config</li>
            <li>The old runner will be automatically kicked once the new one connects</li>
          </ol>
        </div>

        <el-divider />

        <div class="credential-block">
          <h4>Token Expires:</h4>
          <div class="credential-value">
            <code>{{ formatTimestamp(reEnrollData.expires_at) }}</code>
          </div>
        </div>
      </div>

      <template #footer>
        <span class="dialog-footer">
          <el-button v-if="!reEnrollData" @click="reEnrollDialogVisible = false">
            Cancel
          </el-button>
          <el-button
            v-if="!reEnrollData"
            type="primary"
            @click="generateReEnrollToken"
          >
            Generate Credentials
          </el-button>
          <el-button v-else type="primary" @click="closeReEnrollDialog">
            Done
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted } from 'vue'
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
      expiresHours: 24,
      verifySsl: true
    })
    const enrollmentData = ref(null)
    const serverUrl = ref(window.location.origin)

    // Re-enrollment state
    const reEnrollDialogVisible = ref(false)
    const reEnrollRunnerId = ref('')
    const reEnrollData = ref(null)

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
        expiresHours: 24,
        verifySsl: true
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
        expiresHours: 24,
        verifySsl: true
      }
    }

    // Generate complete runner-config.yml
    const generatedConfig = computed(() => {
      if (!enrollmentData.value) return ''

      const config = `---
# ChallengeCtl Runner Configuration
# Generated for runner: ${enrollmentData.value.runner_name}

runner:
  # Unique identifier for this runner
  runner_id: "${enrollmentData.value.runner_name}"

  # Server URL
  server_url: "${serverUrl.value}"

  # Enrollment credentials (remove enrollment_token after first successful run)
  enrollment_token: "${enrollmentData.value.token}"
  api_key: "${enrollmentData.value.api_key}"

  # TLS/SSL Configuration
  # Path to CA certificate file for server verification
  # Leave blank to use system CA certificates
  ca_cert: ""

  # Set to false to disable SSL verification (DEVELOPMENT ONLY!)
  # In production, always use verify_ssl: true with proper certificates
  verify_ssl: ${addRunnerForm.value.verifySsl}

  # Cache directory for downloaded challenge files (relative to runner directory)
  cache_dir: "cache"

  # Heartbeat interval (seconds) - how often to ping server
  heartbeat_interval: 30

  # Poll interval (seconds) - how often to request new tasks
  poll_interval: 10

  # Spectrum Paint Pre-Challenge
  # Set to true to fire spectrum paint before each challenge
  spectrum_paint_before_challenge: true

# Radio/SDR Device Configuration
radios:
  # Model defaults - configure default settings for each SDR type
  models:
  - model: hackrf
    rf_gain: 14
    if_gain: 32
    bias_t: true
    rf_samplerate: 2000000
    ppm: 0

  - model: bladerf
    rf_gain: 43
    bias_t: true
    rf_samplerate: 2000000
    ppm: 0

  - model: usrp
    rf_gain: 20
    bias_t: false
    rf_samplerate: 2000000
    ppm: 0

  # Individual device configuration
  # Customize this section for your specific SDR devices
  devices:
  # HackRF Example (by index)
  - name: 0
    model: hackrf
    rf_gain: 14
    if_gain: 32
    frequency_limits:
      - "144000000-148000000"  # 2m ham band
      - "420000000-450000000"  # 70cm ham band

  # Uncomment and configure for additional devices:
  # BladeRF Example (by serial number)
  # - name: "1234567890abcdef"
  #   model: bladerf
  #   rf_gain: 43
  #   bias_t: true
  #   antenna: TX1
  #   frequency_limits:
  #     - "144000000-148000000"
  #     - "420000000-450000000"

  # USRP Example
  # - name: "type=b200"
  #   model: usrp
  #   rf_gain: 20
  #   frequency_limits:
  #     - "70000000-6000000000"  # Full range

# Notes:
# - Device names can be index numbers (0, 1, 2) or serial numbers/identifiers
# - frequency_limits are optional - if not set, device can use any frequency
# - bias_t and antenna settings are device-specific
# - rf_gain and if_gain values depend on device type and setup
`
      return config
    })

    const downloadConfig = () => {
      if (!enrollmentData.value) return

      const blob = new Blob([generatedConfig.value], { type: 'text/yaml' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'runner-config.yml'
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
      ElMessage.success('Configuration downloaded')
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

    // Re-enrollment functions
    const showReEnrollDialog = (runnerId) => {
      reEnrollDialogVisible.value = true
      reEnrollRunnerId.value = runnerId
      reEnrollData.value = null
    }

    const closeReEnrollDialog = () => {
      reEnrollDialogVisible.value = false
      reEnrollRunnerId.value = ''
      reEnrollData.value = null
    }

    const generateReEnrollToken = async () => {
      if (!reEnrollRunnerId.value) {
        ElMessage.warning('No runner ID specified')
        return
      }

      try {
        const response = await api.post(`/enrollment/re-enroll/${reEnrollRunnerId.value}`, {
          expires_hours: 24
        })

        reEnrollData.value = {
          token: response.data.token,
          api_key: response.data.api_key,
          runner_id: response.data.runner_id,
          expires_at: response.data.expires_at
        }

        ElMessage.success('Re-enrollment credentials generated')
      } catch (error) {
        console.error('Error generating re-enrollment token:', error)
        ElMessage.error('Failed to generate re-enrollment credentials')
      }
    }

    const reEnrollGeneratedConfig = computed(() => {
      if (!reEnrollData.value) return ''

      const config = `---
# ChallengeCtl Runner Configuration - RE-ENROLLMENT
# Generated for runner: ${reEnrollData.value.runner_id}

runner:
  # Unique identifier for this runner
  runner_id: "${reEnrollData.value.runner_id}"

  # Server URL
  server_url: "${serverUrl.value}"

  # Re-enrollment credentials (remove enrollment_token after first successful run)
  enrollment_token: "${reEnrollData.value.token}"
  api_key: "${reEnrollData.value.api_key}"

  # TLS/SSL Configuration
  # Path to CA certificate file for server verification
  # Leave blank to use system CA certificates
  ca_cert: ""

  # Set to false to disable SSL verification (DEVELOPMENT ONLY!)
  # In production, always use verify_ssl: true with proper certificates
  verify_ssl: true

  # Cache directory for downloaded challenge files (relative to runner directory)
  cache_dir: "cache"

  # Heartbeat interval (seconds) - how often to ping server
  heartbeat_interval: 30

  # Poll interval (seconds) - how often to request new tasks
  poll_interval: 10

  # Spectrum Paint Pre-Challenge
  # Set to true to fire spectrum paint before each challenge
  spectrum_paint_before_challenge: true

# Radio/SDR Device Configuration
radios:
  # Model defaults - configure default settings for each SDR type
  models:
  - model: hackrf
    rf_gain: 14
    if_gain: 32
    bias_t: true
    rf_samplerate: 2000000
    ppm: 0

  - model: bladerf
    rf_gain: 43
    bias_t: true
    rf_samplerate: 2000000
    ppm: 0

  - model: usrp
    rf_gain: 20
    bias_t: false
    rf_samplerate: 2000000
    ppm: 0

  # Individual device configuration
  # Customize this section for your specific SDR devices
  devices:
  # HackRF Example (by index)
  - name: 0
    model: hackrf
    rf_gain: 14
    if_gain: 32
    frequency_limits:
      - "144000000-148000000"  # 2m ham band
      - "420000000-450000000"  # 70cm ham band

  # Uncomment and configure for additional devices:
  # BladeRF Example (by serial number)
  # - name: "1234567890abcdef"
  #   model: bladerf
  #   rf_gain: 43
  #   bias_t: true
  #   antenna: TX1
  #   frequency_limits:
  #     - "144000000-148000000"
  #     - "420000000-450000000"

  # USRP Example
  # - name: "type=b200"
  #   model: usrp
  #   rf_gain: 20
  #   frequency_limits:
  #     - "70000000-6000000000"  # Full range

# Notes:
# - Device names can be index numbers (0, 1, 2) or serial numbers/identifiers
# - frequency_limits are optional - if not set, device can use any frequency
# - bias_t and antenna settings are device-specific
# - rf_gain and if_gain values depend on device type and setup
`
      return config
    })

    const downloadReEnrollConfig = () => {
      if (!reEnrollData.value) return

      const blob = new Blob([reEnrollGeneratedConfig.value], { type: 'text/yaml' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `runner-config-${reEnrollData.value.runner_id}.yml`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
      ElMessage.success('Configuration downloaded')
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
      generatedConfig,
      reEnrollDialogVisible,
      reEnrollRunnerId,
      reEnrollData,
      reEnrollGeneratedConfig,
      showAddRunnerDialog,
      generateEnrollmentToken,
      closeAddRunnerDialog,
      copyToClipboard,
      downloadConfig,
      showReEnrollDialog,
      generateReEnrollToken,
      closeReEnrollDialog,
      downloadReEnrollConfig,
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
  font-size: 14px;
}

.credential-value {
  display: flex;
  align-items: center;
  gap: 10px;
  background-color: var(--el-fill-color-light);
  padding: 12px;
  border-radius: 4px;
  border: 1px solid var(--el-border-color);
}

.credential-value code {
  flex: 1;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  word-break: break-all;
}

.setup-instructions {
  margin-top: 20px;
}

.setup-instructions h4 {
  margin: 0 0 10px 0;
}

.setup-instructions ol {
  padding-left: 20px;
}

.setup-instructions li {
  margin-bottom: 10px;
  line-height: 1.6;
}

.setup-instructions code {
  background-color: var(--el-fill-color);
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

.setup-instructions pre {
  overflow-x: auto;
}

.config-display {
  margin-bottom: 20px;
}

.config-display h4 {
  margin: 0 0 10px 0;
  font-size: 14px;
}

.config-content {
  background-color: var(--el-fill-color-light);
  padding: 15px;
  border-radius: 4px;
  border: 1px solid var(--el-border-color);
  font-family: 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
  max-height: 400px;
  overflow-y: auto;
  margin: 0;
  white-space: pre;
}
</style>
