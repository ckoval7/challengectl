<template>
  <div class="runners">
    <h1>Runners</h1>

    <el-table :data="runners" style="width: 100%">
      <el-table-column prop="runner_id" label="Runner ID" width="180" />
      <el-table-column prop="hostname" label="Hostname" width="200" />
      <el-table-column prop="ip_address" label="IP Address" width="150" />
      <el-table-column label="Status" width="100">
        <template #default="scope">
          <el-tag
            :type="scope.row.status === 'online' ? 'success' : 'info'"
            size="small"
          >
            {{ scope.row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="Devices" width="100">
        <template #default="scope">
          {{ scope.row.devices?.length || 0 }}
        </template>
      </el-table-column>
      <el-table-column label="Last Heartbeat" width="180">
        <template #default="scope">
          {{ formatTimestamp(scope.row.last_heartbeat) }}
        </template>
      </el-table-column>
      <el-table-column label="Actions" width="150">
        <template #default="scope">
          <el-button
            size="small"
            type="danger"
            @click="kickRunner(scope.row.runner_id)"
          >
            Kick
          </el-button>
        </template>
      </el-table-column>
      <el-table-column type="expand">
        <template #default="scope">
          <div style="padding: 20px">
            <h4>Devices:</h4>
            <el-table :data="scope.row.devices || []" style="width: 100%">
              <el-table-column prop="device_id" label="ID" width="80" />
              <el-table-column prop="model" label="Model" width="150" />
              <el-table-column prop="name" label="Name/Serial" />
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
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { api } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

export default {
  name: 'Runners',
  setup() {
    const runners = ref([])

    const loadRunners = async () => {
      try {
        const response = await api.get('/runners')
        runners.value = response.data.runners || []
      } catch (error) {
        console.error('Error loading runners:', error)
        ElMessage.error('Failed to load runners')
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

    const formatTimestamp = (timestamp) => {
      if (!timestamp) return 'Never'
      const date = new Date(timestamp)
      return date.toLocaleString()
    }

    onMounted(() => {
      loadRunners()

      // Refresh periodically
      const interval = setInterval(loadRunners, 10000)
      onUnmounted(() => clearInterval(interval))
    })

    return {
      runners,
      kickRunner,
      formatTimestamp
    }
  }
}
</script>

<style scoped>
.runners {
  padding: 20px;
}
</style>
