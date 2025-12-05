<template>
  <div class="recording-history">
    <div class="header">
      <el-button
        type="text"
        class="back-button"
        @click="$router.back()"
      >
        ← Back to Challenges
      </el-button>
      <h1>Recording History</h1>
    </div>

    <div
      v-if="loading"
      class="loading"
    >
      <el-icon class="is-loading">
        <Loading />
      </el-icon>
      Loading recordings...
    </div>

    <div
      v-else-if="challenge"
      class="content"
    >
      <el-card class="challenge-info">
        <h2>{{ challenge.name }}</h2>
        <div class="info-grid">
          <div><strong>Modulation:</strong> {{ challenge.config?.modulation || 'N/A' }}</div>
          <div><strong>Frequency:</strong> {{ formatFrequency(challenge.config?.frequency) }}</div>
          <div>
            <strong>Status:</strong>
            <el-tag
              :type="challenge.enabled ? 'success' : 'info'"
              size="small"
            >
              {{ challenge.enabled ? 'Enabled' : 'Disabled' }}
            </el-tag>
          </div>
          <div><strong>Total Transmissions:</strong> {{ challenge.transmission_count || 0 }}</div>
          <div><strong>Total Recordings:</strong> {{ recordings.length }}</div>
          <div v-if="challenge.last_tx_time">
            <strong>Last Transmission:</strong> {{ formatTimestamp(challenge.last_tx_time) }}
          </div>
        </div>
      </el-card>

      <div
        v-if="recordings.length === 0"
        class="no-recordings"
      >
        <el-empty description="No recordings available for this challenge yet." />
      </div>

      <div
        v-else
        class="recordings-container"
      >
        <h3>All Recordings ({{ recordings.length }})</h3>
        <div class="recordings-grid">
          <div
            v-for="recording in recordings"
            :key="recording.recording_id"
            class="recording-card"
          >
            <div class="recording-header">
              <span class="recording-title">Recording #{{ recording.recording_id }}</span>
              <el-tag
                :type="recording.status === 'completed' ? 'success' : recording.status === 'failed' ? 'danger' : 'warning'"
                size="small"
              >
                {{ recording.status }}
              </el-tag>
            </div>
            <div class="recording-info">
              <div><strong>Listener:</strong> {{ recording.listener_id }}</div>
              <div><strong>Frequency:</strong> {{ formatFrequency(recording.frequency) }}</div>
              <div><strong>Duration:</strong> {{ recording.duration_seconds ? recording.duration_seconds.toFixed(1) : '0.0' }}s</div>
              <div><strong>Started:</strong> {{ formatTimestamp(recording.started_at) }}</div>
              <div v-if="recording.completed_at">
                <strong>Completed:</strong> {{ formatTimestamp(recording.completed_at) }}
              </div>
            </div>
            <div
              v-if="recording.image_path && recording.status === 'completed'"
              class="recording-image"
            >
              <img
                :src="`/api/recordings/${recording.recording_id}/image?size=thumbnail`"
                :alt="`Waterfall for recording ${recording.recording_id}`"
                @click="showImageModal(recording)"
              >
            </div>
            <div
              v-else-if="recording.error_message"
              class="recording-error"
            >
              <el-alert
                type="error"
                :closable="false"
              >
                {{ recording.error_message }}
              </el-alert>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Recording Image Modal -->
    <el-dialog
      v-model="imageModalVisible"
      :title="`Recording #${selectedRecording?.recording_id} - Waterfall`"
      width="90%"
      append-to-body
      class="waterfall-dialog"
      @close="closeImageModal"
    >
      <div
        v-if="selectedRecording"
        class="modal-content"
      >
        <div class="modal-info">
          <p><strong>Challenge:</strong> {{ challenge?.name || 'Unknown' }}</p>
          <p><strong>Listener:</strong> {{ selectedRecording.listener_id }}</p>
          <p><strong>Frequency:</strong> {{ formatFrequency(selectedRecording.frequency) }}</p>
          <p><strong>Duration:</strong> {{ selectedRecording.duration_seconds ? selectedRecording.duration_seconds.toFixed(1) : '0.0' }}s</p>
          <p><strong>Started:</strong> {{ formatTimestamp(selectedRecording.started_at) }}</p>
          <p v-if="selectedRecording.completed_at">
            <strong>Completed:</strong> {{ formatTimestamp(selectedRecording.completed_at) }}
          </p>

          <!-- IQ Recording Section -->
          <div class="iq-section">
            <h4>IQ Recording</h4>
            <div v-if="selectedRecording.iq_file_path">
              <p><strong>Format:</strong> GNU Radio Complex Float32 (.c32)</p>
              <p><strong>File Size:</strong> {{ formatFileSize(selectedRecording.iq_file_size) }}</p>
              <p><strong>Sample Rate:</strong> {{ formatSampleRate(selectedRecording.sample_rate) }}</p>
              <el-button
                type="primary"
                @click="downloadIQ"
              >
                Download IQ Recording
              </el-button>
            </div>
            <div v-else>
              <el-alert
                type="info"
                :closable="false"
                show-icon
              >
                IQ recording not available for this recording
              </el-alert>
            </div>
          </div>
        </div>
        <div class="modal-image">
          <img
            :src="`/api/recordings/${selectedRecording.recording_id}/image?size=full`"
            :alt="`Waterfall for recording ${selectedRecording.recording_id}`"
          >
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'
import { ElMessage } from 'element-plus'
import { formatDateTime } from '../utils/time'
import { Loading } from '@element-plus/icons-vue'

