<template>
  <div
    class="challenge-card"
    :class="{ disabled: !challenge.enabled, expanded: isExpanded }"
  >
    <!-- Card Header -->
    <div
      class="card-header"
      @click="toggleExpand"
    >
      <div class="header-main">
        <div class="challenge-name">
          <el-icon
            v-if="isExpanded"
            class="expand-icon"
          >
            <ArrowDown />
          </el-icon>
          <el-icon
            v-else
            class="expand-icon"
          >
            <ArrowRight />
          </el-icon>
          <span>{{ challenge.name }}</span>
        </div>
        <div class="status-badges">
          <el-tag
            :type="getStatusTagType(challenge.status)"
            size="small"
            effect="dark"
          >
            {{ challenge.status }}
          </el-tag>
          <el-switch
            v-if="showToggle"
            v-model="challengeEnabled"
            size="small"
            @click.stop
          />
        </div>
      </div>
      <div class="header-details">
        <div class="detail-item">
          <el-icon><Operation /></el-icon>
          <span>{{ challenge.config?.modulation || 'Unknown' }}</span>
        </div>
        <div class="detail-item">
          <el-icon><Promotion /></el-icon>
          <span>{{ formatFrequency(challenge.assigned_frequency || challenge.config?.frequency) }}</span>
        </div>
      </div>
    </div>

    <!-- Card Content (Expandable) -->
    <Transition name="expand">
      <div
        v-if="isExpanded"
        class="card-content"
      >
        <!-- Stats Section -->
        <div class="stats-section">
          <div class="stat-item">
            <div class="stat-label">
              Transmissions
            </div>
            <div class="stat-value">
              {{ challenge.transmission_count || 0 }}
            </div>
          </div>
          <div class="stat-item">
            <div class="stat-label">
              Recordings
            </div>
            <div class="stat-value">
              {{ challenge.recording_count || 0 }}
            </div>
          </div>
          <div class="stat-item">
            <div class="stat-label">
              Priority
            </div>
            <div class="stat-value">
              {{ challenge.priority || 0 }}
            </div>
          </div>
          <div class="stat-item">
            <div class="stat-label">
              Queue Position
            </div>
            <div class="stat-value">
              {{ challenge.queue_position || '-' }}
            </div>
          </div>
        </div>

        <!-- Timing Info -->
        <div class="timing-info">
          <div
            v-if="challenge.last_tx_time"
            class="timing-item"
          >
            <el-icon><Clock /></el-icon>
            <span>Last TX: {{ formatTimestamp(challenge.last_tx_time) }}</span>
          </div>
          <div
            v-if="challenge.last_recording_at"
            class="timing-item"
          >
            <el-icon><Camera /></el-icon>
            <span>Last Recording: {{ formatTimestamp(challenge.last_recording_at) }}</span>
          </div>
          <div
            v-if="challenge.next_available_time"
            class="timing-item"
          >
            <el-icon><Timer /></el-icon>
            <span>Next Available: {{ formatTimestamp(challenge.next_available_time) }}</span>
          </div>
        </div>

        <!-- Recording Priority Badge -->
        <div
          v-if="challenge.enabled"
          class="recording-priority"
        >
          <el-tag
            :type="challenge.will_be_recorded ? 'success' : 'info'"
            effect="light"
            size="small"
          >
            Recording Priority: {{ (challenge.recording_priority || 0).toFixed(2) }}
            {{ challenge.will_be_recorded ? ' (Will Record)' : ' (Won\'t Record)' }}
          </el-tag>
        </div>

        <!-- Recordings Section -->
        <div class="recordings-section">
          <div class="section-header">
            <span class="section-title">Recordings</span>
            <el-badge
              :value="challenge.recording_count || 0"
              :max="99"
            />
          </div>
          <RecordingGallery
            :recordings="recordings"
            :placeholders="placeholders"
            :max-recordings="6"
          />
          <div
            v-if="challenge.recording_count > 6"
            class="view-all-link"
          >
            <router-link :to="`/recordings/${challenge.challenge_id}`">
              View All {{ challenge.recording_count }} Recordings →
            </router-link>
          </div>
        </div>

        <!-- Actions Section -->
        <div class="actions-section">
          <el-button
            type="primary"
            size="small"
            :icon="Promotion"
            :disabled="!challenge.enabled || systemPaused"
            @click.stop="handleTrigger"
          >
            Trigger Now
          </el-button>
          <el-button
            type="default"
            size="small"
            :icon="Edit"
            @click.stop="handleEdit"
          >
            Edit
          </el-button>
          <el-button
            type="danger"
            size="small"
            :icon="Delete"
            @click.stop="handleDelete"
          >
            Delete
          </el-button>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import {
  ArrowDown,
  ArrowRight,
  Operation,
  Promotion,
  Clock,
  Camera,
  Timer,
  Edit,
  Delete
} from '@element-plus/icons-vue'
import RecordingGallery from './RecordingGallery.vue'
import { formatDateTime } from '../utils/time.js'

