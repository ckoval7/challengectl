<template>
  <div class="webhooks-container">
    <div class="header">
      <h1>Webhook Management</h1>
      <el-button
        type="primary"
        @click="openCreateDialog"
      >
        <el-icon><Plus /></el-icon>
        Create Webhook
      </el-button>
    </div>

    <el-table
      v-loading="loading"
      :data="webhooks"
      class="w-full"
    >
      <el-table-column
        prop="name"
        label="Name"
        width="200"
      />
      <el-table-column
        prop="url"
        label="Discord Webhook URL"
        width="250"
      >
        <template #default="scope">
          <span class="url-preview">{{ truncateUrl(scope.row.url) }}</span>
        </template>
      </el-table-column>
      <el-table-column
        label="Status"
        width="100"
      >
        <template #default="scope">
          <el-tag :type="scope.row.enabled ? 'success' : 'info'">
            {{ scope.row.enabled ? 'Enabled' : 'Disabled' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        label="Events"
        width="150"
      >
        <template #default="scope">
          <el-tooltip
            :content="formatEventList(scope.row.subscribed_events)"
            placement="top"
          >
            <el-tag size="small">
              {{ scope.row.subscribed_events.length }} categories
            </el-tag>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column
        label="Deliveries"
        width="140"
      >
        <template #default="scope">
          <div class="delivery-stats">
            <el-tag type="success" size="small">
              {{ scope.row.total_deliveries || 0 }} total
            </el-tag>
            <el-tag
              v-if="scope.row.failed_deliveries > 0"
              type="danger"
              size="small"
              class="mt-5"
            >
              {{ scope.row.failed_deliveries }} failed
            </el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column
        prop="last_triggered_at"
        label="Last Triggered"
        width="180"
      >
        <template #default="scope">
          {{ scope.row.last_triggered_at || 'Never' }}
        </template>
      </el-table-column>
      <el-table-column
        label="Actions"
        width="180"
        align="center"
      >
        <template #default="scope">
          <el-button
            size="small"
            @click="testWebhook(scope.row)"
          >
            Test
          </el-button>
          <el-button
            size="small"
            @click="editWebhook(scope.row)"
          >
            Edit
          </el-button>
          <el-button
            size="small"
            type="danger"
            @click="confirmDelete(scope.row)"
          >
            Delete
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Create/Edit Webhook Dialog -->
    <el-dialog
      v-model="showDialog"
      :title="editMode ? 'Edit Webhook' : 'Create Webhook'"
      width="600px"
    >
      <el-form
        ref="webhookFormRef"
        :model="webhookForm"
        :rules="formRules"
        label-width="150px"
      >
        <el-form-item
          label="Name"
          prop="name"
        >
          <el-input
            v-model="webhookForm.name"
            placeholder="Production Discord"
            maxlength="100"
            show-word-limit
          />
        </el-form-item>

        <el-form-item
          label="Discord Webhook URL"
          prop="url"
        >
          <el-input
            v-model="webhookForm.url"
            type="textarea"
            :rows="2"
            placeholder="https://discord.com/api/webhooks/123456/abcdef..."
          />
          <div class="form-hint">
            Get this URL from Discord: Server Settings → Integrations → Webhooks
          </div>
        </el-form-item>

        <el-form-item label="Enabled">
          <el-switch v-model="webhookForm.enabled" />
        </el-form-item>

        <el-form-item
          label="Subscribe to Events"
          prop="subscribed_events"
        >
          <div
            v-loading="loadingCategories"
            class="event-categories"
          >
            <div
              v-for="category in eventCategories"
              :key="category.name"
              class="event-category"
            >
              <el-checkbox
                v-model="webhookForm.subscribed_events"
                :label="category.name"
              >
                <strong>{{ formatCategoryName(category.name) }}</strong>
                <br>
                <span class="category-description">{{ category.description }}</span>
              </el-checkbox>
            </div>
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showDialog = false">
          Cancel
        </el-button>
        <el-button
          type="primary"
          :loading="saving"
          @click="saveWebhook"
        >
          {{ editMode ? 'Update' : 'Create' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { api } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

export default {
  name: 'Webhooks',
  components: {
    Plus
  },
  setup() {
    const webhooks = ref([])
    const loading = ref(false)
    const showDialog = ref(false)
    const editMode = ref(false)
    const saving = ref(false)
    const loadingCategories = ref(false)
    const webhookFormRef = ref(null)
    const eventCategories = ref([])

    const webhookForm = ref({
      webhook_id: null,
      name: '',
      url: '',
      enabled: true,
      subscribed_events: []
    })

    const formRules = {
      name: [
        { required: true, message: 'Please enter webhook name', trigger: 'blur' },
        { max: 100, message: 'Name must be 100 characters or less', trigger: 'blur' }
      ],
      url: [
        { required: true, message: 'Please enter webhook URL', trigger: 'blur' },
        {
          pattern: /^https:\/\/discord\.com\/api\/webhooks\/\d+\/[\w-]+$/,
          message: 'Invalid Discord webhook URL format',
          trigger: 'blur'
        }
      ],
      subscribed_events: [
        {
          type: 'array',
          required: true,
          message: 'Please select at least one event category',
          trigger: 'change'
        }
      ]
    }

    const loadWebhooks = async () => {
      loading.value = true
      try {
        const response = await api.get('/webhooks')
        webhooks.value = response.data.webhooks
      } catch (error) {
        ElMessage.error('Failed to load webhooks')
      } finally {
        loading.value = false
      }
    }

    const loadEventCategories = async () => {
      loadingCategories.value = true
      try {
        const response = await api.get('/webhooks/event-categories')
        eventCategories.value = response.data.categories
      } catch (error) {
        ElMessage.error('Failed to load event categories')
      } finally {
        loadingCategories.value = false
      }
    }

    const openCreateDialog = () => {
      editMode.value = false
      webhookForm.value = {
        webhook_id: null,
        name: '',
        url: '',
        enabled: true,
        subscribed_events: []
      }
      showDialog.value = true
    }

    const editWebhook = (webhook) => {
      editMode.value = true
      webhookForm.value = {
        webhook_id: webhook.webhook_id,
        name: webhook.name,
        url: webhook.url,
        enabled: webhook.enabled,
        subscribed_events: [...webhook.subscribed_events]
      }
      showDialog.value = true
    }

    const saveWebhook = async () => {
      if (!webhookFormRef.value) return

      try {
        await webhookFormRef.value.validate()
      } catch {
        return
      }

      saving.value = true

      try {
        const payload = {
          name: webhookForm.value.name,
          url: webhookForm.value.url,
          enabled: webhookForm.value.enabled,
          subscribed_events: webhookForm.value.subscribed_events
        }

        if (editMode.value) {
          await api.put(`/webhooks/${webhookForm.value.webhook_id}`, payload)
          ElMessage.success('Webhook updated successfully')
        } else {
          await api.post('/webhooks', payload)
          ElMessage.success('Webhook created successfully')
        }

        showDialog.value = false
        loadWebhooks()
      } catch (error) {
        const errorMsg = error.response?.data?.error || 'Failed to save webhook'
        ElMessage.error(errorMsg)
      } finally {
        saving.value = false
      }
    }

    const confirmDelete = async (webhook) => {
      try {
        await ElMessageBox.confirm(
          `Are you sure you want to delete webhook "${webhook.name}"?`,
          'Delete Webhook',
          {
            confirmButtonText: 'Delete',
            cancelButtonText: 'Cancel',
            type: 'warning'
          }
        )

        await api.delete(`/webhooks/${webhook.webhook_id}`)
        ElMessage.success('Webhook deleted successfully')
        loadWebhooks()
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error('Failed to delete webhook')
        }
      }
    }

    const testWebhook = async (webhook) => {
      try {
        const response = await api.post(`/webhooks/${webhook.webhook_id}/test`)

        if (response.data.status === 'success') {
          ElMessage.success('Test message sent successfully! Check your Discord channel.')
        } else {
          ElMessage.error(`Test failed: ${response.data.error}`)
        }
      } catch (error) {
        ElMessage.error('Failed to send test message')
      }
    }

    const truncateUrl = (url) => {
      if (url.length > 40) {
        return url.substring(0, 37) + '...'
      }
      return url
    }

    const formatCategoryName = (name) => {
      return name.split('_').map(word =>
        word.charAt(0).toUpperCase() + word.slice(1)
      ).join(' ')
    }

    const formatEventList = (events) => {
      return events.map(e => formatCategoryName(e)).join(', ')
    }

    onMounted(() => {
      loadWebhooks()
      loadEventCategories()
    })

    return {
      webhooks,
      loading,
      showDialog,
      editMode,
      saving,
      loadingCategories,
      webhookFormRef,
      webhookForm,
      eventCategories,
      formRules,
      openCreateDialog,
      loadWebhooks,
      editWebhook,
      saveWebhook,
      confirmDelete,
      testWebhook,
      truncateUrl,
      formatCategoryName,
      formatEventList
    }
  }
}
</script>

<style scoped>
.webhooks-container {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header h1 {
  margin: 0;
}

.url-preview {
  font-family: monospace;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.delivery-stats {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.event-categories {
  max-height: 400px;
  overflow-y: auto;
}

.event-category {
  margin-bottom: 15px;
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
}

.category-description {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-left: 24px;
}

.form-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 5px;
}

.mt-5 {
  margin-top: 5px;
}
</style>
