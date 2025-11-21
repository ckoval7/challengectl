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
│  │ New: Listener Coordination Service                    │  │
│  │  - Track listener availability                        │  │
│  │  - Calculate recording priorities                     │  │
│  │  - Coordinate listener-transmitter pairs             │  │
│  │  - Store waterfall images and metadata               │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Database Extensions                                   │  │
│  │  - listeners table (similar to runners)              │  │
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
    │Runner 1  │    │Listener 1│    │Listener 2│
    │(HackRF)  │    │(RTL-SDR) │    │(BladeRF) │
    │TX Only   │    │RX Only   │    │RX Only   │
    └──────────┘    └──────────┘    └──────────┘
         │                │               │
         │ Transmits      │ Records       │ Records
         ▼                ▼               ▼
    ┌──────────────────────────────────────────┐
    │         RF Spectrum (e.g., 2m band)      │
    └──────────────────────────────────────────┘
```

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
listener:
  listener_id: "listener-1"
  server_url: "https://192.168.1.100:8443"
  api_key: "listener-key-1"

  heartbeat_interval: 30
  poll_interval: 5  # Check more frequently than runners

  recording:
    output_dir: "recordings"  # Where to store waterfall images
    sample_rate: 2000000      # 2 MHz (match transmitter)
    fft_size: 1024            # FFT bins for waterfall
    frame_rate: 20            # Waterfall frames per second
    gain: 40                  # RF gain

radio:
  model: rtlsdr              # RTL-SDR is cheap, ideal for listeners
  device: "rtl=0"
  frequency_limits:
    - "144000000-148000000"  # 2m band
    - "420000000-450000000"  # 70cm band
```

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

#### 3.1 Database Schema Extensions

**listeners table:**
```sql
CREATE TABLE listeners (
    listener_id TEXT PRIMARY KEY,
    hostname TEXT,
    ip_address TEXT,
    status TEXT,              -- 'online', 'offline'
    enabled BOOLEAN,          -- Can receive assignments
    last_heartbeat TIMESTAMP,
    device_info JSON,         -- Radio capabilities
    api_key_hash TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**recordings table:**
```sql
CREATE TABLE recordings (
    recording_id INTEGER PRIMARY KEY AUTOINCREMENT,
    challenge_id TEXT,
    listener_id TEXT,
    transmission_id INTEGER,   -- Links to specific transmission
    frequency INTEGER,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT,               -- 'recording', 'completed', 'failed'
    image_path TEXT,           -- Path to waterfall PNG
    image_width INTEGER,
    image_height INTEGER,
    sample_rate INTEGER,
    duration_seconds REAL,
    error_message TEXT,
    FOREIGN KEY (challenge_id) REFERENCES challenges(challenge_id),
    FOREIGN KEY (listener_id) REFERENCES listeners(listener_id),
    FOREIGN KEY (transmission_id) REFERENCES transmissions(transmission_id)
);
```

**listener_assignments table:**
```sql
CREATE TABLE listener_assignments (
    assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    listener_id TEXT,
    challenge_id TEXT,
    transmission_id INTEGER,
    frequency INTEGER,
    assigned_at TIMESTAMP,
    expected_start TIMESTAMP,  -- When transmission will begin
    expected_duration REAL,    -- Estimated seconds
    status TEXT,               -- 'assigned', 'recording', 'completed'
    FOREIGN KEY (listener_id) REFERENCES listeners(listener_id),
    FOREIGN KEY (challenge_id) REFERENCES challenges(challenge_id),
    FOREIGN KEY (transmission_id) REFERENCES transmissions(transmission_id)
);
```

#### 3.2 API Endpoints

**Listener Endpoints (require listener API key):**
```
POST /api/listeners/register
  - Register listener with server
  - Request body: {listener_id, hostname, device_info}
  - Response: {status: "success", message: "Registered"}

POST /api/listeners/{id}/heartbeat
  - Send periodic heartbeat
  - Request body: {status, timestamp}
  - Response: {status: "success"}

GET /api/listeners/{id}/assignment
  - Poll for recording assignments
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

POST /api/listeners/{id}/recording_started
  - Report recording has begun
  - Request body: {assignment_id, actual_start_time}
  - Response: {status: "success"}

POST /api/listeners/{id}/recording_complete
  - Report recording finished
  - Request body: {
      assignment_id,
      duration,
      samples_captured
    }
  - Response: {upload_url, recording_id}

