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
          <p class="info-text">
            Runner agents poll the server for available challenges to transmit using TX capable SDR devices.
          </p>
        </div>

        <el-table
          :data="runners"
          row-key="runner_id"
          class="w-full"
        >
          <el-table-column
            v-if="!isMobile"
            prop="runner_id"
            label="Runner ID"
            width="180"
          />
          <el-table-column
            prop="hostname"
            label="Hostname"
            :width="isMobile ? undefined : '200'"
          />
          <el-table-column
            v-if="!isMobile"
            prop="ip_address"
            label="IP Address"
            width="150"
          />
          <el-table-column
            label="Status"
            :width="isMobile ? '120' : '150'"
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
            v-if="!isMobile"
            label="Devices"
            width="100"
          >
            <template #default="scope">
              {{ scope.row.devices?.length || 0 }}
            </template>
          </el-table-column>
          <el-table-column
            v-if="!isMobile"
            label="Last Heartbeat"
            width="180"
          >
            <template #default="scope">
              {{ formatTimestamp(scope.row.last_heartbeat) }}
            </template>
          </el-table-column>
          <el-table-column
            label="Actions"
            :width="isMobile ? '100' : '120'"
            align="center"
          >
            <template #default="scope">
              <el-dropdown @command="(command) => handleRunnerAction(command, scope.row)">
                <el-button
                  size="small"
                  type="primary"
                >
                  Actions
                  <el-icon class="ml-5">
                    <ArrowDown />
                  </el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item :command="scope.row.enabled ? 'disable' : 'enable'">
                      <el-icon><SwitchIcon /></el-icon>
                      {{ scope.row.enabled ? 'Disable Runner' : 'Enable Runner' }}
                    </el-dropdown-item>
                    <el-dropdown-item
                      command="re-enroll"
                      divided
                    >
                      <el-icon><Key /></el-icon>
                      Re-enroll
                    </el-dropdown-item>
                    <el-dropdown-item
                      command="kick"
                      divided
                    >
                      <el-icon><Delete /></el-icon>
                      <span style="color: var(--el-color-danger);">Kick</span>
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
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
                  <el-table-column
                    label="Status"
                    width="120"
                  >
                    <template #default="devScope">
                      <el-tag
                        :type="devScope.row.status === 'online' ? 'success' : devScope.row.status === 'busy' ? 'warning' : 'danger'"
                        size="small"
                      >
                        {{ devScope.row.status || 'unknown' }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="Frequency Limits & Gain">
                    <template #default="devScope">
                      <div v-if="devScope.row.antennas_config">
                        <!-- New format: per-antenna frequency limits and gain -->
                        <div
                          v-for="(antennaInfo, antennaName) in devScope.row.antennas_config"
                          :key="antennaName"
                          style="margin-bottom: 4px;"
                        >
                          <el-tag
                            size="small"
                            :type="antennaInfo.enabled === false ? 'info' : 'success'"
                            style="margin-right: 8px;"
                          >
                            {{ antennaName || 'Default' }}
                          </el-tag>
                          <span style="font-size: 13px;">
                            {{ formatFrequencyLimits(antennaInfo.frequency_limits) }}
                          </span>
                          <span
                            v-if="antennaInfo.rf_gain !== undefined"
                            style="font-size: 12px; color: #606266; margin-left: 8px;"
                          >
                            (Gain: {{ antennaInfo.rf_gain }} dB)
                          </span>
                          <el-tag
                            v-if="antennaInfo.enabled === false"
                            size="small"
                            type="warning"
                            style="margin-left: 4px;"
                          >
                            disabled
                          </el-tag>
                        </div>
                      </div>
                      <div v-else>
                        <!-- Legacy format: device-level frequency limits and gain -->
                        <div>
                          {{ formatFrequencyLimits(devScope.row.frequency_limits) }}
                        </div>
                        <div
                          v-if="devScope.row.rf_gain !== undefined || devScope.row.if_gain !== undefined"
                          style="font-size: 12px; color: #606266; margin-top: 4px;"
                        >
                          <span v-if="devScope.row.rf_gain !== undefined">RF Gain: {{ devScope.row.rf_gain }} dB</span>
                          <span
                            v-if="devScope.row.if_gain !== undefined"
                            style="margin-left: 8px;"
                          >IF Gain: {{ devScope.row.if_gain }} dB</span>
                        </div>
                      </div>
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
          destroy-on-close
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
                  :teleported="false"
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
                :key="device._uid"
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
                    :teleported="false"
                    @change="onDeviceModelChange(device)"
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

                <!-- Single Antenna Mode (HackRF, RTL-SDR) -->
                <template v-if="!device.useMultiAntenna">
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

                  <el-form-item label="Bias-T">
                    <el-checkbox v-model="device.bias_t">
                      Enable Bias-T
                    </el-checkbox>
                    <div class="hint-text">
                      Enable to power external LNA (Low Noise Amplifier)
                    </div>
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
                </template>

                <!-- Multi-Antenna Mode (BladeRF, USRP, LimeSDR) -->
                <template v-else>
                  <el-alert
                    type="info"
                    :closable="false"
                    show-icon
                    class="mb-15"
                  >
                    <template #title>
                      Multi-Antenna Configuration
                    </template>
                    This device supports multiple antennas with independent settings.
                    Configure each antenna below.
                  </el-alert>

                  <el-form-item label="Default RF Gain">
                    <el-input-number
                      v-model="device.rf_gain"
                      :min="0"
                      :max="100"
                    />
                    <div class="hint-text">
                      Fallback gain if not specified per-antenna
                    </div>
                  </el-form-item>

                  <el-form-item label="Default Bias-T">
                    <el-checkbox v-model="device.bias_t">
                      Enable Bias-T (default)
                    </el-checkbox>
                    <div class="hint-text">
                      Fallback bias-t if not specified per-antenna
                    </div>
                  </el-form-item>

                  <!-- Antennas Section -->
                  <div class="antennas-section">
                    <h4>Antennas</h4>

                    <el-card
                      v-for="(antenna, antennaIdx) in device.antennas"
                      :key="antenna._uid"
                      class="antenna-card mb-10"
                      shadow="hover"
                    >
                      <template #header>
                        <div class="antenna-card-header">
                          <span>Antenna: {{ antenna.name }}</span>
                          <el-button
                            type="danger"
                            size="small"
                            plain
                            :disabled="device.antennas.length <= 1"
                            @click="removeAntenna(device, antennaIdx)"
                          >
                            Remove
                          </el-button>
                        </div>
                      </template>

                      <el-form-item label="Antenna Name">
                        <el-input
                          v-model="antenna.name"
                          placeholder="e.g., TX1, TX2, TX/RX"
                        />
                      </el-form-item>

                      <el-form-item label="Enabled">
                        <el-checkbox v-model="antenna.enabled">
                          Antenna Enabled
                        </el-checkbox>
                        <div class="hint-text">
                          Disable for maintenance without removing configuration
                        </div>
                      </el-form-item>

                      <el-form-item label="RF Gain">
                        <el-input-number
                          v-model="antenna.rf_gain"
                          :min="0"
                          :max="100"
                        />
                        <div class="hint-text">
                          Optimal gain for this antenna's frequency range
                        </div>
                      </el-form-item>

                      <el-form-item label="Bias-T">
                        <el-checkbox v-model="antenna.bias_t">
                          Enable Bias-T for this antenna
                        </el-checkbox>
                        <div class="hint-text">
                          Enable to power external LNA on this antenna
                        </div>
                      </el-form-item>

                      <el-form-item label="Frequency Limits">
                        <el-input
                          v-model="antenna.frequency_limits"
                          type="textarea"
                          :rows="2"
                          placeholder="e.g., 144000000-148000000, 420000000-450000000"
                        />
                        <div class="hint-text">
                          Comma-separated ranges for this antenna
                        </div>
                      </el-form-item>
                    </el-card>

                    <el-button
                      type="primary"
                      plain
                      class="w-full"
                      @click="addAntenna(device)"
                    >
                      + Add Antenna
                    </el-button>
                  </div>
                </template>

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
            <!-- Step 2: Display credentials and configuration -->
            <el-alert
              title="Runner Enrollment Created"
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
                <el-form-item label="Runner Name">
                  <el-input
                    :model-value="enrollmentData.runner_name"
                    readonly
                  />
                </el-form-item>

                <el-form-item label="API Key">
                  <el-input
                    :model-value="enrollmentData.api_key"
                    readonly
                    type="textarea"
                    :rows="2"
                  >
                    <template #append>
                      <el-button @click="copyToClipboard(enrollmentData.api_key, 'API Key')">
                        Copy
                      </el-button>
                    </template>
                  </el-input>
                </el-form-item>

                <el-form-item label="Enrollment Token">
                  <el-input
                    :model-value="enrollmentData.enrollment_token"
                    readonly
                    type="textarea"
                    :rows="2"
                  >
                    <template #append>
                      <el-button @click="copyToClipboard(enrollmentData.enrollment_token, 'Enrollment Token')">
                        Copy
                      </el-button>
                    </template>
                  </el-input>
                </el-form-item>

                <el-form-item label="Expires">
                  <el-input
                    :model-value="formatTimestamp(enrollmentData.expires_at)"
                    readonly
                  />
                </el-form-item>
              </el-form>

              <el-divider />

              <h3>Runner Configuration File</h3>
              <p class="hint-text">
                Copy this complete configuration to <code>runner-config.yml</code> on your runner machine:
              </p>

              <el-input
                :model-value="generatedConfig"
                type="textarea"
                :rows="20"
                readonly
              />

              <div class="button-group">
                <el-button
                  type="success"
                  @click="copyToClipboard(generatedConfig, 'Configuration')"
                >
                  Copy Configuration
                </el-button>
                <el-button
                  @click="downloadConfig"
                >
                  Download runner-config.yml
                </el-button>
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
          destroy-on-close
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

          <div v-else>
            <el-alert
              type="success"
              title="Re-enrollment Credentials Generated"
              :closable="false"
            />

            <div class="credentials-section">
              <h3>Enrollment Credentials</h3>

              <el-form label-width="150px">
                <el-form-item label="Runner ID">
                  <el-input
                    :model-value="reEnrollData.runner_id"
                    readonly
                  />
                </el-form-item>

                <el-form-item label="API Key">
                  <el-input
                    :model-value="reEnrollData.api_key"
                    readonly
                    type="textarea"
                    :rows="2"
                  >
                    <template #append>
                      <el-button @click="copyToClipboard(reEnrollData.api_key, 'API Key')">
                        Copy
                      </el-button>
                    </template>
                  </el-input>
                </el-form-item>

                <el-form-item label="Enrollment Token">
                  <el-input
                    :model-value="reEnrollData.token"
                    readonly
                    type="textarea"
                    :rows="2"
                  >
                    <template #append>
                      <el-button @click="copyToClipboard(reEnrollData.token, 'Enrollment Token')">
                        Copy
                      </el-button>
                    </template>
                  </el-input>
                </el-form-item>

                <el-form-item label="Expires">
                  <el-input
                    :model-value="formatTimestamp(reEnrollData.expires_at)"
                    readonly
                  />
                </el-form-item>
              </el-form>

              <el-divider />

              <h3>Runner Configuration File</h3>
              <p class="hint-text">
                Copy this complete configuration to <code>runner-config.yml</code> on your NEW runner machine:
              </p>

              <el-input
                :model-value="reEnrollGeneratedConfig"
                type="textarea"
                :rows="20"
                readonly
              />

              <div class="button-group">
                <el-button
                  type="success"
                  @click="copyToClipboard(reEnrollGeneratedConfig, 'Configuration')"
                >
                  Copy Configuration
                </el-button>
                <el-button
                  @click="downloadReEnrollConfig"
                >
                  Download runner-config.yml
                </el-button>
              </div>

              <el-alert
                type="info"
                :closable="false"
                class="mt-15"
              >
                <p><strong>Next Steps:</strong></p>
                <ol>
                  <li>On the NEW runner machine, save the configuration as <code>runner-config.yml</code></li>
                  <li>Customize the <code>radios</code> section for your SDR devices</li>
                  <li>Start the runner: <code>python -m challengectl.runner.runner</code></li>
                  <li>The old runner will be automatically kicked once the new one connects</li>
                </ol>
              </el-alert>
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
          row-key="agent_id"
          class="w-full"
        >
          <el-table-column
            v-if="!isMobile"
            prop="agent_id"
            label="Listener ID"
            width="180"
          />
          <el-table-column
            prop="hostname"
            label="Hostname"
            :width="isMobile ? undefined : '200'"
          />
          <el-table-column
            v-if="!isMobile"
            prop="ip_address"
            label="IP Address"
            width="150"
          />
          <el-table-column
            label="Status"
            :width="isMobile ? '100' : '150'"
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
            :width="isMobile ? '90' : '150'"
          >
            <template #default="scope">
              <el-tag
                :type="scope.row.websocket_connected ? 'success' : 'warning'"
                size="small"
              >
                {{ isMobile ? (scope.row.websocket_connected ? 'WS' : 'X') : (scope.row.websocket_connected ? 'Connected' : 'Disconnected') }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            v-if="!isMobile"
            label="Devices"
            width="100"
          >
            <template #default="scope">
              {{ scope.row.devices?.length || 0 }}
            </template>
          </el-table-column>
          <el-table-column
            v-if="!isMobile"
            label="Last Heartbeat"
            width="180"
          >
            <template #default="scope">
              {{ formatTimestamp(scope.row.last_heartbeat) }}
            </template>
          </el-table-column>
          <el-table-column
            label="Actions"
            :width="isMobile ? '100' : '120'"
            align="center"
          >
            <template #default="scope">
              <el-dropdown @command="(command) => handleListenerAction(command, scope.row)">
                <el-button
                  size="small"
                  type="primary"
                >
                  Actions
                  <el-icon class="ml-5">
                    <ArrowDown />
                  </el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item :command="scope.row.enabled ? 'disable' : 'enable'">
                      <el-icon><SwitchIcon /></el-icon>
                      {{ scope.row.enabled ? 'Disable Listener' : 'Enable Listener' }}
                    </el-dropdown-item>
                    <el-dropdown-item
                      command="edit-devices"
                      divided
                    >
                      <el-icon><Tools /></el-icon>
                      Edit Devices
                    </el-dropdown-item>
                    <el-dropdown-item command="re-enroll">
                      <el-icon><Key /></el-icon>
                      Re-enroll
                    </el-dropdown-item>
                    <el-dropdown-item
                      command="kick"
                      divided
                    >
                      <el-icon><Delete /></el-icon>
                      <span style="color: var(--el-color-danger);">Kick</span>
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
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
          destroy-on-close
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
                  :teleported="false"
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

              <div
                v-for="(device, index) in addListenerForm.devices"
                :key="device._uid"
                class="device-config-item"
              >
                <div class="device-header">
                  <h4>Device {{ index + 1 }}</h4>
                  <el-button
                    v-if="addListenerForm.devices.length > 1"
                    size="small"
                    type="danger"
                    @click="removeListenerDevice(index)"
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
                    :teleported="false"
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

                <el-form-item label="Gain (dB)">
                  <el-input-number
                    v-model="device.gain"
                    :min="0"
                    :max="100"
                  />
                  <div class="hint-text">
                    RF gain setting (0-100 dB, typical: 20-50)
                  </div>
                </el-form-item>

                <el-form-item label="Waterfall Min (dBm)">
                  <el-input-number
                    v-model="device.waterfall_min_dbm"
                    :min="-120"
                    :max="0"
                    :step="5"
                  />
                  <div class="hint-text">
                    Minimum power level for waterfall display (optional, default: auto-scale)
                  </div>
                </el-form-item>

                <el-form-item label="Waterfall Max (dBm)">
                  <el-input-number
                    v-model="device.waterfall_max_dbm"
                    :min="-120"
                    :max="0"
                    :step="5"
                  />
                  <div class="hint-text">
                    Maximum power level for waterfall display (optional, default: auto-scale)
                  </div>
                </el-form-item>

                <el-form-item label="Frequency Limits">
                  <el-input
                    v-model="device.frequency_limits"
                    placeholder="e.g., 144000000-148000000, 420000000-450000000"
                  />
                  <div class="hint-text">
                    Comma-separated ranges in Hz (optional). Leave blank for full range.
                  </div>
                </el-form-item>

                <el-divider v-if="index < addListenerForm.devices.length - 1" />
              </div>

              <el-button
                type="primary"
                plain
                class="mt-10 w-full"
                @click="addListenerDevice"
              >
                Add Another Device
              </el-button>
            </el-form>

            <div class="dialog-footer">
              <el-button @click="addListenerDialogVisible = false">
                Cancel
              </el-button>
              <el-button
                type="primary"
                :disabled="!addListenerForm.listenerName"
                @click="generateListenerEnrollmentToken"
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
                      <el-button @click="copyToClipboard(listenerEnrollmentData.api_key, 'API Key')">
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
                      <el-button @click="copyToClipboard(listenerEnrollmentData.enrollment_token, 'Enrollment Token')">
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
                  @click="copyToClipboard(listenerEnrollmentData.config_yaml, 'Configuration')"
                >
                  Copy Configuration
                </el-button>
                <el-button
                  @click="downloadConfig(listenerEnrollmentData.config_yaml, `${listenerEnrollmentData.listener_name}-config.yml`)"
                >
                  Download listener-config.yml
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

        <!-- Re-enroll Listener Dialog -->
        <el-dialog
          v-model="reEnrollListenerDialogVisible"
          title="Re-enroll Listener"
          width="700px"
          :close-on-click-modal="false"
          destroy-on-close
        >
          <div v-if="!reEnrollListenerData">
            <el-alert
              type="warning"
              title="Warning"
              description="Generate fresh credentials to migrate this listener to a different host or update compromised credentials."
              :closable="false"
            />

            <p><strong>Listener ID:</strong> {{ reEnrollListenerId }}</p>
            <p>This will generate new enrollment credentials. The old API key will remain valid until the listener re-enrolls with the new credentials.</p>
          </div>

          <div v-else>
            <el-alert
              type="success"
              title="Re-enrollment Credentials Generated"
              :closable="false"
            />

            <div class="credentials-section">
              <h3>Enrollment Credentials</h3>

              <el-form label-width="150px">
                <el-form-item label="Listener ID">
                  <el-input
                    :model-value="reEnrollListenerData.listener_id"
                    readonly
                  />
                </el-form-item>

                <el-form-item label="API Key">
                  <el-input
                    :model-value="reEnrollListenerData.api_key"
                    readonly
                    type="textarea"
                    :rows="2"
                  >
                    <template #append>
                      <el-button @click="copyToClipboard(reEnrollListenerData.api_key, 'API Key')">
                        Copy
                      </el-button>
                    </template>
                  </el-input>
                </el-form-item>

                <el-form-item label="Enrollment Token">
                  <el-input
                    :model-value="reEnrollListenerData.token"
                    readonly
                    type="textarea"
                    :rows="2"
                  >
                    <template #append>
                      <el-button @click="copyToClipboard(reEnrollListenerData.token, 'Enrollment Token')">
                        Copy
                      </el-button>
                    </template>
                  </el-input>
                </el-form-item>

                <el-form-item label="Expires">
                  <el-input
                    :model-value="formatTimestamp(reEnrollListenerData.expires_at)"
                    readonly
                  />
                </el-form-item>
              </el-form>

              <el-divider />

              <h3>Listener Configuration File</h3>
              <p class="hint-text">
                Copy this complete configuration to <code>listener-config.yml</code> on your NEW listener machine:
              </p>

              <el-input
                :model-value="reEnrollListenerGeneratedConfig"
                type="textarea"
                :rows="20"
                readonly
              />

              <div class="button-group">
                <el-button
                  type="success"
                  @click="copyToClipboard(reEnrollListenerGeneratedConfig, 'Configuration')"
                >
                  Copy Configuration
                </el-button>
                <el-button
                  @click="downloadReEnrollListenerConfig"
                >
                  Download listener-config.yml
                </el-button>
              </div>

              <el-alert
                type="info"
                :closable="false"
                class="mt-15"
              >
                <p><strong>Next Steps:</strong></p>
                <ol>
                  <li>On the NEW listener machine, save the configuration as <code>listener-config.yml</code></li>
                  <li>Install dependencies: <code>pip install -r requirements-listener.txt</code></li>
                  <li>Start the listener: <code>python listener/listener.py --config listener-config.yml</code></li>
                  <li>The old listener will be automatically kicked once the new one connects</li>
                </ol>
              </el-alert>
            </div>
          </div>

          <template #footer>
            <span class="dialog-footer">
              <el-button
                v-if="!reEnrollListenerData"
                @click="reEnrollListenerDialogVisible = false"
              >
                Cancel
              </el-button>
              <el-button
                v-if="!reEnrollListenerData"
                type="primary"
                @click="generateReEnrollListenerToken"
              >
                Generate Re-enrollment Credentials
              </el-button>
              <el-button
                v-if="reEnrollListenerData"
                type="primary"
                @click="closeReEnrollListenerDialog"
              >
                Done
              </el-button>
            </span>
          </template>
        </el-dialog>

        <!-- Edit Listener Devices Dialog -->
        <el-dialog
          v-model="editListenerDevicesDialogVisible"
          title="Edit Listener Devices"
          width="700px"
          :close-on-click-modal="false"
          destroy-on-close
        >
          <div v-if="editListenerForm">
            <el-alert
              type="info"
              :closable="false"
              class="mb-15"
            >
              <p>
                Edit device configuration for listener <strong>{{ editListenerForm.agent_id }}</strong>.
                Changes will be applied immediately and affect future recordings.
              </p>
            </el-alert>

            <div
              v-for="(device, index) in editListenerForm.devices"
              :key="device._uid"
              class="device-config-item"
            >
              <div class="device-header">
                <h4>Device {{ index + 1 }}</h4>
                <el-button
                  v-if="editListenerForm.devices.length > 1"
                  size="small"
                  type="danger"
                  @click="editListenerForm.devices.splice(index, 1)"
                >
                  Remove
                </el-button>
              </div>

              <el-form label-width="150px">
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
                    :teleported="false"
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
                      label="Simulated"
                      value="simulated"
                    />
                  </el-select>
                </el-form-item>

                <el-form-item label="Gain (dB)">
                  <el-input-number
                    v-model="device.gain"
                    :min="0"
                    :max="60"
                    :step="1"
                  />
                  <div class="hint-text">
                    RF gain in dB (typical: 20-50 for RTL-SDR, 0-40 for HackRF)
                  </div>
                </el-form-item>

                <el-form-item label="Waterfall Min (dBm)">
                  <el-input-number
                    v-model="device.waterfall_min_dbm"
                    :min="-120"
                    :max="0"
                    :step="5"
                  />
                  <div class="hint-text">
                    Minimum power level for waterfall display (optional, leave empty for auto-scale)
                  </div>
                </el-form-item>

                <el-form-item label="Waterfall Max (dBm)">
                  <el-input-number
                    v-model="device.waterfall_max_dbm"
                    :min="-120"
                    :max="0"
                    :step="5"
                  />
                  <div class="hint-text">
                    Maximum power level for waterfall display (optional, leave empty for auto-scale)
                  </div>
                </el-form-item>

                <el-form-item label="Frequency Limits">
                  <el-input
                    v-model="device.frequency_limits"
                    placeholder="e.g., 144000000-148000000, 420000000-450000000"
                  />
                  <div class="hint-text">
                    Comma-separated ranges in Hz (optional). Leave blank for full range.
                  </div>
                </el-form-item>
              </el-form>

              <el-divider v-if="index < editListenerForm.devices.length - 1" />
            </div>

            <el-button
              type="primary"
              plain
              class="mt-10 w-full"
              @click="editListenerForm.devices.push({ _uid: generateDeviceId(), name: String(editListenerForm.devices.length), model: 'rtlsdr', gain: 40, waterfall_min_dbm: null, waterfall_max_dbm: null, frequency_limits: '' })"
            >
              Add Another Device
            </el-button>
          </div>

          <template #footer>
            <span class="dialog-footer">
              <el-button @click="editListenerDevicesDialogVisible = false">
                Cancel
              </el-button>
              <el-button
                type="primary"
                @click="saveListenerDevices"
              >
                Save Changes
              </el-button>
            </span>
          </template>
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
          destroy-on-close
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
import { ArrowDown, Switch as SwitchIcon, Tools, Key, Delete } from '@element-plus/icons-vue'
import { useBreakpoint } from '../composables/useBreakpoint'

export default {
  name: 'Runners',
  setup() {
    const runners = ref([])
    const listeners = ref([])

    // Breakpoint detection for responsive design
    const { isMobile } = useBreakpoint()

    // Unique ID generator for device objects (fixes Vue 3.5 reactivity with v-for)
    let deviceIdCounter = 0
    const generateDeviceId = () => {
      return `device_${Date.now()}_${deviceIdCounter++}`
    }

    // Antenna ID generator
    const generateAntennaId = () => `antenna-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`

    // Device model configurations for multi-antenna support
    const MULTI_ANTENNA_MODELS = {
      'bladerf': {
        defaultAntennas: [
          { name: 'TX1', enabled: true, rf_gain: 43, bias_t: true,
            frequency_limits: '144000000-148000000, 420000000-450000000' },
          { name: 'TX2', enabled: true, rf_gain: 50, bias_t: false,
            frequency_limits: '900000000-915000000, 2400000000-2500000000' }
        ],
        defaultRfGain: 43,
        defaultBiasT: false
      },
      'usrp': {
        defaultAntennas: [
          { name: 'TX/RX', enabled: true, rf_gain: 25, bias_t: false,
            frequency_limits: '70000000-6000000000' }
        ],
        defaultRfGain: 20,
        defaultBiasT: false
      },
      'limesdr': {
        defaultAntennas: [
          { name: 'TX1', enabled: true, rf_gain: 40, bias_t: false, frequency_limits: '' },
          { name: 'TX2', enabled: true, rf_gain: 40, bias_t: false, frequency_limits: '' }
        ],
        defaultRfGain: 40,
        defaultBiasT: false
      }
    }

    const SINGLE_ANTENNA_MODELS = {
      'hackrf': { defaultRfGain: 14, defaultIfGain: 32, defaultBiasT: true },
      'rtlsdr': { defaultGain: 40 }
    }

    const isMultiAntennaModel = (model) => model in MULTI_ANTENNA_MODELS

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
          _uid: generateDeviceId(),
          name: '0',
          model: 'hackrf',
          rf_gain: 14,
          if_gain: 32,
          bias_t: true,
          frequency_limits: '144000000-148000000, 420000000-450000000',
          useMultiAntenna: false,
          antennas: []
        }
      ]
    })
    const enrollmentData = ref(null)
    const serverUrl = ref(window.location.origin)

    // Re-enrollment state (runners)
    const reEnrollDialogVisible = ref(false)
    const reEnrollRunnerId = ref('')
    const reEnrollData = ref(null)

    // Re-enrollment state (listeners)
    const reEnrollListenerDialogVisible = ref(false)
    const reEnrollListenerId = ref('')
    const reEnrollListenerData = ref(null)

    // Listener enrollment state
    // Note: Updated to support multiple devices like runners
    const addListenerDialogVisible = ref(false)
    const addListenerForm = ref({
      listenerName: '',
      expiresHours: 24,
      devices: [
        {
          _uid: generateDeviceId(),
          name: '0',
          model: 'rtlsdr',
          gain: 40,
          waterfall_min_dbm: null,  // null = auto-scale
          waterfall_max_dbm: null,  // null = auto-scale
          frequency_limits: ''
        }
      ]
    })
    const listenerEnrollmentData = ref(null)

    // Edit listener devices state
    const editListenerDevicesDialogVisible = ref(false)
    const editListenerForm = ref(null)

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
        } catch {
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
            _uid: generateDeviceId(),
            name: '0',
            model: 'hackrf',
            rf_gain: 14,
            if_gain: 32,
            bias_t: true,
            frequency_limits: '144000000-148000000, 420000000-450000000',
            useMultiAntenna: false,
            antennas: []
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
        devices: [
          {
            _uid: generateDeviceId(),
            name: '0',
            model: 'rtlsdr',
            gain: 40,
            waterfall_min_dbm: null,
            waterfall_max_dbm: null,
            frequency_limits: ''
          }
        ]
      }
    }

    const addDevice = () => {
      addRunnerForm.value.devices.push({
        _uid: generateDeviceId(),
        name: String(addRunnerForm.value.devices.length),
        model: 'hackrf',
        rf_gain: 14,
        if_gain: 32,
        bias_t: true,
        frequency_limits: '144000000-148000000, 420000000-450000000',
        useMultiAntenna: false,
        antennas: []
      })
    }

    const removeDevice = (index) => {
      addRunnerForm.value.devices.splice(index, 1)
    }

    const onDeviceModelChange = (device) => {
      const model = device.model

      if (isMultiAntennaModel(model)) {
        // Switch to multi-antenna mode
        device.useMultiAntenna = true
        const modelConfig = MULTI_ANTENNA_MODELS[model]
        device.rf_gain = modelConfig.defaultRfGain
        device.bias_t = modelConfig.defaultBiasT
        device.antennas = modelConfig.defaultAntennas.map(ant => ({
          _uid: generateAntennaId(),
          ...ant
        }))
        device.frequency_limits = ''
      } else {
        // Switch to single-antenna mode
        device.useMultiAntenna = false
        const modelConfig = SINGLE_ANTENNA_MODELS[model]
        if (modelConfig) {
          device.rf_gain = modelConfig.defaultRfGain
          if (model === 'hackrf') {
            device.if_gain = modelConfig.defaultIfGain
          }
          device.bias_t = modelConfig.defaultBiasT
        }
        device.antennas = []
        if (model === 'hackrf') {
          device.frequency_limits = '144000000-148000000, 420000000-450000000'
        }
      }
    }

    const addAntenna = (device) => {
      device.antennas.push({
        _uid: generateAntennaId(),
        name: `TX${device.antennas.length + 1}`,
        enabled: true,
        rf_gain: device.rf_gain,
        bias_t: device.bias_t,
        frequency_limits: ''
      })
    }

    const removeAntenna = (device, antennaIndex) => {
      if (device.antennas.length > 1) {
        device.antennas.splice(antennaIndex, 1)
      } else {
        ElMessage.warning('At least one antenna is required')
      }
    }

    const addListenerDevice = () => {
      addListenerForm.value.devices.push({
        _uid: generateDeviceId(),
        name: String(addListenerForm.value.devices.length),
        model: 'rtlsdr',
        gain: 40,
        waterfall_min_dbm: null,
        waterfall_max_dbm: null,
        frequency_limits: ''
      })
    }

    const removeListenerDevice = (index) => {
      addListenerForm.value.devices.splice(index, 1)
    }

    // Validation functions
    const validateDeviceConfiguration = (device) => {
      const errors = []

      if (!device.name?.trim()) errors.push('Device name is required')
      if (!device.model) errors.push('Device model is required')

      if (device.useMultiAntenna) {
        if (!device.antennas?.length) {
          errors.push('At least one antenna is required for multi-antenna devices')
        }

        const antennaNames = device.antennas.map(a => a.name)
        const duplicates = antennaNames.filter((name, idx) => antennaNames.indexOf(name) !== idx)
        if (duplicates.length > 0) {
          errors.push(`Duplicate antenna names: ${duplicates.join(', ')}`)
        }

        device.antennas.forEach((antenna, idx) => {
          if (!antenna.name?.trim()) {
            errors.push(`Antenna ${idx + 1}: Name is required`)
          }
          if (antenna.rf_gain < 0) {
            errors.push(`Antenna ${antenna.name}: RF gain must be >= 0`)
          }
        })
      } else {
        if (device.rf_gain < 0) errors.push('RF gain must be >= 0')
        if (device.model === 'hackrf' && device.if_gain < 0) {
          errors.push('IF gain must be >= 0 for HackRF')
        }
      }

      return errors
    }

    const validateAllDevices = () => {
      const allErrors = []
      addRunnerForm.value.devices.forEach((device, idx) => {
        const errors = validateDeviceConfiguration(device)
        if (errors.length > 0) {
          allErrors.push(`Device ${idx + 1} (${device.name}):`)
          allErrors.push(...errors.map(e => `  - ${e}`))
        }
      })

      if (allErrors.length > 0) {
        ElMessage.error({ message: allErrors.join('\n'), duration: 5000 })
        return false
      }
      return true
    }

    const generateEnrollmentToken = async () => {
      if (!addRunnerForm.value.runnerName) {
        ElMessage.warning('Please enter a runner name')
        return
      }

      if (!validateAllDevices()) {
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
            _uid: generateDeviceId(),
            name: '0',
            model: 'hackrf',
            rf_gain: 14,
            if_gain: 32,
            bias_t: true,
            frequency_limits: '144000000-148000000, 420000000-450000000',
            useMultiAntenna: false,
            antennas: []
          }
        ]
      }
    }

    // YAML generation helper functions
    const generateSingleAntennaDeviceYaml = (device) => {
      const freqLimits = device.frequency_limits
        ? device.frequency_limits.split(',').map(f => f.trim()).filter(f => f)
        : []

      let yaml = `  - name: ${device.name}\n`
      yaml += `    model: ${device.model}\n`
      yaml += `    rf_gain: ${device.rf_gain}\n`

      if (device.model === 'hackrf' && device.if_gain !== undefined) {
        yaml += `    if_gain: ${device.if_gain}\n`
      }

      if (device.bias_t !== undefined) {
        yaml += `    bias_t: ${device.bias_t}\n`
      }

      if (freqLimits.length > 0) {
        yaml += `    frequency_limits:\n`
        freqLimits.forEach(limit => {
          yaml += `      - "${limit}"\n`
        })
      }

      return yaml
    }

    const generateMultiAntennaDeviceYaml = (device) => {
      let yaml = `  - name: ${device.name}\n`
      yaml += `    model: ${device.model}\n`
      yaml += `    rf_gain: ${device.rf_gain}  # Default fallback\n`
      yaml += `    bias_t: ${device.bias_t}  # Default fallback\n`

      if (device.model === 'hackrf' && device.if_gain !== undefined) {
        yaml += `    if_gain: ${device.if_gain}\n`
      }

      yaml += `    antennas:\n`

      device.antennas.forEach(antenna => {
        const freqLimits = antenna.frequency_limits
          ? antenna.frequency_limits.split(',').map(f => f.trim()).filter(f => f)
          : []

        yaml += `      ${antenna.name}:\n`

        if (antenna.enabled !== undefined && !antenna.enabled) {
          yaml += `        enabled: false\n`
        }

        yaml += `        bias_t: ${antenna.bias_t}\n`
        yaml += `        rf_gain: ${antenna.rf_gain}\n`

        if (freqLimits.length > 0) {
          yaml += `        frequency_limits:\n`
          freqLimits.forEach(limit => {
            yaml += `          - "${limit}"\n`
          })
        }
      })

      return yaml
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
  if (device.useMultiAntenna && device.antennas && device.antennas.length > 0) {
    return generateMultiAntennaDeviceYaml(device)
  } else {
    return generateSingleAntennaDeviceYaml(device)
  }
}).join('\n')}
`
      return config
    })

    const downloadConfig = (content = null, filename = null) => {
      // Support both runner and listener configs
      let configContent = content
      let configFilename = filename

      if (!configContent) {
        // Default to runner config if no content provided
        if (!enrollmentData.value) return
        configContent = generatedConfig.value
        configFilename = 'runner-config.yml'
      }

      const blob = new Blob([configContent], { type: 'text/yaml' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = configFilename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
      ElMessage.success('Configuration downloaded')
    }

    const copyToClipboard = async (text, label) => {
      try {
        // Check if clipboard API is available (requires HTTPS or localhost)
        if (!navigator.clipboard) {
          ElMessage({
            message: 'Clipboard not available over HTTP. Please use HTTPS or download the file instead.',
            type: 'warning',
            duration: 5000,
            showClose: true
          })
          return
        }

        await navigator.clipboard.writeText(text)
        ElMessage.success(`${label} copied to clipboard`)
      } catch (error) {
        console.error('Failed to copy:', error)
        ElMessage({
          message: 'Failed to copy to clipboard. Try downloading the file instead.',
          type: 'error',
          duration: 5000,
          showClose: true
        })
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

    // Listener re-enrollment functions
    const showReEnrollListenerDialog = (listenerId) => {
      reEnrollListenerDialogVisible.value = true
      reEnrollListenerId.value = listenerId
      reEnrollListenerData.value = null
    }

    const closeReEnrollListenerDialog = () => {
      reEnrollListenerDialogVisible.value = false
      reEnrollListenerId.value = ''
      reEnrollListenerData.value = null
    }

    const generateReEnrollListenerToken = async () => {
      if (!reEnrollListenerId.value) {
        ElMessage.warning('No listener ID specified')
        return
      }

      try {
        const response = await api.post(`/enrollment/re-enroll/${reEnrollListenerId.value}`, {
          expires_hours: 24
        })

        reEnrollListenerData.value = {
          token: response.data.token,
          api_key: response.data.api_key,
          listener_id: response.data.listener_id || response.data.agent_id,
          expires_at: response.data.expires_at
        }

        ElMessage.success('Re-enrollment credentials generated')
      } catch (error) {
        console.error('Error generating re-enrollment token:', error)
        ElMessage.error('Failed to generate re-enrollment credentials')
      }
    }

    const reEnrollListenerGeneratedConfig = computed(() => {
      if (!reEnrollListenerData.value) return ''

      const config = `---
