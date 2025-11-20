<template>
  <div class="not-found">
    <div class="content">
      <div class="error-code">404</div>
      <div class="signal-icon">
        <el-icon :size="80">
          <Connection />
        </el-icon>
      </div>
      <h1>{{ randomMessage }}</h1>
      <p class="subtitle">The page you're looking for doesn't exist.</p>
      <div class="actions">
        <el-button
          type="primary"
          @click="goHome"
        >
          Return Home
        </el-button>
        <el-button @click="goBack">
          Go Back
        </el-button>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Connection } from '@element-plus/icons-vue'

export default {
  name: 'NotFound',
  components: {
    Connection
  },
  setup() {
    const router = useRouter()
    const randomMessage = ref('')

    const messages = [
      "We scanned the air waves, but haven't received your signal",
      "No transmission detected on this frequency",
      "Signal lost: unable to establish connection",
      "This wavelength appears to be empty",
      "Frequency scan complete: no data found",
      "We've tuned all bands, but this channel is silent",
      "RF sweep shows no activity at this location"
    ]

    const getRandomMessage = () => {
      const randomIndex = Math.floor(Math.random() * messages.length)
      return messages[randomIndex]
    }

    onMounted(() => {
      randomMessage.value = getRandomMessage()
    })

    const goHome = () => {
      router.push('/')
    }

    const goBack = () => {
      router.back()
    }

    return {
      randomMessage,
      goHome,
      goBack,
      Connection
    }
  }
}
</script>

<style scoped>
.not-found {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 20px;
  background: var(--el-bg-color);
}

.content {
  text-align: center;
  max-width: 600px;
}

.error-code {
  font-size: 120px;
  font-weight: bold;
  color: var(--el-color-primary);
  line-height: 1;
  margin-bottom: 20px;
  text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.1);
}

.signal-icon {
  margin-bottom: 30px;
  color: var(--el-text-color-secondary);
  opacity: 0.7;
}

h1 {
  font-size: 1.8em;
  color: var(--el-text-color-primary);
  margin: 0 0 15px 0;
  font-weight: 600;
}

.subtitle {
  font-size: 1.1em;
  color: var(--el-text-color-regular);
  margin: 0 0 40px 0;
}

.actions {
  display: flex;
  gap: 15px;
  justify-content: center;
  flex-wrap: wrap;
}

/* Animation for the signal icon */
.signal-icon {
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 0.7;
  }
  50% {
    opacity: 0.3;
  }
}

/* Mobile responsiveness */
@media (max-width: 768px) {
  .error-code {
    font-size: 80px;
  }

  h1 {
    font-size: 1.4em;
  }

  .subtitle {
    font-size: 1em;
  }

  .actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
