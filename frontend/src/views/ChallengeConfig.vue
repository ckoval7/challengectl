<template>
  <div class="challenge-config">
    <h1>Manage Challenges</h1>

    <el-tabs
      v-model="activeTab"
      type="border-card"
    >
      <!-- Live Status Tab (REWRITTEN) -->
      <el-tab-pane
        label="Live Status"
        name="status"
      >
        <!-- Mobile View: Card-based layout -->
        <div
          v-if="isMobile"
          class="cards-layout"
        >
          <TransitionGroup name="challenge-list">
            <ChallengeCard
              v-for="challenge in sortedChallenges"
              :key="challenge.challenge_id"
              :challenge="challenge"
              :recordings="getRecordings(challenge.challenge_id)"
              :placeholders="getPlaceholders(challenge.challenge_id)"
              :system-paused="systemPaused"
              @toggle-enabled="toggleEnabled"
              @trigger="triggerChallenge"
              @edit="editChallenge"
              @delete="deleteChallenge"
            />
          </TransitionGroup>
        </div>

        <!-- Desktop View: Table with expandable rows -->
        <el-table
          v-else
          :data="sortedChallenges"
          row-key="challenge_id"
          :expand-row-keys="expandedRowKeys"
          class="w-full"
          @expand-change="handleExpandChange"
        >
          <el-table-column type="expand">
            <template #default="props">
              <div class="recordings-section">
                <h3>Recordings</h3>
                <RecordingGallery
                  :recordings="getRecordings(props.row.challenge_id)"
                  :placeholders="getPlaceholders(props.row.challenge_id)"
                  :max-recordings="6"
                />
                <div
                  v-if="shouldShowViewAllLink(props.row.challenge_id)"
                  class="view-all-link"
                >
                  <router-link :to="`/recordings/${props.row.challenge_id}`">
                    View All {{ props.row.recording_count }} Recordings →
                  </router-link>
                </div>
              </div>
            </template>
          </el-table-column>
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
            width="250"
          >
            <template #default="scope">
              <template v-if="scope.row.config?.frequency">
                {{ formatFrequency(scope.row.config.frequency) }}
              </template>
              <template v-else-if="scope.row.config?.frequency_ranges">
                <el-tooltip
                  :content="formatFrequencyRanges(scope.row.config.frequency_ranges)"
                  placement="top"
                >
                  <el-tag
                    type="info"
                    size="small"
                  >
                    <template v-if="scope.row.config.frequency_ranges.length === 1">
                      {{ formatFrequencyRanges(scope.row.config.frequency_ranges) }}
                    </template>
                    <template v-else>
                      {{ scope.row.config.frequency_ranges.length }} ranges
                    </template>
                  </el-tag>
                </el-tooltip>
              </template>
              <template v-else-if="scope.row.config?.manual_frequency_range">
                <el-tag
                  type="warning"
                  size="small"
                >
                  Custom: {{ formatFrequency(scope.row.config.manual_frequency_range.min_hz) }} - {{ formatFrequency(scope.row.config.manual_frequency_range.max_hz) }}
                </el-tag>
              </template>
              <template v-else>
                N/A
              </template>
            </template>
          </el-table-column>
          <el-table-column
            label="Status"
            width="100"
          >
            <template #default="scope">
              <el-tag
                :type="getStatusType(scope.row)"
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
                :model-value="scope.row.enabled"
                @change="(val) => toggleEnabled(scope.row.challenge_id, val)"
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
                :disabled="systemPaused"
                @click="triggerChallenge(scope.row.challenge_id)"
              >
                Trigger Now
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- Playlist Tab (REWRITTEN) -->
      <el-tab-pane
        label="Playlist"
        name="playlist"
      >
        <div class="playlist-description">
          <p>View the transmission queue order and recording schedule for all enabled challenges.</p>
        </div>

        <!-- Mobile View: Card-based layout -->
        <div
          v-if="isMobile"
          class="cards-layout playlist-cards"
        >
          <TransitionGroup name="playlist">
            <ChallengeCard
              v-for="challenge in playlistChallenges"
              :key="challenge.challenge_id"
              :challenge="challenge"
              :recordings="getRecordings(challenge.challenge_id)"
              :placeholders="getPlaceholders(challenge.challenge_id)"
              :system-paused="systemPaused"
              :show-toggle="false"
              @toggle-enabled="toggleEnabled"
              @trigger="triggerChallenge"
              @edit="editChallenge"
              @delete="deleteChallenge"
            />
          </TransitionGroup>
        </div>

        <!-- Desktop View: Table -->
        <el-table
          v-else
          :data="playlistChallenges"
          :default-sort="{ prop: 'queue_position', order: 'ascending' }"
          class="w-full playlist-table"
        >
          <el-table-column
            prop="queue_position"
            label="Queue #"
            width="90"
            align="center"
          >
            <template #default="scope">
              <el-tag
                v-if="scope.row.queue_position"
                :type="scope.row.queue_position === 1 ? 'danger' : scope.row.queue_position <= 3 ? 'warning' : 'info'"
                size="large"
              >
                #{{ scope.row.queue_position }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            prop="name"
            label="Challenge Name"
            width="250"
          >
            <template #default="scope">
              <strong v-if="scope.row.queue_position === 1">{{ scope.row.name }}</strong>
              <span v-else>{{ scope.row.name }}</span>
            </template>
          </el-table-column>
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
            width="180"
          >
            <template #default="scope">
              {{ scope.row.assigned_frequency ? formatFrequency(scope.row.assigned_frequency)
                 : scope.row.config?.frequency ? formatFrequency(scope.row.config.frequency)
                 : 'N/A' }}
            </template>
          </el-table-column>
          <el-table-column
            label="Priority"
            width="120"
            align="center"
          >
            <template #default="scope">
              <el-tag
                :type="getPriorityType(scope.row.dynamic_priority || scope.row.priority)"
                size="small"
              >
                {{ formatDynamicPriority(scope.row) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            label="Status"
            width="120"
          >
            <template #default="scope">
              <el-tag
                :type="getStatusType(scope.row)"
                size="small"
              >
                {{ scope.row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            label="Next Available"
            width="180"
          >
            <template #default="scope">
              <span :class="{ 'ready-now': !scope.row.next_available_time }">
                {{ formatNextAvailable(scope.row.next_available_time) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column
            label="Recording Priority"
            width="150"
            align="center"
          >
            <template #default="scope">
              <div class="recording-priority-cell">
                <el-tag
                  :type="getRecordingPriorityType(scope.row.recording_priority)"
                  size="small"
                >
                  {{ formatRecordingPriority(scope.row.recording_priority) }}
                </el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column
            label="Will Record"
            width="120"
            align="center"
          >
            <template #default="scope">
              <el-tag
                :type="scope.row.will_be_recorded ? 'success' : ''"
                size="small"
              >
                {{ scope.row.will_be_recorded ? 'Yes' : 'No' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- Create/Edit Challenge Tab (PRESERVED) -->
      <el-tab-pane
        label="Create Challenge"
        name="create"
      >
        <el-form
          ref="formRef"
          :model="challengeForm"
          label-width="180px"
          class="form-container"
        >
          <h3>Basic Information</h3>

          <el-form-item
            label="Challenge Name"
            required
          >
            <el-input
              v-model="challengeForm.name"
              placeholder="e.g., NBFM_FLAG_1"
            />
          </el-form-item>

          <el-form-item
            label="Modulation"
            required
          >
            <el-select
              v-model="challengeForm.modulation"
              placeholder="Select modulation"
              @change="onModulationChange"
            >
              <el-option
                label="NBFM (Narrowband FM)"
                value="nbfm"
              />
              <el-option
                label="SSB (Single Sideband)"
                value="ssb"
              />
              <el-option
                label="FreeDV"
                value="freedv"
              />
              <el-option
                label="CW (Morse Code)"
                value="cw"
              />
              <el-option
                label="ASK (Amplitude Shift Keying)"
                value="ask"
              />
              <el-option
                label="POCSAG (Pager)"
                value="pocsag"
              />
              <el-option
                label="FHSS (Frequency Hopping)"
                value="fhss"
              />
              <el-option
                label="LRS Pager"
                value="lrs"
              />
            </el-select>
          </el-form-item>

          <el-form-item
            label="Frequency Mode"
            required
          >
            <el-radio-group v-model="frequencyMode">
              <el-radio label="direct">
                Single Frequency
              </el-radio>
              <el-radio label="ranges">
                Named Ranges
              </el-radio>
              <el-radio label="manual">
                Manual Range
              </el-radio>
            </el-radio-group>
          </el-form-item>

          <el-form-item
            v-if="frequencyMode === 'direct'"
            label="Frequency (MHz)"
            required
          >
            <el-input-number
              v-model="challengeForm.frequency_mhz"
              :min="1"
              :max="6000"
              :step="0.001"
              :precision="3"
              class="w-full"
            />
          </el-form-item>

          <el-form-item
            v-if="frequencyMode === 'manual'"
            label="Custom Frequency Range (MHz)"
            required
          >
            <div style="display: flex; gap: 10px; align-items: center;">
              <el-input-number
                v-model="challengeForm.manual_min_mhz"
                placeholder="Min MHz"
                :min="1"
                :max="6000"
                :step="0.001"
                :precision="3"
                style="flex: 1; min-width: 180px;"
              />
              <span>to</span>
              <el-input-number
                v-model="challengeForm.manual_max_mhz"
                placeholder="Max MHz"
                :min="1"
                :max="6000"
                :step="0.001"
                :precision="3"
                style="flex: 1; min-width: 180px;"
              />
            </div>
            <div class="text-sm text-gray-500 mt-5">
              A random frequency will be selected within this range for each transmission
            </div>
          </el-form-item>

          <el-form-item
            v-if="frequencyMode === 'ranges'"
            label="Named Frequency Ranges"
            required
          >
            <div style="display: flex; gap: 8px; align-items: flex-start;">
              <el-select
                v-model="challengeForm.frequency_ranges"
                multiple
                :placeholder="availableFrequencyRanges.length === 0 ? 'No ranges available - click Reload' : 'Select one or more ranges...'"
                style="flex: 1; min-width: 350px; width: 100%;"
                popper-class="frequency-ranges-dropdown"
                collapse-tags
                collapse-tags-tooltip
              >
                <template v-if="availableFrequencyRanges.length === 0">
                  <el-option
                    disabled
                    value=""
                    label="No frequency ranges configured"
                  />
                </template>
                <el-option
                  v-for="range in availableFrequencyRanges"
                  v-else
                  :key="range.name"
                  :label="range.display_name || range.name"
                  :value="range.name"
                >
                  <span style="font-weight: 500">{{ range.display_name || range.name }}</span>
                  <span style="color: var(--el-text-color-secondary); font-size: 12px; margin-left: 8px">
                    {{ range.description }}
                  </span>
                </el-option>
              </el-select>
              <el-tooltip
                content="Reload frequency ranges from config file"
                placement="top"
              >
                <el-button
                  :icon="loadingRanges ? 'Loading' : 'Refresh'"
                  :loading="loadingRanges"
                  @click="reloadFrequencyRanges"
                >
                  Reload
                </el-button>
              </el-tooltip>
            </div>
            <div class="text-sm text-gray-500 mt-5">
              A random frequency will be selected from the chosen range(s) for each transmission
            </div>
          </el-form-item>

          <el-form-item label="Enabled">
            <el-switch v-model="challengeForm.enabled" />
          </el-form-item>

          <h3>Challenge Content</h3>

          <el-form-item
            v-if="['nbfm', 'ssb', 'freedv', 'fhss'].includes(challengeForm.modulation)"
            label="Flag (Audio File)"
          >
            <el-input
              v-model="challengeForm.flag"
              placeholder="Path to WAV file or upload below"
            />
            <el-upload
              ref="flagUploadRef"
              :auto-upload="false"
              :limit="1"
              accept=".wav"
              @change="handleFlagFileChange"
            >
              <el-button
                size="small"
                class="mt-10"
              >
                Choose File
              </el-button>
            </el-upload>
          </el-form-item>

          <el-form-item
            v-if="['cw', 'ask', 'pocsag'].includes(challengeForm.modulation)"
            label="Flag (Text)"
          >
            <el-input
              v-model="challengeForm.flag"
              type="textarea"
              :rows="3"
              placeholder="Enter flag text"
            />
          </el-form-item>

          <el-form-item
            v-if="challengeForm.modulation === 'lrs'"
            label="Flag (Arguments)"
          >
            <el-input
              v-model="challengeForm.flag"
              placeholder="e.g., -s 10 -p 976 -pf 1"
            />
            <div
              class="text-xs mt-5"
              style="color: var(--el-color-info)"
            >
              LRS pager arguments: -s &lt;systemid 0-255&gt; -p &lt;pagerid 0-1023&gt; -pf &lt;function&gt;<br>
              Function codes: 1=Flash/Vibe 30s, 4=Beep 3x, 10=Flash/Vibe 1s, 2=Flash 5min, 3=Flash/Beep 5x5, 5=Beep 5min, 6=Glow 5min, 7=Glow/Vib 15x, 68=Beep 3x
            </div>
          </el-form-item>

          <h3>Timing Configuration</h3>

          <el-form-item
            label="Min Delay (seconds)"
            required
          >
            <el-input-number
              v-model="challengeForm.min_delay"
              :min="1"
              :max="challengeForm.max_delay"
              class="w-full"
            />
            <div
              v-if="challengeForm.min_delay > challengeForm.max_delay"
              class="text-xs mt-5"
              style="color: var(--el-color-danger)"
            >
              Min delay must be less than or equal to max delay
            </div>
          </el-form-item>

          <el-form-item
            label="Max Delay (seconds)"
            required
          >
            <el-input-number
              v-model="challengeForm.max_delay"
              :min="challengeForm.min_delay"
              :max="3600"
              class="w-full"
            />
            <div
              v-if="challengeForm.max_delay < challengeForm.min_delay"
              class="text-xs mt-5"
              style="color: var(--el-color-danger)"
            >
              Max delay must be greater than or equal to min delay
            </div>
          </el-form-item>

          <el-form-item label="Priority">
            <el-input-number
              v-model="challengeForm.priority"
              :min="0"
              :max="100"
              class="w-full"
            />
            <div class="hint-text">
              Higher priority challenges are transmitted first (higher number = higher priority)
            </div>
          </el-form-item>

          <h3>Public Dashboard Visibility</h3>

          <el-form-item label="Public Fields">
            <el-checkbox-group v-model="challengeForm.public_fields">
              <el-checkbox label="name">
                Name
              </el-checkbox>
              <el-checkbox label="modulation">
                Modulation
              </el-checkbox>
              <el-checkbox label="frequency">
                Frequency
              </el-checkbox>
              <el-checkbox label="status">
                Status
              </el-checkbox>
              <el-checkbox label="last_tx_time">
                Last TX Time
              </el-checkbox>
            </el-checkbox-group>
            <div class="hint-text">
              Select which fields are visible on the public dashboard
            </div>
          </el-form-item>

          <h3 v-if="showModulationSpecificFields">
            Modulation-Specific Settings
          </h3>

          <!-- NBFM/SSB/FreeDV/FHSS settings -->
          <el-form-item
            v-if="['nbfm', 'ssb', 'freedv', 'fhss'].includes(challengeForm.modulation)"
            label="WAV Sample Rate"
          >
            <el-input-number
              v-model="challengeForm.wav_samplerate"
              :min="8000"
              :max="192000"
              :step="1000"
              class="w-full"
            />
          </el-form-item>

          <!-- SSB settings -->
          <el-form-item
            v-if="challengeForm.modulation === 'ssb'"
            label="Mode"
          >
            <el-select
              v-model="challengeForm.mode"
              placeholder="Select sideband mode"
              class="w-full"
            >
              <el-option
                label="USB (Upper Sideband)"
                value="usb"
              />
              <el-option
                label="LSB (Lower Sideband)"
                value="lsb"
              />
            </el-select>
            <div class="hint-text">
              USB is typically used above 10 MHz, LSB below 10 MHz
            </div>
          </el-form-item>

          <!-- FreeDV settings -->
          <el-form-item
            v-if="challengeForm.modulation === 'freedv'"
            label="Mode"
          >
            <el-select
              v-model="challengeForm.mode"
              placeholder="Select sideband mode"
              class="w-full"
            >
              <el-option
                label="USB (Upper Sideband)"
                value="usb"
              />
              <el-option
                label="LSB (Lower Sideband)"
                value="lsb"
              />
            </el-select>
            <div class="hint-text">
              USB is typically used above 10 MHz, LSB below 10 MHz
            </div>
          </el-form-item>

          <!-- CW settings -->
          <el-form-item
            v-if="challengeForm.modulation === 'cw'"
            label="Speed (WPM)"
          >
            <el-input-number
              v-model="challengeForm.speed"
              :min="5"
              :max="60"
              class="w-full"
            />
          </el-form-item>

          <!-- FHSS settings -->
          <template v-if="challengeForm.modulation === 'fhss'">
            <el-form-item label="Channel Spacing (Hz)">
              <el-input-number
                v-model="challengeForm.channel_spacing"
                :min="1000"
                :max="1000000"
                :step="1000"
                class="w-full"
              />
            </el-form-item>

            <el-form-item label="Hop Rate (Hz)">
              <el-input-number
                v-model="challengeForm.hop_rate"
                :min="1"
                :max="1000"
                class="w-full"
              />
            </el-form-item>

            <el-form-item label="Hop Time (seconds)">
              <el-input-number
                v-model="challengeForm.hop_time"
                :min="1"
                :max="300"
                class="w-full"
              />
            </el-form-item>

            <el-form-item label="Seed">
              <el-input
                v-model="challengeForm.seed"
                placeholder="Hopping sequence seed"
              />
            </el-form-item>
          </template>

          <el-form-item>
            <el-button
              type="primary"
              @click="createChallenge"
            >
              Create Challenge
            </el-button>
            <el-button @click="resetForm">
              Reset
            </el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <!-- Import from YAML Tab (PRESERVED) -->
      <el-tab-pane
        label="Import from YAML"
        name="import"
      >
        <div class="form-container">
          <el-alert
            title="Import Challenges"
            type="info"
            :closable="false"
            class="mb-xl"
          >
            Upload a YAML file containing challenge definitions along with any associated files
            (audio files, binary files, etc.). This can also be used for automation via API.
          </el-alert>

          <h3>YAML File</h3>
          <el-upload
            ref="yamlUploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".yml,.yaml"
            @change="handleYamlChange"
          >
            <el-button type="primary">
              Select YAML File
            </el-button>
          </el-upload>

          <h3 class="mt-30">
            Challenge Files (Optional)
          </h3>
          <p class="text-sm text-secondary">
            Upload audio files, binary files, or other resources referenced in your YAML.
            File paths in the YAML will be automatically updated.
          </p>

          <el-upload
            ref="filesUploadRef"
            :auto-upload="false"
            multiple
            accept=".wav,.bin,.txt,.py,.grc"
            :file-list="challengeFiles"
            @change="handleFilesChange"
          >
            <el-button>Add Files</el-button>
          </el-upload>

          <div class="mt-30">
            <el-button
              type="primary"
              :disabled="!yamlFile"
              :loading="importing"
              @click="importChallenges"
            >
              Import Challenges
            </el-button>
            <el-button @click="clearImportForm">
              Clear
            </el-button>
          </div>

          <el-divider />

          <h3>API Endpoint for Automation</h3>
          <el-alert
            type="success"
            :closable="false"
            class="mb-10"
          >
            <div>
              <strong>POST /api/challenges/import</strong>
            </div>
            <div
              class="mt-10 text-xs"
              style="font-family: monospace"
            >
              Content-Type: multipart/form-data<br>
              Required: yaml_file (YAML file)<br>
              Optional: Additional files referenced in YAML
            </div>
          </el-alert>

          <el-collapse>
            <el-collapse-item
              title="Example cURL Command"
              name="curl"
            >
              <pre class="code-example"><code>curl -X POST http://localhost:8080/api/challenges/import \
  -H "X-CSRF-Token: YOUR_CSRF_TOKEN" \
  -b "session=YOUR_SESSION_COOKIE" \
  -F "yaml_file=@challenges.yml" \
  -F "example_voice.wav=@/path/to/example_voice.wav" \
  -F "flag_data.bin=@/path/to/flag_data.bin"</code></pre>
            </el-collapse-item>

            <el-collapse-item
              title="Example Python Script"
              name="python"
            >
              <pre class="code-example"><code>import requests

url = "http://localhost:8080/api/challenges/import"
files = {
    'yaml_file': open('challenges.yml', 'rb'),
    'example_voice.wav': open('example_voice.wav', 'rb'),
}
cookies = {'session': 'YOUR_SESSION_COOKIE'}
headers = {'X-CSRF-Token': 'YOUR_CSRF_TOKEN'}

response = requests.post(url, files=files, cookies=cookies, headers=headers)
print(response.json())</code></pre>
            </el-collapse-item>
          </el-collapse>
        </div>
      </el-tab-pane>

      <!-- Manage Challenges Tab (PRESERVED) -->
      <el-tab-pane
        label="Manage Challenges"
        name="manage"
      >
        <div class="mb-xl">
          <el-button
            type="success"
            @click="loadChallenges"
          >
            Refresh List
          </el-button>
        </div>

        <el-table
          :data="sortedChallenges"
          class="w-full"
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
            width="250"
          >
            <template #default="scope">
              <template v-if="scope.row.config?.frequency">
                {{ formatFrequency(scope.row.config.frequency) }}
              </template>
              <template v-else-if="scope.row.config?.frequency_ranges">
                <el-tooltip
                  :content="formatFrequencyRanges(scope.row.config.frequency_ranges)"
                  placement="top"
                >
                  <el-tag
                    type="info"
                    size="small"
                  >
                    <template v-if="scope.row.config.frequency_ranges.length === 1">
                      {{ formatFrequencyRanges(scope.row.config.frequency_ranges) }}
                    </template>
                    <template v-else>
                      {{ scope.row.config.frequency_ranges.length }} ranges
                    </template>
                  </el-tag>
                </el-tooltip>
              </template>
              <template v-else-if="scope.row.config?.manual_frequency_range">
                <el-tag
                  type="warning"
                  size="small"
                >
                  Custom: {{ formatFrequency(scope.row.config.manual_frequency_range.min_hz) }} - {{ formatFrequency(scope.row.config.manual_frequency_range.max_hz) }}
                </el-tag>
              </template>
              <template v-else>
                N/A
              </template>
            </template>
          </el-table-column>
          <el-table-column
            label="Status"
            width="100"
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
            label="TX Count"
            width="100"
          >
            <template #default="scope">
              {{ scope.row.transmission_count || 0 }}
            </template>
          </el-table-column>
          <el-table-column
            label="Actions"
            min-width="180"
          >
            <template #default="scope">
              <el-button
                size="small"
                type="primary"
                @click="editChallenge(scope.row)"
              >
                Edit
              </el-button>
              <el-popconfirm
                title="Are you sure you want to delete this challenge?"
                @confirm="deleteChallenge(scope.row.challenge_id)"
              >
                <template #reference>
                  <el-button
                    size="small"
                    type="danger"
                  >
                    Delete
                  </el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- Edit Challenge Dialog -->
    <el-dialog
      v-model="editDialogVisible"
      title="Edit Challenge"
      width="800px"
    >
      <el-form
        :model="editForm"
        label-width="180px"
      >
        <el-form-item label="Challenge Name">
          <el-input
            v-model="editForm.name"
            disabled
          />
        </el-form-item>

        <el-form-item label="Configuration (JSON)">
          <el-input
            v-model="editConfigJson"
            type="textarea"
            :rows="15"
            style="font-family: monospace"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="editDialogVisible = false">
          Cancel
        </el-button>
        <el-button
          type="primary"
          @click="saveEditedChallenge"
        >
          Save
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../api'
import { websocket } from '../websocket'
import { formatDateTime, parseServerTime } from '../utils/time'
import { useBreakpoint } from '../composables/useBreakpoint.js'
import ChallengeCard from '../components/ChallengeCard.vue'
import RecordingGallery from '../components/RecordingGallery.vue'

// Composables
const { isMobile } = useBreakpoint()

// UI State
const activeTab = ref('status')
const systemPaused = ref(false)
const importing = ref(false)
const loadingRanges = ref(false)
const editDialogVisible = ref(false)
const editForm = ref({})
const editConfigJson = ref('')

// WebSocket-first state management with Maps
const challengesMap = ref(new Map())
const recordingsMap = ref(new Map())
const recordingPlaceholders = ref(new Map())
const expandedChallenges = ref(new Set())

// Frequency ranges
const availableFrequencyRanges = ref([])
const frequencyMode = ref('direct')

// Create form
const challengeForm = ref({
  name: '',
  modulation: 'nbfm',
  frequency_mhz: 146.550,
  frequency_ranges: [],
  manual_min_mhz: null,
  manual_max_mhz: null,
  enabled: true,
  flag: '',
  min_delay: 60,
  max_delay: 90,
  priority: 0,
  public_fields: ['name', 'modulation', 'frequency', 'status'],
  wav_samplerate: 48000,
  mode: 'usb',
  speed: 35,
  channel_spacing: 10000,
  hop_rate: 10,
  hop_time: 60,
  seed: '',
})

const flagFile = ref(null)
const flagUploadRef = ref(null)

// Import form
const yamlFile = ref(null)
const challengeFiles = ref([])
const yamlUploadRef = ref(null)
const filesUploadRef = ref(null)

// Computed properties
const showModulationSpecificFields = computed(() => {
  return challengeForm.value.modulation !== ''
})

// Sorted challenges: enabled first (alphabetically), then disabled (alphabetically)
const sortedChallenges = computed(() => {
  const challenges = Array.from(challengesMap.value.values())
  return challenges.sort((a, b) => {
    if (a.enabled !== b.enabled) {
      return b.enabled - a.enabled // Enabled first
    }
    return (a.name || '').localeCompare(b.name || '')
  })
})

// Playlist challenges: enabled only, sorted by queue_position
const playlistChallenges = computed(() => {
  const challenges = Array.from(challengesMap.value.values())
  return challenges
    .filter(c => c.enabled && c.queue_position !== null)
    .sort((a, b) => (a.queue_position || 999) - (b.queue_position || 999))
})

// Computed property for expanded row keys (for el-table expand state persistence)
const expandedRowKeys = computed(() => {
  return Array.from(expandedChallenges.value)
})

// Helper functions to get recordings and placeholders
function getRecordings(challengeId) {
  return recordingsMap.value.get(challengeId) || []
}

function getPlaceholders(challengeId) {
  return recordingPlaceholders.value.get(challengeId) || []
}

function shouldShowViewAllLink(challengeId) {
  // Use the actual recording_count from the challenge data
  const challenge = challengesMap.value.get(challengeId)
  return challenge && challenge.recording_count > 6
}

// Client-side queue position calculator (matches server logic)
function recalculateQueuePositions() {
  // Get all enabled challenges that are in the queue
  const allChallenges = Array.from(challengesMap.value.values())
  const queueableChallenges = allChallenges.filter(c =>
    c.enabled && ['queued', 'waiting', 'assigned'].includes(c.status)
  )

  // Sort using playlist order logic:
  // 1. Challenges at position 0 (just assigned) go to top
  // 2. Regular challenges sorted by priority in the middle
  // 3. Challenges at position 999999 (just completed) go to bottom
  const sorted = queueableChallenges.sort((a, b) => {
    const aPos = a.queue_position || 0
    const bPos = b.queue_position || 0

    // Challenges marked for top (position 0) come first
    if (aPos === 0 && bPos !== 0) return -1
    if (bPos === 0 && aPos !== 0) return 1

    // Challenges marked for bottom (position 999999) come last
    if (aPos === 999999 && bPos !== 999999) return 1
    if (bPos === 999999 && aPos !== 999999) return -1

    // For all others, sort by dynamic priority (highest first)
    const aPriority = a.dynamic_priority !== undefined ? a.dynamic_priority : a.priority || 0
    const bPriority = b.dynamic_priority !== undefined ? b.dynamic_priority : b.priority || 0

    if (aPriority !== bPriority) {
      return bPriority - aPriority
    }

    // Finally, alphabetically by name (ASC)
    return (a.name || '').localeCompare(b.name || '')
  })

  // Assign queue positions to sorted challenges
  sorted.forEach((challenge, index) => {
    challenge.queue_position = index + 1
    challengesMap.value.set(challenge.challenge_id, challenge)
  })

  // Clear queue_position for challenges not in queue
  allChallenges.forEach(challenge => {
    if (!challenge.enabled || !['queued', 'waiting', 'assigned'].includes(challenge.status)) {
      challenge.queue_position = null
      challengesMap.value.set(challenge.challenge_id, challenge)
    }
  })

  console.log('Queue positions recalculated:', sorted.map(c => ({
    name: c.name,
    queue_position: c.queue_position,
    dynamic_priority: c.dynamic_priority,
    priority: c.priority,
    last_tx_time: c.last_tx_time
  })))
}

// Data loading
async function loadChallenges() {
  try {
    const response = await api.get('/challenges')
    const challenges = response.data.challenges || []

    // Populate Map
    challengesMap.value.clear()
    challenges.forEach(challenge => {
      challengesMap.value.set(challenge.challenge_id, {
        ...challenge,
        enabled: Boolean(challenge.enabled)
      })
    })

    // Load initial recordings for each challenge (most recent 6)
    for (const challenge of challenges) {
      await loadChallengeRecordings(challenge.challenge_id)
    }
  } catch (error) {
    console.error('Failed to load challenges:', error)
    ElMessage.error('Failed to load challenges')
  }
}

async function loadChallengeRecordings(challengeId) {
  try {
    const response = await api.get(`/challenges/${challengeId}/recordings`, {
      params: { limit: 6 }
    })
    const recordings = response.data.recordings || []
    recordingsMap.value.set(challengeId, recordings)
  } catch (error) {
    console.error(`Failed to load recordings for challenge ${challengeId}:`, error)
    recordingsMap.value.set(challengeId, [])
  }
}

async function loadFrequencyRanges() {
  try {
    const response = await api.get('/frequency-ranges')
    availableFrequencyRanges.value = response.data || []
  } catch (error) {
    console.error('Failed to load frequency ranges:', error)
  }
}

async function reloadFrequencyRanges() {
  loadingRanges.value = true
  try {
    const response = await api.post('/frequency-ranges/reload')
    availableFrequencyRanges.value = response.data.ranges || []
    ElMessage.success(`Reloaded ${response.data.count} frequency ranges`)
  } catch (error) {
    console.error('Failed to reload frequency ranges:', error)
    ElMessage.error(error.response?.data?.error || 'Failed to reload frequency ranges')
  } finally {
    loadingRanges.value = false
  }
}

// WebSocket event handlers (granular updates)
function handleRecordingStarted(event) {
  console.log('Recording started:', event)
  const { challenge_id, recording_id, listener_id, frequency } = event

  // Add placeholder
  const placeholders = recordingPlaceholders.value.get(challenge_id) || []
  const newPlaceholder = {
    recording_id,
    listener_id,
    frequency,
    status: 'in_progress'
  }

  // Create new array reference to trigger Vue reactivity
  recordingPlaceholders.value.set(challenge_id, [newPlaceholder, ...placeholders])
}

function handleRecordingComplete(event) {
  console.log('Recording complete:', event)
  const { challenge_id, recording_id, status } = event

  // Update placeholder status
  const placeholders = recordingPlaceholders.value.get(challenge_id) || []
  const placeholder = placeholders.find(p => p.recording_id === recording_id)
  if (placeholder) {
    placeholder.status = status
    // Create new array reference to trigger Vue reactivity
    recordingPlaceholders.value.set(challenge_id, [...placeholders])
  }
}

function handleRecordingImageUploaded(event) {
  console.log('Recording image uploaded:', event)
  const { challenge_id, recording_id, width, height, image_url, started_at, timestamp } = event

  if (!challenge_id || !recording_id) {
    console.warn('Missing required fields in recording_image_uploaded event:', event)
    return
  }

  // Remove placeholder
  const placeholders = recordingPlaceholders.value.get(challenge_id) || []
  const filteredPlaceholders = placeholders.filter(p => p.recording_id !== recording_id)
  recordingPlaceholders.value.set(challenge_id, filteredPlaceholders)

  // Create recording object from event data
  const recording = {
    recording_id,
    challenge_id,
    status: 'completed',
    image_path: image_url,  // The server sends image_url
    image_width: width,
    image_height: height,
    started_at: started_at,
    completed_at: timestamp
  }

  // Add to recordings list (prepend to show newest first)
  const recordings = recordingsMap.value.get(challenge_id) || []

  // Create new array reference to trigger Vue reactivity
  const updatedRecordings = [recording, ...recordings]

  // Keep only most recent 6
  if (updatedRecordings.length > 6) {
    updatedRecordings.splice(6)
  }

  recordingsMap.value.set(challenge_id, updatedRecordings)
}

function handleChallengeUpdated(event) {
  console.log('Challenge updated:', event)
  const { challenge } = event

  // Update single challenge in Map
  if (challenge && challenge.challenge_id) {
    challengesMap.value.set(challenge.challenge_id, {
      ...challenge,
      enabled: Boolean(challenge.enabled)
    })

    // Recalculate queue positions (enabled/priority/status may have changed)
    recalculateQueuePositions()
  }
}

function handleChallengeAssigned(event) {
  console.log('Challenge assigned:', event)
  const { challenge_id, runner_id, status, frequency } = event

  // Update challenge status
  const challenge = challengesMap.value.get(challenge_id)
  if (challenge) {
    const previousStatus = challenge.status
    challenge.status = status || 'assigned'
    challenge.assigned_to = runner_id
    // Store the actual selected frequency for display in playlist
    if (frequency) {
      challenge.assigned_frequency = frequency
    }

    // Move to top of playlist when transitioning to assigned
    if (previousStatus !== 'assigned' && (previousStatus === 'waiting' || previousStatus === 'queued')) {
      // Set a very low position to move to top
      challenge.queue_position = 0
    }

    challengesMap.value.set(challenge_id, challenge)

    // Recalculate queue positions to renumber everything
    recalculateQueuePositions()
  }
}

function handleTransmissionComplete(event) {
  console.log('Transmission complete:', event)
  const { challenge_id, success, recording_priority, will_be_recorded, challenge: updatedChallenge } = event

  const challenge = challengesMap.value.get(challenge_id)
  if (challenge && updatedChallenge) {
    const previousStatus = challenge.status
    // Use full updated challenge data from server (includes fresh dynamic_priority, status, etc.)
    const updated = {
      ...updatedChallenge,
      enabled: Boolean(updatedChallenge.enabled),
      recording_priority,
      will_be_recorded
    }

    // Move to bottom of playlist when transitioning from assigned to waiting
    if (previousStatus === 'assigned' && updated.status === 'waiting') {
      // Set a very high position to move to bottom
      updated.queue_position = 999999
    }

    challengesMap.value.set(challenge_id, updated)
  } else if (challenge) {
    // Fallback to local update if server didn't send full challenge data
    const previousStatus = challenge.status
    challenge.transmission_count = (challenge.transmission_count || 0) + 1
    challenge.status = 'waiting'  // Server always sets to 'waiting' after completion
    challenge.last_tx_time = new Date().toISOString()

    // Clear the assigned frequency since transmission is complete
    delete challenge.assigned_frequency

    // Update recording priority from server calculation
    if (recording_priority !== undefined) {
      challenge.recording_priority = recording_priority
    }
    if (will_be_recorded !== undefined) {
      challenge.will_be_recorded = will_be_recorded
    }

    // Move to bottom of playlist when transitioning from assigned to waiting
    if (previousStatus === 'assigned') {
      challenge.queue_position = 999999
    }

    challengesMap.value.set(challenge_id, challenge)
  }

  // Recalculate queue positions with fresh dynamic_priority values
  recalculateQueuePositions()
}

// Challenge actions
async function toggleEnabled(challengeId, enabled) {
  const challenge = challengesMap.value.get(challengeId)
  if (!challenge) return

  const previousEnabled = challenge.enabled

  // Wait for switch component to complete its DOM update before triggering re-sort
  // This prevents the "can't access property 'checked', d.value is null" error
  await nextTick()
  await new Promise(resolve => setTimeout(resolve, 100))

  // Now update local state (this triggers table re-sort via sortedChallenges computed)
  challenge.enabled = enabled
  challengesMap.value.set(challengeId, challenge)
  recalculateQueuePositions()

  // Make API call in background
  try {
    await api.post(`/challenges/${challengeId}/enable`, { enabled })
    ElMessage.success(`Challenge ${enabled ? 'enabled' : 'disabled'}`)
  } catch (error) {
    console.error('Error toggling challenge:', error)
    ElMessage.error('Failed to update challenge')

    // Rollback on error
    await new Promise(resolve => setTimeout(resolve, 100))
    challenge.enabled = previousEnabled
    challengesMap.value.set(challengeId, challenge)
    recalculateQueuePositions()
  }
}

async function triggerChallenge(challengeId) {
  try {
    await api.post(`/challenges/${challengeId}/trigger`)
    ElMessage.success('Challenge triggered')
    loadChallenges()
  } catch (error) {
    console.error('Error triggering challenge:', error)
    ElMessage.error('Failed to trigger challenge')
  }
}

function editChallenge(challenge) {
  editForm.value = { ...challenge }
  editConfigJson.value = JSON.stringify(challenge.config, null, 2)
  editDialogVisible.value = true
}

async function saveEditedChallenge() {
  try {
    const config = JSON.parse(editConfigJson.value)
    await api.put(`/challenges/${editForm.value.challenge_id}`, { config })
    ElMessage.success('Challenge updated successfully')
    editDialogVisible.value = false
    loadChallenges()
  } catch (error) {
    console.error('Failed to update challenge:', error)
    if (error instanceof SyntaxError) {
      ElMessage.error('Invalid JSON format')
    } else {
      ElMessage.error(error.response?.data?.error || 'Failed to update challenge')
    }
  }
}

async function deleteChallenge(challengeId) {
  try {
    await api.delete(`/challenges/${challengeId}`)
    ElMessage.success('Challenge deleted successfully')
    challengesMap.value.delete(challengeId)
    recordingsMap.value.delete(challengeId)
    recordingPlaceholders.value.delete(challengeId)
  } catch (error) {
    console.error('Failed to delete challenge:', error)
    ElMessage.error(error.response?.data?.error || 'Failed to delete challenge')
  }
}

// Form handlers (preserved from backup)
function onModulationChange() {
  challengeForm.value.flag = ''
  flagFile.value = null
  if (flagUploadRef.value) {
    flagUploadRef.value.clearFiles()
  }
}

function handleFlagFileChange(file) {
  flagFile.value = file.raw
}

function handleYamlChange(file) {
  yamlFile.value = file.raw
}

function handleFilesChange(file, fileList) {
  challengeFiles.value = fileList
}

function resetForm() {
  challengeForm.value = {
    name: '',
    modulation: 'nbfm',
    frequency_mhz: 146.550,
    frequency_ranges: [],
    manual_min_mhz: null,
    manual_max_mhz: null,
    enabled: true,
    flag: '',
    min_delay: 60,
    max_delay: 90,
    priority: 0,
    public_fields: ['name', 'modulation', 'frequency', 'status'],
    wav_samplerate: 48000,
    mode: 'usb',
    speed: 35,
    channel_spacing: 10000,
    hop_rate: 10,
    hop_time: 60,
    seed: '',
  }
  frequencyMode.value = 'direct'
  flagFile.value = null
  if (flagUploadRef.value) {
    flagUploadRef.value.clearFiles()
  }
}

function clearImportForm() {
  yamlFile.value = null
  challengeFiles.value = []
  if (yamlUploadRef.value) {
    yamlUploadRef.value.clearFiles()
  }
  if (filesUploadRef.value) {
    filesUploadRef.value.clearFiles()
  }
}

function convertPublicFieldsToView(publicFields) {
  const fields = publicFields || []
  return {
    show_modulation: fields.includes('modulation'),
    show_frequency: fields.includes('frequency'),
    show_last_tx_time: fields.includes('last_tx_time'),
    show_active_status: fields.includes('status')
  }
}

async function createChallenge() {
  if (!challengeForm.value.name) {
    ElMessage.error('Challenge name is required')
    return
  }

  if (!challengeForm.value.modulation) {
    ElMessage.error('Modulation is required')
    return
  }

  // Validate frequency
  if (frequencyMode.value === 'direct') {
    if (!challengeForm.value.frequency_mhz) {
      ElMessage.error('Frequency is required')
      return
    }
  } else if (frequencyMode.value === 'ranges') {
    if (!challengeForm.value.frequency_ranges || challengeForm.value.frequency_ranges.length === 0) {
      ElMessage.error('At least one frequency range is required')
      return
    }
  } else if (frequencyMode.value === 'manual') {
    if (!challengeForm.value.manual_min_mhz || !challengeForm.value.manual_max_mhz) {
      ElMessage.error('Both minimum and maximum frequencies are required')
      return
    }
    if (challengeForm.value.manual_min_mhz >= challengeForm.value.manual_max_mhz) {
      ElMessage.error('Minimum frequency must be less than maximum frequency')
      return
    }
  }

  if (challengeForm.value.min_delay > challengeForm.value.max_delay) {
    ElMessage.error('Min delay must be less than or equal to max delay')
    return
  }

  try {
    const config = {
      name: challengeForm.value.name,
      modulation: challengeForm.value.modulation,
      enabled: challengeForm.value.enabled,
      min_delay: challengeForm.value.min_delay,
      max_delay: challengeForm.value.max_delay,
      priority: challengeForm.value.priority,
      public_view: convertPublicFieldsToView(challengeForm.value.public_fields),
    }

    // Add frequency
    if (frequencyMode.value === 'direct') {
      config.frequency = Math.round(challengeForm.value.frequency_mhz * 1000000)
    } else if (frequencyMode.value === 'ranges') {
      config.frequency_ranges = challengeForm.value.frequency_ranges
    } else if (frequencyMode.value === 'manual') {
      config.manual_frequency_range = {
        min_hz: Math.round(challengeForm.value.manual_min_mhz * 1000000),
        max_hz: Math.round(challengeForm.value.manual_max_mhz * 1000000)
      }
    }

    // Handle file upload
    if (flagFile.value) {
      try {
        const formData = new FormData()
        formData.append('file', flagFile.value)
        const uploadResponse = await api.post('/files/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })
        config.flag_file_hash = uploadResponse.data.file_hash
        if (!challengeForm.value.flag) {
          config.flag = uploadResponse.data.filename
        }
      } catch (uploadError) {
        console.error('Failed to upload file:', uploadError)
        ElMessage.error(uploadError.response?.data?.error || 'Failed to upload file')
        return
      }
    }

    if (challengeForm.value.flag && !flagFile.value) {
      config.flag = challengeForm.value.flag
    }

    // Add modulation-specific fields
    if (['nbfm', 'ssb', 'freedv', 'fhss'].includes(challengeForm.value.modulation)) {
      config.wav_samplerate = challengeForm.value.wav_samplerate
    }
    if (['ssb', 'freedv'].includes(challengeForm.value.modulation)) {
      config.mode = challengeForm.value.mode
    }
    if (challengeForm.value.modulation === 'cw') {
      config.speed = challengeForm.value.speed
    }
    if (challengeForm.value.modulation === 'fhss') {
      config.channel_spacing = challengeForm.value.channel_spacing
      config.hop_rate = challengeForm.value.hop_rate
      config.hop_time = challengeForm.value.hop_time
      if (challengeForm.value.seed) {
        config.seed = challengeForm.value.seed
      }
    }

    await api.post('/challenges', {
      name: challengeForm.value.name,
      config: config
    })

    ElMessage.success('Challenge created successfully')
    resetForm()
    loadChallenges()
    activeTab.value = 'manage'
  } catch (error) {
    console.error('Failed to create challenge:', error)
    ElMessage.error(error.response?.data?.error || 'Failed to create challenge')
  }
}

async function importChallenges() {
  if (!yamlFile.value) {
    ElMessage.error('Please select a YAML file')
    return
  }

  importing.value = true

  try {
    const formData = new FormData()
    formData.append('yaml_file', yamlFile.value)

    challengeFiles.value.forEach(file => {
      formData.append(file.name, file.raw)
    })

    const response = await api.post('/challenges/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })

    const result = response.data
    let message = `Imported successfully: ${result.added} added, ${result.updated} updated`
    if (result.files_uploaded > 0) {
      message += `, ${result.files_uploaded} files uploaded`
    }

    ElMessage.success(message)

    if (result.errors && result.errors.length > 0) {
      ElMessage.warning(`Some errors occurred: ${result.errors.join(', ')}`)
    }

    clearImportForm()
    loadChallenges()
    activeTab.value = 'manage'
  } catch (error) {
    console.error('Failed to import challenges:', error)
    ElMessage.error(error.response?.data?.error || 'Failed to import challenges')
  } finally {
    importing.value = false
  }
}

// Expand/collapse tracking
function handleExpandChange(row, expandedRows) {
  if (expandedRows.includes(row)) {
    expandedChallenges.value.add(row.challenge_id)
  } else {
    expandedChallenges.value.delete(row.challenge_id)
  }
}

// Formatting helpers
function formatFrequency(freq) {
  if (!freq) return 'N/A'
  if (freq >= 1000000000) {
    return `${(freq / 1000000000).toFixed(3)} GHz`
  } else if (freq >= 1000000) {
    return `${(freq / 1000000).toFixed(3)} MHz`
  } else if (freq >= 1000) {
    return `${(freq / 1000).toFixed(3)} kHz`
  }
  return `${freq} Hz`
}

function getDisplayNameForRange(rangeName) {
  const range = availableFrequencyRanges.value.find(r => r.name === rangeName)
  return range?.display_name || rangeName
}

function formatFrequencyRanges(ranges) {
  if (!ranges || ranges.length === 0) return 'N/A'
  return ranges.map(r => getDisplayNameForRange(r)).join(', ')
}

function formatNextAvailable(isoTimestamp) {
  if (!isoTimestamp) {
    return 'Ready now'
  }

  const targetTime = parseServerTime(isoTimestamp)
  const now = new Date()
  const diffMs = targetTime - now

  if (diffMs <= 0) {
    return 'Ready now'
  }

  const diffSec = Math.floor(diffMs / 1000)
  const diffMin = Math.floor(diffSec / 60)
  const diffHour = Math.floor(diffMin / 60)
  const diffDay = Math.floor(diffHour / 24)

  if (diffDay > 0) {
    return `Ready in ${diffDay}d ${diffHour % 24}h`
  } else if (diffHour > 0) {
    return `Ready in ${diffHour}h ${diffMin % 60}m`
  } else if (diffMin > 0) {
    return `Ready in ${diffMin}m`
  } else {
    return `Ready in ${diffSec}s`
  }
}

function formatRecordingPriority(priority) {
  if (priority === null || priority === undefined) {
    return 'N/A'
  }
  if (priority >= 1000) {
    return '1000+'
  }
  return priority.toFixed(1)
}

function getRecordingPriorityType(priority) {
  if (priority === null || priority === undefined) {
    return 'info'
  }
  if (priority >= 1000) {
    return 'danger'
  } else if (priority >= 10) {
    return 'warning'
  } else if (priority >= 1.0) {
    return 'success'
  } else {
    return 'info'
  }
}

function formatDynamicPriority(challenge) {
  const dynamic = challenge.dynamic_priority
  const base = challenge.priority || 0

  if (dynamic === undefined || dynamic === null) {
    return base.toString()
  }

  // Show the dynamic priority value
  // If it's significantly different from base (boosted by time), show both
  const boost = dynamic - base
  if (boost >= 1.0) {
    return `${Math.round(dynamic)} (${base}+${Math.round(boost)}m)`
  }

  return Math.round(dynamic).toString()
}

function getPriorityType(priority) {
  if (priority >= 100) {
    return 'danger'
  } else if (priority >= 75) {
    return 'danger'
  } else if (priority >= 50) {
    return 'warning'
  } else if (priority >= 25) {
    return 'success'
  } else {
    return 'info'
  }
}

function getStatusType(challenge) {
  if (!challenge.enabled) return 'info'
  switch (challenge.status) {
    case 'queued': return 'success'
    case 'waiting': return 'warning'
    case 'assigned': return ''
    default: return 'info'
  }
}

function handleSystemControl(event) {
  console.log('System control:', event)
  const { action } = event
  systemPaused.value = action === 'pause'
}

function handleInitialState(data) {
  console.log('Received initial state in ChallengeConfig')
  if (data.stats && typeof data.stats.paused !== 'undefined') {
    systemPaused.value = data.stats.paused
  }
}

async function fetchSystemStatus() {
  try {
    const response = await api.get('/control/status')
    systemPaused.value = response.data.paused
  } catch (error) {
    console.error('Failed to fetch system status:', error)
  }
}

const formatTimestamp = formatDateTime

// Lifecycle hooks
onMounted(() => {
  loadChallenges()
  loadFrequencyRanges()
  fetchSystemStatus()

  // WebSocket setup
  websocket.connect()
  websocket.on('recording_started', handleRecordingStarted)
  websocket.on('recording_complete', handleRecordingComplete)
  websocket.on('recording_image_uploaded', handleRecordingImageUploaded)
  websocket.on('challenge_updated', handleChallengeUpdated)
  websocket.on('challenge_assigned', handleChallengeAssigned)
  websocket.on('transmission_complete', handleTransmissionComplete)
  websocket.on('system_control', handleSystemControl)
  websocket.on('initial_state', handleInitialState)
})

onUnmounted(() => {
  websocket.off('recording_started', handleRecordingStarted)
  websocket.off('recording_complete', handleRecordingComplete)
  websocket.off('recording_image_uploaded', handleRecordingImageUploaded)
  websocket.off('challenge_updated', handleChallengeUpdated)
  websocket.off('challenge_assigned', handleChallengeAssigned)
  websocket.off('transmission_complete', handleTransmissionComplete)
  websocket.off('system_control', handleSystemControl)
  websocket.off('initial_state', handleInitialState)
})
</script>

<style scoped>
.challenge-config {
  padding: 20px;
}

h1 {
  margin-bottom: 20px;
}

h3 {
  margin-top: 20px;
  margin-bottom: 15px;
  color: var(--el-text-color-primary);
  font-weight: 600;
}

.el-tabs {
  margin-top: 20px;
}

.code-example {
  background: var(--el-fill-color-light);
  padding: 15px;
  border-radius: 4px;
  overflow-x: auto;
  color: var(--el-text-color-primary);
}

/* Cards layout for mobile */
.cards-layout {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* Recordings section in expanded rows */
.recordings-section {
  padding: 20px;
  background-color: var(--el-fill-color-lighter);
  border-radius: 4px;
  margin: 10px 0;
}

.recordings-section h3 {
  margin-top: 0;
  margin-bottom: 15px;
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

/* Playlist Tab Styles */
.playlist-description {
  margin-bottom: 20px;
  padding: 15px;
  background-color: var(--el-fill-color-light);
  border-radius: 4px;
}

.playlist-description p {
  margin: 0;
  color: var(--el-text-color-regular);
}

.playlist-table {
  margin-top: 10px;
}

.playlist-table .el-table__row:first-child {
  font-weight: bold;
  background-color: var(--el-fill-color-lighter);
}

.ready-now {
  color: var(--el-color-success);
  font-weight: 600;
}

.recording-priority-cell {
  display: flex;
  justify-content: center;
  align-items: center;
}

/* Smooth table row transitions for desktop view */
.el-table__row {
  transition: all 0.6s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

/* Animations for mobile card view */
.challenge-list-move,
.challenge-list-enter-active,
.challenge-list-leave-active {
  transition: all 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

.challenge-list-enter-from {
  opacity: 0;
  transform: translateY(-30px) scale(0.95);
}

.challenge-list-leave-to {
  opacity: 0;
  transform: translateY(30px) scale(0.95);
}

.challenge-list-leave-active {
  position: absolute;
  width: 100%;
}

.playlist-move,
.playlist-enter-active,
.playlist-leave-active {
  transition: all 0.4s cubic-bezier(0.55, 0, 0.1, 1);
}

.playlist-enter-from {
  opacity: 0;
  transform: scaleY(0.8);
}

.playlist-leave-to {
  opacity: 0;
  transform: scaleY(0.8);
}

/* Dark mode adjustments */
html.dark .code-example {
  background: #2d2d2d;
  color: var(--el-text-color-primary);
  border: 1px solid var(--el-border-color);
}

html.dark .recordings-section {
  background-color: var(--el-fill-color-dark);
}

html.dark .playlist-description {
  background-color: var(--el-fill-color-dark);
}

html.dark .playlist-description p {
  color: var(--el-text-color-regular);
}
</style>

<style>
/* Non-scoped styles for dropdown popper */
.frequency-ranges-dropdown {
  min-width: 400px !important;
  max-width: 600px !important;
}

.frequency-ranges-dropdown .el-select-dropdown__item {
  height: auto !important;
  min-height: 34px;
  padding: 8px 20px !important;
  white-space: normal !important;
  line-height: 1.4;
}
</style>
