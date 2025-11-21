# ChallengeCtl Codebase Analysis

## Executive Summary

ChallengeCtl is a distributed SDR (Software Defined Radio) challenge management system with three main components:
1. **Server** - Central Python/Flask controller coordinating challenges
2. **Runners** - Distributed clients executing challenges on SDR hardware
3. **Frontend** - Vue.js web UI for monitoring and management

The system uses **pessimistic database locking** to prevent duplicate challenge assignments and manages a complex workflow from challenge start to completion.

---

## 1. Challenge Execution Architecture

### High-Level Workflow

```
Challenge Definition (YAML)
           ↓
Server Database (SQLite)
           ↓
Runner Polling
           ↓
Task Assignment (Atomic DB Lock)
           ↓
File Download + Verification
           ↓
Challenge Execution (GNU Radio)
           ↓
Completion Report
           ↓
Status Update + Delay Timer
           ↓
Requeue for Next Transmission
```

### Challenge Lifecycle States

1. **queued**: Ready to be assigned to a runner
2. **assigned**: Currently being transmitted by a runner
3. **waiting**: In delay timer between transmissions
4. **disabled**: Not active

### Challenge State Transitions

```
queued → assigned → waiting → [delay expires] → queued
  ↑                                               ↓
  └───────────────────────────────────────────────┘
```

### Key Database Tables

**challenges table**:
- `challenge_id` - Unique identifier
- `name` - Challenge name (unique)
- `config` - JSON blob containing all parameters
- `status` - Current state (queued/assigned/waiting)
- `assigned_to` - Runner ID when assigned
- `assigned_at` - Assignment timestamp
- `assignment_expires` - 5-minute timeout
- `last_tx_time` - Last completion time
- `next_tx_time` - Calculated next transmission time
- `transmission_count` - Number of times transmitted
- `enabled` - Whether active
- `priority` - Higher values execute first

**transmissions table**:
- Records every transmission event
- Links challenge to runner to device
- Tracks success/failure and error messages
- Contains frequency, timing, and device information

### Challenge Frequency Configuration

Three methods for specifying frequencies:

```yaml
# Method 1: Single fixed frequency
frequency: 146550000  # Hz

# Method 2: Named ranges (random selection)
frequency_ranges: [ham_144, ham_440]

# Method 3: Custom range
manual_frequency_range:
  min_hz: 146000000
  max_hz: 148000000
```

---

## 2. Spectrum Painting Implementation

### What is Spectrum Painting?

Spectrum painting is a GNU Radio technique that uses OFDM to paint patterns in the RF spectrum. The implementation is in `/challenges/spectrum_paint.py`.

### Spectrum Paint Flow Graph

```
File Source (rfhs.bin)
        ↓
Paint Block (spectrum painting encoder)
        ↓
Stream to Vector (4096 samples)
        ↓
OFDM Cyclic Prefixer
        ↓
osmocom Sink (transmit via SDR)
```

### Key Parameters

- **Sample Rate**: 2,000,000 Hz (2 MHz)
- **FFT Size**: 4096
- **Gain**: 50 dB RF, 20 dB IF, 20 dB BB
- **File Input**: Binary file (rfhs.bin) containing data to paint

### Execution Flow

1. Runner loads spectrum_paint.py
2. Initializes GNU Radio flow graph
3. Sets frequency on osmocom sink
4. Starts transmission
5. Reads from input file and transmits as OFDM signals

### In Challenge Context

When a runner executes a challenge with `modulation: paint`:

```python
# From runner.py execute_challenge()
p = Process(target=spectrum_paint.main, args=(frequency, device_string, antenna))
p.start()
p.join()  # Wait for completion
success = (p.exitcode == 0)
```

**Optional Pre-Spectrum-Paint**:
The runner can optionally run spectrum painting BEFORE each challenge transmission:
```python
if self.spectrum_paint_before_challenge and modulation != 'paint':
    self.run_spectrum_paint(frequency, device_string, antenna)
```

---

## 3. Distributed Architecture

### Architecture Overview

