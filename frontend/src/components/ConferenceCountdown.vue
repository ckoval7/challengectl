<template>
  <div class="conference-countdown">
    <span v-if="loading">Loading...</span>
    <span v-else-if="error">{{ error }}</span>
    <span v-else-if="hasEnded" class="ended">{{ conferenceName }} RFCTF has ended</span>
    <span v-else class="countdown">
      {{ countdownLabel }}: {{ formattedCountdown }}
      <span v-if="showEndOfDay" class="end-of-day"> | Day ends: {{ endOfDayCountdown }}</span>
    </span>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import axios from 'axios'

const loading = ref(true)
const error = ref(null)
const conferenceName = ref('Conference')
const conferenceStart = ref(null)
const conferenceStop = ref(null)
const endOfDay = ref(null)
const currentTime = ref(new Date())
let intervalId = null

// Parse datetime string with timezone
function parseDateTime(dateStr) {
  if (!dateStr) return null

  // Format: "2063-04-05 09:00:00 -5"
  const parts = dateStr.match(/^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})\s+([+-]\d+)$/)
  if (!parts) return null

  const [, year, month, day, hour, minute, second, tzOffset] = parts
  const offsetHours = parseInt(tzOffset)

  // Create date in UTC then adjust for timezone
  const date = new Date(Date.UTC(
    parseInt(year),
    parseInt(month) - 1,
    parseInt(day),
    parseInt(hour),
    parseInt(minute),
    parseInt(second)
  ))

  // Adjust for timezone offset (offset is in hours, convert to milliseconds)
  date.setTime(date.getTime() - (offsetHours * 60 * 60 * 1000))

  return date
}

// Format time difference as countdown string
function formatCountdown(milliseconds) {
  const totalSeconds = Math.floor(milliseconds / 1000)

  const days = Math.floor(totalSeconds / 86400)
  const hours = Math.floor((totalSeconds % 86400) / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60

  const parts = []
  if (days > 0) parts.push(`${days}d`)
  if (hours > 0 || days > 0) parts.push(`${hours}h`)
  if (minutes > 0 || hours > 0 || days > 0) parts.push(`${minutes}m`)
  parts.push(`${seconds}s`)

  return parts.join(' ')
}

// Calculate end of day time for today
function getEndOfDayTime() {
  if (!endOfDay.value) return null

  const [hours, minutes] = endOfDay.value.split(':').map(Number)
  const now = new Date()
  const eod = new Date(now)
  eod.setHours(hours, minutes, 0, 0)

  // If end of day has passed, use tomorrow
  if (eod <= now) {
    eod.setDate(eod.getDate() + 1)
  }

  return eod
}

// Computed properties
const hasEnded = computed(() => {
  if (!conferenceStop.value) return false
  return currentTime.value >= conferenceStop.value
})

const beforeStart = computed(() => {
  if (!conferenceStart.value) return false
  return currentTime.value < conferenceStart.value
})

const countdownLabel = computed(() => {
  if (beforeStart.value) return 'Starts in'
  return 'Ends in'
})

const formattedCountdown = computed(() => {
  if (hasEnded.value) return ''

  const targetTime = beforeStart.value ? conferenceStart.value : conferenceStop.value
  if (!targetTime) return 'Unknown'

  const diff = targetTime - currentTime.value
  if (diff < 0) return '0s'

  return formatCountdown(diff)
})

const showEndOfDay = computed(() => {
  // Only show end of day timer during the conference
  return !beforeStart.value && !hasEnded.value && endOfDay.value
})

const endOfDayCountdown = computed(() => {
  const eodTime = getEndOfDayTime()
  if (!eodTime) return ''

  const diff = eodTime - currentTime.value
  if (diff < 0) return '0s'

  return formatCountdown(diff)
})

// Lifecycle hooks
onMounted(async () => {
  try {
    const response = await axios.get('/api/conference')
    conferenceName.value = response.data.name || 'Conference'
    conferenceStart.value = parseDateTime(response.data.start)
    conferenceStop.value = parseDateTime(response.data.stop)
    endOfDay.value = response.data.end_of_day

    loading.value = false

    // Update every second
    intervalId = setInterval(() => {
      currentTime.value = new Date()
    }, 1000)
  } catch (err) {
    console.error('Error loading conference info:', err)
    error.value = 'Failed to load conference info'
    loading.value = false
  }
})

onUnmounted(() => {
  if (intervalId) {
    clearInterval(intervalId)
  }
})
</script>

<style scoped>
.conference-countdown {
  font-size: 0.9em;
  white-space: nowrap;
}

.countdown {
  font-weight: 500;
}

.ended {
  color: #f56c6c;
  font-weight: 600;
}

.end-of-day {
  opacity: 0.8;
  font-size: 0.9em;
}
</style>
