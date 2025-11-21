<template>
  <div class="runners">
    <div class="header">
      <h1>Agents</h1>
    </div>

    <el-tabs
      v-model="activeTab"
      type="border-card"
    >
      <!-- Runners Tab -->
      <el-tab-pane
        label="Runners"
        name="runners"
      >
        <div class="tab-header">
          <el-button
            type="primary"
            @click="showAddRunnerDialog"
          >
            Add Runner
          </el-button>
        </div>

        <el-table
          :data="runners"
          class="w-full"
        >
          <el-table-column
            prop="runner_id"
            label="Runner ID"
            width="180"
          />
          <el-table-column
            prop="hostname"
            label="Hostname"
            width="200"
          />
          <el-table-column
            prop="ip_address"
            label="IP Address"
            width="150"
          />
          <el-table-column
            label="Status"
            width="150"
          >
            <template #default="scope">
              <el-space>
                <el-tag
                  :type="scope.row.status === 'online' ? 'success' : 'info'"
                  size="small"
                >
                  {{ scope.row.status }}
                </el-tag>
                <el-tag
                  v-if="!scope.row.enabled"
                  type="warning"
                  size="small"
                >
                  disabled
                </el-tag>
              </el-space>
            </template>
          </el-table-column>
          <el-table-column
            label="Devices"
            width="100"
          >
            <template #default="scope">
              {{ scope.row.devices?.length || 0 }}
            </template>
          </el-table-column>
          <el-table-column
            label="Last Heartbeat"
            width="180"
          >
            <template #default="scope">
              {{ formatTimestamp(scope.row.last_heartbeat) }}
            </template>
          </el-table-column>
          <el-table-column
            label="Actions"
            width="300"
          >
            <template #default="scope">
              <el-space>
                <el-button
                  v-if="scope.row.enabled"
                  size="small"
                  type="warning"
                  @click="disableRunner(scope.row.runner_id)"
                >
                  Disable
                </el-button>
                <el-button
                  v-else
                  size="small"
                  type="success"
                  @click="enableRunner(scope.row.runner_id)"
                >
                  Enable
                </el-button>
                <el-button
                  size="small"
                  type="primary"
                  @click="showReEnrollDialog(scope.row.runner_id)"
                >
                  Re-enroll
                </el-button>
                <el-button
                  size="small"
                  type="danger"
                  @click="kickRunner(scope.row.runner_id)"
                >
                  Kick
                </el-button>
              </el-space>
            </template>
          </el-table-column>
          <el-table-column type="expand">
            <template #default="scope">
              <div class="p-xl">
                <h4>Devices:</h4>
                <el-table
                  :data="scope.row.devices || []"
                  class="w-full"
                >
                  <el-table-column
                    prop="device_id"
                    label="ID"
                    width="80"
                  />
                  <el-table-column
                    prop="model"
                    label="Model"
                    width="150"
                  />
                  <el-table-column
                    prop="name"
                    label="Name/Serial"
                  />
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

        <!-- Add Runner Dialog -->
        <el-dialog
          v-model="addRunnerDialogVisible"
          title="Add Runner"
          width="800px"
          :close-on-click-modal="false"
        >
          <div v-if="!enrollmentData">
            <!-- Step 1: Enter runner name and configuration -->
            <el-form
              :model="addRunnerForm"
              label-width="150px"
            >
              <el-form-item label="Runner Name">
                <el-input
                  v-model="addRunnerForm.runnerName"
                  placeholder="e.g., sdr-station-1"
                  @keyup.enter="generateEnrollmentToken"
                />
              </el-form-item>
              <el-form-item label="Token Expiry">
                <el-select
                  v-model="addRunnerForm.expiresHours"
                  placeholder="Select expiry time"
                >
                  <el-option
                    label="1 hour"
                    :value="1"
                  />
                  <el-option
                    label="6 hours"
                    :value="6"
                  />
                  <el-option
                    label="24 hours (default)"
                    :value="24"
                  />
                  <el-option
                    label="7 days"
                    :value="168"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="Verify SSL">
                <el-switch
                  v-model="addRunnerForm.verifySsl"
                  active-text="Enabled"
                  inactive-text="Disabled"
                />
                <div class="hint-text">
                  Disable only for development with self-signed certificates
                </div>
              </el-form-item>

              <el-divider content-position="left">
                SDR Device Configuration (Optional)
              </el-divider>

              <div
                v-for="(device, index) in addRunnerForm.devices"
                :key="index"
                class="device-config-item"
              >
                <div class="device-header">
                  <h4>Device {{ index + 1 }}</h4>
                  <el-button
                    v-if="addRunnerForm.devices.length > 1"
                    size="small"
                    type="danger"
                    @click="removeDevice(index)"
                  >
                    Remove
                  </el-button>
                </div>

                <el-form-item label="Device Name">
                  <el-input
                    v-model="device.name"
                    placeholder="e.g., 0, 1, or serial number"
                  />
                  <div class="hint-text">
                    Device index (0, 1, 2) or serial number
                  </div>
                </el-form-item>

                <el-form-item label="Model">
                  <el-select
                    v-model="device.model"
                    placeholder="Select SDR model"
                  >
                    <el-option
                      label="HackRF"
                      value="hackrf"
                    />
                    <el-option
                      label="BladeRF"
                      value="bladerf"
                    />
                    <el-option
                      label="USRP"
                      value="usrp"
                    />
                    <el-option
                      label="LimeSDR"
                      value="limesdr"
                    />
                  </el-select>
                </el-form-item>

                <el-form-item label="RF Gain">
                  <el-input-number
                    v-model="device.rf_gain"
                    :min="0"
                    :max="100"
                  />
                </el-form-item>

                <el-form-item
                  v-if="device.model === 'hackrf'"
                  label="IF Gain"
                >
                  <el-input-number
                    v-model="device.if_gain"
                    :min="0"
                    :max="47"
                  />
                </el-form-item>

                <el-form-item label="Frequency Limits">
                  <el-input
                    v-model="device.frequency_limits"
                    type="textarea"
                    :rows="2"
                    placeholder="e.g., 144000000-148000000, 420000000-450000000"
                  />
                  <div class="hint-text">
                    Comma-separated ranges (optional). Leave blank for full range.
                  </div>
                </el-form-item>

                <el-divider v-if="index < addRunnerForm.devices.length - 1" />
              </div>

              <el-button
                type="primary"
                plain
                class="mt-10 w-full"
                @click="addDevice"
              >
                Add Another Device
              </el-button>
            </el-form>
          </div>

          <div
            v-else
            class="enrollment-data"
          >
            <!-- Step 2: Display complete configuration -->
            <el-alert
              title="Important: Save this configuration now!"
              type="warning"
              description="The enrollment token and API key will only be shown once. Download or copy the complete configuration below."
              :closable="false"
              show-icon
              class="mb-xl"
            />

            <div class="mb-15">
              <el-space>
                <el-button
                  type="primary"
                  @click="copyToClipboard(generatedConfig, 'Configuration')"
                >
                  Copy Full Config
                </el-button>
                <el-button
                  type="success"
                  @click="downloadConfig"
                >
                  Download runner-config.yml
                </el-button>
              </el-space>
            </div>

            <div class="config-display">
              <h4>Complete Runner Configuration:</h4>
              <pre class="config-content">{{ generatedConfig }}</pre>
            </div>

            <el-divider />

            <div class="setup-instructions">
              <h4>Setup Instructions:</h4>
              <ol>
                <li>Download or copy the complete configuration above</li>
                <li>On your runner machine, save as <code>runner-config.yml</code></li>
                <li>Customize the <code>radios</code> section for your SDR devices</li>
                <li>Start the runner with: <code>python -m challengectl.runner.runner</code></li>
                <li>After successful enrollment, remove the <code>enrollment_token</code> line from the config</li>
              </ol>
            </div>

            <el-divider />

            <div class="credential-block">
              <h4>Token Expires:</h4>
              <div class="credential-value">
                <code>{{ formatTimestamp(enrollmentData.expires_at) }}</code>
              </div>
            </div>
          </div>

          <template #footer>
            <span class="dialog-footer">
              <el-button
                v-if="!enrollmentData"
                @click="addRunnerDialogVisible = false"
              >
                Cancel
              </el-button>
              <el-button
                v-if="!enrollmentData"
                type="primary"
                :disabled="!addRunnerForm.runnerName"
                @click="generateEnrollmentToken"
              >
                Generate Token
              </el-button>
              <el-button
                v-else
                type="primary"
                @click="closeAddRunnerDialog"
              >
                Done
              </el-button>
            </span>
          </template>
        </el-dialog>

        <!-- Re-enroll Runner Dialog -->
        <el-dialog
          v-model="reEnrollDialogVisible"
          title="Re-enroll Runner"
          width="800px"
          :close-on-click-modal="false"
        >
          <div v-if="!reEnrollData">
            <el-alert
              title="Re-enrollment Process"
              type="info"
              description="Generate fresh credentials to migrate this runner to a different host or update compromised credentials."
              :closable="false"
              show-icon
              class="mb-xl"
            />
            <p><strong>Runner ID:</strong> {{ reEnrollRunnerId }}</p>
            <p>This will generate new enrollment credentials. The old API key will remain valid until the runner re-enrolls with the new credentials.</p>
          </div>

          <div
            v-else
            class="enrollment-data"
          >
            <el-alert
              title="Important: Save this configuration now!"
              type="warning"
              description="The enrollment token and API key will only be shown once. Download or copy the complete configuration below."
              :closable="false"
              show-icon
              class="mb-xl"
            />

            <div class="mb-15">
              <el-space>
                <el-button
                  type="primary"
                  @click="copyToClipboard(reEnrollGeneratedConfig, 'Configuration')"
                >
                  Copy Full Config
                </el-button>
                <el-button
                  type="success"
                  @click="downloadReEnrollConfig"
                >
                  Download runner-config.yml
                </el-button>
              </el-space>
            </div>

            <div class="config-display">
              <h4>Complete Runner Configuration:</h4>
              <pre class="config-content">{{ reEnrollGeneratedConfig }}</pre>
            </div>

            <el-divider />

            <div class="setup-instructions">
              <h4>Re-enrollment Instructions:</h4>
              <ol>
                <li>Download or copy the complete configuration above</li>
                <li>On the NEW runner machine, save as <code>runner-config.yml</code></li>
                <li>Customize the <code>radios</code> section for your SDR devices</li>
                <li>Start the runner with: <code>python -m challengectl.runner.runner</code></li>
                <li>After successful re-enrollment, remove the <code>enrollment_token</code> line from the config</li>
                <li>The old runner will be automatically kicked once the new one connects</li>
              </ol>
            </div>

            <el-divider />

            <div class="credential-block">
              <h4>Token Expires:</h4>
              <div class="credential-value">
                <code>{{ formatTimestamp(reEnrollData.expires_at) }}</code>
              </div>
            </div>
          </div>

          <template #footer>
            <span class="dialog-footer">
              <el-button
                v-if="!reEnrollData"
                @click="reEnrollDialogVisible = false"
              >
                Cancel
              </el-button>
              <el-button
                v-if="!reEnrollData"
                type="primary"
                @click="generateReEnrollToken"
              >
                Generate Credentials
              </el-button>
              <el-button
                v-else
                type="primary"
                @click="closeReEnrollDialog"
              >
                Done
              </el-button>
            </span>
          </template>
        </el-dialog>
      </el-tab-pane>

      <!-- Listeners Tab -->
      <el-tab-pane
        label="Listeners"
        name="listeners"
      >
        <div class="tab-header">
          <el-button
            type="primary"
            @click="showAddListenerDialog"
          >
            Add Listener
          </el-button>
          <p class="info-text">
            Listener agents capture RF spectrum and generate waterfall images when transmissions occur.
            They connect via WebSocket for real-time coordination.
          </p>
        </div>

        <el-table
          :data="listeners"
          class="w-full"
        >
          <el-table-column
            prop="agent_id"
            label="Listener ID"
            width="180"
          />
          <el-table-column
            prop="hostname"
            label="Hostname"
            width="200"
          />
          <el-table-column
            prop="ip_address"
            label="IP Address"
            width="150"
          />
          <el-table-column
            label="Status"
            width="150"
          >
            <template #default="scope">
              <el-space>
                <el-tag
                  :type="scope.row.status === 'online' ? 'success' : 'info'"
                  size="small"
                >
                  {{ scope.row.status }}
                </el-tag>
                <el-tag
                  v-if="!scope.row.enabled"
                  type="warning"
                  size="small"
                >
                  disabled
                </el-tag>
              </el-space>
            </template>
          </el-table-column>
          <el-table-column
            label="WebSocket"
            width="150"
          >
            <template #default="scope">
              <el-tag
                :type="scope.row.websocket_connected ? 'success' : 'warning'"
                size="small"
              >
                {{ scope.row.websocket_connected ? 'Connected' : 'Disconnected' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            label="Devices"
            width="100"
          >
            <template #default="scope">
              {{ scope.row.devices?.length || 0 }}
            </template>
          </el-table-column>
          <el-table-column
            label="Last Heartbeat"
            width="180"
          >
            <template #default="scope">
              {{ formatTimestamp(scope.row.last_heartbeat) }}
            </template>
          </el-table-column>
          <el-table-column
            label="Actions"
            width="250"
          >
            <template #default="scope">
              <el-space>
                <el-button
                  v-if="scope.row.enabled"
                  size="small"
                  type="warning"
                  @click="disableListener(scope.row.agent_id)"
                >
                  Disable
                </el-button>
                <el-button
                  v-else
                  size="small"
                  type="success"
                  @click="enableListener(scope.row.agent_id)"
                >
                  Enable
                </el-button>
                <el-button
                  size="small"
                  type="danger"
                  @click="kickListener(scope.row.agent_id)"
                >
                  Kick
                </el-button>
              </el-space>
            </template>
          </el-table-column>
        </el-table>

        <div
          v-if="listeners.length === 0"
          class="empty-state"
        >
          <p>No listener agents registered.</p>
          <p>Deploy listener agents with SDR hardware to capture spectrum recordings.</p>
          <p>See <code>listener/README.md</code> for setup instructions.</p>
        </div>

        <!-- Add Listener Dialog -->
        <el-dialog
          v-model="addListenerDialogVisible"
          title="Add Listener"
          width="700px"
          :close-on-click-modal="false"
        >
          <div v-if="!listenerEnrollmentData">
            <!-- Step 1: Enter listener name and configuration -->
            <el-form
              :model="addListenerForm"
              label-width="150px"
            >
              <el-form-item label="Listener Name">
                <el-input
                  v-model="addListenerForm.listenerName"
                  placeholder="e.g., listener-1"
                  @keyup.enter="generateListenerEnrollmentToken"
                />
              </el-form-item>
              <el-form-item label="Token Expiry">
                <el-select
                  v-model="addListenerForm.expiresHours"
                  placeholder="Select expiry time"
                >
                  <el-option
                    label="1 hour"
                    :value="1"
                  />
                  <el-option
                    label="6 hours"
                    :value="6"
                  />
                  <el-option
                    label="24 hours (default)"
                    :value="24"
                  />
                  <el-option
                    label="7 days"
                    :value="168"
                  />
                </el-select>
              </el-form-item>

              <el-divider content-position="left">
                SDR Device Configuration (Optional)
              </el-divider>

              <el-form-item label="Device Type">
                <el-select
                  v-model="addListenerForm.deviceType"
                  placeholder="Select SDR model"
                >
                  <el-option
                    label="RTL-SDR"
                    value="rtlsdr"
                  />
                  <el-option
                    label="HackRF"
                    value="hackrf"
                  />
                  <el-option
                    label="USRP"
                    value="usrp"
                  />
                  <el-option
                    label="BladeRF"
                    value="bladerf"
                  />
                </el-select>
                <div class="hint-text">
                  Type of SDR receiver hardware
                </div>
              </el-form-item>

              <el-form-item label="Device ID">
                <el-input
                  v-model="addListenerForm.deviceId"
                  placeholder="e.g., rtlsdr=0, hackrf=0"
                />
                <div class="hint-text">
                  osmosdr device string (e.g., rtlsdr=0, hackrf=0, uhd=0)
                </div>
              </el-form-item>
            </el-form>

            <div class="dialog-footer">
              <el-button @click="addListenerDialogVisible = false">
                Cancel
              </el-button>
              <el-button
                type="primary"
                @click="generateListenerEnrollmentToken"
                :disabled="!addListenerForm.listenerName"
              >
                Generate Token
              </el-button>
            </div>
          </div>

          <div v-else>
            <!-- Step 2: Show enrollment credentials -->
            <el-alert
              title="Listener Enrollment Created"
              type="success"
              :closable="false"
              show-icon
            >
              <p>
                Copy the API key and enrollment token below. They will only be shown once!
              </p>
            </el-alert>

            <div class="credentials-section">
              <h3>Enrollment Credentials</h3>

              <el-form label-width="150px">
                <el-form-item label="Listener Name">
                  <el-input
                    :model-value="listenerEnrollmentData.listener_name"
                    readonly
                  />
                </el-form-item>

                <el-form-item label="API Key">
                  <el-input
                    :model-value="listenerEnrollmentData.api_key"
                    readonly
                    type="textarea"
                    :rows="2"
                  >
                    <template #append>
                      <el-button @click="copyToClipboard(listenerEnrollmentData.api_key)">
                        Copy
                      </el-button>
                    </template>
                  </el-input>
                </el-form-item>

                <el-form-item label="Enrollment Token">
                  <el-input
                    :model-value="listenerEnrollmentData.enrollment_token"
                    readonly
                    type="textarea"
                    :rows="2"
                  >
                    <template #append>
                      <el-button @click="copyToClipboard(listenerEnrollmentData.enrollment_token)">
                        Copy
                      </el-button>
                    </template>
                  </el-input>
                </el-form-item>

                <el-form-item label="Expires">
                  <el-input
                    :model-value="formatTimestamp(listenerEnrollmentData.expires_at)"
                    readonly
                  />
                </el-form-item>
              </el-form>

              <el-divider />

              <h3>Listener Configuration File</h3>
              <p class="hint-text">
                Copy this complete configuration to <code>listener-config.yml</code> on your listener machine:
              </p>

              <el-input
                :model-value="listenerEnrollmentData.config_yaml"
                type="textarea"
                :rows="20"
                readonly
              />

              <div class="button-group">
                <el-button
                  type="success"
                  @click="copyToClipboard(listenerEnrollmentData.config_yaml)"
                >
                  Copy Configuration
                </el-button>
                <el-button
                  @click="downloadConfig(listenerEnrollmentData.config_yaml, `${listenerEnrollmentData.listener_name}-config.yml`)"
                >
                  Download as File
                </el-button>
              </div>
            </div>

            <div class="dialog-footer">
              <el-button
                type="primary"
                @click="addListenerDialogVisible = false; loadAgents()"
              >
                Done
              </el-button>
            </div>
          </div>
        </el-dialog>
      </el-tab-pane>

      <!-- Provisioning Keys Tab -->
      <el-tab-pane
        v-if="userPermissions.includes('create_provisioning_key')"
        label="Provisioning Keys"
        name="provisioning"
      >
        <div class="tab-header">
          <el-button
            type="primary"
            @click="showCreateProvKeyDialog"
          >
            Create Provisioning Key
          </el-button>
        </div>

        <el-table
          :data="provisioningKeys"
          class="w-full"
        >
          <el-table-column
            prop="key_id"
            label="Key ID"
            width="200"
          />
          <el-table-column
            prop="description"
            label="Description"
            min-width="200"
          />
          <el-table-column
            prop="created_by"
            label="Created By"
            width="150"
          />
          <el-table-column
            prop="created_at"
            label="Created"
            width="180"
          >
            <template #default="scope">
              {{ formatTimestamp(scope.row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column
            prop="last_used_at"
            label="Last Used"
            width="180"
          >
            <template #default="scope">
              {{ scope.row.last_used_at ? formatTimestamp(scope.row.last_used_at) : 'Never' }}
            </template>
          </el-table-column>
          <el-table-column
            label="Status"
            width="120"
          >
            <template #default="scope">
              <el-tag
                :type="scope.row.enabled ? 'success' : 'info'"
                size="small"
              >
                {{ scope.row.enabled ? 'Enabled' : 'Disabled' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            label="Actions"
            width="250"
          >
            <template #default="scope">
              <el-space>
                <el-button
                  v-if="scope.row.enabled"
                  size="small"
                  type="warning"
                  @click="toggleProvKey(scope.row.key_id, false)"
                >
                  Disable
                </el-button>
                <el-button
                  v-else
                  size="small"
                  type="success"
                  @click="toggleProvKey(scope.row.key_id, true)"
                >
                  Enable
                </el-button>
                <el-button
                  size="small"
                  type="danger"
                  @click="deleteProvKey(scope.row.key_id)"
                >
                  Delete
                </el-button>
              </el-space>
            </template>
          </el-table-column>
        </el-table>

        <!-- Create Provisioning Key Dialog -->
        <el-dialog
          v-model="createProvKeyDialogVisible"
          title="Create Provisioning Key"
          width="600px"
          :close-on-click-modal="false"
        >
          <div v-if="!createdProvKey">
            <el-form
              :model="createProvKeyForm"
              label-width="120px"
            >
              <el-form-item label="Key ID">
                <el-input
                  v-model="createProvKeyForm.keyId"
                  placeholder="e.g., ci-cd-pipeline"
                  @keyup.enter="createProvKey"
                />
                <div class="hint-text">
                  A unique identifier for this key (e.g., "prod-terraform", "staging-ci")
                </div>
              </el-form-item>
              <el-form-item label="Description">
                <el-input
                  v-model="createProvKeyForm.description"
                  type="textarea"
                  :rows="2"
                  placeholder="Optional: Describe the purpose of this key"
                />
              </el-form-item>
            </el-form>
          </div>

          <div
            v-else
            class="created-key-display"
          >
            <el-alert
              title="Important: Save this API key now!"
              type="warning"
              description="This key will only be shown once. Copy it to a secure location."
              :closable="false"
              show-icon
              class="mb-xl"
            />

            <div class="key-info">
              <div class="key-row">
                <strong>Key ID:</strong>
                <code>{{ createdProvKey.key_id }}</code>
              </div>
              <div class="key-row">
                <strong>API Key:</strong>
                <code class="api-key">{{ createdProvKey.api_key }}</code>
                <el-button
                  size="small"
                  @click="copyToClipboard(createdProvKey.api_key, 'API key')"
                >
                  Copy
                </el-button>
              </div>
              <div
                v-if="createdProvKey.description"
                class="key-row"
              >
                <strong>Description:</strong>
                <span>{{ createdProvKey.description }}</span>
              </div>
            </div>

            <el-divider />

            <h4>Usage Example</h4>
            <div class="config-content">
              <pre>{{ provisioningKeyUsageExample }}</pre>
            </div>
            <el-button
              size="small"
              @click="copyToClipboard(provisioningKeyUsageExample, 'Example')"
            >
              Copy Example
            </el-button>
          </div>

          <template #footer>
            <span class="dialog-footer">
              <el-button
                v-if="!createdProvKey"
                @click="closeCreateProvKeyDialog"
              >Cancel</el-button>
              <el-button
                v-if="!createdProvKey"
                type="primary"
                @click="createProvKey"
              >
                Create Key
              </el-button>
              <el-button
                v-else
                type="primary"
                @click="closeCreateProvKeyDialog"
              >
                Done
              </el-button>
            </span>
          </template>
        </el-dialog>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { api } from '../api'
import { websocket } from '../websocket'
import { userPermissions } from '../auth'
import { ElMessage, ElMessageBox } from 'element-plus'
import { formatDateTime } from '../utils/time'

export default {
  name: 'Runners',
  setup() {
    const runners = ref([])
    const listeners = ref([])

    // Runner enrollment state
    // Note: Kept separate from listener enrollment due to significantly different
    // form structures (runners have complex multi-device config, listeners are simpler)
    const addRunnerDialogVisible = ref(false)
    const addRunnerForm = ref({
      runnerName: '',
      expiresHours: 24,
      verifySsl: true,
      devices: [
        {
          name: '0',
          model: 'hackrf',
          rf_gain: 14,
          if_gain: 32,
          frequency_limits: '144000000-148000000, 420000000-450000000'
        }
      ]
    })
    const enrollmentData = ref(null)
    const serverUrl = ref(window.location.origin)

    // Re-enrollment state
    const reEnrollDialogVisible = ref(false)
    const reEnrollRunnerId = ref('')
    const reEnrollData = ref(null)

    // Listener enrollment state
    // Note: Kept separate due to different form structure and simpler device config
    const addListenerDialogVisible = ref(false)
    const addListenerForm = ref({
      listenerName: '',
      expiresHours: 24,
      deviceType: 'rtlsdr',
      deviceId: 'rtlsdr=0'
    })
    const listenerEnrollmentData = ref(null)

    const loadRunners = async () => {
      try {
        const response = await api.get('/runners')
        runners.value = response.data.runners || []
      } catch (error) {
        console.error('Error loading runners:', error)
        ElMessage.error('Failed to load runners')
      }
    }

    const loadAgents = async () => {
      try {
        // Try to load from unified /agents endpoint first
        // Fallback to /runners if not available (backward compatibility)
        let agentsData = []

        try {
          const response = await api.get('/agents')
          agentsData = response.data.agents || []
        } catch (err) {
          // Fallback to old endpoint
          const response = await api.get('/runners')
          agentsData = (response.data.runners || []).map(r => ({
            ...r,
            agent_id: r.runner_id,
            agent_type: 'runner',
            websocket_connected: false
          }))
        }

        // Filter by agent type
        runners.value = agentsData.filter(a => a.agent_type === 'runner')
        listeners.value = agentsData.filter(a => a.agent_type === 'listener')

      } catch (error) {
        console.error('Error loading agents:', error)
        ElMessage.error('Failed to load agents')
      }
    }

    const showAddRunnerDialog = () => {
      addRunnerDialogVisible.value = true
      enrollmentData.value = null
      addRunnerForm.value = {
        runnerName: '',
        expiresHours: 24,
        verifySsl: true,
        devices: [
          {
            name: '0',
            model: 'hackrf',
            rf_gain: 14,
            if_gain: 32,
            frequency_limits: '144000000-148000000, 420000000-450000000'
          }
        ]
      }
    }

    const showAddListenerDialog = () => {
      addListenerDialogVisible.value = true
      listenerEnrollmentData.value = null
      addListenerForm.value = {
        listenerName: '',
        expiresHours: 24,
        deviceType: 'rtlsdr',
        deviceId: 'rtlsdr=0'
      }
    }

    const addDevice = () => {
      addRunnerForm.value.devices.push({
        name: String(addRunnerForm.value.devices.length),
        model: 'hackrf',
        rf_gain: 14,
        if_gain: 32,
        frequency_limits: '144000000-148000000, 420000000-450000000'
      })
    }

    const removeDevice = (index) => {
      addRunnerForm.value.devices.splice(index, 1)
    }

    const generateEnrollmentToken = async () => {
      if (!addRunnerForm.value.runnerName) {
        ElMessage.warning('Please enter a runner name')
        return
      }

      try {
        const response = await api.post('/enrollment/token', {
          runner_name: addRunnerForm.value.runnerName,
          expires_hours: addRunnerForm.value.expiresHours
        })

        enrollmentData.value = response.data
        ElMessage.success('Enrollment token generated')
      } catch (error) {
        console.error('Error generating enrollment token:', error)
        ElMessage.error('Failed to generate enrollment token')
      }
    }

    const closeAddRunnerDialog = () => {
      addRunnerDialogVisible.value = false
      enrollmentData.value = null
      addRunnerForm.value = {
        runnerName: '',
        expiresHours: 24,
        verifySsl: true,
        devices: [
          {
            name: '0',
            model: 'hackrf',
            rf_gain: 14,
            if_gain: 32,
            frequency_limits: '144000000-148000000, 420000000-450000000'
          }
        ]
      }
    }

    // Generate complete runner-config.yml
    const generatedConfig = computed(() => {
      if (!enrollmentData.value) return ''

      const config = `---
# ChallengeCtl Runner Configuration
# Generated for runner: ${enrollmentData.value.runner_name}

runner:
  # Unique identifier for this runner
  runner_id: "${enrollmentData.value.runner_name}"

  # Server URL
  server_url: "${serverUrl.value}"

  # Enrollment credentials (enrollment_token can be left in config, it will be ignored once enrolled)
  enrollment_token: "${enrollmentData.value.token}"
  api_key: "${enrollmentData.value.api_key}"

  # TLS/SSL Configuration
  # Path to CA certificate file for server verification
  # Leave blank to use system CA certificates
  ca_cert: ""

  # Set to false to disable SSL verification (DEVELOPMENT ONLY!)
  # In production, always use verify_ssl: true with proper certificates
  verify_ssl: ${addRunnerForm.value.verifySsl}

  # Cache directory for downloaded challenge files (relative to runner directory)
  cache_dir: "cache"

  # Heartbeat interval (seconds) - how often to ping server
  heartbeat_interval: 30

  # Poll interval (seconds) - how often to request new tasks
  poll_interval: 10

  # Spectrum Paint Pre-Challenge
  # Set to true to fire spectrum paint before each challenge
  spectrum_paint_before_challenge: true

# Radio/SDR Device Configuration
radios:
  # Model defaults - configure default settings for each SDR type
  models:
  - model: hackrf
    rf_gain: 14
    if_gain: 32
    bias_t: true
    rf_samplerate: 2000000
    ppm: 0

  - model: bladerf
    rf_gain: 43
    bias_t: true
    rf_samplerate: 2000000
    ppm: 0

  - model: usrp
    rf_gain: 20
    bias_t: false
    rf_samplerate: 2000000
    ppm: 0

  # Individual device configuration
  devices:
${addRunnerForm.value.devices.map(device => {
  const freqLimits = device.frequency_limits
    ? device.frequency_limits.split(',').map(f => f.trim()).filter(f => f)
    : []

  let deviceYaml = `  - name: ${device.name}\n`
  deviceYaml += `    model: ${device.model}\n`
  deviceYaml += `    rf_gain: ${device.rf_gain}\n`

  if (device.model === 'hackrf' && device.if_gain !== undefined) {
    deviceYaml += `    if_gain: ${device.if_gain}\n`
  }

  if (freqLimits.length > 0) {
    deviceYaml += `    frequency_limits:\n`
    freqLimits.forEach(limit => {
      deviceYaml += `      - "${limit}"\n`
    })
  }

  return deviceYaml
}).join('\n')}
`
      return config
    })

    const downloadConfig = () => {
      if (!enrollmentData.value) return

      const blob = new Blob([generatedConfig.value], { type: 'text/yaml' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'runner-config.yml'
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
      ElMessage.success('Configuration downloaded')
    }

    const copyToClipboard = async (text, label) => {
      try {
        await navigator.clipboard.writeText(text)
        ElMessage.success(`${label} copied to clipboard`)
      } catch (error) {
        console.error('Failed to copy:', error)
        ElMessage.error('Failed to copy to clipboard')
      }
    }

    // Re-enrollment functions
    const showReEnrollDialog = (runnerId) => {
      reEnrollDialogVisible.value = true
      reEnrollRunnerId.value = runnerId
      reEnrollData.value = null
    }

    const closeReEnrollDialog = () => {
      reEnrollDialogVisible.value = false
      reEnrollRunnerId.value = ''
      reEnrollData.value = null
    }

    const generateReEnrollToken = async () => {
      if (!reEnrollRunnerId.value) {
        ElMessage.warning('No runner ID specified')
        return
      }

      try {
        const response = await api.post(`/enrollment/re-enroll/${reEnrollRunnerId.value}`, {
          expires_hours: 24
        })

        reEnrollData.value = {
          token: response.data.token,
          api_key: response.data.api_key,
          runner_id: response.data.runner_id,
          expires_at: response.data.expires_at
        }

        ElMessage.success('Re-enrollment credentials generated')
      } catch (error) {
        console.error('Error generating re-enrollment token:', error)
        ElMessage.error('Failed to generate re-enrollment credentials')
      }
    }

    const reEnrollGeneratedConfig = computed(() => {
      if (!reEnrollData.value) return ''

      const config = `---
# ChallengeCtl Runner Configuration - RE-ENROLLMENT
# Generated for runner: ${reEnrollData.value.runner_id}

runner:
  # Unique identifier for this runner
  runner_id: "${reEnrollData.value.runner_id}"

  # Server URL
  server_url: "${serverUrl.value}"

  # Re-enrollment credentials (enrollment_token can be left in config, it will be ignored once enrolled)
  enrollment_token: "${reEnrollData.value.token}"
  api_key: "${reEnrollData.value.api_key}"

  # TLS/SSL Configuration
  # Path to CA certificate file for server verification
  # Leave blank to use system CA certificates
  ca_cert: ""

  # Set to false to disable SSL verification (DEVELOPMENT ONLY!)
  # In production, always use verify_ssl: true with proper certificates
  verify_ssl: true

  # Cache directory for downloaded challenge files (relative to runner directory)
  cache_dir: "cache"

  # Heartbeat interval (seconds) - how often to ping server
  heartbeat_interval: 30

  # Poll interval (seconds) - how often to request new tasks
  poll_interval: 10

  # Spectrum Paint Pre-Challenge
  # Set to true to fire spectrum paint before each challenge
  spectrum_paint_before_challenge: true

# Radio/SDR Device Configuration
radios:
  # Model defaults - configure default settings for each SDR type
  models:
  - model: hackrf
    rf_gain: 14
    if_gain: 32
    bias_t: true
    rf_samplerate: 2000000
    ppm: 0

  - model: bladerf
    rf_gain: 43
    bias_t: true
    rf_samplerate: 2000000
    ppm: 0

  - model: usrp
    rf_gain: 20
    bias_t: false
    rf_samplerate: 2000000
    ppm: 0

  # Individual device configuration
  # Customize this section for your specific SDR devices
  devices:
  # HackRF Example (by index)
  - name: 0
    model: hackrf
    rf_gain: 14
    if_gain: 32
    frequency_limits:
      - "144000000-148000000"  # 2m ham band
      - "420000000-450000000"  # 70cm ham band

  # Uncomment and configure for additional devices:
  # BladeRF Example (by serial number)
  # - name: "1234567890abcdef"
  #   model: bladerf
  #   rf_gain: 43
  #   bias_t: true
  #   antenna: TX1
  #   frequency_limits:
  #     - "144000000-148000000"
  #     - "420000000-450000000"

  # USRP Example
  # - name: "type=b200"
  #   model: usrp
  #   rf_gain: 20
  #   frequency_limits:
  #     - "70000000-6000000000"  # Full range

# Notes:
# - Device names can be index numbers (0, 1, 2) or serial numbers/identifiers
# - frequency_limits are optional - if not set, device can use any frequency
# - bias_t and antenna settings are device-specific
# - rf_gain and if_gain values depend on device type and setup
`
      return config
    })

    const downloadReEnrollConfig = () => {
      if (!reEnrollData.value) return

      const blob = new Blob([reEnrollGeneratedConfig.value], { type: 'text/yaml' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `runner-config-${reEnrollData.value.runner_id}.yml`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
      ElMessage.success('Configuration downloaded')
    }

    const enableRunner = async (runnerId) => {
      try {
        await api.post(`/runners/${runnerId}/enable`)
        ElMessage.success('Runner enabled')
        // WebSocket will update the UI automatically
      } catch (error) {
        console.error('Error enabling runner:', error)
        ElMessage.error('Failed to enable runner')
      }
    }

    const disableRunner = async (runnerId) => {
      try {
        await api.post(`/runners/${runnerId}/disable`)
        ElMessage.success('Runner disabled')
        // WebSocket will update the UI automatically
      } catch (error) {
        console.error('Error disabling runner:', error)
        ElMessage.error('Failed to disable runner')
      }
    }

    const enableListener = async (listenerId) => {
      try {
        await api.post(`/agents/${listenerId}/enable`)
        ElMessage.success('Listener enabled')
        // WebSocket will update the UI automatically
      } catch (error) {
        console.error('Error enabling listener:', error)
        ElMessage.error('Failed to enable listener')
      }
    }

    const disableListener = async (listenerId) => {
      try {
        await api.post(`/agents/${listenerId}/disable`)
        ElMessage.success('Listener disabled')
        // WebSocket will update the UI automatically
      } catch (error) {
        console.error('Error disabling listener:', error)
        ElMessage.error('Failed to disable listener')
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

    const kickListener = async (listenerId) => {
      try {
        await ElMessageBox.confirm(
          `Remove listener ${listenerId}?`,
          'Confirm',
          {
            confirmButtonText: 'Remove',
            cancelButtonText: 'Cancel',
            type: 'warning'
          }
        )

        await api.delete(`/agents/${listenerId}`)
        ElMessage.success('Listener removed')
        loadAgents()
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error('Failed to remove listener')
        }
      }
    }

    const generateListenerEnrollmentToken = async () => {
      if (!addListenerForm.value.listenerName) {
        ElMessage.error('Listener name is required')
        return
      }

      try {
        // Generate enrollment token via enrollment endpoint
        const response = await api.post('/enrollment/token', {
          runner_name: addListenerForm.value.listenerName,
          expires_hours: addListenerForm.value.expiresHours,
          agent_type: 'listener'
        })

        // Generate complete configuration YAML
        const configYaml = `# ChallengeCtl Listener Configuration
# Generated: ${new Date().toISOString()}

agent:
  agent_id: "${addListenerForm.value.listenerName}"
  server_url: "${serverUrl.value}"
  api_key: "${response.data.api_key}"
  heartbeat_interval: 30
  websocket_enabled: true
  websocket_reconnect_delay: 5

  recording:
    output_dir: "recordings"
    sample_rate: 2000000  # 2 MHz
    fft_size: 1024
    frame_rate: 20
    gain: 40  # Adjust based on signal strength
    pre_roll_seconds: 5
    post_roll_seconds: 5

    device:
      id: "${addListenerForm.value.deviceId}"
      type: "${addListenerForm.value.deviceType}"

logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
`

        listenerEnrollmentData.value = {
          listener_name: addListenerForm.value.listenerName,
          api_key: response.data.api_key,
          enrollment_token: response.data.token,
          expires_at: response.data.expires_at,
          config_yaml: configYaml
        }

        ElMessage.success('Listener enrollment token generated')
      } catch (error) {
        console.error('Error generating listener enrollment token:', error)
        ElMessage.error('Failed to generate enrollment token')
      }
    }

    const handleRunnerStatusEvent = (event) => {
      console.log('Runners page received runner_status event:', event)

      const runner = runners.value.find(r => r.runner_id === event.runner_id)

      if (event.status === 'online') {
        if (!runner) {
          // New runner registered, reload full list to get all details
          console.log('New runner detected, reloading list')
          loadRunners()
        } else {
          // Update existing runner status
          console.log('Updating runner to online:', event.runner_id)
          runner.status = 'online'
          if (event.last_heartbeat) {
            runner.last_heartbeat = event.last_heartbeat
          }
        }
      } else if (event.status === 'offline') {
        if (runner) {
          // Mark runner as offline
          console.log('Updating runner to offline:', event.runner_id)
          runner.status = 'offline'
        }
      }
    }

    const handleRunnerEnabledEvent = (event) => {
      console.log('Runners page received runner_enabled event:', event)

      const runner = runners.value.find(r => r.runner_id === event.runner_id)
      if (runner) {
        runner.enabled = event.enabled
        console.log(`Updated runner ${event.runner_id} enabled status to:`, event.enabled)
      }
    }

    const handleListenerStatusEvent = (event) => {
      console.log('Agents page received listener_status event:', event)

      const listener = listeners.value.find(l => l.agent_id === event.agent_id || l.agent_id === event.listener_id)

      if (event.status === 'online') {
        if (!listener) {
          // New listener registered, reload full list
          console.log('New listener detected, reloading agents')
          loadAgents()
        } else {
          // Update existing listener status
          console.log('Updating listener to online:', event.agent_id)
          listener.status = 'online'
          if (event.last_heartbeat) {
            listener.last_heartbeat = event.last_heartbeat
          }
          if (event.websocket_connected !== undefined) {
            listener.websocket_connected = event.websocket_connected
          }
        }
      } else if (event.status === 'offline') {
        if (listener) {
          // Mark listener as offline
          console.log('Updating listener to offline:', event.agent_id)
          listener.status = 'offline'
          listener.websocket_connected = false
        }
      }
    }

    onMounted(() => {
      loadAgents()  // Load both runners and listeners
      loadProvisioningKeys()

      // Connect WebSocket for real-time updates
      websocket.connect()
      websocket.on('runner_status', handleRunnerStatusEvent)
      websocket.on('listener_status', handleListenerStatusEvent)
      websocket.on('runner_enabled', handleRunnerEnabledEvent)
    })

    // Provisioning Keys state
    const activeTab = ref('runners')
    const provisioningKeys = ref([])
    const createProvKeyDialogVisible = ref(false)
    const createProvKeyForm = ref({
      keyId: '',
      description: ''
    })
    const createdProvKey = ref(null)

    const loadProvisioningKeys = async () => {
      try {
        const response = await api.get('/provisioning/keys')
        provisioningKeys.value = response.data.keys || []
      } catch (error) {
        console.error('Error loading provisioning keys:', error)
        ElMessage.error('Failed to load provisioning keys')
      }
    }

    const showCreateProvKeyDialog = () => {
      createProvKeyDialogVisible.value = true
      createdProvKey.value = null
      createProvKeyForm.value = {
        keyId: '',
        description: ''
      }
    }

    const createProvKey = async () => {
      if (!createProvKeyForm.value.keyId) {
        ElMessage.warning('Please enter a key ID')
        return
      }

      try {
        const response = await api.post('/provisioning/keys', {
          key_id: createProvKeyForm.value.keyId,
          description: createProvKeyForm.value.description
        })

        createdProvKey.value = response.data
        ElMessage.success('Provisioning key created')
        loadProvisioningKeys()
      } catch (error) {
        console.error('Error creating provisioning key:', error)
        ElMessage.error(error.response?.data?.error || 'Failed to create provisioning key')
      }
    }

    const closeCreateProvKeyDialog = () => {
      createProvKeyDialogVisible.value = false
      createdProvKey.value = null
      createProvKeyForm.value = {
        keyId: '',
        description: ''
      }
    }

    const toggleProvKey = async (keyId, enabled) => {
      try {
        await api.post(`/provisioning/keys/${keyId}/toggle`, { enabled })
        ElMessage.success(`Key ${enabled ? 'enabled' : 'disabled'}`)
        loadProvisioningKeys()
      } catch (error) {
        console.error('Error toggling provisioning key:', error)
        ElMessage.error('Failed to toggle key')
      }
    }

    const deleteProvKey = async (keyId) => {
      try {
        await ElMessageBox.confirm(
          `Are you sure you want to delete the provisioning key "${keyId}"? This action cannot be undone.`,
          'Delete Provisioning Key',
          {
            confirmButtonText: 'Delete',
            cancelButtonText: 'Cancel',
            type: 'warning'
          }
        )

        await api.delete(`/provisioning/keys/${keyId}`)
        ElMessage.success('Key deleted')
        loadProvisioningKeys()
      } catch (error) {
        if (error === 'cancel') return
        console.error('Error deleting provisioning key:', error)
        ElMessage.error('Failed to delete key')
      }
    }

    const provisioningKeyUsageExample = computed(() => {
      if (!createdProvKey.value) return ''

      return `# Provision a new runner using this key
curl -k \\
  -X POST \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer ${createdProvKey.value.api_key}" \\
  -d '{"runner_name":"my-runner"}' \\
  ${serverUrl.value}/api/provisioning/provision

# The response includes a complete runner-config.yml in the 'config_yaml' field`
    })

    onUnmounted(() => {
      websocket.off('runner_status', handleRunnerStatusEvent)
      websocket.off('runner_enabled', handleRunnerEnabledEvent)
    })

    return {
      activeTab,
      runners,
      listeners,
      addRunnerDialogVisible,
      addRunnerForm,
      enrollmentData,
      serverUrl,
      generatedConfig,
      reEnrollDialogVisible,
      reEnrollRunnerId,
      reEnrollData,
      reEnrollGeneratedConfig,
      showAddRunnerDialog,
      addDevice,
      removeDevice,
      generateEnrollmentToken,
      closeAddRunnerDialog,
      copyToClipboard,
      downloadConfig,
      showReEnrollDialog,
      generateReEnrollToken,
      closeReEnrollDialog,
      downloadReEnrollConfig,
      enableRunner,
      disableRunner,
      enableListener,
      disableListener,
      kickRunner,
      kickListener,
      addListenerDialogVisible,
      addListenerForm,
      listenerEnrollmentData,
      showAddListenerDialog,
      generateListenerEnrollmentToken,
      provisioningKeys,
      createProvKeyDialogVisible,
      createProvKeyForm,
      createdProvKey,
      showCreateProvKeyDialog,
      createProvKey,
      closeCreateProvKeyDialog,
      toggleProvKey,
      deleteProvKey,
      provisioningKeyUsageExample,
      userPermissions,
      formatTimestamp: formatDateTime
    }
  }
}
</script>

<style scoped>
.runners {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.enrollment-data {
  padding: 10px;
}

.credential-block {
  margin-bottom: 20px;
}

.credential-block h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
}

.credential-value {
  display: flex;
  align-items: center;
  gap: 10px;
  background-color: var(--el-fill-color-light);
  padding: 12px;
  border-radius: 4px;
  border: 1px solid var(--el-border-color);
}

.credential-value code {
  flex: 1;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  word-break: break-all;
}

.setup-instructions {
  margin-top: 20px;
}

.setup-instructions h4 {
  margin: 0 0 10px 0;
}

.setup-instructions ol {
  padding-left: 20px;
}

.setup-instructions li {
  margin-bottom: 10px;
  line-height: 1.6;
}

.setup-instructions code {
  background-color: var(--el-fill-color);
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

.setup-instructions pre {
  overflow-x: auto;
}

.config-display {
  margin-bottom: 20px;
}

.config-display h4 {
  margin: 0 0 10px 0;
  font-size: 14px;
}

.config-content {
  background-color: var(--el-fill-color-light);
  padding: 15px;
  border-radius: 4px;
  border: 1px solid var(--el-border-color);
  font-family: 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
  max-height: 400px;
  overflow-y: auto;
  margin: 0;
  white-space: pre;
}

.tab-header {
  margin-bottom: 20px;
}

.created-key-display {
  padding: 10px;
}

.key-info {
  margin-bottom: 20px;
}

.key-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 15px;
}

.key-row strong {
  min-width: 100px;
}

.key-row code {
  flex: 1;
  background-color: var(--el-fill-color-light);
  padding: 8px 12px;
  border-radius: 4px;
  border: 1px solid var(--el-border-color);
  font-family: 'Courier New', monospace;
  font-size: 13px;
  word-break: break-all;
}

.key-row code.api-key {
  font-weight: 600;
}

.device-config-item {
  margin-bottom: 20px;
}

.device-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.device-header h4 {
  margin: 0;
}
</style>
