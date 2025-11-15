<template>
  <div id="app">
    <el-container style="height: 100vh">
      <el-header height="60px" style="background: #409EFF; color: white; display: flex; align-items: center; padding: 0 20px;">
        <h2 style="margin: 0">ChallengeCtl Control Center</h2>
        <div style="flex: 1"></div>
        <el-button
          v-if="systemPaused"
          type="success"
          @click="resumeSystem"
          style="margin-right: 10px"
        >
          Resume
        </el-button>
        <el-button
          v-else
          type="warning"
          @click="pauseSystem"
          style="margin-right: 10px"
        >
          Pause
        </el-button>
        <el-button
          type="danger"
          @click="emergencyStop"
        >
          Emergency Stop
        </el-button>
      </el-header>

      <el-container>
        <el-aside width="200px" style="background: #f5f7fa; padding: 20px;">
          <el-menu
            :default-active="$route.path"
            router
            style="border: none; background: transparent"
          >
            <el-menu-item index="/">
              <el-icon><Monitor /></el-icon>
              <span>Dashboard</span>
            </el-menu-item>
            <el-menu-item index="/runners">
              <el-icon><Connection /></el-icon>
              <span>Runners</span>
            </el-menu-item>
            <el-menu-item index="/challenges">
              <el-icon><Document /></el-icon>
              <span>Challenges</span>
            </el-menu-item>
            <el-menu-item index="/logs">
              <el-icon><Notebook /></el-icon>
              <span>Logs</span>
            </el-menu-item>
          </el-menu>
        </el-aside>

        <el-main>
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script>
import { ref } from 'vue'
import { Monitor, Connection, Document, Notebook } from '@element-plus/icons-vue'
import { api } from './api'
import { ElMessage, ElMessageBox } from 'element-plus'

export default {
  name: 'App',
  components: {
    Monitor,
    Connection,
    Document,
    Notebook
  },
  setup() {
    const systemPaused = ref(false)

    const pauseSystem = async () => {
      try {
        await api.post('/api/control/pause')
        systemPaused.value = true
        ElMessage.success('System paused')
      } catch (error) {
        ElMessage.error('Failed to pause system')
      }
    }

    const resumeSystem = async () => {
      try {
        await api.post('/api/control/resume')
        systemPaused.value = false
        ElMessage.success('System resumed')
      } catch (error) {
        ElMessage.error('Failed to resume system')
      }
    }

    const emergencyStop = async () => {
      try {
        await ElMessageBox.confirm(
          'This will stop all transmissions immediately. Continue?',
          'Emergency Stop',
          {
            confirmButtonText: 'Stop All',
            cancelButtonText: 'Cancel',
            type: 'error'
          }
        )

        await api.post('/api/control/emergency-stop')
        systemPaused.value = true
        ElMessage.success('Emergency stop activated')
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error('Emergency stop failed')
        }
      }
    }

    return {
      systemPaused,
      pauseSystem,
      resumeSystem,
      emergencyStop
    }
  }
}
</script>

<style>
body {
  margin: 0;
  padding: 0;
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
}

#app {
  height: 100vh;
}
</style>
