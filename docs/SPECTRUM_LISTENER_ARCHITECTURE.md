# Spectrum Listener Architecture

## Overview

The Spectrum Listener system adds passive RF monitoring capabilities to challengectl, allowing automated capture and visualization of challenge transmissions. This creates a library of waterfall images for each challenge, useful for debugging, documentation, and verification.

## Design Goals

1. **Passive Monitoring**: Listen to challenges without interfering with transmissions
2. **Smart Scheduling**: Prioritize challenges that haven't been recorded recently
3. **Resource Efficiency**: Handle disproportionate listener-to-transmitter ratios
4. **Quality Waterfall Images**: Generate high-quality, zoomable waterfall visualizations
5. **UI Integration**: Seamlessly display recordings in the challenge management interface
6. **Persistence**: Store recordings with metadata for historical reference

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    ChallengeCtl Server                      │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Unified Agent Management System                       │  │
│  │  - Track all agents (transmitters & listeners)       │  │
│  │  - Calculate recording priorities                     │  │
│  │  - Coordinate transmitter-listener pairs             │  │
│  │  - Store waterfall images and metadata               │  │
│  │  - Shared provisioning & enrollment                  │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Database Schema Updates                               │  │
│  │  - agents table (unified runners + listeners)        │  │
│  │  - recordings table (waterfall metadata)             │  │
│  │  - listener_assignments table (active recordings)    │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
      HTTP Polling    HTTP Polling    HTTP Polling
           │               │               │
           ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │ Agent 1  │    │ Agent 2  │    │ Agent 3  │
    │(HackRF)  │    │(RTL-SDR) │    │(BladeRF) │
    │TX Only   │    │RX Only   │    │RX Only   │
    │type:     │    │type:     │    │type:     │
    │runner    │    │listener  │    │listener  │
    └──────────┘    └──────────┘    └──────────┘
         │                │               │
         │ Transmits      │ Records       │ Records
         ▼                ▼               ▼
    ┌──────────────────────────────────────────┐
    │         RF Spectrum (e.g., 2m band)      │
    └──────────────────────────────────────────┘
```

**Key Architectural Change:** Runners and listeners are unified as "agents" with a `type` field. This simplifies provisioning, management, and UI display while maintaining their distinct roles.

## Component Design

### 1. Listener Client (`listener.py`)

A new Python client similar to `runner.py` but specialized for receiving:

**Responsibilities:**
- Register with server as a listener (not a runner)
- Poll for recording assignments
- Capture IQ samples using osmocom source block
- Generate waterfall images from captured data
- Upload completed waterfalls to server
- Report recording status (started, completed, failed)

**Key Differences from Runner:**
- No GNU Radio transmit flowgraphs
- Single receive flowgraph with configurable parameters
- Generates PNG waterfall images
- Monitors for assignment start/stop signals

**Configuration (`listener-config.yml`):**
```yaml
agent:
  agent_id: "listener-1"          # Unique identifier
  agent_type: "listener"          # Type: 'runner' or 'listener'
  server_url: "https://192.168.1.100:8443"
  api_key: "agent-key-1"          # Shared provisioning with runners

  heartbeat_interval: 30
  poll_interval: 5                # Check more frequently than runners

  recording:
    output_dir: "recordings"      # Where to store waterfall images
    sample_rate: 2000000          # 2 MHz (match transmitter)
    fft_size: 1024                # FFT bins for waterfall
    frame_rate: 20                # Waterfall frames per second
    gain: 40                      # RF gain

radio:
  model: rtlsdr                   # RTL-SDR is cheap, ideal for listeners
  device: "rtl=0"
  frequency_limits:
    - "144000000-148000000"       # 2m band
    - "420000000-450000000"       # 70cm band
```

**Unified Provisioning:**
- Listeners use the same enrollment tokens as runners
- API keys work for both agent types
- Agent type is specified during registration
- Simplifies credential management

### 2. GNU Radio Flowgraph (`spectrum_listener.py`)

**Purpose:** Capture IQ samples and generate waterfall data

**Flow Graph:**
```
osmocom Source (RTL-SDR/BladeRF/etc)
        ↓
  [Set frequency, sample rate, gain]
        ↓
Stream to Vector (FFT size)
        ↓
FFT (Complex to Mag^2)
        ↓
Log10 Converter
        ↓
Keep One in N (decimation for frame rate)
        ↓
Vector Sink / File Sink
        ↓
[Python: Generate waterfall image]
```

**Implementation Details:**
- Use `gr.fft_vcc` for frequency domain conversion
- Use `blocks.complex_to_mag_squared` for power calculation
- Use `blocks.nlog10_ff` for dB conversion
- Store FFT frames in memory buffer
- Generate PNG on completion using matplotlib/PIL

**Dynamic Control:**
- Frequency set based on challenge assignment
- Duration calculated from challenge transmission time estimates
- Add pre-roll (5s before) and post-roll (5s after) for complete capture

### 3. Server Extensions

#### 3.1 Database Schema Updates

**Unified agents table (replaces existing runners table):**

The existing `runners` table is renamed/extended to `agents` to support both transmitters and listeners:

```sql
-- Migration: Rename runners to agents and add type column
ALTER TABLE runners RENAME TO agents;
ALTER TABLE agents ADD COLUMN agent_type TEXT DEFAULT 'runner';  -- 'runner' or 'listener'