const props = defineProps({
  challenge: {
    type: Object,
    required: true
  },
  recordings: {
    type: Array,
    default: () => []
  },
  placeholders: {
    type: Array,
    default: () => []
  },
  systemPaused: {
    type: Boolean,
    default: false
  },
  showToggle: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['toggle-enabled', 'trigger', 'edit', 'delete'])

const isExpanded = ref(false)

// Computed property for enabled state to avoid prop mutation
const challengeEnabled = computed({
  get: () => props.challenge.enabled,
  set: (value) => {
    emit('toggle-enabled', props.challenge.challenge_id, value)
  }
})

function toggleExpand() {
  isExpanded.value = !isExpanded.value
}

function handleTrigger() {
  emit('trigger', props.challenge.challenge_id)
}

function handleEdit() {
  emit('edit', props.challenge)
}

function handleDelete() {
  emit('delete', props.challenge.challenge_id)
}

function getStatusTagType(status) {
  const statusMap = {
    'assigned': 'warning',
    'waiting': 'info',
    'queued': 'success',
    'failed': 'danger'
  }
  return statusMap[status] || 'info'
}

function formatFrequency(hz) {
  if (!hz) return 'Unknown'
  const mhz = hz / 1e6
  return `${mhz.toFixed(3)} MHz`
}

function formatTimestamp(timestamp) {
  if (!timestamp) return 'Unknown'
  return formatDateTime(timestamp)
}
</script>

<style scoped>
.challenge-card {
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  background: var(--el-bg-color);
  margin-bottom: 12px;
  overflow: hidden;
  transition: all 0.3s ease;
}

.challenge-card.expanded {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.challenge-card.disabled {
  opacity: 0.7;
  background: var(--el-fill-color-lighter);
}

.card-header {
  padding: 16px;
  cursor: pointer;
  user-select: none;
  transition: background-color 0.2s;
}

.card-header:hover {
  background-color: var(--el-fill-color-light);
}

.header-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.challenge-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.expand-icon {
  transition: transform 0.3s ease;
  flex-shrink: 0;
}

.status-badges {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-details {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.detail-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.card-content {
  border-top: 1px solid var(--el-border-color-lighter);
  padding: 16px;
  background-color: var(--el-fill-color-blank);
}

.stats-section {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.stat-item {
  text-align: center;
  padding: 12px;
  background: var(--el-bg-color);
  border-radius: 6px;
  border: 1px solid var(--el-border-color-lighter);
}

.stat-label {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
  text-transform: uppercase;
}

.stat-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.timing-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
}

.timing-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.recording-priority {
  margin-bottom: 16px;
}

.recordings-section {
  margin-bottom: 16px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.view-all-link {
  margin-top: 12px;
  text-align: center;
  padding: 8px;
}

.view-all-link a {
  color: var(--el-color-primary);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  transition: color 0.2s;
}

.view-all-link a:hover {
  color: var(--el-color-primary-light-3);
  text-decoration: underline;
}

.actions-section {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.actions-section .el-button {
  flex: 1;
  min-width: 100px;
}

/* Expand/collapse animation */
.expand-enter-active,
.expand-leave-active {
  transition: all 0.3s ease;
  max-height: 2000px;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  max-height: 0;
  opacity: 0;
  padding-top: 0;
  padding-bottom: 0;
}

/* Mobile optimizations */
@media (max-width: 768px) {
  .card-header {
    padding: 12px;
  }

  .challenge-name {
    font-size: 15px;
  }

  .header-details {
    gap: 12px;
  }

  .detail-item {
    font-size: 12px;
  }

  .stats-section {
    grid-template-columns: repeat(2, 1fr);
  }

  .actions-section {
    flex-direction: column;
  }

  .actions-section .el-button {
    width: 100%;
  }
}
</style>
