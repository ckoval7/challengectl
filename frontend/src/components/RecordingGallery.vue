<template>
  <div class="recording-gallery">
    <div
      v-if="displayRecordings.length === 0 && placeholders.length === 0"
      class="no-recordings"
    >
      <el-empty
        description="No recordings yet"
        :image-size="80"
      />
    </div>

    <div
      v-else
      class="recordings-grid"
    >
      <!-- Placeholders for in-progress recordings (newest first) -->
      <TransitionGroup name="recording-pop">
        <div
          v-for="placeholder in placeholders"
          :key="`placeholder-${placeholder.recording_id}`"
          class="recording-card placeholder"
        >
          <div class="placeholder-content">
            <el-icon
              class="recording-icon"
              :size="32"
            >
              <Loading />
            </el-icon>
            <div class="placeholder-text">
              <div class="recording-status">
                {{ getPlaceholderStatusText(placeholder.status) }}
              </div>
              <div class="recording-meta">
                <span v-if="placeholder.listener_id">Listener: {{ placeholder.listener_id }}</span>
                <span v-if="placeholder.frequency">{{ formatFrequency(placeholder.frequency) }}</span>
              </div>
            </div>
          </div>
          <el-progress
            :percentage="100"
            :indeterminate="true"
            :show-text="false"
            :stroke-width="4"
            class="recording-progress"
          />
        </div>

        <!-- Completed recordings (newest first, limited to maxRecordings) -->
        <div
          v-for="recording in displayRecordings"
          :key="`recording-${recording.recording_id}`"
          class="recording-card"
          @click="previewRecording(recording)"
        >
          <div class="recording-image">
            <img
              v-if="recording.image_path"
              :src="getImageUrl(recording.recording_id)"
              :alt="`Recording ${recording.recording_id}`"
              loading="lazy"
            >
            <div
              v-else
              class="no-image"
            >
              <el-icon :size="32">
                <Picture />
              </el-icon>
              <span>No image</span>
            </div>
          </div>
          <div class="recording-info">
            <div class="recording-time">
              {{ formatTimestamp(recording.completed_at || recording.created_at) }}
            </div>
            <div class="recording-details">
              <el-tag
                v-if="recording.status === 'completed'"
                type="success"
                size="small"
              >
                Completed
              </el-tag>
              <el-tag
                v-else-if="recording.status === 'failed'"
                type="danger"
                size="small"
              >
                Failed
              </el-tag>
              <el-tag
                v-else
                type="info"
                size="small"
              >
                {{ recording.status }}
              </el-tag>
              <span
                v-if="recording.frequency"
                class="frequency"
              >{{ formatFrequency(recording.frequency) }}</span>
            </div>
          </div>
        </div>
      </TransitionGroup>
    </div>

    <!-- Image preview dialog -->
    <el-dialog
      v-model="previewDialogVisible"
      :title="`Recording ${selectedPreviewRecording?.recording_id || ''}`"
      width="90%"
      append-to-body
      :close-on-click-modal="true"
      :close-on-press-escape="true"
    >
      <div
        v-if="selectedPreviewRecording"
        class="preview-content"
      >
        <img
          v-if="selectedPreviewRecording.image_path"
          :src="getImageUrl(selectedPreviewRecording.recording_id)"
          :alt="`Recording ${selectedPreviewRecording.recording_id}`"
          class="preview-image"
        >
        <div class="preview-metadata">
          <el-descriptions
            :column="2"
            border
          >
            <el-descriptions-item label="Recording ID">
              {{ selectedPreviewRecording.recording_id }}
            </el-descriptions-item>
            <el-descriptions-item label="Status">
              <el-tag
                v-if="selectedPreviewRecording.status === 'completed'"
                type="success"
              >
                Completed
              </el-tag>
              <el-tag
                v-else-if="selectedPreviewRecording.status === 'failed'"
                type="danger"
              >
                Failed
              </el-tag>
              <el-tag
                v-else
                type="info"
              >
                {{ selectedPreviewRecording.status }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="Frequency">
              {{ formatFrequency(selectedPreviewRecording.frequency) }}
            </el-descriptions-item>
            <el-descriptions-item label="Sample Rate">
              {{ formatSampleRate(selectedPreviewRecording.sample_rate) }}
            </el-descriptions-item>
            <el-descriptions-item label="Started">
              {{ formatTimestamp(selectedPreviewRecording.started_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="Completed">
              {{ formatTimestamp(selectedPreviewRecording.completed_at) }}
            </el-descriptions-item>
            <el-descriptions-item
              v-if="selectedPreviewRecording.duration_seconds"
              label="Duration"
            >
              {{ selectedPreviewRecording.duration_seconds.toFixed(1) }}s
            </el-descriptions-item>
            <el-descriptions-item
              v-if="selectedPreviewRecording.image_width && selectedPreviewRecording.image_height"
              label="Image Size"
            >
              {{ selectedPreviewRecording.image_width }} x {{ selectedPreviewRecording.image_height }}px
            </el-descriptions-item>
          </el-descriptions>
          <div
            v-if="selectedPreviewRecording.error_message"
            class="error-message"
          >
            <el-alert
              type="error"
              :closable="false"
              show-icon
            >
              <template #title>
                Error
              </template>
              {{ selectedPreviewRecording.error_message }}
            </el-alert>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Loading, Picture } from '@element-plus/icons-vue'
import { formatDateTime } from '../utils/time.js'

const props = defineProps({
  recordings: {
    type: Array,
    default: () => []
  },
  placeholders: {
    type: Array,
    default: () => []
  },
  maxRecordings: {
    type: Number,
    default: 6
  }
})

const previewDialogVisible = ref(false)
const selectedPreviewRecording = ref(null)

// Display only the most recent N recordings (newest first)
const displayRecordings = computed(() => {
  const sorted = [...props.recordings].sort((a, b) => {
    const timeA = new Date(b.started_at || b.created_at)
    const timeB = new Date(a.started_at || a.created_at)
    return timeA - timeB
  })
  return sorted.slice(0, props.maxRecordings)
})

// Get status text for placeholder based on status
function getPlaceholderStatusText(status) {
  const statusMap = {
    'in_progress': 'Recording in progress...',
    'completed': 'Processing...',
    'failed': 'Recording failed'
  }
  return statusMap[status] || 'Recording in progress...'
}

function getImageUrl(recordingId) {
  return `/api/recordings/${recordingId}/image`
}

function formatFrequency(hz) {
  if (!hz) return 'Unknown'
  const mhz = hz / 1e6
  return `${mhz.toFixed(3)} MHz`
}

function formatSampleRate(rate) {
  if (!rate) return 'Unknown'
  const msps = rate / 1e6
  return `${msps.toFixed(1)} Msps`
}

function formatTimestamp(timestamp) {
  if (!timestamp) return 'Unknown'
  return formatDateTime(timestamp)
}

function previewRecording(recording) {
  selectedPreviewRecording.value = recording
  previewDialogVisible.value = true
}
</script>

<style scoped>
.recording-gallery {
  padding: 12px 0;
}

.no-recordings {
  padding: 40px 20px;
  text-align: center;
  color: var(--el-text-color-secondary);
}

.recordings-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

@media (max-width: 768px) {
  .recordings-grid {
    grid-template-columns: 1fr;
  }
}

.recording-card {
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  overflow: hidden;
  background: var(--el-bg-color);
  transition: all 0.3s ease;
  cursor: pointer;
}

.recording-card:not(.placeholder):hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.recording-card.placeholder {
  cursor: default;
  background: var(--el-fill-color-light);
}

.placeholder-content {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
}

.recording-icon {
  color: var(--el-color-primary);
  animation: spin 1.5s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.placeholder-text {
  flex: 1;
}

.recording-status {
  font-weight: 500;
  color: var(--el-text-color-primary);
  margin-bottom: 4px;
}

.recording-meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  display: flex;
  gap: 12px;
}

.recording-progress {
  padding: 0 20px 12px;
}

.recording-image {
  aspect-ratio: 16 / 9;
  background: var(--el-fill-color-darker);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.recording-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.no-image {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: var(--el-text-color-placeholder);
}

.recording-info {
  padding: 12px;
}

.recording-time {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-primary);
  margin-bottom: 8px;
}

.recording-details {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.frequency {
  color: var(--el-text-color-secondary);
}

/* Pop-in animation for new recordings */
.recording-pop-enter-active {
  animation: pop-in 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.recording-pop-leave-active {
  animation: pop-out 0.3s ease-out;
}

@keyframes pop-in {
  from {
    opacity: 0;
    transform: scale(0.8) translateY(-20px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

@keyframes pop-out {
  from {
    opacity: 1;
    transform: scale(1);
  }
  to {
    opacity: 0;
    transform: scale(0.8);
  }
}

/* Preview dialog */
.preview-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.preview-image {
  width: 100%;
  max-height: 70vh;
  object-fit: contain;
  background: var(--el-fill-color-darker);
  border-radius: 4px;
}

.preview-metadata {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.error-message {
  margin-top: 12px;
}
</style>