POST /api/recordings/{id}/upload
  - Upload waterfall image (multipart/form-data)
  - File field: "waterfall"
  - Response: {status: "success", image_url}

POST /api/listeners/{id}/recording_failed
  - Report recording failure
  - Request body: {assignment_id, error_message}
  - Response: {status: "success"}
```

**Admin Endpoints (require admin auth):**
```
GET /api/recordings
  - List all recordings with pagination
  - Query params: challenge_id, listener_id, page, per_page
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
       # Get most recent recording timestamp
       last_recording = get_last_recording(challenge.challenge_id)

       if last_recording is None:
           # Never recorded - highest priority
           return 1000

       # Time since last recording (hours)
       hours_since = (now() - last_recording.completed_at).total_seconds() / 3600

       # Priority decays over time but never reaches zero
       # Recent recording: low priority
       # Old recording: medium priority
       # Never recorded: high priority
       priority = min(1000, hours_since * 10)

       # Boost priority based on challenge priority setting
       priority *= (challenge.priority / 10.0)

       return priority
   ```

3. **Select challenge with highest priority score**

4. **Check if challenge is currently assigned to a runner:**
   - If assigned: Create listener assignment synchronized with transmission
   - If queued: Wait for runner assignment (or assign both atomically)

5. **Create listener assignment:**
   - Record assignment in database
   - Return assignment details to listener
   - Set expected_start based on runner's assignment time

**Coordinated Assignment:**

When a runner is assigned a challenge:
```python
def assign_task_to_runner(runner_id):
    with db.begin_immediate():
        # Assign challenge to runner (existing logic)
        challenge = assign_challenge(runner_id)

        if challenge:
            # Check if listeners are available
            listeners = get_available_listeners_for_frequency(challenge.frequency)

            if listeners:
                # Assign to highest priority listener
                listener = select_listener_by_priority(listeners, challenge)
                create_listener_assignment(
                    listener.listener_id,
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
        <el-descriptions-item label="Listener">
          {{ currentRecording.listener_id }}
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
      return `${date.toLocaleString()} - ${rec.listener_id}`
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

#### 4.3 New View: Listeners.vue

Similar to `Runners.vue`, for managing listeners:

```vue
<template>
  <div class="listeners">
    <h1>Spectrum Listeners</h1>

    <el-table :data="listeners">
      <el-table-column prop="listener_id" label="Listener ID" />
      <el-table-column label="Status">
        <template #default="scope">
          <el-tag :type="scope.row.status === 'online' ? 'success' : 'danger'">
            {{ scope.row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="Device">
        <template #default="scope">
          {{ scope.row.device_info?.model || 'N/A' }}
        </template>
      </el-table-column>
      <el-table-column label="Current Assignment">
        <template #default="scope">
          {{ scope.row.current_assignment?.challenge_name || 'None' }}
        </template>
      </el-table-column>
      <el-table-column label="Recordings">
        <template #default="scope">
          {{ scope.row.recording_count || 0 }}
        </template>
      </el-table-column>
      <el-table-column label="Enabled">
        <template #default="scope">
          <el-switch
            v-model="scope.row.enabled"
            @change="toggleListener(scope.row)"
          />
        </template>
      </el-table-column>
      <el-table-column label="Actions">
        <template #default="scope">
          <el-button size="small" type="danger" @click="kickListener(scope.row.listener_id)">
            Kick
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
```

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

Scenario: 10 challenges, 3 runners, 1 listener

```
Challenges:
- NBFM_1: Last recorded 5 days ago
- NBFM_2: Last recorded 2 days ago
- NBFM_3: Never recorded
- CW_1: Last recorded 1 hour ago
- CW_2: Never recorded
- SSB_1: Last recorded 10 hours ago
- ... (4 more)

Priority Calculation:
1. NBFM_3: 1000 (never recorded)
2. CW_2: 1000 (never recorded)
3. NBFM_1: 1200 (5 days * 10 * 2.4 = 1200, capped at 1000 + priority boost)
4. NBFM_2: 480 (2 days * 10 * 2.4)
5. SSB_1: 100 (10 hours * 10)
6. CW_1: 10 (1 hour * 10)

When listener polls:
- Server selects NBFM_3 (highest priority)
- If NBFM_3 not currently assigned to runner:
  - Wait for next assignment
- If NBFM_3 currently assigned to runner:
  - Create listener assignment immediately
  - Listener begins recording
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