# ChallengeCtl Listener Configuration - RE-ENROLLMENT
# Generated for listener: ${reEnrollListenerData.value.listener_id}

agent:
  # Agent type and identification
  agent_type: listener
  agent_id: "${reEnrollListenerData.value.listener_id}"

  # Server URL
  server_url: "${serverUrl.value}"

  # Re-enrollment credentials (enrollment_token can be left in config, it will be ignored once enrolled)
  enrollment_token: "${reEnrollListenerData.value.token}"
  api_key: "${reEnrollListenerData.value.api_key}"

  # TLS/SSL Configuration
  ca_cert: ""
  verify_ssl: true

  # Heartbeat interval (seconds)
  heartbeat_interval: 30

  # WebSocket configuration
  websocket_enabled: true
  websocket_reconnect_delay: 5

  # Recording configuration
  recording:
    output_dir: "recordings"
    sample_rate: 2000000
    fft_size: 1024
    frame_rate: 20
    gain: 40
    pre_roll_seconds: 5
    post_roll_seconds: 5
    reference_level_dbm: -10.0

    # SDR device configuration
    device:
      id: "rtlsdr=0"  # Customize for your device
      type: "rtlsdr"  # rtlsdr, hackrf, usrp, etc.
`
      return config
    })

    const downloadReEnrollListenerConfig = () => {
      if (!reEnrollListenerData.value) return

      const blob = new Blob([reEnrollListenerGeneratedConfig.value], { type: 'text/yaml' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `listener-config-${reEnrollListenerData.value.listener_id}.yml`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
      ElMessage.success('Configuration downloaded')
    }

    const enableRunner = async (runnerId) => {
      try {
        await api.post(`/agents/${runnerId}/enable`)
        ElMessage.success('Runner enabled')
        // WebSocket will update the UI automatically
      } catch (error) {
        console.error('Error enabling runner:', error)
        ElMessage.error('Failed to enable runner')
      }
    }

    const disableRunner = async (runnerId) => {
      try {
        await api.post(`/agents/${runnerId}/disable`)
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

    const showEditListenerDevicesDialog = (listener) => {
      // Parse devices from JSON if needed
      let devices = listener.devices
      if (typeof devices === 'string') {
        devices = JSON.parse(devices)
      }

      // Create editable copy of devices with proper structure
      editListenerForm.value = {
        agent_id: listener.agent_id,
        devices: devices.map(d => ({
          _uid: generateDeviceId(),
          name: d.name || d.device_id || '0',
          model: d.model || 'rtlsdr',
          gain: d.gain || 40,
          waterfall_min_dbm: d.waterfall_min_dbm !== undefined ? d.waterfall_min_dbm : null,
          waterfall_max_dbm: d.waterfall_max_dbm !== undefined ? d.waterfall_max_dbm : null,
          frequency_limits: Array.isArray(d.frequency_limits)
            ? d.frequency_limits.join(', ')
            : (d.frequency_limits || '')
        }))
      }

      editListenerDevicesDialogVisible.value = true
    }

    const saveListenerDevices = async () => {
      try {
        // Convert devices back to server format
        const devices = editListenerForm.value.devices.map(d => {
          const device = {
            device_id: d.name,
            name: d.name,
            model: d.model,
            gain: d.gain
          }

          // Only include waterfall params if they're set
          if (d.waterfall_min_dbm !== null && d.waterfall_min_dbm !== undefined) {
            device.waterfall_min_dbm = d.waterfall_min_dbm
          }
          if (d.waterfall_max_dbm !== null && d.waterfall_max_dbm !== undefined) {
            device.waterfall_max_dbm = d.waterfall_max_dbm
          }

          // Parse frequency limits
          if (d.frequency_limits) {
            device.frequency_limits = d.frequency_limits
              .split(',')
              .map(f => f.trim())
              .filter(f => f)
          }

          return device
        })

        await api.put(`/agents/${editListenerForm.value.agent_id}/devices`, { devices })

        ElMessage.success('Device configuration updated')
        editListenerDevicesDialogVisible.value = false
        loadAgents()
      } catch (error) {
        console.error('Error updating listener devices:', error)
        ElMessage.error('Failed to update device configuration')
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

        await api.delete(`/agents/${runnerId}`)
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

        // Generate devices YAML section
        const devicesYaml = addListenerForm.value.devices.map(device => {
          const freqLimits = device.frequency_limits
            ? device.frequency_limits.split(',').map(f => f.trim()).filter(f => f)
            : []

          let deviceYaml = `  - name: ${device.name}\n`
          deviceYaml += `    model: ${device.model}\n`
          deviceYaml += `    gain: ${device.gain}\n`

          // Add waterfall scale parameters if set
          if (device.waterfall_min_dbm !== null && device.waterfall_min_dbm !== undefined) {
            deviceYaml += `    waterfall_min_dbm: ${device.waterfall_min_dbm}\n`
          }
          if (device.waterfall_max_dbm !== null && device.waterfall_max_dbm !== undefined) {
            deviceYaml += `    waterfall_max_dbm: ${device.waterfall_max_dbm}\n`
          }

          if (freqLimits.length > 0) {
            deviceYaml += `    frequency_limits:\n`
            freqLimits.forEach(limit => {
              deviceYaml += `      - "${limit}"\n`
            })
          }

          return deviceYaml
        }).join('\n')

        // Generate complete configuration YAML
        const configYaml = `# ChallengeCtl Listener Configuration