```
┌─────────────────────────────────────────────────┐
│            Web Browser (Admin UI)               │
│           (Vue.js Frontend - HTTPS)             │
└──────────────────┬──────────────────────────────┘
                   │ HTTPS + WebSocket (Socket.IO)
                   ▼
┌─────────────────────────────────────────────────┐
│        ChallengeCtl Server (Python/Flask)       │
│  ┌────────────────────────────────────────────┐ │
│  │  REST API Endpoints                        │ │
│  │  - Runner registration/heartbeat           │ │
│  │  - Task assignment with DB locking         │ │
│  │  - File serving                            │ │
│  │  - Admin operations                        │ │
│  └────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────┐ │
│  │  SQLite Database                           │ │
│  │  - Challenges                              │ │
│  │  - Runners                                 │ │
│  │  - Transmissions (history)                 │ │
│  │  - Users, Sessions, API Keys               │ │
│  └────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────┐ │
│  │  Background Tasks (APScheduler)            │ │
│  │  - Cleanup stale runners (30s)             │ │
│  │  - Cleanup stale assignments (30s)         │ │
│  │  - Cleanup expired sessions (60s)          │ │
│  │  - Cleanup stale temporary users (5min)    │ │
│  └────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────┐ │
│  │  WebSocket (Socket.IO)                     │ │
│  │  Real-time event broadcasting              │ │
│  └────────────────────────────────────────────┘ │
└──────────────────┬──────────────────────────────┘
    HTTP (Polling) │
    ┌─────────────┼─────────────┬─────────────┐
    ▼             ▼             ▼             ▼
┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐
│Runner 1│  │Runner 2│  │Runner 3│  │Runner N│
│(HackRF)│  │(Blade) │  │(USRP)  │  │ ...    │
└────────┘  └────────┘  └────────┘  └────────┘
```

### Communication Flow

#### Runner Registration & Heartbeat

```
Runner Startup:
  1. Load config
  2. Enroll with server (one-time)
  3. Send POST /api/runners/register
  4. Receive acknowledgment
  5. Start heartbeat loop

Heartbeat Loop (every 30 seconds):
  1. POST /api/runners/{id}/heartbeat
  2. Server updates last_heartbeat timestamp
  3. Continue until shutdown

Shutdown:
  1. Send POST /api/runners/{id}/signout
  2. Server marks runner offline immediately
  3. Requeue any assigned tasks
```

#### Task Assignment (Mutual Exclusion)

```
Runner requests task:
  GET /api/runners/{runner_id}/task

Server processes request:
  1. BEGIN IMMEDIATE transaction (locks database)
  2. SELECT challenge WHERE status='queued' OR status='waiting'
  3. Filter by:
     - Runner's frequency capabilities
     - Challenge enabled=1
     - If 'waiting': check if delay has expired
  4. SELECT first challenge (by priority, then random)
  5. UPDATE status='assigned', assigned_to=runner_id
  6. INSERT/UPDATE transmission record
  7. COMMIT transaction (release lock)
  8. Return challenge details to runner

Runner receives task:
  1. Parse response
  2. Download any required files
  3. Execute challenge
  4. Report completion
```

### Transmitter/Receiver Architecture

#### Transmitter Side (Runners)

Each runner:
- Has N SDR devices with frequency capabilities
- Polls server for tasks at configurable interval (default: 10s)
- Downloads files as needed (cached by SHA-256 hash)
- Executes challenges using GNU Radio
- Reports success/failure back to server

#### Server Side (Task Distribution)

The server:
- Maintains queue of challenges in database
- Tracks runner status and capabilities
- Uses atomic database transactions to prevent duplicates
- Assigns tasks based on availability and runner constraints
- Monitors for stale assignments (timeout after 5 minutes)
- Requeues failed/timed-out tasks

#### No Receiver

The system only transmits challenges. It does NOT listen/receive:
- No spectrum monitoring
- No flag reception
- Students capture flags through independent monitoring

---

## 4. Challenge Management UI Structure

### Frontend Components (Vue.js 3)

**Location**: `/frontend/src/`

Key components:
- `Dashboard.vue` - System overview with statistics
- `Runners.vue` - Runner management and monitoring
- `Challenges.vue` - Challenge control and queue
- `Logs.vue` - Real-time log streaming
- `Users.vue` - Admin user management
- `PublicDashboard.vue` - Read-only public view

### Dashboard Features

**Real-time Statistics**:
- Runners online count
- Challenges queued count
- Total transmissions
- Success rate (%)

**Runner Management**:
- Enable/disable individual runners
- Kick (forcefully disconnect) runners
- Re-enroll runners
- View devices and capabilities
- Monitor last heartbeat

**Challenge Control**:
- View all challenges with current status
- Enable/disable challenges
- Trigger immediate transmission
- View transmission history
- Monitor delays between transmissions

**Log Streaming**:
- Real-time logs from server and all runners
- Filter by source (server or specific runner)
- Filter by level (DEBUG, INFO, WARNING, ERROR)
- Last 500 logs buffered

### WebSocket Event Types

The frontend receives real-time updates via WebSocket:

