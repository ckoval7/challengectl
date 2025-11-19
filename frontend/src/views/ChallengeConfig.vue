<template>
  <div class="challenge-config">
    <h1>Manage Challenges</h1>

    <el-tabs
      v-model="activeTab"
      type="border-card"
    >
      <!-- Live Status Tab -->
      <el-tab-pane
        label="Live Status"
        name="status"
      >
        <div style="margin-bottom: 20px">
          <el-button
            type="primary"
            @click="reloadChallenges"
          >
            Reload from Config
          </el-button>
        </div>

        <el-table
          :data="challenges"
          style="width: 100%"
        >
          <el-table-column
            prop="name"
            label="Name"
            width="200"
          />
          <el-table-column
            label="Modulation"
            width="120"
          >
            <template #default="scope">
              {{ scope.row.config?.modulation || 'N/A' }}
            </template>
          </el-table-column>
          <el-table-column
            label="Frequency"
            width="150"
          >
            <template #default="scope">
              {{ formatFrequency(scope.row.config?.frequency) }}
            </template>
          </el-table-column>
          <el-table-column
            label="Status"
            width="100"
          >
            <template #default="scope">
              <el-tag
                :type="getStatusType(scope.row)"
                size="small"
              >
                {{ !scope.row.enabled ? 'disabled' : scope.row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            label="Enabled"
            width="100"
          >
            <template #default="scope">
              <el-switch
                v-model="scope.row.enabled"
                @change="toggleChallenge(scope.row)"
              />
            </template>
          </el-table-column>
          <el-table-column
            label="TX Count"
            width="100"
          >
            <template #default="scope">
              {{ scope.row.transmission_count || 0 }}
            </template>
          </el-table-column>
          <el-table-column
            label="Last TX"
            width="180"
          >
            <template #default="scope">
              {{ formatTimestamp(scope.row.last_tx_time) }}
            </template>
          </el-table-column>
          <el-table-column
            label="Actions"
            width="150"
          >
            <template #default="scope">
              <el-button
                size="small"
                type="primary"
                @click="triggerChallenge(scope.row.challenge_id)"
              >
                Trigger Now
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- Create/Edit Challenge Tab -->
      <el-tab-pane
        label="Create Challenge"
        name="create"
      >
        <el-form
          ref="formRef"
          :model="challengeForm"
          label-width="180px"
          style="max-width: 800px"
        >
          <h3>Basic Information</h3>

          <el-form-item
            label="Challenge Name"
            required
          >
            <el-input
              v-model="challengeForm.name"
              placeholder="e.g., NBFM_FLAG_1"
            />
          </el-form-item>

          <el-form-item
            label="Modulation"
            required
          >
            <el-select
              v-model="challengeForm.modulation"
              placeholder="Select modulation"
              @change="onModulationChange"
            >
              <el-option
                label="NBFM (Narrowband FM)"
                value="nbfm"
              />
              <el-option
                label="SSB (Single Sideband)"
                value="ssb"
              />
              <el-option
                label="FreeDV"
                value="freedv"
              />
              <el-option
                label="CW (Morse Code)"
                value="cw"
              />
              <el-option
                label="ASK (Amplitude Shift Keying)"
                value="ask"
              />
              <el-option
                label="POCSAG (Pager)"
                value="pocsag"
              />
              <el-option
                label="FHSS (Frequency Hopping)"
                value="fhss"
              />
              <el-option
                label="LoRa"
                value="lrs"
              />
            </el-select>
          </el-form-item>

          <el-form-item
            label="Frequency (Hz)"
            required
          >
            <el-input-number
              v-model="challengeForm.frequency"
              :min="1000000"
              :max="6000000000"
              :step="1000"
              style="width: 100%"
            />
          </el-form-item>

          <el-form-item label="Enabled">
            <el-switch v-model="challengeForm.enabled" />
          </el-form-item>

          <h3>Challenge Content</h3>

          <el-form-item
            v-if="['nbfm', 'ssb', 'freedv', 'fhss'].includes(challengeForm.modulation)"
            label="Flag (Audio File)"
          >
            <el-input
              v-model="challengeForm.flag"
              placeholder="Path to WAV file or upload below"
            />
            <el-upload
              ref="flagUploadRef"
              :auto-upload="false"
              :limit="1"
              accept=".wav"
              @change="handleFlagFileChange"
            >
              <el-button
                size="small"
                style="margin-top: 10px"
              >
                Choose File
              </el-button>
            </el-upload>
          </el-form-item>

          <el-form-item
            v-if="['cw', 'ask', 'pocsag'].includes(challengeForm.modulation)"
            label="Flag (Text)"
          >
            <el-input
              v-model="challengeForm.flag"
              type="textarea"
              :rows="3"
              placeholder="Enter flag text"
            />
          </el-form-item>

          <el-form-item
            v-if="challengeForm.modulation === 'lrs'"
            label="Flag (Binary File)"
          >
            <el-input
              v-model="challengeForm.flag"
              placeholder="Path to binary file or upload below"
            />
            <el-upload
              ref="flagUploadRef"
              :auto-upload="false"
              :limit="1"
              accept=".bin"
              @change="handleFlagFileChange"
            >
              <el-button
                size="small"
                style="margin-top: 10px"
              >
                Choose File
              </el-button>
            </el-upload>
          </el-form-item>

          <h3>Timing Configuration</h3>

          <el-form-item label="Min Delay (seconds)">
            <el-input-number
              v-model="challengeForm.min_delay"
              :min="1"
              :max="3600"
              style="width: 100%"
            />
          </el-form-item>

          <el-form-item label="Max Delay (seconds)">
            <el-input-number
              v-model="challengeForm.max_delay"
              :min="1"
              :max="3600"
              style="width: 100%"
            />
          </el-form-item>

          <el-form-item label="Priority">
            <el-input-number
              v-model="challengeForm.priority"
              :min="0"
              :max="100"
              style="width: 100%"
            />
            <div style="font-size: 12px; color: var(--el-text-color-secondary); margin-top: 5px">
              Higher priority challenges are transmitted first (higher number = higher priority)
            </div>
          </el-form-item>

          <h3>Public Dashboard Visibility</h3>

          <el-form-item label="Public Fields">
            <el-checkbox-group v-model="challengeForm.public_fields">
              <el-checkbox label="name">
                Name
              </el-checkbox>
              <el-checkbox label="modulation">
                Modulation
              </el-checkbox>
              <el-checkbox label="frequency">
                Frequency
              </el-checkbox>
              <el-checkbox label="status">
                Status
              </el-checkbox>
              <el-checkbox label="last_tx_time">
                Last TX Time
              </el-checkbox>
            </el-checkbox-group>
            <div style="font-size: 12px; color: var(--el-text-color-secondary); margin-top: 5px">
              Select which fields are visible on the public dashboard
            </div>
          </el-form-item>

          <h3 v-if="showModulationSpecificFields">
            Modulation-Specific Settings
          </h3>

          <!-- NBFM/SSB/FreeDV/FHSS settings -->
          <el-form-item
            v-if="['nbfm', 'ssb', 'freedv', 'fhss'].includes(challengeForm.modulation)"
            label="WAV Sample Rate"
          >
            <el-input-number
              v-model="challengeForm.wav_samplerate"
              :min="8000"
              :max="192000"
              :step="1000"
              style="width: 100%"
            />
          </el-form-item>

          <!-- CW settings -->
          <el-form-item
            v-if="challengeForm.modulation === 'cw'"
            label="Speed (WPM)"
          >
            <el-input-number
              v-model="challengeForm.speed"
              :min="5"
              :max="60"
              style="width: 100%"
            />
          </el-form-item>

          <!-- FHSS settings -->
          <template v-if="challengeForm.modulation === 'fhss'">
            <el-form-item label="Channel Spacing (Hz)">
              <el-input-number
                v-model="challengeForm.channel_spacing"
                :min="1000"
                :max="1000000"
                :step="1000"
                style="width: 100%"
              />
            </el-form-item>

            <el-form-item label="Hop Rate (Hz)">
              <el-input-number
                v-model="challengeForm.hop_rate"
                :min="1"
                :max="1000"
                style="width: 100%"
              />
            </el-form-item>

            <el-form-item label="Hop Time (seconds)">
              <el-input-number
                v-model="challengeForm.hop_time"
                :min="1"
                :max="300"
                style="width: 100%"
              />
            </el-form-item>

            <el-form-item label="Seed">
              <el-input
                v-model="challengeForm.seed"
                placeholder="Hopping sequence seed"
              />
            </el-form-item>
          </template>

          <!-- LoRa settings -->
          <template v-if="challengeForm.modulation === 'lrs'">
            <el-form-item label="Spreading Factor">
              <el-input-number
                v-model="challengeForm.spreading_factor"
                :min="6"
                :max="12"
                style="width: 100%"
              />
            </el-form-item>

            <el-form-item label="Bandwidth (Hz)">
              <el-select
                v-model="challengeForm.bandwidth"
                placeholder="Select bandwidth"
              >
                <el-option
                  label="125 kHz"
                  :value="125000"
                />
                <el-option
                  label="250 kHz"
                  :value="250000"
                />
                <el-option
                  label="500 kHz"
                  :value="500000"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="Coding Rate">
              <el-select
                v-model="challengeForm.coding_rate"
                placeholder="Select coding rate"
              >
                <el-option
                  label="4/5"
                  value="4/5"
                />
                <el-option
                  label="4/6"
                  value="4/6"
                />
                <el-option
                  label="4/7"
                  value="4/7"
                />
                <el-option
                  label="4/8"
                  value="4/8"
                />
              </el-select>
            </el-form-item>
          </template>

          <el-form-item>
            <el-button
              type="primary"
              @click="createChallenge"
            >
              Create Challenge
            </el-button>
            <el-button @click="resetForm">
              Reset
            </el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <!-- Import from YAML Tab -->
      <el-tab-pane
        label="Import from YAML"
        name="import"
      >
        <div style="max-width: 800px">
          <el-alert
            title="Import Challenges"
            type="info"
            :closable="false"
            style="margin-bottom: 20px"
          >
            Upload a YAML file containing challenge definitions along with any associated files
            (audio files, binary files, etc.). This can also be used for automation via API.
          </el-alert>

          <h3>YAML File</h3>
          <el-upload
            ref="yamlUploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".yml,.yaml"
            @change="handleYamlChange"
          >
            <el-button type="primary">
              Select YAML File
            </el-button>
          </el-upload>

          <h3 style="margin-top: 30px">
            Challenge Files (Optional)
          </h3>
          <p style="color: #666; font-size: 14px">
            Upload audio files, binary files, or other resources referenced in your YAML.
            File paths in the YAML will be automatically updated.
          </p>

          <el-upload
            ref="filesUploadRef"
            :auto-upload="false"
            multiple
            accept=".wav,.bin,.txt,.py,.grc"
            :file-list="challengeFiles"
            @change="handleFilesChange"
          >
            <el-button>Add Files</el-button>
          </el-upload>

          <div style="margin-top: 30px">
            <el-button
              type="primary"
              :disabled="!yamlFile"
              :loading="importing"
              @click="importChallenges"
            >
              Import Challenges
            </el-button>
            <el-button @click="clearImportForm">
              Clear
            </el-button>
          </div>

          <el-divider />

          <h3>API Endpoint for Automation</h3>
          <el-alert
            type="success"
            :closable="false"
            style="margin-bottom: 10px"
          >
            <div>
              <strong>POST /api/challenges/import</strong>
            </div>
            <div style="margin-top: 10px; font-family: monospace; font-size: 12px">
              Content-Type: multipart/form-data<br>
              Required: yaml_file (YAML file)<br>
              Optional: Additional files referenced in YAML
            </div>
          </el-alert>

          <el-collapse>
            <el-collapse-item
              title="Example cURL Command"
              name="curl"
            >
              <pre class="code-example"><code>curl -X POST http://localhost:8080/api/challenges/import \
  -H "X-CSRF-Token: YOUR_CSRF_TOKEN" \
  -b "session=YOUR_SESSION_COOKIE" \
  -F "yaml_file=@challenges.yml" \
  -F "example_voice.wav=@/path/to/example_voice.wav" \
  -F "flag_data.bin=@/path/to/flag_data.bin"</code></pre>
            </el-collapse-item>

            <el-collapse-item
              title="Example Python Script"
              name="python"
            >
              <pre class="code-example"><code>import requests

url = "http://localhost:8080/api/challenges/import"
files = {
    'yaml_file': open('challenges.yml', 'rb'),
    'example_voice.wav': open('example_voice.wav', 'rb'),
}
cookies = {'session': 'YOUR_SESSION_COOKIE'}
headers = {'X-CSRF-Token': 'YOUR_CSRF_TOKEN'}

response = requests.post(url, files=files, cookies=cookies, headers=headers)
print(response.json())</code></pre>
            </el-collapse-item>
          </el-collapse>
        </div>
      </el-tab-pane>

      <!-- Manage Challenges Tab -->
      <el-tab-pane
        label="Manage Challenges"
        name="manage"
      >
        <div style="margin-bottom: 20px">
          <el-button
            type="success"
            @click="loadChallenges"
          >
            Refresh List
          </el-button>
        </div>

        <el-table
          :data="challenges"
          style="width: 100%"
        >
          <el-table-column
            prop="name"
            label="Name"
            width="200"
          />
          <el-table-column
            label="Modulation"
            width="120"
          >
            <template #default="scope">
              {{ scope.row.config?.modulation || 'N/A' }}
            </template>
          </el-table-column>
          <el-table-column
            label="Frequency"
            width="150"
          >
            <template #default="scope">
              {{ formatFrequency(scope.row.config?.frequency) }}
            </template>
          </el-table-column>
          <el-table-column
            label="Status"
            width="100"
          >
            <template #default="scope">
              <el-tag
                :type="scope.row.enabled ? 'success' : 'info'"
                size="small"
              >
                {{ scope.row.enabled ? 'Enabled' : 'Disabled' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            label="TX Count"
            width="100"
          >
            <template #default="scope">
              {{ scope.row.transmission_count || 0 }}
            </template>
          </el-table-column>
          <el-table-column
            label="Actions"
            min-width="180"
          >
            <template #default="scope">
              <el-button
                size="small"
                type="primary"
                @click="editChallenge(scope.row)"
              >
                Edit
              </el-button>
              <el-popconfirm
                title="Are you sure you want to delete this challenge?"
                @confirm="deleteChallenge(scope.row.challenge_id)"
              >
                <template #reference>
                  <el-button
                    size="small"
                    type="danger"
                  >
                    Delete
                  </el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- Edit Challenge Dialog -->
    <el-dialog
      v-model="editDialogVisible"
      title="Edit Challenge"
      width="800px"
    >
      <el-form
        :model="editForm"
        label-width="180px"
      >
        <el-form-item label="Challenge Name">
          <el-input
            v-model="editForm.name"
            disabled
          />
        </el-form-item>

        <el-form-item label="Configuration (JSON)">
          <el-input
            v-model="editConfigJson"
            type="textarea"
            :rows="15"
            style="font-family: monospace"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="editDialogVisible = false">
          Cancel
        </el-button>
        <el-button
          type="primary"
          @click="saveEditedChallenge"
        >
          Save
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { api } from '../api'
import { ElMessage } from 'element-plus'
import { formatDateTime } from '../utils/time'

export default {
  name: 'ChallengeConfig',
  setup() {
    const activeTab = ref('status')
    const challenges = ref([])
    const importing = ref(false)

    // Create form
    const challengeForm = ref({
      name: '',
      modulation: 'nbfm',
      frequency: 146550000,
      enabled: true,
      flag: '',
      min_delay: 60,
      max_delay: 90,
      priority: 0,
      public_fields: ['name', 'modulation', 'frequency', 'status'], // Default public fields
      wav_samplerate: 48000,
      speed: 35, // CW
      channel_spacing: 10000, // FHSS
      hop_rate: 10, // FHSS
      hop_time: 60, // FHSS
      seed: '', // FHSS
      spreading_factor: 7, // LoRa
      bandwidth: 125000, // LoRa
      coding_rate: '4/5', // LoRa
    })

    const flagFile = ref(null)
    const flagUploadRef = ref(null)

    // Import form
    const yamlFile = ref(null)
    const challengeFiles = ref([])
    const yamlUploadRef = ref(null)
    const filesUploadRef = ref(null)

    // Edit dialog
    const editDialogVisible = ref(false)
    const editForm = ref({})
    const editConfigJson = ref('')

    const showModulationSpecificFields = computed(() => {
      return challengeForm.value.modulation !== ''
    })

    // Convert public_fields array to public_view object format
    const convertPublicFieldsToView = (publicFields) => {
      if (!publicFields || publicFields.length === 0) {
        return {}
      }

      return {
        show_modulation: publicFields.includes('modulation'),
        show_frequency: publicFields.includes('frequency'),
        show_last_tx_time: publicFields.includes('last_tx_time'),
        show_active_status: publicFields.includes('status')
      }
    }

    const onModulationChange = () => {
      // Reset flag when modulation changes
      challengeForm.value.flag = ''
      flagFile.value = null
      if (flagUploadRef.value) {
        flagUploadRef.value.clearFiles()
      }
    }

    const handleFlagFileChange = (file) => {
      flagFile.value = file.raw
    }

    const handleYamlChange = (file) => {
      yamlFile.value = file.raw
    }

    const handleFilesChange = (file, fileList) => {
      challengeFiles.value = fileList
    }

    const resetForm = () => {
      challengeForm.value = {
        name: '',
        modulation: 'nbfm',
        frequency: 146550000,
        enabled: true,
        flag: '',
        min_delay: 60,
        max_delay: 90,
        priority: 0,
        public_fields: ['name', 'modulation', 'frequency', 'status'],
        wav_samplerate: 48000,
        speed: 35,
        channel_spacing: 10000,
        hop_rate: 10,
        hop_time: 60,
        seed: '',
        spreading_factor: 7,
        bandwidth: 125000,
        coding_rate: '4/5',
      }
      flagFile.value = null
      if (flagUploadRef.value) {
        flagUploadRef.value.clearFiles()
      }
    }

    const clearImportForm = () => {
      yamlFile.value = null
      challengeFiles.value = []
      if (yamlUploadRef.value) {
        yamlUploadRef.value.clearFiles()
      }
      if (filesUploadRef.value) {
        filesUploadRef.value.clearFiles()
      }
    }

    const createChallenge = async () => {
      if (!challengeForm.value.name) {
        ElMessage.error('Challenge name is required')
        return
      }

      if (!challengeForm.value.modulation) {
        ElMessage.error('Modulation is required')
        return
      }

      if (!challengeForm.value.frequency) {
        ElMessage.error('Frequency is required')
        return
      }

      try {
        // Build config object based on modulation type
        const config = {
          name: challengeForm.value.name,
          modulation: challengeForm.value.modulation,
          frequency: challengeForm.value.frequency,
          enabled: challengeForm.value.enabled,
          min_delay: challengeForm.value.min_delay,
          max_delay: challengeForm.value.max_delay,
          priority: challengeForm.value.priority,
          public_view: convertPublicFieldsToView(challengeForm.value.public_fields),
        }

        // Handle file upload if a file was selected
        if (flagFile.value) {
          try {
            // Upload the file first
            const formData = new FormData()
            formData.append('file', flagFile.value)

            const uploadResponse = await api.post('/files/upload', formData, {
              headers: {
                'Content-Type': 'multipart/form-data'
              }
            })

            // Store the file hash in the config
            config.flag_file_hash = uploadResponse.data.file_hash
            // Also store the original filename for reference
            if (!challengeForm.value.flag) {
              config.flag = uploadResponse.data.filename
            }
          } catch (uploadError) {
            console.error('Failed to upload file:', uploadError)
            ElMessage.error(uploadError.response?.data?.error || 'Failed to upload file')
            return
          }
        }

        // Add flag text if provided (and no file was uploaded)
        if (challengeForm.value.flag && !flagFile.value) {
          config.flag = challengeForm.value.flag
        }

        // Add modulation-specific fields
        if (['nbfm', 'ssb', 'freedv', 'fhss'].includes(challengeForm.value.modulation)) {
          config.wav_samplerate = challengeForm.value.wav_samplerate
        }

        if (challengeForm.value.modulation === 'cw') {
          config.speed = challengeForm.value.speed
        }

        if (challengeForm.value.modulation === 'fhss') {
          config.channel_spacing = challengeForm.value.channel_spacing
          config.hop_rate = challengeForm.value.hop_rate
          config.hop_time = challengeForm.value.hop_time
          if (challengeForm.value.seed) {
            config.seed = challengeForm.value.seed
          }
        }

        if (challengeForm.value.modulation === 'lrs') {
          config.spreading_factor = challengeForm.value.spreading_factor
          config.bandwidth = challengeForm.value.bandwidth
          config.coding_rate = challengeForm.value.coding_rate
        }

        await api.post('/challenges', {
          name: challengeForm.value.name,
          config: config
        })

        ElMessage.success('Challenge created successfully')
        resetForm()
        loadChallenges()
        activeTab.value = 'manage'
      } catch (error) {
        console.error('Failed to create challenge:', error)
        ElMessage.error(error.response?.data?.error || 'Failed to create challenge')
      }
    }

    const importChallenges = async () => {
      if (!yamlFile.value) {
        ElMessage.error('Please select a YAML file')
        return
      }

      importing.value = true

      try {
        const formData = new FormData()
        formData.append('yaml_file', yamlFile.value)

        // Add challenge files
        challengeFiles.value.forEach(file => {
          formData.append(file.name, file.raw)
        })

        const response = await api.post('/challenges/import', formData, {
          headers: {
            'Content-Type': 'multipart/form-data'
          }
        })

        const result = response.data
        let message = `Imported successfully: ${result.added} added, ${result.updated} updated`
        if (result.files_uploaded > 0) {
          message += `, ${result.files_uploaded} files uploaded`
        }

        ElMessage.success(message)

        if (result.errors && result.errors.length > 0) {
          ElMessage.warning(`Some errors occurred: ${result.errors.join(', ')}`)
        }

        clearImportForm()
        loadChallenges()
        activeTab.value = 'manage'
      } catch (error) {
        console.error('Failed to import challenges:', error)
        ElMessage.error(error.response?.data?.error || 'Failed to import challenges')
      } finally {
        importing.value = false
      }
    }

    const loadChallenges = async () => {
      try {
        const response = await api.get('/challenges')
        // Ensure enabled is a proper boolean
        challenges.value = (response.data.challenges || []).map(c => ({
          ...c,
          enabled: Boolean(c.enabled)
        }))
      } catch (error) {
        console.error('Failed to load challenges:', error)
        ElMessage.error('Failed to load challenges')
      }
    }

    const reloadChallenges = async () => {
      try {
        const response = await api.post('/challenges/reload')
        ElMessage.success(`Reloaded challenges: ${response.data.added} added`)
        loadChallenges()
      } catch (error) {
        console.error('Error reloading challenges:', error)
        ElMessage.error('Failed to reload challenges')
      }
    }

    const toggleChallenge = async (challenge) => {
      try {
        await api.post(`/challenges/${challenge.challenge_id}/enable`, {
          enabled: challenge.enabled
        })
        ElMessage.success(`Challenge ${challenge.enabled ? 'enabled' : 'disabled'}`)
        // Reload to ensure UI is in sync with database
        await loadChallenges()
      } catch (error) {
        console.error('Error toggling challenge:', error)
        ElMessage.error('Failed to update challenge')
        loadChallenges()  // Reload to reset state
      }
    }

    const triggerChallenge = async (challengeId) => {
      try {
        await api.post(`/challenges/${challengeId}/trigger`)
        ElMessage.success('Challenge triggered')
        loadChallenges()
      } catch (error) {
        console.error('Error triggering challenge:', error)
        ElMessage.error('Failed to trigger challenge')
      }
    }

    const getStatusType = (challenge) => {
      if (!challenge.enabled) return 'info'
      switch (challenge.status) {
        case 'queued': return 'success'  // Green - ready
        case 'waiting': return 'warning' // Orange - delay timer
        case 'assigned': return ''       // Default - transmitting
        default: return 'info'
      }
    }

    const editChallenge = (challenge) => {
      editForm.value = { ...challenge }
      editConfigJson.value = JSON.stringify(challenge.config, null, 2)
      editDialogVisible.value = true
    }

    const saveEditedChallenge = async () => {
      try {
        const config = JSON.parse(editConfigJson.value)

        await api.put(`/challenges/${editForm.value.challenge_id}`, {
          config: config
        })

        ElMessage.success('Challenge updated successfully')
        editDialogVisible.value = false
        loadChallenges()
      } catch (error) {
        console.error('Failed to update challenge:', error)
        if (error instanceof SyntaxError) {
          ElMessage.error('Invalid JSON format')
        } else {
          ElMessage.error(error.response?.data?.error || 'Failed to update challenge')
        }
      }
    }

    const deleteChallenge = async (challengeId) => {
      try {
        await api.delete(`/challenges/${challengeId}`)
        ElMessage.success('Challenge deleted successfully')
        loadChallenges()
      } catch (error) {
        console.error('Failed to delete challenge:', error)
        ElMessage.error(error.response?.data?.error || 'Failed to delete challenge')
      }
    }

    const formatFrequency = (freq) => {
      if (!freq) return 'N/A'
      if (freq >= 1000000000) {
        return `${(freq / 1000000000).toFixed(3)} GHz`
      } else if (freq >= 1000000) {
        return `${(freq / 1000000).toFixed(3)} MHz`
      } else if (freq >= 1000) {
        return `${(freq / 1000).toFixed(3)} kHz`
      }
      return `${freq} Hz`
    }

    onMounted(() => {
      loadChallenges()

      // Refresh periodically for live status
      const interval = setInterval(loadChallenges, 15000)
      onUnmounted(() => clearInterval(interval))
    })

    return {
      activeTab,
      challenges,
      importing,
      challengeForm,
      flagFile,
      flagUploadRef,
      yamlFile,
      challengeFiles,
      yamlUploadRef,
      filesUploadRef,
      editDialogVisible,
      editForm,
      editConfigJson,
      showModulationSpecificFields,
      onModulationChange,
      handleFlagFileChange,
      handleYamlChange,
      handleFilesChange,
      resetForm,
      clearImportForm,
      createChallenge,
      importChallenges,
      loadChallenges,
      reloadChallenges,
      toggleChallenge,
      triggerChallenge,
      getStatusType,
      formatTimestamp: formatDateTime,
      editChallenge,
      saveEditedChallenge,
      deleteChallenge,
      formatFrequency,
    }
  }
}
</script>

<style scoped>
.challenge-config {
  padding: 20px;
}

h1 {
  margin-bottom: 20px;
}

h3 {
  margin-top: 20px;
  margin-bottom: 15px;
  color: var(--el-text-color-primary);
  font-weight: 600;
}

.el-tabs {
  margin-top: 20px;
}

.code-example {
  background: #f5f5f5;
  padding: 15px;
  border-radius: 4px;
  overflow-x: auto;
  color: #333;
}

/* Dark mode adjustments */
html.dark .code-example {
  background: #2d2d2d;
  color: #e0e0e0;
  border: 1px solid #444;
}
</style>