# Generated: ${new Date().toISOString()}

agent:
  agent_id: "${addListenerForm.value.listenerName}"
  server_url: "${serverUrl.value}"

  # Enrollment credentials (enrollment_token can be left in config, it will be ignored once enrolled)
  enrollment_token: "${response.data.token}"
  api_key: "${response.data.api_key}"

  heartbeat_interval: 30
  websocket_enabled: true
  websocket_reconnect_delay: 5

  recording:
    output_dir: "recordings"
    sample_rate: 2000000  # 2 MHz
    fft_size: 1024
    frame_rate: 20
    pre_roll_seconds: 5
    post_roll_seconds: 5

# SDR Device Configuration
radios:
  # Individual device configuration
  devices:
${devicesYaml}

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

    const handleRunnerAction = (command, runner) => {
      switch (command) {
        case 'enable':
          enableRunner(runner.runner_id)
          break
        case 'disable':
          disableRunner(runner.runner_id)
          break
        case 're-enroll':
          showReEnrollDialog(runner.runner_id)
          break
        case 'kick':
          kickRunner(runner.runner_id)
          break
      }
    }

    const handleListenerAction = (command, listener) => {
      switch (command) {
        case 'enable':
          enableListener(listener.agent_id)
          break
        case 'disable':
          disableListener(listener.agent_id)
          break
        case 'edit-devices':
          showEditListenerDevicesDialog(listener)
          break
        case 're-enroll':
          showReEnrollListenerDialog(listener.agent_id)
          break
        case 'kick':
          kickListener(listener.agent_id)
          break
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

    const handleListenerEnabledEvent = (event) => {
      console.log('Agents page received listener_enabled event:', event)

      const listener = listeners.value.find(l => l.agent_id === event.agent_id || l.agent_id === event.listener_id)
      if (listener) {
        listener.enabled = event.enabled
        console.log(`Updated listener ${event.agent_id} enabled status to:`, event.enabled)
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

    const handleDeviceStatusEvent = (event) => {
      console.log('Agents page received device_status event:', event)

      // Find agent (runner or listener) by agent_id
      const allAgents = [...runners.value, ...listeners.value]
      const agent = allAgents.find(a => a.agent_id === event.agent_id)

      if (agent && agent.devices) {
        // Find device by device_id and update status
        const device = agent.devices.find(d => d.device_id === event.device_id)
        if (device) {
          console.log(`Updating device ${event.device_id} status to ${event.status} for agent ${event.agent_id}`)
          device.status = event.status
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
      websocket.on('listener_enabled', handleListenerEnabledEvent)
      websocket.on('device_status', handleDeviceStatusEvent)
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
      websocket.off('listener_status', handleListenerStatusEvent)
      websocket.off('runner_enabled', handleRunnerEnabledEvent)
      websocket.off('listener_enabled', handleListenerEnabledEvent)
      websocket.off('device_status', handleDeviceStatusEvent)
    })

    // Helper functions for frequency display
    const formatFrequency = (hz) => {
      if (!hz) return 'N/A'
      const num = parseInt(hz)
      if (num >= 1000000000) {
        return `${(num / 1000000000).toFixed(1)} GHz`
      } else if (num >= 1000000) {
        return `${(num / 1000000).toFixed(0)} MHz`
      }
      return `${(num / 1000).toFixed(0)} kHz`
    }

    const formatFrequencyLimits = (limits) => {
      if (!limits || limits.length === 0) return 'Any'
      return limits.map(range => {
        const [min, max] = range.split('-')
        return `${formatFrequency(min)}-${formatFrequency(max)}`
      }).join(', ')
    }

    return {
      activeTab,
      runners,
      listeners,
      isMobile,
      loadAgents,
      addRunnerDialogVisible,
      addRunnerForm,
      enrollmentData,
      serverUrl,
      generatedConfig,
      reEnrollDialogVisible,
      reEnrollRunnerId,
      reEnrollData,
      reEnrollGeneratedConfig,
      reEnrollListenerDialogVisible,
      reEnrollListenerId,
      reEnrollListenerData,
      reEnrollListenerGeneratedConfig,
      showAddRunnerDialog,
      addDevice,
      removeDevice,
      onDeviceModelChange,
      addAntenna,
      removeAntenna,
      generateDeviceId,
      generateEnrollmentToken,
      closeAddRunnerDialog,
      copyToClipboard,
      downloadConfig,
      showReEnrollDialog,
      generateReEnrollToken,
      closeReEnrollDialog,
      downloadReEnrollConfig,
      showReEnrollListenerDialog,
      generateReEnrollListenerToken,
      closeReEnrollListenerDialog,
      downloadReEnrollListenerConfig,
      enableRunner,
      disableRunner,
      enableListener,
      disableListener,
      kickRunner,
      kickListener,
      handleRunnerAction,
      handleListenerAction,
      addListenerDialogVisible,
      addListenerForm,
      listenerEnrollmentData,
      editListenerDevicesDialogVisible,
      editListenerForm,
      showEditListenerDevicesDialog,
      saveListenerDevices,
      showAddListenerDialog,
      addListenerDevice,
      removeListenerDevice,
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
      formatTimestamp: formatDateTime,
      // Frequency formatting helpers
      formatFrequency,
      formatFrequencyLimits,
      // Icons
      ArrowDown,
      SwitchIcon,
      Tools,
      Key,
      Delete
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

.antennas-section {
  margin-top: 15px;
}

.antennas-section h4 {
  margin-bottom: 10px;
  font-weight: 600;
}

.antenna-card {
  margin-bottom: 10px;
}

.antenna-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.hint-text {
  font-size: 12px;
  color: #666;
  margin-top: 4px;
}
</style>
