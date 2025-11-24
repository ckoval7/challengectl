# Architecture Overview

This document provides a technical overview of the ChallengeCtl system architecture, explaining how components interact, how data flows through the system, and the key design decisions that enable reliable challenge distribution.

## Table of Contents

- [System Overview](#system-overview)
- [Component Architecture](#component-architecture)
- [Spectrum Listener Architecture](#spectrum-listener-architecture)
- [Data Flow](#data-flow)
- [Database Schema](#database-schema)
- [Mutual Exclusion Mechanism](#mutual-exclusion-mechanism)
- [Failure Detection and Recovery](#failure-detection-and-recovery)
- [File Synchronization](#file-synchronization)
- [Security Model](#security-model)
- [Scalability Considerations](#scalability-considerations)

## System Overview

ChallengeCtl implements a distributed client-server architecture for coordinating SDR challenge transmissions across multiple devices. The system is designed with the following goals:

1. **Mutual Exclusion**: Ensure each challenge is transmitted by only one runner at a time
2. **Fault Tolerance**: Automatically recover from runner failures
3. **Simplicity**: Minimal dependencies and straightforward deployment
4. **Observability**: Real-time monitoring of all system components
5. **Spectrum Recording**: Capture and visualize transmissions with listener agents

### High-Level Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Web Browser                        │
│              (Vue.js Frontend)                       │
└──────────────────┬──────────────────────────────────┘
                   │ HTTPS + WebSocket
                   ▼
┌─────────────────────────────────────────────────────┐
│                  ChallengeCtl Server                 │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │   Flask API  │  │   Database   │  │ WebSocket │ │
│  │  (REST API)  │  │  (SQLite)    │  │ Broadcast │ │
│  │              │  │              │  │  /agents  │ │
│  └──────────────┘  └──────────────┘  └───────────┘ │
│  ┌──────────────────────────────────────────────┐   │
│  │        Background Tasks                      │   │
│  │  - Cleanup stale assignments                 │   │
│  │  - Requeue timed-out tasks                   │   │
│  │  - Monitor agent health                      │   │
│  │  - Priority-based recording coordination     │   │
│  └──────────────────────────────────────────────┘   │
└────────┬──────────────────────────────┬─────────────┘
         │ HTTP (Polling)                │ WebSocket (Push)
         │                               │
         │                        ┌──────┴──────┐
         │                        ▼             ▼
         │                   ┌──────────┐  ┌──────────┐
         │                   │Listener 1│  │Listener 2│
         │                   │(RTL-SDR) │  │(HackRF)  │
         │                   └──────────┘  └──────────┘
         │                        │             │
         │                        ▼             ▼
         │                     [Radio]       [Radio]
         │                    (Receive)     (Receive)
         │
         ├─────────┬─────────┬─────────────┐
         ▼         ▼         ▼             ▼
    ┌────────┐ ┌────────┐ ┌────────┐  ┌────────┐
    │Runner 1│ │Runner 2│ │Runner 3│  │Runner N│
    │(HackRF)│ │(LimeSDR│ │(USRP)  │  │  ...   │
    └────────┘ └────────┘ └────────┘  └────────┘
         │         │         │             │
         ▼         ▼         ▼             ▼
      [Radio]  [Radio]  [Radio]       [Radio]
    (Transmit)(Transmit)(Transmit)   (Transmit)
```

## Component Architecture

### Server Components

The server is implemented in Python using Flask and consists of several modules:

#### 1. Flask Application (`server.py`)

The main server application that:
- Initializes the database connection
- Loads challenge configuration from YAML
- Starts background maintenance tasks
- Launches the Flask web server with SocketIO support

**Key responsibilities**:
- Application lifecycle management
- Configuration loading and validation
- Graceful shutdown handling

#### 2. API Layer (`api.py`)

Provides REST endpoints for:
- **Runner Operations**: Registration, heartbeat, task polling, completion reporting
- **Admin Operations**: Dashboard data, runner management, challenge control
- **Public Operations**: Health checks, public challenge listings

**Authentication**:
- Runner endpoints: API key authentication
- Admin endpoints: Session-based authentication with username/password + TOTP
- Public endpoints: No authentication required

#### 3. Database Layer (`database.py`)

Manages all database operations with pessimistic locking for mutual exclusion:

**Core operations**:
- Runner registration and heartbeat tracking
- Challenge state management
- Task assignment with atomic locking
- Transmission history logging
- User account management

**Concurrency control**:
- Uses `BEGIN IMMEDIATE` transactions for write operations
- Implements row-level locking for task assignment
- Handles lock timeouts and retries

#### 4. WebSocket Broadcast

Real-time event broadcasting to connected web clients:

**Event types**:
- Challenge state changes (queued, assigned, completed)
- Runner status updates (online, offline, busy)
- Transmission events
- Log messages

#### 5. Background Tasks

The server runs periodic background tasks for system maintenance:

| Task | Interval | Description |
|------|----------|-------------|
| Cleanup stale runners | 30 seconds | Marks runners offline if heartbeat timeout exceeded (90s) |
| Cleanup stale assignments | 30 seconds | Requeues challenges with expired assignments (5 minutes) |
| Cleanup expired sessions | 60 seconds | Removes expired user sessions from database |
| Cleanup expired TOTP codes | 60 seconds | Removes old TOTP verification codes |

These tasks ensure system reliability by automatically detecting and recovering from failures without manual intervention.

### Runner Components

Each runner is a long-running Python process that:

1. **Registers** with the server using its API key
2. **Sends heartbeats** every 30 seconds to indicate it's alive (configurable)
3. **Polls for tasks** every 10 seconds by default (configurable)
4. **Downloads files** needed for challenges (cached locally)
5. **Executes transmissions** using GNU Radio and SDR hardware
6. **Reports completion** or errors back to the server
7. **Signs out** on graceful shutdown

**Runner lifecycle**:

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Start   │────▶│ Register │────▶│   Idle   │────▶│ Assigned │
└──────────┘     └──────────┘     └────┬─────┘     └────┬─────┘
                                       │                 │
                                       │ Poll (no task)  │ Download
                                       │◀────────────────┘ files
                                       │                 │
                                       │                 ▼
                                       │            ┌──────────┐
                                       │            │Transmit  │
                                       │            └────┬─────┘
                                       │                 │
                                       │                 │ Complete
                                       │◀────────────────┘
                                       │
                                       │ Shutdown signal
                                       ▼
                                  ┌──────────┐
                                  │ Sign Out │
                                  └──────────┘
```

### Frontend Components

The Vue.js frontend provides:

- **Dashboard**: Overview of system status and recent transmissions
- **Agents** (Runners/Listeners/Provisioning):
  - **Runners Tab**: List of registered runner agents with status and controls
  - **Listeners Tab**: List of registered listener agents with WebSocket status
  - **Provisioning Tab**: Enrollment token and API key management
- **Challenges**: Challenge management and manual triggering
- **Logs**: Real-time log streaming from server and agents

The frontend communicates with the server via:
- REST API for data retrieval and actions
- WebSocket for real-time updates (no polling required)

## Spectrum Listener Architecture

The spectrum listener subsystem enables automatic capture and visualization of RF transmissions. When a runner is assigned a transmission task, the server can coordinate with listener agents to capture the spectrum and generate waterfall images.

### Design Goals

1. **Priority-Based Recording**: Record transmissions intelligently based on priority rather than recording every transmission
2. **Real-Time Coordination**: Use WebSocket push notifications for precise timing (±1s vs ±15s with polling)
3. **Minimal Overhead**: Only record high-value transmissions to conserve resources
4. **Flexible Deployment**: Support varying numbers of listeners vs runners (e.g., 2 listeners for 10 runners)

### Unified Agent Model

Both runners and listeners are managed as "agents" in the database:

```
agents table:
  - agent_id (PRIMARY KEY)
  - agent_type ('runner' or 'listener')
  - hostname, ip_address, devices
  - status ('online' or 'offline')
  - enabled (boolean)
  - websocket_connected (boolean, listeners only)
  - websocket_last_connected (timestamp)
```

**Key differences**:
- **Runners**: Poll via HTTP for task assignments, transmit RF signals
- **Listeners**: Connect via WebSocket for real-time push, receive RF signals and generate waterfall images

### Recording Priority Algorithm

The server calculates a priority score for each challenge transmission:

```python
def calculate_recording_priority(challenge):
    # Never recorded = highest priority
    if no previous recording:
        return 1000.0

    # Get transmission count since last recording
    transmissions_since = count_transmissions_since_last_recording(challenge)

    # Calculate time factor (increases over hours)
    minutes_since = time_since_last_recording(challenge)
    time_multiplier = min(10.0, minutes_since / 60.0)

    # Combine factors
    priority = transmissions_since * time_multiplier

    # Apply challenge priority boost (0-10 scale)
    priority *= (challenge.priority / 10.0)

    return min(1000.0, priority)
```

**Assignment decision**:
- If `priority >= threshold` (default 10.0), assign a listener
- Example: Challenge transmitted 5 times in past hour → priority = 5 × 1.0 = 5.0 (below threshold, not recorded)
- Example: Challenge not recorded in 3 hours, transmitted 4 times → priority = 4 × 3.0 = 12.0 (above threshold, recorded)

This prevents recording every transmission while ensuring good coverage of all challenges.

### Coordinated Assignment Workflow

When a runner polls for a task:

```
1. Server assigns challenge to runner (HTTP polling)
   └─ Creates transmission record in database

2. Server calculates recording priority
   └─ If priority >= threshold:
       ├─ Find available listeners (online + WebSocket connected)
       ├─ Create listener_assignment record
       ├─ Push 'recording_assignment' event via WebSocket
       │  (includes frequency, expected_start, expected_duration)
       └─ Listener receives assignment instantly

3. Listener prepares for recording
   ├─ Waits until expected_start time
   ├─ Starts GNU Radio flowgraph
   ├─ Captures RF with pre-roll buffer (5s before transmission)
   └─ Reports recording started to server

4. Runner executes transmission
   └─ Listener is already recording

5. Transmission completes
   └─ Listener continues recording with post-roll buffer (5s after)

6. Listener generates waterfall image
   ├─ Converts FFT data to dB scale
   ├─ Generates PNG with matplotlib
   └─ Uploads to server

7. Server stores waterfall metadata
   └─ Image available in web UI
```

**Timing precision**:
- HTTP polling: ±15s coordination accuracy (10s poll interval)
- WebSocket push: ±1s coordination accuracy (instant notification)

### WebSocket Agent Namespace

Listeners connect to the `/agents` WebSocket namespace for real-time coordination:

**Authentication**:
```python
# Listener connects with API key
socketio.connect(
    server_url,
    auth={'agent_id': 'listener-1', 'api_key': api_key},
    namespaces=['/agents']
)
```

**Events**:

Server → Listener:
- `connected`: Connection acknowledgment
- `recording_assignment`: New recording task with full details
- `assignment_cancelled`: If transmission fails before recording starts

Listener → Server:
- `heartbeat`: Optional WebSocket heartbeat (in addition to HTTP)

**Agent-specific rooms**:
- Each listener joins room `agent_<id>`
- Server emits to specific room: `socketio.emit('recording_assignment', data, room='agent_listener-1')`
- Enables targeted messaging without broadcasting to all listeners

### Listener Components

A listener agent consists of:

1. **listener.py**: Main Python client
   - WebSocket connection management
   - Recording assignment handler
   - HTTP registration and heartbeat
   - Orchestrates capture and upload workflow

2. **spectrum_listener.py**: GNU Radio flowgraph
   - Osmocom source for SDR hardware (RTL-SDR, HackRF, USRP, etc.)
   - FFT processing with configurable size and frame rate
   - IQ sample capture and vector sink
   - Simulated mode for testing without hardware

3. **waterfall_generator.py**: Waterfall image generation
   - Converts FFT power data to dB scale
   - Custom colormap (blue → green → yellow → red)
   - Auto-scaling using 5th-95th percentile
   - Matplotlib PNG output with frequency/time axes

4. **listener-config.yml**: Configuration
   - Agent ID and server URL
   - SDR device settings (sample rate, gain, device ID)
   - Recording parameters (FFT size, frame rate)
   - Pre-roll and post-roll timing

### Database Schema Extensions

**recordings table**:
```sql
CREATE TABLE recordings (
    recording_id INTEGER PRIMARY KEY,
    challenge_id TEXT,
    agent_id TEXT,  -- listener agent
    transmission_id INTEGER,
    frequency INTEGER,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT,  -- 'recording', 'completed', 'failed'
    image_path TEXT,  -- path to waterfall PNG
    image_width INTEGER,
    image_height INTEGER,
    sample_rate INTEGER,
    duration_seconds REAL,
    error_message TEXT
)
```

**listener_assignments table**:
```sql
CREATE TABLE listener_assignments (
    assignment_id INTEGER PRIMARY KEY,
    agent_id TEXT,
    challenge_id TEXT,
    transmission_id INTEGER,
    frequency INTEGER,
    assigned_at TIMESTAMP,
    expected_start TIMESTAMP,
    expected_duration REAL,
    status TEXT,  -- 'pending', 'recording', 'completed', 'cancelled'
    cancelled_at TIMESTAMP,
    completed_at TIMESTAMP
)
```

### API Endpoints

**Agent management** (unified for runners and listeners):
- `POST /api/agents/register` - Register with `agent_type` parameter
- `POST /api/agents/<id>/heartbeat` - Heartbeat (HTTP)
- `POST /api/agents/<id>/signout` - Graceful shutdown
- `GET /api/agents` - List all agents (admin, with optional type filter)
- `POST /api/agents/<id>/enable` - Enable agent
- `POST /api/agents/<id>/disable` - Disable agent

**Recording management**:
- `POST /api/agents/<id>/recording/start` - Listener reports recording started
- `POST /api/agents/<id>/recording/<id>/complete` - Listener reports completion
- `POST /api/agents/<id>/recording/<id>/upload` - Upload waterfall PNG
- `GET /api/recordings` - List recordings (admin)
- `GET /api/recordings/<id>/image` - Serve waterfall image
- `GET /api/challenges/<id>/recordings` - Get recordings for challenge

### Deployment Scenarios

**Scenario 1: Single listener, 5 runners**
- Listener records high-priority transmissions only
- Example: Records each challenge once per hour
- Low resource overhead, good coverage

**Scenario 2: Multiple listeners, many runners**
- First available listener gets assignment
- Future: Load balancing across listeners
- Future: Frequency-based listener selection

**Scenario 3: No listeners**
- System operates normally without any listeners
- No recording coordination overhead
- Backward compatible with pure runner deployments

### Failure Handling

**Listener failures**:
- WebSocket disconnect: Server marks `websocket_connected = false`
- Heartbeat timeout: Server marks listener offline
- Recording failure: Listener reports error, server logs to database
- No listeners available: Server logs warning, transmission proceeds normally

**Recording failures**:
- GNU Radio errors: Captured in error_message field
- File upload errors: Retried by listener
- Partial recordings: Marked as 'failed' in database

## Data Flow

### Challenge Assignment Flow

```
1. Runner Polls for Task
   ├─ Sends GET request to /api/task
   ├─ Includes runner_id and frequency capabilities
   └─ Waits for server response

2. Server Finds Available Challenge (Atomic)
   ├─ BEGIN IMMEDIATE transaction
   ├─ SELECT challenge WHERE status='queued' OR status='waiting' FOR UPDATE
   ├─ Filter by runner's frequency limits and enabled=1
   ├─ Check if 'waiting' challenge's delay has expired
   ├─   If delay expired: UPDATE status='waiting' → 'queued'
   ├─ SELECT first 'queued' challenge (by priority, then random)
   ├─ UPDATE challenge SET status='assigned', assigned_to=runner_id
   ├─ COMMIT transaction
   └─ Return challenge details to runner (or empty if none available)

3. Runner Downloads Files
   ├─ Checks local cache for file (by SHA-256)
   ├─ If not cached: GET /api/file/<hash>
   ├─ Verifies SHA-256 hash
   └─ Saves to cache

4. Runner Executes Transmission
   ├─ Generates signal using GNU Radio
   ├─ Transmits via SDR hardware
   ├─ Monitors for errors
   └─ Logs execution details

5. Runner Reports Completion
   ├─ POST to /api/complete
   ├─ Includes success/failure status
   └─ Includes any error messages

6. Server Processes Completion
   ├─ BEGIN IMMEDIATE transaction
   ├─ UPDATE challenge SET status='waiting' (starts delay timer)
   ├─ UPDATE challenge SET last_tx_time=now()
   ├─ UPDATE challenge SET assigned_to=NULL, assigned_at=NULL
   ├─ UPDATE challenge SET transmission_count++
   ├─ INSERT transmissions entry
   ├─ COMMIT transaction
   └─ Broadcast WebSocket event

7. Challenge Waits for Next Transmission
   ├─ Challenge remains in 'waiting' state
   ├─ Delay timer = (min_delay + max_delay) / 2 seconds
   ├─ When runner next polls and delay has expired
   └─ Status transitions from 'waiting' → 'queued' → 'assigned'
```

**Challenge State Cycle**:
- **queued**: Ready to be assigned to a runner
- **assigned**: Currently being transmitted by a runner
- **waiting**: Delay timer active, not yet ready for next transmission
- Flow: `queued` → `assigned` → `waiting` → (delay expires) → `queued`

### Heartbeat Flow

```
Runner (every 30s)                Server
       │                             │
       │  POST /api/heartbeat        │
       │  {runner_id: "runner-1"}    │
       ├────────────────────────────▶│
       │                             │ UPDATE runners
       │                             │ SET last_heartbeat=now()
       │                             │
       │  200 OK                     │
       │◀────────────────────────────┤
       │                             │
```

If a runner misses 3 consecutive heartbeats (90 seconds), the server marks it as offline and requeues any assigned tasks.

## Database Schema

The server uses SQLite with the following schema:

### agents

Unified table for both runner and listener agents (new in spectrum listener architecture).

| Column | Type | Description |
|--------|------|-------------|
| `agent_id` | TEXT PRIMARY KEY | Unique agent identifier |
| `agent_type` | TEXT | Agent type: 'runner' or 'listener' |
| `hostname` | TEXT | Agent machine hostname |
| `ip_address` | TEXT | Agent IP address |
| `mac_address` | TEXT | MAC address (for host validation) |
| `machine_id` | TEXT | Machine ID (for host validation) |
| `status` | TEXT | online or offline |
| `enabled` | BOOLEAN | Whether agent can receive tasks/assignments |
| `last_heartbeat` | TIMESTAMP | Last received heartbeat |
| `devices` | JSON | JSON array of SDR devices and their capabilities |
| `api_key_hash` | TEXT | Bcrypt-hashed API key |
| `websocket_connected` | BOOLEAN | WebSocket connection status (listeners only) |
| `websocket_last_connected` | TIMESTAMP | Last WebSocket connection time |
| `created_at` | TIMESTAMP | Initial registration time |
| `updated_at` | TIMESTAMP | Last update time |

### runners (legacy)

Legacy table maintained for backward compatibility. New agents register in the `agents` table.

| Column | Type | Description |
|--------|------|-------------|
| `runner_id` | TEXT PRIMARY KEY | Unique runner identifier |
| `hostname` | TEXT | Runner machine hostname |
| `ip_address` | TEXT | Runner IP address |
| `status` | TEXT | online, offline, or busy |
| `enabled` | BOOLEAN | Whether runner can receive tasks |
| `last_heartbeat` | TIMESTAMP | Last received heartbeat |
| `devices` | TEXT | JSON array of SDR devices and their capabilities |
| `api_key_hash` | TEXT | Bcrypt-hashed API key |
| `created_at` | TIMESTAMP | Initial registration time |
| `updated_at` | TIMESTAMP | Last update time |

**Migration**: On first startup with the new schema, existing runners are automatically migrated to the `agents` table with `agent_type='runner'`.

### recordings

Stores waterfall image metadata for spectrum captures.

| Column | Type | Description |
|--------|------|-------------|
| `recording_id` | INTEGER PRIMARY KEY | Auto-incrementing ID |
| `challenge_id` | TEXT | Challenge that was recorded |
| `agent_id` | TEXT | Listener agent that performed recording |
| `transmission_id` | INTEGER | Associated transmission ID |
| `frequency` | INTEGER | Center frequency (Hz) |
| `started_at` | TIMESTAMP | Recording start time |
| `completed_at` | TIMESTAMP | Recording completion time |
| `status` | TEXT | recording, completed, or failed |
| `image_path` | TEXT | Path to waterfall PNG file |
| `image_width` | INTEGER | Image width in pixels |
| `image_height` | INTEGER | Image height in pixels |
| `sample_rate` | INTEGER | SDR sample rate (Hz) |
| `duration_seconds` | REAL | Actual recording duration |
| `error_message` | TEXT | Error details (if failed) |
| `created_at` | TIMESTAMP | Record creation time |

### listener_assignments

Tracks recording assignments to listener agents for coordination.

| Column | Type | Description |
|--------|------|-------------|
| `assignment_id` | INTEGER PRIMARY KEY | Auto-incrementing ID |
| `agent_id` | TEXT | Listener agent ID |
| `challenge_id` | TEXT | Challenge to be recorded |
| `transmission_id` | INTEGER | Associated transmission ID |
| `frequency` | INTEGER | Center frequency (Hz) |
| `assigned_at` | TIMESTAMP | When assignment was created |
| `expected_start` | TIMESTAMP | Expected transmission start time |
| `expected_duration` | REAL | Expected duration (seconds) |
| `status` | TEXT | pending, recording, completed, cancelled, or failed |
| `cancelled_at` | TIMESTAMP | When assignment was cancelled (if applicable) |
| `completed_at` | TIMESTAMP | When recording completed |

### challenges

Stores challenge definitions and current state. Challenge configuration is stored as a JSON blob in the `config` column.

| Column | Type | Description |
|--------|------|-------------|
| `challenge_id` | TEXT PRIMARY KEY | Challenge identifier (usually the challenge name) |
| `name` | TEXT UNIQUE | Challenge name |
| `config` | TEXT | JSON blob containing all challenge parameters (frequency, modulation, file paths, delays, etc.) |
| `status` | TEXT | queued, waiting, assigned, or disabled |
| `priority` | INTEGER | Challenge priority (higher = more important) |
| `last_tx_time` | TIMESTAMP | Last transmission completion time |
| `next_tx_time` | TIMESTAMP | Calculated next transmission time |
| `transmission_count` | INTEGER | Total number of transmissions |
| `assigned_to` | TEXT | Runner ID currently assigned (NULL if not assigned) |
| `assigned_at` | TIMESTAMP | When current assignment was made |
| `assignment_expires` | TIMESTAMP | When assignment will timeout |
| `enabled` | BOOLEAN | Whether challenge is active |
| `created_at` | TIMESTAMP | Challenge creation time |

**Note**: There is no separate `assignments` table. Assignment information is tracked directly in the `challenges` table via the `assigned_to`, `assigned_at`, and `assignment_expires` columns.

### transmissions

Historical record of all transmissions.

| Column | Type | Description |
|--------|------|-------------|
| `transmission_id` | INTEGER PRIMARY KEY | Auto-incrementing ID |
| `challenge_id` | INTEGER | Challenge that was transmitted |
| `runner_id` | TEXT | Runner that executed the transmission |
| `device_id` | TEXT | Specific SDR device used |
| `frequency` | INTEGER | Transmission frequency (Hz) |
| `started_at` | TIMESTAMP | Transmission start time |
| `completed_at` | TIMESTAMP | Transmission completion time |
| `status` | TEXT | success or failure |
| `error_message` | TEXT | Error details (if failed) |

### files

Content-addressed storage for challenge files.

| Column | Type | Description |
|--------|------|-------------|
| `file_hash` | TEXT PRIMARY KEY | SHA-256 hash of file content |
| `filename` | TEXT | Original filename |
| `size` | INTEGER | File size in bytes |
| `mime_type` | TEXT | MIME type of file |
| `file_path` | TEXT | Path to file on server |
| `created_at` | TIMESTAMP | When file was registered |

### system_state

Key-value store for system-wide state.

| Column | Type | Description |
|--------|------|-------------|
| `key` | TEXT PRIMARY KEY | State key (e.g., "paused") |
| `value` | TEXT | State value |
| `updated_at` | TIMESTAMP | Last update time |

### users

Admin user accounts.

| Column | Type | Description |
|--------|------|-------------|
| `username` | TEXT PRIMARY KEY | Login username (unique identifier) |
| `password_hash` | TEXT | Bcrypt password hash |
| `totp_secret` | TEXT | Encrypted TOTP secret for 2FA |
| `enabled` | BOOLEAN | Whether account is active |
| `password_change_required` | BOOLEAN | Force password change on next login |
| `created_at` | TIMESTAMP | Account creation time |
| `last_login` | TIMESTAMP | Last successful login time |

### sessions

Session management for web interface.

| Column | Type | Description |
|--------|------|-------------|
| `session_token` | TEXT PRIMARY KEY | Unique session identifier |
| `username` | TEXT | Associated user account |
| `expires` | TIMESTAMP | Session expiration time (24 hours) |
| `totp_verified` | BOOLEAN | Whether TOTP has been verified for this session |
| `created_at` | TIMESTAMP | Session creation time |

**Note**: Runner API keys are stored bcrypt-hashed in the database using the secure enrollment process. API keys are associated with `enrollment_tokens` and runner records, providing strong security through one-way hashing and host validation.

## Mutual Exclusion Mechanism

ChallengeCtl guarantees that each challenge is transmitted by only one runner at a time using pessimistic database locking.

### Why Mutual Exclusion?

In RF CTF competitions, having multiple devices transmit the same challenge simultaneously causes:
- Signal interference and collision
- Degraded signal quality
- Difficult or impossible flag capture
- Unfair advantage or disadvantage to competitors

### How It Works

The assignment process uses a database transaction with immediate locking:

```python
# Simplified pseudocode
def assign_task(runner_id, frequency_limits):
    with db.begin_immediate():  # Locks database for writing
        # Find waiting challenge within runner's frequency limits
        challenge = db.query(
            "SELECT * FROM challenges "
            "WHERE status = 'waiting' "
            "AND assigned_to IS NULL "
            "AND frequency BETWEEN ? AND ? "
            "ORDER BY priority DESC, RANDOM() "
            "LIMIT 1 "
            "FOR UPDATE"  # Row-level lock
        )

        if challenge:
            # Update state and assignment atomically
            db.execute(
                "UPDATE challenges "
                "SET status = 'assigned', "
                "    assigned_to = ?, "
                "    assigned_at = ?, "
                "    assignment_expires = ? "
                "WHERE challenge_id = ?",
                (runner_id, now(), now() + 5_minutes, challenge.id)
            )

            return challenge

        return None  # No tasks available
```

**Key guarantees**:

1. **Atomicity**: State changes happen in a single transaction
2. **Isolation**: Other transactions wait until lock is released
3. **Consistency**: A challenge in "assigned" state always has a non-NULL `assigned_to` value
4. **Durability**: Committed assignments survive server crashes

### Handling Concurrent Requests

When multiple runners poll simultaneously:

```
Time  Runner 1              Runner 2              Database
──────────────────────────────────────────────────────────
T1    GET /api/task
      ├─ BEGIN IMMEDIATE
      └─ LOCK acquired     GET /api/task
                            ├─ BEGIN IMMEDIATE
                            └─ Waiting for lock...
T2    SELECT challenge=A
      UPDATE state=assigned
      INSERT assignment
      COMMIT
      └─ LOCK released
                            └─ LOCK acquired
T3                          SELECT challenge=B
                            UPDATE state=assigned
                            INSERT assignment
                            COMMIT
                            └─ LOCK released
```

Result: Runner 1 gets challenge A, Runner 2 gets challenge B. No duplicates.

## Failure Detection and Recovery

The system handles various failure scenarios automatically.

### Runner Failure Detection

**Heartbeat mechanism**:
- Runners send heartbeat every 30 seconds
- Server expects heartbeat within 90 seconds (3x interval)
- If heartbeat timeout exceeded, runner marked offline

**Cleanup process**:

```python
def cleanup_stale_runners():
    timeout = now() - 90_seconds

    # Find runners with old heartbeats
    stale_runners = db.query(
        "SELECT runner_id FROM runners "
        "WHERE last_heartbeat < ? AND status != 'offline'",
        timeout
    )

    for runner in stale_runners:
        # Mark runner offline
        db.execute(
            "UPDATE runners SET status = 'offline' "
            "WHERE runner_id = ?",
            runner.id
        )

        # Requeue assigned tasks
        db.execute(
            "UPDATE challenges "
            "SET status = 'waiting', "
            "    assigned_to = NULL, "
            "    assigned_at = NULL, "
            "    assignment_expires = NULL "
            "WHERE assigned_to = ?",
            runner.id
        )
```

### Task Timeout

Tasks that remain assigned for too long (5 minutes) are automatically requeued:

```python
def cleanup_stale_assignments():
    timeout = now()

    # Find challenges where assignment has expired
    stale = db.query(
        "SELECT challenge_id, assigned_to FROM challenges "
        "WHERE assignment_expires < ? "
        "AND assigned_to IS NOT NULL",
        timeout
    )

    for challenge in stale:
        # Requeue challenge and clear assignment
        db.execute(
            "UPDATE challenges "
            "SET status = 'waiting', "
            "    assigned_to = NULL, "
            "    assigned_at = NULL, "
            "    assignment_expires = NULL "
            "WHERE challenge_id = ?",
            challenge.challenge_id
        )
```

### Server Failure Recovery

If the server crashes or restarts:

1. **Database state is preserved** (SQLite is durable)
2. **Runners continue heartbeats** and will reconnect
3. **Assigned tasks are preserved** in the challenges table (via `assigned_to`, `assigned_at`, `assignment_expires` columns)
4. **Background tasks resume** cleanup and queueing

Runners detect server downtime through failed HTTP requests and will retry with exponential backoff.

## File Synchronization

ChallengeCtl uses content-addressed storage for challenge files.

### File Hashing

Each challenge file is identified by its SHA-256 hash:

```python
def hash_file(filepath):
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()
```

### Download and Caching

When a runner receives a task:

```python
def prepare_file(file_hash, cache_dir):
    cache_path = os.path.join(cache_dir, file_hash)

    # Check if file already cached
    if os.path.exists(cache_path):
        # Verify hash
        if hash_file(cache_path) == file_hash:
            return cache_path
        else:
            # Hash mismatch, re-download
            os.remove(cache_path)

    # Download from server
    response = requests.get(f'/api/file/{file_hash}')

    # Write to cache
    with open(cache_path, 'wb') as f:
        f.write(response.content)

    # Verify hash
    if hash_file(cache_path) != file_hash:
        raise ValueError("Downloaded file hash mismatch")

    return cache_path
```

**Benefits**:
- Files are downloaded only once per runner
- Hash verification prevents corruption
- Multiple challenges can share the same file
- Cache survives runner restarts

## Security Model

### Authentication

**Runner authentication**:
- API keys sent in `Authorization: Bearer <key>` header
- Keys stored bcrypt-hashed in database via secure enrollment process
- Each runner has unique key for accountability
- Multi-factor host validation prevents credential reuse on multiple machines
  - Host identifiers collected: MAC address, machine ID, IP address, hostname
  - Validation enforced immediately (no grace period)
  - At least ONE identifier must match for authentication
  - Re-enrollment process for legitimate host migration

**Admin authentication**:
- Username + password (bcrypt hashed in database)
- TOTP two-factor authentication (encrypted secrets in database)
- Session cookies (24-hour expiry, stored in database)
- CSRF protection on state-changing operations

### Authorization

**Access control**:
- Public endpoints: No authentication (health check, public challenges)
- Runner endpoints: Valid API key required
- Admin endpoints: Valid session + TOTP required

### Network Security

**Recommendations**:
- Deploy server behind nginx with TLS/SSL
- Use firewall to restrict port 8443 access
- Isolate SDR runners on dedicated network segment
- Use VPN for remote runner connections

### Data Protection

**Sensitive data**:
- Passwords: Bcrypt hashed (work factor 12)
- TOTP secrets: AES-256 encrypted with server master key
- API keys: Bcrypt-hashed in database with multi-factor host binding
- Session cookies: Signed and HTTPOnly

## Scalability Considerations

### Current Limitations

SQLite with pessimistic locking scales well for:
- Up to 20-30 concurrent runners
- Hundreds of challenges
- Moderate web interface usage

**Bottlenecks**:
- Database write lock contention (one writer at a time)
- Single server instance (no horizontal scaling)

### Scaling Strategies

**For larger deployments**:

1. **Use PostgreSQL**: Replace SQLite for better concurrent write performance
2. **Add caching**: Use Redis for session storage and real-time data
3. **Optimize polling**: Increase poll interval for runners (trade latency for reduced load)
4. **Distribute file serving**: Use CDN or object storage for challenge files
5. **Load balance**: Deploy multiple server instances with shared database

**Vertical scaling**:
- Increase database timeout settings
- Optimize database indexes
- Use SSD storage for database file

## Next Steps

Now that you understand the architecture, you can:

- [Review the API Reference](API-Reference) for detailed endpoint documentation
- [Explore the Configuration Reference](Configuration-Reference) for all options
- [Read the Troubleshooting guide](Troubleshooting) for common issues
- Contribute to the project by understanding the codebase structure