```javascript
// Runner events
'runner_status' - Runner connected/disconnected
{
  runner_id: 'runner-1',
  status: 'online|offline',
  timestamp: ISO8601
}

'runner_enabled' - Runner enable/disable changed
{
  runner_id: 'runner-1',
  enabled: true/false,
  timestamp: ISO8601
}

// Challenge events
'challenge_assigned' - Challenge assigned to runner
{
  runner_id: 'runner-1',
  challenge_id: 'CHALLENGE_1',
  challenge_name: 'NBFM_FLAG_1',
  timestamp: ISO8601
}

'transmission_complete' - Challenge transmission finished
{
  runner_id: 'runner-1',
  challenge_id: 'CHALLENGE_1',
  status: 'success|failure',
  frequency: 146550000,
  error_message: 'if applicable',
  timestamp: ISO8601
}

// Logging
'log' - Real-time log entry
{
  type: 'log',
  source: 'server|runner-1',
  level: 'DEBUG|INFO|WARNING|ERROR',
  message: 'Log message text',
  timestamp: ISO8601
}
```

### CORS & Security

- CORS origins configured in `server-config.yml`
- WebSocket uses session cookies (HTTPOnly)
- Admin endpoints require session token + CSRF token
- Runner endpoints require API key in Authorization header
- Rate limiting applied to prevent abuse

---

## 5. Listener/Monitoring Infrastructure

### Server-Side Monitoring

#### Real-Time Logging

**WebSocketHandler** (api.py):
```python
class WebSocketHandler(logging.Handler):
    - Captures all server logs
    - Stores last 500 in log_buffer
    - Broadcasts via Socket.IO to all clients
```

**ServerLogHandler** (runner.py):
```python
class ServerLogHandler(logging.Handler):
    - Runner sends logs to server
    - POST /api/runners/{id}/log endpoint
    - Server broadcasts to WebUI clients
```

#### Background Monitoring Tasks

Running every 30 seconds:
1. **cleanup_stale_runners()** - Mark offline if 90s no heartbeat
2. **cleanup_stale_assignments()** - Requeue if 5 min no completion

Running every 60 seconds:
1. **cleanup_expired_sessions()** - Remove stale user sessions
2. **cleanup_expired_totp_codes()** - Clear old TOTP codes

Running every 5 minutes:
1. **cleanup_stale_temporary_users()** - Disable 24h+ incomplete users

#### Statistics Collection

Dashboard statistics from `/api/dashboard`:
```python
{
  'runners_online': int,
  'runners_total': int,
  'challenges_queued': int,
  'challenges_total': int,
  'total_transmissions': int,
  'success_rate': float (0-100),
  'recent_transmissions': [...],
  'system_paused': bool
}
```

### Runner-Side Monitoring

#### Health Monitoring

Each runner:
1. Sends heartbeat every 30 seconds (configurable)
2. Includes status, last activity time
3. Server marks offline after 90s of missed heartbeats

#### Capability Tracking

Each runner broadcasts:
- Hostname and IP address
- SDR device count and models
- Frequency limits per device
- GNU Radio version

#### Execution Monitoring

During challenge execution:
1. Log each modulation type invocation
2. Capture GNU Radio errors to logs
3. Report completion with success/failure
4. Include any error messages
5. Record actual frequency used

### No Passive Listening

The system does NOT:
- Listen to RF spectrum
- Monitor flag reception
- Verify challenge success
- Decode transmitted signals

This is intentional - challenges are "fire and forget" for the server. External monitoring equipment captures flags.

---

## 6. Database Schema

### Complete Schema

#### runners
```sql
runner_id (TEXT, PRIMARY KEY)
hostname (TEXT)
ip_address (TEXT)
mac_address (TEXT)  -- Added for host validation
machine_id (TEXT)   -- Added for host validation
status (TEXT) -- 'online', 'offline'
enabled (BOOLEAN) -- Can receive new tasks
last_heartbeat (TIMESTAMP)
devices (JSON) -- Array of device capabilities
api_key_hash (TEXT) -- Bcrypt hash (not plain text)
created_at (TIMESTAMP)
updated_at (TIMESTAMP)
```

#### challenges
```sql
challenge_id (TEXT, PRIMARY KEY)
name (TEXT, UNIQUE)
config (JSON) -- Complete challenge config
status (TEXT) -- queued, assigned, waiting, disabled
priority (INTEGER) -- Higher = more important
last_tx_time (TIMESTAMP)
next_tx_time (TIMESTAMP)
transmission_count (INTEGER)
assigned_to (TEXT, FK runners.runner_id)
assigned_at (TIMESTAMP)
assignment_expires (TIMESTAMP)
enabled (BOOLEAN)
created_at (TIMESTAMP)
```