-- Updated schema:
CREATE TABLE agents (
    agent_id TEXT PRIMARY KEY,            -- Replaces runner_id/listener_id
    agent_type TEXT NOT NULL,             -- 'runner' or 'listener'
    hostname TEXT,
    ip_address TEXT,
    mac_address TEXT,                     -- For host validation
    machine_id TEXT,                      -- For host validation
    status TEXT,                          -- 'online', 'offline'
    enabled BOOLEAN,                      -- Can receive assignments
    last_heartbeat TIMESTAMP,
    devices JSON,                         -- Array of device capabilities (existing)
    api_key_hash TEXT,                    -- Bcrypt hash
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Create indexes for common queries
CREATE INDEX idx_agents_type_status ON agents(agent_type, status);
CREATE INDEX idx_agents_enabled ON agents(enabled);
```

**Benefits of Unified Schema:**
- Single enrollment/provisioning workflow
- Simplified API endpoints (agents instead of runners/listeners)
- Easier UI management (one "Agents" page)
- Agents can potentially support both roles in future

**recordings table:**
```sql
CREATE TABLE recordings (
    recording_id INTEGER PRIMARY KEY AUTOINCREMENT,
    challenge_id TEXT,
    agent_id TEXT,                         -- References agents table (listener)
    transmission_id INTEGER,               -- Links to specific transmission
    frequency INTEGER,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT,                           -- 'recording', 'completed', 'failed'
    image_path TEXT,                       -- Path to waterfall PNG
    image_width INTEGER,
    image_height INTEGER,
    sample_rate INTEGER,
    duration_seconds REAL,
    error_message TEXT,
    FOREIGN KEY (challenge_id) REFERENCES challenges(challenge_id),
    FOREIGN KEY (agent_id) REFERENCES agents(agent_id),
    FOREIGN KEY (transmission_id) REFERENCES transmissions(transmission_id)
);

-- Indexes for common queries
CREATE INDEX idx_recordings_challenge ON recordings(challenge_id);
CREATE INDEX idx_recordings_agent ON recordings(agent_id);
CREATE INDEX idx_recordings_completed_at ON recordings(completed_at);
```

**listener_assignments table:**
```sql
CREATE TABLE listener_assignments (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT,                         -- References agents table (listener)
    challenge_id TEXT,
    transmission_id INTEGER,
    frequency INTEGER,
    assigned_at TIMESTAMP,
    expected_start TIMESTAMP,              -- When transmission will begin
    expected_duration REAL,                -- Estimated seconds
    status TEXT,                           -- 'assigned', 'recording', 'completed'
    FOREIGN KEY (agent_id) REFERENCES agents(agent_id),
    FOREIGN KEY (challenge_id) REFERENCES challenges(challenge_id),
    FOREIGN KEY (transmission_id) REFERENCES transmissions(transmission_id)
);

-- Indexes
CREATE INDEX idx_listener_assignments_agent ON listener_assignments(agent_id);
CREATE INDEX idx_listener_assignments_status ON listener_assignments(status);
```

**Note:** The existing `challenges` table's `assigned_to` field references `runners.runner_id`. After migration, this should reference `agents.agent_id` for consistency.

#### 3.2 API Endpoints

**Updated Agent Endpoints (unified runners + listeners):**

The existing runner endpoints are extended to support both agent types:

```
POST /api/agents/register
  - Register agent (runner or listener) with server
  - Request body: {
      agent_id,
      agent_type,      # 'runner' or 'listener'
      hostname,
      devices          # Array of device capabilities
    }
  - Response: {status: "success", message: "Registered"}
  - Replaces: /api/runners/register and /api/listeners/register

POST /api/agents/{id}/heartbeat
  - Send periodic heartbeat (works for both types)
  - Request body: {status, timestamp}
  - Response: {status: "success"}
  - Replaces: /api/runners/{id}/heartbeat and /api/listeners/{id}/heartbeat

POST /api/agents/{id}/signout
  - Graceful signout on shutdown (both types)
  - Response: {status: "success"}
  - Replaces: /api/runners/{id}/signout

GET /api/agents/{id}/task
  - Poll for task assignment (runner agents only)
  - Response: {challenge details} or empty
  - Existing endpoint, unchanged behavior

POST /api/agents/{id}/complete
  - Report task completion (runner agents only)
  - Request body: {success, device_id, frequency, error_message}
  - Response: {status: "success"}
  - Existing endpoint, unchanged behavior

GET /api/agents/{id}/assignment
  - Poll for recording assignments (listener agents only)
  - Response: {
      assignment_id,
      challenge_id,
      challenge_name,
      frequency,
      expected_start,  # ISO timestamp
      expected_duration,
      modulation_type
    }
  - Returns empty if no assignment
  - New endpoint for listeners

POST /api/agents/{id}/recording_started
  - Report recording has begun (listener agents only)
  - Request body: {assignment_id, actual_start_time}
  - Response: {status: "success"}

POST /api/agents/{id}/recording_complete
  - Report recording finished (listener agents only)
  - Request body: {
      assignment_id,
      duration,
      samples_captured
    }
  - Response: {upload_url, recording_id}

POST /api/agents/{id}/recording_failed
  - Report recording failure (listener agents only)
  - Request body: {assignment_id, error_message}
  - Response: {status: "success"}

POST /api/agents/{id}/log
  - Forward log entries to server (both types)
  - Existing endpoint, unchanged
```

**Recording Endpoints:**
```
POST /api/recordings/{id}/upload
  - Upload waterfall image (multipart/form-data)
  - File field: "waterfall"
  - Response: {status: "success", image_url}
```

**Admin Endpoints (require admin auth):**
```
GET /api/agents
  - List all agents (runners + listeners)
  - Query params: type (optional: 'runner' or 'listener')
  - Response: {agents: [...]}
  - Replaces: GET /api/runners

GET /api/agents/{id}
  - Get detailed agent information
  - Response: {agent details, current_assignment, statistics}
  - Replaces: GET /api/runners/{id}

POST /api/agents/{id}/enable
  - Enable agent to receive assignments
  - Response: {status: "success"}
  - Replaces: POST /api/runners/{id}/enable

POST /api/agents/{id}/disable
  - Disable agent from receiving tasks/assignments
  - Response: {status: "success"}
  - Replaces: POST /api/runners/{id}/disable

DELETE /api/agents/{id}
  - Kick agent (forcefully disconnect)
  - Response: {status: "success"}
  - Replaces: DELETE /api/runners/{id}

GET /api/recordings
  - List all recordings with pagination
  - Query params: challenge_id, agent_id, page, per_page
  - Response: {recordings: [...], total, page, per_page}

GET /api/recordings/{id}
  - Get recording details
  - Response: {recording metadata + image_url}

GET /api/recordings/{id}/image
  - Serve waterfall image file
  - Response: PNG image (Content-Type: image/png)

DELETE /api/recordings/{id}
  - Delete a recording
  - Response: {status: "success"}

GET /api/challenges/{id}/recordings
  - Get all recordings for a specific challenge
  - Response: {recordings: [...]}
```

#### 3.3 Coordination Logic

**Recording Priority Algorithm:**

When a listener polls for an assignment, the server:

1. **Find eligible challenges:**
   - Status = 'queued' or 'assigned'
   - Enabled = true
   - Frequency within listener's capabilities

2. **Calculate priority score for each:**
   ```python
   def calculate_recording_priority(challenge):
       # Get most recent recording and transmission count
       last_recording = get_last_recording(challenge.challenge_id)
       transmissions_since_last_recording = get_transmissions_since_recording(
           challenge.challenge_id,
           last_recording.completed_at if last_recording else None
       )

       if last_recording is None:
           # Never recorded - highest priority
           return 1000

       # Time-based component (minutes since last recording)
       minutes_since = (now() - last_recording.completed_at).total_seconds() / 60

       # Transmission-based component
       # For high-frequency challenges (multiple per hour), this is more important
       # than pure time-based priority
       transmission_factor = transmissions_since_last_recording

       # Combined priority calculation
       # Base: Number of transmissions since last recording (primary factor)
       # Multiplier: Time decay (secondary factor)
       #
       # Examples (assuming ~10 transmissions/hour):
       # - 5 transmissions, 30 mins: priority = 5 * (30/60) = 2.5
       # - 20 transmissions, 2 hours: priority = 20 * (120/60) = 40
       # - 100 transmissions, 10 hours: priority = 100 * (600/60) = 1000 (capped)
       #
       # This ensures:
       # - Recently recorded challenges have low priority
       # - Challenges with many transmissions since recording get higher priority
       # - Very old recordings (even if few transmissions) still get recorded

       time_multiplier = min(10.0, minutes_since / 60.0)  # Cap at 10x for very old
       priority = transmission_factor * time_multiplier

       # Cap at reasonable maximum
       priority = min(1000, priority)

       # Boost based on challenge priority setting (1-100)
       # Allows manual prioritization of important challenges
       priority_multiplier = challenge.priority / 10.0
       priority *= priority_multiplier

       # Final clamp
       priority = min(1000, priority)

       return priority
   ```

   **Algorithm Rationale:**
   - **Transmission-based primary metric**: Since challenges transmit frequently (multiple times per hour), we don't need to record every transmission. Priority is based on how many transmissions have occurred since the last recording.
   - **Time-based multiplier**: Ensures old recordings get refreshed even if transmission count is low. Also provides diversity by naturally spreading recordings over time.
   - **Configurable weighting**: Challenge priority setting allows admins to boost specific challenges.
   - **Result**: Listeners naturally sample challenges periodically rather than recording every single transmission, while ensuring all challenges get recorded regularly.

3. **Select challenge with highest priority score**

4. **Check if challenge is currently assigned to a runner:**
   - If assigned: Create listener assignment synchronized with transmission
   - If queued: Wait for runner assignment (or assign both atomically)

5. **Create listener assignment:**
   - Record assignment in database
   - Return assignment details to listener
   - Set expected_start based on runner's assignment time

**Coordinated Assignment:**

When a runner agent is assigned a challenge:
```python
def assign_task_to_runner_agent(agent_id):
    with db.begin_immediate():
        # Assign challenge to runner agent (existing logic)
        challenge = assign_challenge(agent_id)

        if challenge:
            # Check if listener agents are available
            listener_agents = get_available_agents_for_frequency(
                challenge.frequency,
                agent_type='listener'
            )

            if listener_agents:
                # Calculate priority for each listener agent
                # Select listener with highest recording priority
                listener = select_listener_by_priority(listener_agents, challenge)

                create_listener_assignment(
                    listener.agent_id,
                    challenge.challenge_id,
                    transmission_id,
                    expected_start=now() + timedelta(seconds=10),  # Runner prep time
                    expected_duration=estimate_duration(challenge)
                )

    return challenge
```

**Duration Estimation:**

Estimate challenge duration based on modulation type:
```python
def estimate_duration(challenge):
    modulation = challenge.config.get('modulation')

    if modulation == 'cw':
        message_length = len(challenge.config.get('message', ''))
        wpm = challenge.config.get('wpm', 20)
        return (message_length * 60) / (wpm * 5) + 10  # +10s buffer

    elif modulation in ['nbfm', 'ssb', 'freedv']:
        # File-based: estimate from file size
        file_hash = challenge.config.get('flag', '').replace('sha256:', '')
        file_info = get_file_info(file_hash)
        # Assume typical audio duration
        return 180  # 3 minutes + buffer

    elif modulation == 'paint':
        return 10  # Spectrum paint is quick

    elif modulation == 'fhss':
        hop_count = challenge.config.get('num_hops', 10)
        dwell_time = challenge.config.get('dwell_time', 0.5)
        return hop_count * dwell_time + 10

    else:
        return 120  # Default 2 minutes
```

### 4. Frontend Integration

#### 4.1 Update Challenges View (`Challenges.vue`)

Add a new column to the challenges table:

```vue
<el-table-column
  label="Recordings"
  width="120"
>
  <template #default="scope">
    <el-badge
      :value="scope.row.recording_count || 0"
      :type="scope.row.recording_count > 0 ? 'success' : 'info'"
    >
      <el-button
        size="small"
        @click="viewRecordings(scope.row.challenge_id)"
      >
        View
      </el-button>
    </el-badge>
  </template>
</el-table-column>
```

#### 4.2 New Component: RecordingsModal.vue

Display waterfall images for a challenge:

```vue
<template>
  <el-dialog
    v-model="visible"
    title="Challenge Recordings"
    width="90%"
    :fullscreen="isFullscreen"
  >
    <!-- Toolbar -->
    <div class="recordings-toolbar">
      <el-button @click="isFullscreen = !isFullscreen">
        {{ isFullscreen ? 'Exit Fullscreen' : 'Fullscreen' }}
      </el-button>
      <el-button @click="zoomIn">Zoom In</el-button>
      <el-button @click="zoomOut">Zoom Out</el-button>
      <el-select v-model="selectedRecording" placeholder="Select recording">
        <el-option
          v-for="rec in recordings"
          :key="rec.recording_id"
          :label="formatRecordingLabel(rec)"
          :value="rec.recording_id"
        />
      </el-select>
    </div>

    <!-- Waterfall Display -->
    <div class="waterfall-container" ref="waterfallContainer">
      <div
        class="waterfall-wrapper"
        :style="{ transform: `scale(${zoom})` }"
      >
        <img
          v-if="currentRecording"
          :src="getImageUrl(currentRecording.recording_id)"
          :alt="`Waterfall for ${challengeName}`"
          class="waterfall-image"
          @load="onImageLoad"
        />

        <!-- Loading indicator -->
        <el-skeleton v-else :rows="10" animated />
      </div>
    </div>

    <!-- Metadata -->
    <div v-if="currentRecording" class="recording-metadata">
      <el-descriptions :column="3" border>
        <el-descriptions-item label="Recorded">
          {{ formatTimestamp(currentRecording.completed_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="Frequency">
          {{ formatFrequency(currentRecording.frequency) }}
        </el-descriptions-item>
        <el-descriptions-item label="Duration">
          {{ currentRecording.duration_seconds?.toFixed(1) }}s
        </el-descriptions-item>
        <el-descriptions-item label="Recorded By">
          {{ currentRecording.agent_id }}
        </el-descriptions-item>
        <el-descriptions-item label="Sample Rate">
          {{ formatSampleRate(currentRecording.sample_rate) }}
        </el-descriptions-item>
        <el-descriptions-item label="Image Size">
          {{ currentRecording.image_width }}x{{ currentRecording.image_height }}
        </el-descriptions-item>
      </el-descriptions>
    </div>
  </el-dialog>
</template>

<script>
export default {
  data() {
    return {
      visible: false,
      isFullscreen: false,
      zoom: 1.0,
      selectedRecording: null,
      recordings: [],
      challengeId: null,
      challengeName: null
    }
  },
  computed: {
    currentRecording() {
      return this.recordings.find(r => r.recording_id === this.selectedRecording)
    }
  },
  methods: {
    async open(challengeId, challengeName) {
      this.challengeId = challengeId
      this.challengeName = challengeName
      this.visible = true
      await this.loadRecordings()
    },

    async loadRecordings() {
      const response = await api.get(`/challenges/${this.challengeId}/recordings`)
      this.recordings = response.data.recordings
      if (this.recordings.length > 0) {
        // Select most recent by default
        this.selectedRecording = this.recordings[0].recording_id
      }
    },

    getImageUrl(recordingId) {
      return `/api/recordings/${recordingId}/image`
    },

    zoomIn() {
      this.zoom = Math.min(this.zoom * 1.2, 5.0)
    },

    zoomOut() {
      this.zoom = Math.max(this.zoom / 1.2, 0.5)
    },

    formatRecordingLabel(rec) {
      const date = new Date(rec.completed_at)
      return `${date.toLocaleString()} - ${rec.agent_id}`
    }
  }
}
</script>

<style scoped>
.waterfall-container {
  max-height: 70vh;
  overflow: auto;
  background: #1a1a1a;
  border: 1px solid #333;
  position: relative;
}

.waterfall-wrapper {
  transform-origin: top left;
  transition: transform 0.2s ease-out;
  display: inline-block;
}

.waterfall-image {
  display: block;
  width: 100%;
  height: auto;
  /* Images can be very tall, container scrolls */
}

.recordings-toolbar {
  margin-bottom: 15px;
  display: flex;
  gap: 10px;
  align-items: center;
}

.recording-metadata {
  margin-top: 20px;
  padding: 15px;
  background: #f5f5f5;
  border-radius: 4px;
}
</style>
```

**Key UI Features:**
- **Scrollable container**: Handles very tall waterfall images
- **Zoom controls**: In/Out buttons with smooth scaling
- **Fullscreen mode**: Maximize viewing area
- **Recording selector**: Dropdown to switch between recordings
- **Metadata display**: Show recording details below image
- **Dark background**: Better contrast for waterfall colors

#### 4.3 Updated View: Agents.vue (Replaces Runners.vue)

Unified view for managing all agents (runners + listeners):

```vue
<template>
  <div class="agents">
    <h1>Agents</h1>

    <!-- Filter controls -->
    <div class="mb-xl">
      <el-radio-group v-model="filterType" @change="loadAgents">
        <el-radio-button label="all">All Agents</el-radio-button>
        <el-radio-button label="runner">Runners</el-radio-button>
        <el-radio-button label="listener">Listeners</el-radio-button>
      </el-radio-group>
    </div>

    <el-table :data="filteredAgents" class="w-full">
      <el-table-column prop="agent_id" label="Agent ID" width="150" />

      <el-table-column label="Type" width="100">
        <template #default="scope">
          <el-tag :type="scope.row.agent_type === 'runner' ? 'primary' : 'success'">
            {{ scope.row.agent_type }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column label="Status" width="100">
        <template #default="scope">
          <el-tag :type="scope.row.status === 'online' ? 'success' : 'danger'">
            {{ scope.row.status }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column prop="hostname" label="Hostname" width="150" />

      <el-table-column label="Devices" width="120">
        <template #default="scope">
          <span v-if="scope.row.devices && scope.row.devices.length">
            {{ scope.row.devices[0]?.model || 'Unknown' }}
            <el-tag v-if="scope.row.devices.length > 1" size="small">
              +{{ scope.row.devices.length - 1 }}
            </el-tag>
          </span>
          <span v-else>No devices</span>
        </template>
      </el-table-column>

      <el-table-column label="Current Assignment" width="200">
        <template #default="scope">
          <span v-if="scope.row.current_assignment">
            {{ scope.row.current_assignment.challenge_name }}
          </span>
          <span v-else class="text-muted">Idle</span>
        </template>
      </el-table-column>

      <el-table-column label="Stats" width="150">
        <template #default="scope">
          <!-- For runners: transmission count -->
          <span v-if="scope.row.agent_type === 'runner'">
            TX: {{ scope.row.transmission_count || 0 }}
          </span>
          <!-- For listeners: recording count -->
          <span v-else>
            Rec: {{ scope.row.recording_count || 0 }}
          </span>
        </template>
      </el-table-column>

      <el-table-column label="Last Heartbeat" width="180">
        <template #default="scope">
          {{ formatTimestamp(scope.row.last_heartbeat) }}
        </template>
      </el-table-column>

      <el-table-column label="Enabled" width="100" align="center">
        <template #default="scope">
          <el-switch
            v-model="scope.row.enabled"
            @change="toggleAgent(scope.row)"
          />
        </template>
      </el-table-column>

      <el-table-column label="Actions" width="150">
        <template #default="scope">
          <el-button
            size="small"
            type="danger"
            @click="kickAgent(scope.row.agent_id)"
          >
            Kick
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'
import { ElMessage } from 'element-plus'
import { formatDateTime } from '../utils/time'

export default {
  name: 'Agents',
  setup() {
    const agents = ref([])
    const filterType = ref('all')

    const filteredAgents = computed(() => {
      if (filterType.value === 'all') {
        return agents.value
      }
      return agents.value.filter(a => a.agent_type === filterType.value)
    })

    const loadAgents = async () => {
      try {
        const params = filterType.value !== 'all' ? { type: filterType.value } : {}
        const response = await api.get('/agents', { params })
        agents.value = response.data.agents || []
      } catch (error) {
        console.error('Error loading agents:', error)
        ElMessage.error('Failed to load agents')
      }
    }

    const toggleAgent = async (agent) => {
      try {
        const endpoint = agent.enabled ? 'enable' : 'disable'
        await api.post(`/agents/${agent.agent_id}/${endpoint}`)
        ElMessage.success(`Agent ${agent.enabled ? 'enabled' : 'disabled'}`)
      } catch (error) {
        console.error('Error toggling agent:', error)
        ElMessage.error('Failed to update agent')
        loadAgents()  // Reload to reset state
      }
    }

    const kickAgent = async (agentId) => {
      try {
        await api.delete(`/agents/${agentId}`)
        ElMessage.success('Agent kicked')
        loadAgents()
      } catch (error) {
        console.error('Error kicking agent:', error)
        ElMessage.error('Failed to kick agent')
      }
    }

    onMounted(() => {
      loadAgents()
      // Refresh periodically
      const interval = setInterval(loadAgents, 15000)
      onUnmounted(() => clearInterval(interval))
    })

    return {
      agents,
      filterType,
      filteredAgents,
      loadAgents,
      toggleAgent,
      kickAgent,
      formatTimestamp: formatDateTime
    }
  }
}
</script>

<style scoped>
.agents {
  padding: 20px;
}

.text-muted {
  color: #909399;
  font-style: italic;
}
</style>
```

**Key Features:**
- **Type filtering**: Toggle between all/runners/listeners
- **Unified table**: Single view for all agent types
- **Type-specific stats**: Shows TX count for runners, recording count for listeners
- **Visual differentiation**: Color-coded tags for agent type
- **Shared actions**: Enable/disable and kick work for both types

### 5. Waterfall Image Generation

#### 5.1 Python Implementation

Use matplotlib to generate high-quality waterfall images:

```python
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

class WaterfallGenerator:
    def __init__(self, sample_rate, fft_size, frame_rate):
        self.sample_rate = sample_rate
        self.fft_size = fft_size
        self.frame_rate = frame_rate
        self.fft_frames = []

        # Create custom colormap (blue-green-yellow-red)
        self.colormap = LinearSegmentedColormap.from_list(
            'waterfall',
            ['#000033', '#0000ff', '#00ff00', '#ffff00', '#ff0000']
        )

    def add_fft_frame(self, fft_data):
        """Add a single FFT frame (array of power values in dB)"""
        self.fft_frames.append(fft_data)

    def generate_image(self, output_path, title=None):
        """Generate waterfall PNG from accumulated FFT frames"""
        if not self.fft_frames:
            raise ValueError("No FFT data to plot")

        # Convert list to 2D array (time x frequency)
        waterfall_data = np.array(self.fft_frames)

        # Determine image dimensions
        # Width: FFT size (frequency bins)
        # Height: Number of frames (time)
        height, width = waterfall_data.shape

        # Calculate aspect ratio to keep frequency axis readable
        # Target: ~1000 pixels wide, height proportional to duration
        dpi = 100
        fig_width = 10  # inches (1000 pixels at 100 DPI)
        fig_height = max(8, height / self.frame_rate * 2)  # At least 8 inches

        fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=dpi)

        # Plot waterfall
        extent = [
            -self.sample_rate / 2e6,  # Min freq (MHz, negative = below center)
            self.sample_rate / 2e6,   # Max freq (MHz, positive = above center)
            len(self.fft_frames) / self.frame_rate,  # Max time (seconds)
            0  # Min time (top of image)
        ]

        im = ax.imshow(
            waterfall_data,
            aspect='auto',
            cmap=self.colormap,
            interpolation='bilinear',
            extent=extent,
            vmin=np.percentile(waterfall_data, 5),   # Auto-scale: 5th percentile
            vmax=np.percentile(waterfall_data, 95)   # Auto-scale: 95th percentile
        )

        # Labels and formatting
        ax.set_xlabel('Frequency Offset (MHz)', fontsize=12)
        ax.set_ylabel('Time (seconds)', fontsize=12)
        if title:
            ax.set_title(title, fontsize=14, fontweight='bold')

        # Colorbar
        cbar = plt.colorbar(im, ax=ax, label='Power (dB)')

        # Tight layout to maximize plot area
        plt.tight_layout()

        # Save to file
        plt.savefig(output_path, dpi=dpi, bbox_inches='tight')
        plt.close(fig)

        return {
            'width': int(fig_width * dpi),
            'height': int(fig_height * dpi),
            'duration': len(self.fft_frames) / self.frame_rate
        }
```

#### 5.2 GNU Radio Integration

Modified `spectrum_listener.py` to capture FFT data:

```python
from gnuradio import gr, blocks, fft
import osmosdr
import numpy as np

class SpectrumListener(gr.top_block):
    def __init__(self, frequency, device, sample_rate, fft_size, gain):
        gr.top_block.__init__(self, "Spectrum Listener")

        self.waterfall_gen = WaterfallGenerator(sample_rate, fft_size, frame_rate=20)

        # Source
        self.osmosdr_source = osmosdr.source(args=device)
        self.osmosdr_source.set_sample_rate(sample_rate)
        self.osmosdr_source.set_center_freq(frequency, 0)
        self.osmosdr_source.set_gain(gain, 0)

        # FFT processing
        self.stream_to_vector = blocks.stream_to_vector(gr.sizeof_gr_complex, fft_size)
        self.fft = fft.fft_vcc(fft_size, True, window.blackmanharris(fft_size), True)
        self.complex_to_mag_sq = blocks.complex_to_mag_squared(fft_size)
        self.nlog10 = blocks.nlog10_ff(10, fft_size, 0)  # Convert to dB

        # Decimation for desired frame rate
        samples_per_frame = int(sample_rate / 20)  # 20 fps
        self.keep_one_in_n = blocks.keep_one_in_n(
            gr.sizeof_float * fft_size,
            samples_per_frame // fft_size
        )

        # Sink (capture to callback)
        self.vector_sink = blocks.vector_sink_f(fft_size)

        # Connect blocks
        self.connect(self.osmosdr_source, self.stream_to_vector)
        self.connect(self.stream_to_vector, self.fft)
        self.connect(self.fft, self.complex_to_mag_sq)
        self.connect(self.complex_to_mag_sq, self.nlog10)
        self.connect(self.nlog10, self.keep_one_in_n)
        self.connect(self.keep_one_in_n, self.vector_sink)

    def get_waterfall_data(self):
        """Extract FFT frames from vector sink"""
        data = np.array(self.vector_sink.data())
        num_frames = len(data) // self.fft_size

        for i in range(num_frames):
            frame = data[i * self.fft_size : (i + 1) * self.fft_size]
            # FFT shift to center DC
            frame = np.fft.fftshift(frame)
            self.waterfall_gen.add_fft_frame(frame)
```

### 6. Operational Workflow

#### 6.1 Typical Recording Scenario

```
1. Challenge "NBFM_FLAG_1" is queued
   ↓
2. Server assigns to Runner-1
   - Challenge status: queued → assigned
   - Runner-1 downloads files, prepares transmission
   ↓
3. Server checks for available listeners
   - Finds Listener-1 online and capable
   - Calculates priority: NBFM_FLAG_1 last recorded 3 days ago → High priority
   ↓
4. Server assigns to Listener-1
   - Creates listener_assignment record
   - expected_start: now + 10 seconds (runner prep time)
   - expected_duration: 180 seconds (estimated)
   ↓
5. Listener-1 receives assignment
   - Configures GNU Radio flowgraph
   - Sets frequency to match challenge
   - Starts recording 5 seconds early (pre-roll)
   - Reports: POST /recording_started
   ↓
6. Runner-1 begins transmission
   - Transmits challenge signal
   ↓
7. Listener-1 captures signal
   - GNU Radio receives and processes IQ samples
   - FFT frames accumulated in memory
   - Waterfall data building in real-time
   ↓
8. Transmission completes (3 minutes later)
   - Runner-1 reports completion
   - Listener-1 continues recording 5 seconds (post-roll)
   ↓
9. Listener-1 generates waterfall
   - Calls waterfall_gen.generate_image()
   - PNG file saved locally
   - Reports: POST /recording_complete
   ↓
10. Listener-1 uploads image
    - POST /recordings/{id}/upload (multipart form)
    - Server stores in files/waterfalls/{recording_id}.png
    ↓
11. Server updates database
    - recording status: recording → completed
    - image_path, dimensions, duration saved
    ↓
12. Admin views in WebUI
    - Challenges table shows recording_count badge
    - Click "View Recordings" opens modal
    - Waterfall displayed with zoom/scroll
```

#### 6.2 Priority Scheduling Example

Scenario: 10 challenges, 3 runner agents, 1 listener agent

Challenges transmit ~10 times per hour (every 6 minutes average)

```
Challenges with transmission history:
- NBFM_1: Last recorded 2 hours ago, 20 transmissions since
- NBFM_2: Last recorded 30 minutes ago, 5 transmissions since
- NBFM_3: Never recorded, 100+ transmissions total
- CW_1: Last recorded 10 minutes ago, 2 transmissions since
- CW_2: Never recorded, 50+ transmissions total
- SSB_1: Last recorded 4 hours ago, 40 transmissions since
- FHSS_1: Last recorded 1 hour ago, 10 transmissions since
- ... (3 more)

Priority Calculation (using updated algorithm):
1. NBFM_3: 1000 (never recorded - always highest priority)
2. CW_2: 1000 (never recorded)
3. SSB_1: ~267 (40 transmissions × (4 hours / 60 min / 60 min) = 40 × 6.67)
4. NBFM_1: ~67 (20 transmissions × (2 hours / 60 min / 60 min) = 20 × 3.33)
5. FHSS_1: ~17 (10 transmissions × (1 hour / 60 min / 60 min) = 10 × 1.67)
6. NBFM_2: ~4 (5 transmissions × (30 min / 60 min) = 5 × 0.5)
7. CW_1: ~0.3 (2 transmissions × (10 min / 60 min) = 2 × 0.17)

When listener agent polls:
- Server calculates priorities for all eligible challenges
- Selects NBFM_3 (highest priority, never recorded)
- If NBFM_3 not currently assigned to runner agent:
  - Wait for next assignment (or queue for next transmission)
- If NBFM_3 currently assigned to runner agent:
  - Create listener assignment immediately
  - Listener agent begins recording
- After recording NBFM_3:
  - NBFM_3 priority drops to 0 (just recorded)
  - Next poll will select CW_2 (next highest priority)

Result: Listener naturally rotates through all challenges, prioritizing:
- Challenges never recorded (immediate attention)
- Challenges with many transmissions since last recording
- Challenges not recorded in a long time (even if few transmissions)
```

### 7. Storage and Retention

#### 7.1 File Organization

```
files/
  waterfalls/
    1.png          # recording_id 1
    2.png          # recording_id 2
    3.png
    ...
```

#### 7.2 Retention Policy

**Option 1: Keep All Recordings**
- Simple: never delete
- Disk usage: ~500 KB per recording (estimated)
- 1000 recordings = ~500 MB
- Suitable for most deployments

**Option 2: Keep N Most Recent Per Challenge**
- Configurable limit (e.g., keep last 10)
- Automatically delete oldest when limit reached
- Saves disk space for long-running systems

**Option 3: Time-Based Retention**
- Delete recordings older than N days
- Configurable per challenge or globally
- Example: keep recordings from last 30 days

**Recommended:** Option 1 with manual cleanup interface

#### 7.3 Disk Space Estimation

Assumptions:
- Average waterfall: 1000x4000 pixels PNG = ~400 KB
- 10 challenges
- 100 transmissions per challenge per day
- 1 listener recording 20% of transmissions

Daily storage: 10 × 100 × 0.2 × 0.4 MB = **80 MB/day**

Monthly: **~2.4 GB/month**

Yearly: **~29 GB/year**

**Mitigation:**
- PNG compression (optimize for web)
- JPEG option for reduced quality/size
- Thumbnail generation for preview
- S3/object storage for long-term archival

### 8. Configuration Options

#### 8.1 Server Configuration (`server-config.yml`)

Add listener section:

```yaml
listeners:
  enabled: true

  # Coordination settings
  coordination:
    # Assign listeners to all transmissions, or only prioritized ones
    mode: priority  # 'all' or 'priority'

    # Minimum hours between recordings of same challenge
    min_hours_between_recordings: 24

    # Pre-roll and post-roll seconds
    pre_roll: 5
    post_roll: 5

  # Storage settings
  storage:
    waterfalls_dir: "files/waterfalls"
    max_recordings_per_challenge: 20  # 0 = unlimited
    retention_days: 0  # 0 = keep forever
```

### 9. Security Considerations

1. **Authentication:** Listeners use same API key system as runners
2. **Upload Size Limits:** Restrict waterfall image size (e.g., 10 MB max)
3. **File Validation:** Verify uploaded files are valid PNG images
4. **Path Traversal:** Sanitize recording_id in file paths
5. **Rate Limiting:** Prevent upload spam
6. **Access Control:** Only admins can view/delete recordings

### 10. Testing Strategy

#### 10.1 Unit Tests

- Waterfall generation with synthetic data
- Priority calculation algorithm
- Duration estimation for each modulation type

#### 10.2 Integration Tests

- Listener registration and heartbeat
- Assignment coordination
- Image upload and retrieval
- Recording metadata storage

#### 10.3 End-to-End Tests

- Full transmission + recording cycle
- Multiple listeners competing for assignments
- Priority-based selection
- UI display of recordings

### 11. Future Enhancements

1. **Real-Time Preview:** WebSocket stream of waterfall during recording
2. **Signal Analysis:** Automatic detection of signal features
3. **Thumbnail Generation:** Small preview images for table view
4. **Recording Comparison:** Side-by-side view of multiple recordings
5. **Export Options:** Download as JSON, CSV with metadata
6. **Automated Quality Metrics:** SNR, signal duration, frequency accuracy
7. **Demodulation Playback:** Decode and play back audio challenges
8. **Spectrogram Annotations:** Mark signal features, anomalies
9. **Multi-Listener Correlation:** Compare recordings from different locations
10. **Machine Learning:** Classify modulation types, detect anomalies

### 12. Implementation Phases

**Phase 1: Core Infrastructure (Week 1-2)**
- Database schema extensions
- Listener client skeleton
- Basic API endpoints
- Registration and heartbeat

**Phase 2: Recording Engine (Week 2-3)**
- GNU Radio spectrum_listener.py
- Waterfall generation
- Upload mechanism
- Storage backend

**Phase 3: Coordination (Week 3-4)**
- Priority algorithm
- Assignment logic
- Duration estimation
- Coordinated transmission/recording

**Phase 4: UI Integration (Week 4-5)**
- Listeners management view
- Recordings modal in Challenges
- Image display with zoom/scroll
- Metadata display

**Phase 5: Testing & Polish (Week 5-6)**
- End-to-end testing
- Performance optimization
- Documentation
- Deployment guide

---

## Summary

This architecture adds powerful passive monitoring capabilities to challengectl while maintaining the existing distributed design principles. Key benefits:

- **Non-intrusive:** Listeners don't interfere with transmissions
- **Scalable:** Works with any ratio of listeners to transmitters
- **Prioritized:** Automatically records challenges that need it most
- **Visual:** High-quality waterfall images for verification and debugging
- **Integrated:** Seamless UI experience for viewing recordings

The system leverages existing patterns (polling, API keys, database locking) and extends them naturally for a new component type. The result is a cohesive monitoring solution that complements the transmission infrastructure.
