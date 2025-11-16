<template>
  <div class="challenges">
    <h1>Challenges</h1>

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
            :type="!scope.row.enabled ? 'info' : (scope.row.status === 'queued' ? 'success' : (scope.row.status === 'assigned' ? 'warning' : 'info'))"
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
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'
import { api } from '../api'
import { ElMessage } from 'element-plus'

export default {
  name: 'Challenges',
  setup() {
    const challenges = ref([])

    const loadChallenges = async () => {
      try {
        const response = await api.get('/challenges')
        challenges.value = response.data.challenges || []
      } catch (error) {
        console.error('Error loading challenges:', error)
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

    const formatTimestamp = (timestamp) => {
      if (!timestamp) return 'Never'
      const date = new Date(timestamp)
      return date.toLocaleString()
    }

    const formatFrequency = (hz) => {
      if (!hz) return 'N/A'
      return (hz / 1e6).toFixed(3) + ' MHz'
    }

    onMounted(() => {
      loadChallenges()

      // Refresh periodically
      const interval = setInterval(loadChallenges, 15000)
      onUnmounted(() => clearInterval(interval))
    })

    return {
      challenges,
      reloadChallenges,
      toggleChallenge,
      triggerChallenge,
      formatTimestamp,
      formatFrequency
    }
  }
}
</script>

<style scoped>
.challenges {
  padding: 20px;
}
</style>