#### transmissions
```sql
transmission_id (INTEGER, PRIMARY KEY AUTO)
challenge_id (TEXT, FK challenges.challenge_id)
runner_id (TEXT, FK runners.runner_id)
device_id (TEXT)
frequency (INTEGER)
started_at (TIMESTAMP)
completed_at (TIMESTAMP)
status (TEXT) -- success, failure
error_message (TEXT)
```

#### files
```sql
file_hash (TEXT, PRIMARY KEY) -- SHA-256
filename (TEXT)
size (INTEGER)
mime_type (TEXT)
file_path (TEXT)
created_at (TIMESTAMP)
```

#### system_state
```sql
key (TEXT, PRIMARY KEY) -- e.g., 'paused'
value (TEXT)
updated_at (TIMESTAMP)
```

#### users
```sql
username (TEXT, PRIMARY KEY)
password_hash (TEXT) -- Bcrypt
totp_secret (TEXT) -- AES-256 encrypted
enabled (BOOLEAN)
password_change_required (BOOLEAN)
is_temporary (BOOLEAN)
created_at (TIMESTAMP)
last_login (TIMESTAMP)
```

#### sessions
```sql
session_token (TEXT, PRIMARY KEY)
username (TEXT, FK users.username)
expires (TIMESTAMP) -- 24 hours from creation
totp_verified (BOOLEAN)
created_at (TIMESTAMP)
```

#### enrollment_tokens
```sql
token (TEXT, PRIMARY KEY)
runner_name (TEXT)
created_by (TEXT, FK users.username)
created_at (TIMESTAMP)
expires_at (TIMESTAMP)
used (BOOLEAN)
used_at (TIMESTAMP)
used_by_runner_id (TEXT)
re_enrollment_for (TEXT) -- For re-enrolling existing runners
```

#### provisioning_api_keys
```sql
key_id (TEXT, PRIMARY KEY)
key_hash (TEXT) -- Bcrypt hash
description (TEXT)
created_by (TEXT, FK users.username)
created_at (TIMESTAMP)
last_used_at (TIMESTAMP)
enabled (BOOLEAN)
```

### Mutual Exclusion Mechanism

Uses **pessimistic database locking** with SQLite:

```python
def assign_task(runner_id):
    with db.begin_immediate():  # IMMEDIATE lock acquired
        # Find available challenge
        challenge = db.query(
            "SELECT * FROM challenges "
            "WHERE status = 'queued' "
            "AND enabled = 1 "
            "ORDER BY priority DESC, RANDOM() "
            "LIMIT 1 "
            "FOR UPDATE"  # Row-level lock
        )
        
        if challenge:
            # Atomic update
            db.execute(
                "UPDATE challenges "
                "SET status = 'assigned', "
                "    assigned_to = ?, "
                "    assigned_at = NOW(), "
                "    assignment_expires = NOW() + 5 minutes "
                "WHERE challenge_id = ?",
                (runner_id, challenge.id)
            )
            return challenge
    
    return None
```

**Guarantee**: Two runners will NEVER get the same queued challenge simultaneously.

---

## 7. Challenge Workflow: Start to Completion

### Complete Timeline

```
T0: Challenge Definition
    └─ Created in config or via API
    └─ Stored in database with status='queued'

T1: Runner Polling (every 10 seconds)
    ├─ Runner sends: GET /api/runners/{id}/task
    └─ Server responds: Challenge details (or empty)

T2: Task Assignment (10-30 second window)
    ├─ First available runner receives challenge
    ├─ Server atomically updates: status='assigned'
    ├─ Assignment timestamp and 5-minute timeout set
    └─ All other runners get empty response

T3: File Download (if needed)
    ├─ Runner checks local cache (by SHA-256)
    ├─ If missing: GET /api/files/{hash}
    ├─ Server streams file content
    ├─ Runner verifies SHA-256 before use
    └─ File stored in cache for future use

T4: Challenge Execution
    ├─ Spectrum paint (optional, before challenge)
    │  └─ 3-5 seconds, depends on parameters
    ├─ Challenge execution (modulation type specific)
    │  ├─ CW: ~1-2 minutes (depends on message)
    │  ├─ NBFM: ~2-5 minutes (file dependent)
    │  ├─ SSB: ~2-5 minutes (file dependent)
    │  ├─ FHSS: ~5-60 seconds (config dependent)
    │  └─ Paint: ~3-5 seconds
    └─ GNU Radio output to SDR device

T5: Completion Report
    ├─ Runner sends: POST /api/runners/{id}/complete
    ├─ Includes: success/failure, device_id, frequency
    ├─ Server receives and logs
    └─ Database updated with transmission record

T6: State Update
    ├─ Challenge status changes: 'assigned' → 'waiting'
    ├─ 'last_tx_time' set to current time
    ├─ 'transmission_count' incremented
    ├─ 'assigned_to' and 'assigned_at' cleared
    └─ Delay timer set: (min_delay + max_delay) / 2

T7: Delay Period (default: 60-120 seconds)
    ├─ Challenge in 'waiting' state
    ├─ No runners can be assigned to it
    └─ Timer decrements

T8: Delay Expiration
    ├─ Background task detects delay expired
    ├─ Status changes: 'waiting' → 'queued'
    └─ Challenge available for next runner

T9: Loop Repeats
    └─ Back to T1 for next transmission cycle
```

