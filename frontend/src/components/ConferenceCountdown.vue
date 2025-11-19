<template>
  <div class="conference-countdown">
    <span v-if="loading">Loading...</span>
    <span v-else-if="error">{{ error }}</span>
    <span v-else-if="hasEnded" class="ended">{{ conferenceName }} RFCTF has ended</span>
    <span v-else class="countdown">
      {{ countdownLabel }}: {{ formattedCountdown }}
      <span v-if="showDayEndTimer" class="end-of-day"> | Day ends: {{ dayEndCountdown }}</span>
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
const dayStart = ref(null)
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

// Calculate day start time (today or tomorrow)
function getDayStartTime() {
  if (!dayStart.value) return null

  const [hours, minutes] = dayStart.value.split(':').map(Number)
  const now = new Date()
  const start = new Date(now)
  start.setHours(hours, minutes, 0, 0)

  // If day start has passed, use tomorrow
  if (start <= now) {
    start.setDate(start.getDate() + 1)
  }

  return start
}

// Calculate end of day time (today or tomorrow)
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

// Check if current time is outside daily operating hours
function isOutsideDailyHours() {
  if (!dayStart.value || !endOfDay.value) return false

  const now = currentTime.value
  const [startHours, startMinutes] = dayStart.value.split(':').map(Number)
  const [endHours, endMinutes] = endOfDay.value.split(':').map(Number)

  const currentMinutes = now.getHours() * 60 + now.getMinutes()
  const startMinutesOfDay = startHours * 60 + startMinutes
  const endMinutesOfDay = endHours * 60 + endMinutes

  // Handle cases where end_of_day might be before day_start (overnight)
  if (endMinutesOfDay > startMinutesOfDay) {
    // Normal case: day_start=09:00, end_of_day=17:00
    return currentMinutes < startMinutesOfDay || currentMinutes >= endMinutesOfDay
  } else {
    // Overnight case: day_start=22:00, end_of_day=06:00
    return currentMinutes >= endMinutesOfDay && currentMinutes < startMinutesOfDay
  }
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

  // During conference: check if we're outside daily hours
  if (!hasEnded.value && isOutsideDailyHours()) {
    return 'Day starts in'
  }

  return 'Ends in'
})

const formattedCountdown = computed(() => {
  if (hasEnded.value) return ''

  // Before conference starts
  if (beforeStart.value) {
    const diff = conferenceStart.value - currentTime.value
    if (diff < 0) return '0s'
    return formatCountdown(diff)
  }

  // During conference but outside daily hours - countdown to next day start
  if (isOutsideDailyHours()) {
    const nextStart = getDayStartTime()
    if (!nextStart) return 'Unknown'
    const diff = nextStart - currentTime.value
    if (diff < 0) return '0s'
    return formatCountdown(diff)
  }

  // During conference and within daily hours - countdown to conference end
  const diff = conferenceStop.value - currentTime.value
  if (diff < 0) return '0s'
  return formatCountdown(diff)
})

const showDayEndTimer = computed(() => {
  // Only show day end timer during conference, within daily hours, and when end_of_day is set
  return !beforeStart.value && !hasEnded.value && !isOutsideDailyHours() && endOfDay.value
})

const dayEndCountdown = computed(() => {
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
    dayStart.value = response.data.day_start
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