export default {
  name: 'RecordingHistory',
  components: {
    Loading
  },
  setup() {
    const route = useRoute()
    const challengeId = route.params.challengeId

    const loading = ref(true)
    const challenge = ref(null)
    const recordings = ref([])
    const imageModalVisible = ref(false)
    const selectedRecording = ref(null)

    const loadChallenge = async () => {
      try {
        const response = await api.get('/challenges')
        const allChallenges = response.data.challenges || []
        challenge.value = allChallenges.find(c => c.challenge_id === challengeId)

        if (!challenge.value) {
          ElMessage.error('Challenge not found')
        }
      } catch (error) {
        console.error('Failed to load challenge:', error)
        ElMessage.error('Failed to load challenge information')
      }
    }

    const loadRecordings = async () => {
      try {
        const response = await api.get(`/challenges/${challengeId}/recordings?limit=1000`)
        recordings.value = response.data.recordings || []
      } catch (error) {
        console.error('Failed to load recordings:', error)
        ElMessage.error('Failed to load recordings')
        recordings.value = []
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

    const showImageModal = (recording) => {
      selectedRecording.value = recording
      imageModalVisible.value = true
    }

    const closeImageModal = () => {
      imageModalVisible.value = false
      selectedRecording.value = null
    }

    const downloadIQ = async () => {
      if (!selectedRecording.value?.recording_id) return

      try {
        const response = await fetch(
          `/api/recordings/${selectedRecording.value.recording_id}/iq`,
          {
            method: 'GET',
            credentials: 'include'
          }
        )

        if (response.ok) {
          const blob = await response.blob()
          const url = window.URL.createObjectURL(blob)
          const link = document.createElement('a')
          link.href = url
          link.download = `recording_${selectedRecording.value.recording_id}_iq.c32`
          document.body.appendChild(link)
          link.click()
          window.URL.revokeObjectURL(url)
          document.body.removeChild(link)
        } else {
          ElMessage.error('Failed to download IQ file')
        }
      } catch (error) {
        ElMessage.error(`Error: ${error.message}`)
      }
    }

    const formatFileSize = (bytes) => {
      if (!bytes) return 'Unknown'
      const units = ['B', 'KB', 'MB', 'GB']
      let size = bytes
      let unitIndex = 0
      while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024
        unitIndex++
      }
      return `${size.toFixed(2)} ${units[unitIndex]}`
    }

    const formatSampleRate = (sampleRate) => {
      if (!sampleRate) return 'Unknown'
      return `${(sampleRate / 1e6).toFixed(1)} MHz`
    }

    onMounted(async () => {
      loading.value = true
      await Promise.all([loadChallenge(), loadRecordings()])
      loading.value = false
    })

    return {
      loading,
      challenge,
      recordings,
      imageModalVisible,
      selectedRecording,
      formatFrequency,
      formatTimestamp: formatDateTime,
      showImageModal,
      closeImageModal,
      downloadIQ,
      formatFileSize,
      formatSampleRate,
    }
  }
}
</script>

<style scoped>
.recording-history {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.header {
  margin-bottom: 20px;
}

.back-button {
  margin-bottom: 10px;
  padding-left: 0;
  font-size: 14px;
}

h1 {
  margin: 0;
  font-size: 28px;
  color: var(--el-text-color-primary);
}

.loading {
  text-align: center;
  padding: 60px 20px;
  color: #909399;
  font-size: 16px;
}

.content {
  display: flex;
  flex-direction: column;
  gap: 30px;
}

.challenge-info {
  background: var(--el-bg-color);
}

.challenge-info h2 {
  margin: 0 0 20px 0;
  color: var(--el-text-color-primary);
  font-size: 24px;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 15px;
  font-size: 14px;
  color: var(--el-text-color-regular);
}

.info-grid strong {
  color: var(--el-text-color-primary);
  margin-right: 8px;
}

.no-recordings {
  text-align: center;
  padding: 60px 20px;
}

.recordings-container h3 {
  margin: 0 0 20px 0;
  color: var(--el-text-color-primary);
  font-size: 20px;
  font-weight: 600;
}

.recordings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 20px;
}

.recording-card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  padding: 15px;
  transition: box-shadow 0.3s;
}

.recording-card:hover {
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.recording-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--el-border-color-light);
}

.recording-title {
  font-weight: bold;
  color: var(--el-text-color-primary);
}

.recording-info {
  margin-bottom: 15px;
  font-size: 13px;
  color: var(--el-text-color-regular);
  line-height: 1.8;
}

.recording-info strong {
  color: var(--el-text-color-primary);
  margin-right: 5px;
}

.recording-image {
  margin-top: 15px;
  text-align: center;
  cursor: pointer;
}

.recording-image img {
  width: 100%;
  height: 400px;
  object-fit: cover;
  object-position: top;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  transition: transform 0.2s;
}

.recording-image img:hover {
  transform: scale(1.02);
}

.recording-error {
  margin-top: 10px;
}

.modal-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.modal-info {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  padding: 15px;
  background-color: var(--el-fill-color-light);
  border-radius: 4px;
}

.modal-info p {
  margin: 0;
  font-size: 14px;
  color: var(--el-text-color-regular);
}

.modal-info strong {
  color: var(--el-text-color-primary);
}

.modal-image {
  text-align: center;
}

.modal-image img {
  width: 100%;
  height: auto;
  display: block;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
}

/* Waterfall dialog with 100% width image and vertical scrolling */
:deep(.waterfall-dialog .el-dialog__body) {
  max-height: 80vh;
  overflow-y: auto;
  overflow-x: hidden;
}

.iq-section {
  grid-column: 1 / -1;
  margin-top: 10px;
  padding-top: 15px;
  border-top: 1px solid var(--el-border-color);
}

.iq-section h4 {
  margin: 0 0 10px 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.iq-section p {
  margin: 5px 0;
}

.iq-section .el-button {
  margin-top: 10px;
}
</style>