### Example Configuration

```yaml
challenges:
  - name: NBFM_Example
    frequency: 146550000  # or frequency_ranges: [ham_144]
    modulation: nbfm
    flag: challenges/example.wav
    min_delay: 60        # Minimum seconds between transmissions
    max_delay: 120       # Maximum seconds between transmissions
    enabled: true
    priority: 10         # Higher = transmitted more frequently
    public_view:
      show_frequency: true
      show_last_tx_time: false
```

### Transmission Attempt Failure Handling

```
Runner assigned challenge but fails to execute:
  1. Runner catches exception in execute_challenge()
  2. Reports: POST /api/complete with success=false
  3. Server updates status='waiting' (requeue with delay)
  4. Transmission record logged with error message
  5. Challenge available again after delay

Runner dies before reporting:
  1. Server detects stale assignment (5-minute timeout)
  2. Background cleanup task requeues challenge
  3. Status changed: 'assigned' → 'waiting'
  4. Challenge available for another runner
  5. No manual intervention needed

Runner disconnects:
  1. Heartbeat monitoring detects offline (90 seconds)
  2. Cleanup task runs automatically
  3. Any assigned tasks requeued with delay
  4. Runner status updated in WebUI
  5. Re-enables when runner reconnects
```

---

## 8. Key Design Decisions & Trade-offs

### Why SQLite?
- Simple deployment (single file)
- Sufficient for 10-20 runners
- Built-in transactions for locking
- No separate database server needed
- Can migrate to PostgreSQL later

### Why Polling (not Push)?
- Simpler firewall rules (runners initiate)
- Easier NAT/VPN traversal
- Runners can cache work offline
- More resilient to network issues

### Why Flask (not FastAPI)?
- Simpler for synchronous workloads
- Better Flask-SocketIO integration
- Widely deployed and stable

### Why Vue.js (not React)?
- Simpler for this admin panel use case
- Element Plus component library
- Single-file components

### Why GNU Radio (not USRP GNU Radio)?
- Works with multiple SDR types (HackRF, BladeRF, etc.)
- Better cross-platform support
- Easier signal processing

---

## 9. Current Limitations & Scalability

### Current Limits
- **Max Runners**: 10-20 with SQLite
- **Max Challenges**: Hundreds
- **Transmission Rate**: 100+ per runner per hour
- **Single Server**: No failover

### Scaling Paths
1. **PostgreSQL** - Replace SQLite for better concurrency
2. **Redis** - Caching layer and session storage
3. **Load Balancing** - Multiple server instances
4. **CDN** - Distributed file serving
5. **Monitoring** - Prometheus metrics export

---

## File Structure Summary

```
challengectl/
├── server/
│   ├── server.py          # Entry point, background tasks
│   ├── api.py             # REST API endpoints
│   ├── database.py        # SQLite schema & operations
│   └── crypto.py          # TOTP encryption
├── runner/
│   └── runner.py          # Runner client, task execution
├── challenges/
│   ├── cw.py              # Morse code modulation
│   ├── nbfm.py            # Narrowband FM
│   ├── spectrum_paint.py  # OFDM spectrum painting
│   └── [others]           # Additional modulations
├── frontend/
│   ├── src/
│   │   ├── views/         # Vue pages (Dashboard, Runners, etc.)
│   │   ├── websocket.js   # Socket.IO client
│   │   ├── api.js         # REST client
│   │   └── router.js      # Vue Router config
│   └── dist/              # Built production files
└── docs/
    ├── DISTRIBUTED_ARCHITECTURE.md
    ├── Architecture.md
    └── DEPLOYMENT.md
```

