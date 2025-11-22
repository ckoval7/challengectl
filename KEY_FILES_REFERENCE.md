# Key Files Reference Guide

This document maps the important files to their functionality.

## Server Components

### `/server/server.py` (Main Entry Point)
**Lines: ~250**
**Purpose**: Server initialization and background task scheduling

**Key Classes**:
- `ChallengeCtlServer` - Main controller with background tasks
- Background tasks: Cleanup runners, assignments, sessions, users (via APScheduler)

**Key Functions**:
- `setup_background_tasks()` - Schedule cleanup operations
- `signal_handler()` - Graceful shutdown

**Run with**: `python3 server.py -c server-config.yml`

---

### `/server/api.py` (REST API and WebSocket)
**Lines: ~3000+**
**Purpose**: All HTTP endpoints and WebSocket real-time updates

**Key Classes**:
- `ChallengeCtlAPI` - Main API server
- `WebSocketHandler` - Log broadcasting via Socket.IO

**Key API Endpoints**:
- `POST /api/agents/register` - Runner registration
- `POST /api/agents/{id}/heartbeat` - Heartbeat
- `GET /api/agents/{id}/task` - Task polling (CRITICAL - has mutual exclusion lock)
- `POST /api/agents/{id}/complete` - Completion reporting
- `POST /api/agents/{id}/log` - Log forwarding
- `GET /api/dashboard` - Statistics
- `GET /api/challenges` - List challenges
- `POST /api/challenges/{id}/trigger` - Manual trigger
- `GET /api/files/{hash}` - File download

**Authentication**:
- Runner: API key in `Authorization: Bearer` header
- Admin: Session token + TOTP
- Public: No auth required for `/api/public/*`

**Rate Limiting**: Default 100 per minute, runner endpoints higher

---

### `/server/database.py` (SQLite Schema and Operations)
**Lines: ~1000+**
**Purpose**: Database abstraction and schema management

**Key Classes**:
- `Database` - Thread-safe SQLite wrapper

**Key Methods**:
- `init_database()` - Creates tables on startup
- `assign_task()` - CRITICAL: Atomic task assignment with locking
- `get_task()` - Retrieve task for runner
- `report_completion()` - Process transmission completion
- `cleanup_stale_runners()` - Mark offline after 90s
- `cleanup_stale_assignments()` - Requeue after 5min timeout
- `find_runner_by_api_key()` - Authentication with host validation

**Threading**: Uses `threading.local()` for thread-safe connections

**Locking Strategy**: Uses `BEGIN IMMEDIATE` for exclusive database locks

---

### `/server/crypto.py`
**Purpose**: TOTP encryption and password hashing

**Key Functions**:
- `encrypt_totp_secret()` - AES-256 encryption
- `decrypt_totp_secret()` - AES-256 decryption
- Password hashing via `bcrypt`

---

## Runner Components

### `/runner/runner.py` (Runner Client)
**Lines: ~800+**
**Purpose**: Client that polls for tasks, downloads files, executes challenges

**Key Classes**:
- `ChallengeCtlRunner` - Main runner
- `ServerLogHandler` - Forward logs to server

**Key Methods**:
- `register()` - Register with server
- `enroll()` - Enrollment using token (one-time)
- `send_heartbeat()` - Periodic heartbeat (every 30s)
- `heartbeat_loop()` - Background thread
- `get_task()` - Poll for work
- `download_file()` - Download with verification
- `execute_challenge()` - CRITICAL: Run the challenge (lines 514-678)
- `run_spectrum_paint()` - Optional spectrum painting before challenge
- `report_completion()` - Report success/failure

**Challenge Execution** (`execute_challenge` method):
- Selects device
- Optional spectrum paint
- Calls appropriate modulation module based on config
- Returns (success, device_id, frequency)

**Modulations Supported**:
- `cw` - Morse code (via cw.py)
- `ask` - Amplitude shift keying (via ask.py)
- `nbfm` - Narrowband FM (via nbfm.py)
- `ssb` - Single sideband (via ssb_tx.py)
- `fhss` - Frequency hopping (via fhss_tx.py)
- `freedv` - Digital voice (via freedv_tx.py)
- `pocsag` - Pager (via pocsagtx_osmocom.py)
- `lrs` - Pager (via lrs_pager.py + lrs_tx.py)
- `paint` - Spectrum painting (via spectrum_paint.py)

---

## Challenge Implementations

### `/challenges/spectrum_paint.py`
**Lines: ~108**
**Purpose**: OFDM spectrum painting GNU Radio flow graph

**Key Class**:
- `spectrum_paint` - GNU Radio flow graph

**Key Blocks**:
- `paint.paint_bc` - Spectrum painter block
- `blocks.file_source` - Input data from file
- `digital.ofdm_cyclic_prefixer` - OFDM encoding
- `osmosdr.sink` - SDR transmitter

**Main Function**:
- Takes: `freq`, `device`, `antenna`
- Sets up flow graph and transmits

### `/challenges/nbfm.py`
**Lines: ~200+**
**Purpose**: Narrowband FM modulation

**Key Class**:
- `nbfm` - GNU Radio flow graph

**Parameters**:
- `audio_gain` - Audio level
- `freq` - Center frequency
- `dev` - Device string
- `wav_file` - Audio input file
- `wav_rate` - Sample rate (default 48kHz)

### `/challenges/cw.py`
**Lines: ~200+**
**Purpose**: Morse code modulation

**Features**:
- Morse code dictionary for characters
- CW generation at specified WPM
- Frequency offset capability

---

## Frontend Components

### `/frontend/src/websocket.js`
**Lines: ~85**
**Purpose**: Socket.IO client for real-time updates

**Key Class**:
- `WebSocketManager` - Singleton WebSocket handler

**Event Types Received**:
- `log` - Real-time logs
- `runner_status` - Runner online/offline
- `challenge_assigned` - Task assignment
- `transmission_complete` - Completion
- Custom listeners via `on(eventType, callback)`

### `/frontend/src/views/Dashboard.vue`
**Purpose**: System overview and statistics

**Updates from WebSocket**:
- Real-time runner status changes
- Challenge assignments
- Transmission completions
- Live logs

**Statistics Displayed**:
- Runners online / total
- Challenges queued / total
- Total transmissions
- Success rate (%)

### `/frontend/src/views/Runners.vue`
**Purpose**: Runner management

**Operations**:
- Add new runner (generates enrollment token)
- Enable/disable runners
- Re-enroll runners
- Kick (disconnect) runners
- View device details
- Monitor heartbeat timestamps

### `/frontend/src/views/Challenges.vue`
**Purpose**: Challenge control

**Operations**:
- Enable/disable challenges
- Trigger immediate transmission
- View queue status
- Monitor transmission history
- Adjust delays and priorities

### `/frontend/src/views/Logs.vue`
**Purpose**: Real-time log viewer

**Features**:
- Live streaming via WebSocket
- Filter by source (server / runner)
- Filter by level
- Last 500 logs buffered

### `/frontend/src/api.js`
**Lines: ~200+**
**Purpose**: REST API client wrapper

**Key Functions**:
- `getDashboard()` - Fetch stats
- `getRunners()` - List runners
- `getChallenges()` - List challenges
- `triggerChallenge()` - Manual trigger
- `enableRunner()` / `disableRunner()` - Control runner
- `getLogs()` - Fetch logs

---

## Configuration Files

### `server-config.yml` (Server Configuration)
**Key Sections**:
```yaml
server:
  bind: "0.0.0.0"
  port: 8443
  
conference:
  name: "Event Name"
  start: "2025-01-01 09:00:00"
  stop: "2025-01-03 18:00:00"

challenges:
  - name: CHALLENGE_NAME
    frequency: 146550000
    modulation: nbfm
    flag: challenges/file.wav
    min_delay: 60
    max_delay: 120
    enabled: true

frequency_ranges:
  - name: ham_144
    min_hz: 144000000
    max_hz: 148000000
```

### `runner-config.yml` (Runner Configuration)
**Key Sections**:
```yaml
runner:
  runner_id: "runner-1"
  server_url: "https://challengectl.example.com:8443"
  api_key: "from-web-ui"
  enrollment_token: "from-web-ui"
  poll_interval: 10
  heartbeat_interval: 30
  cache_dir: "cache"

radios:
  devices:
    - name: 0
      model: hackrf
      frequency_limits:
        - "144000000-148000000"
        - "420000000-450000000"
```

---

## Database Access

### Most Critical Method: `assign_task()` in database.py

This is where mutual exclusion happens:

```python
def assign_task(self, runner_id: str, frequency_limits: List = None) -> Optional[Dict]:
    """Atomically assign a task to a runner with pessimistic locking."""
    
    with self.get_connection() as conn:
        cursor = conn.cursor()
        
        # BEGIN IMMEDIATE - locks database
        cursor.execute('BEGIN IMMEDIATE')
        
        # Find available challenge
        cursor.execute('''
            SELECT * FROM challenges
            WHERE status = 'queued' AND enabled = 1
            AND ... (frequency checks)
            ORDER BY priority DESC, RANDOM()
            LIMIT 1
            FOR UPDATE
        ''')
        
        challenge = cursor.fetchone()
        
        if challenge:
            # Atomic update
            cursor.execute('''
                UPDATE challenges
                SET status = 'assigned',
                    assigned_to = ?,
                    assigned_at = NOW(),
                    assignment_expires = NOW() + 5 minutes
                WHERE challenge_id = ?
            ''', (runner_id, challenge['challenge_id']))
            
            conn.commit()  # RELEASE LOCK
            return dict(challenge)
        
        conn.commit()  # RELEASE LOCK
        return None
```

**Why BEGIN IMMEDIATE?**
- Locks database for exclusive write access
- Prevents race conditions
- Two runners cannot get same challenge
- Timeout on lock contention

---

## Key Workflows

### Challenge Execution Flow (from runner.py)

```
1. Runner.main() starts
2. enroll() - one-time enrollment
3. register() - register with server
4. start heartbeat_loop() - background thread
5. main_loop():
   a. get_task() - poll for work
   b. IF task received:
      - download_file() if needed
      - run_spectrum_paint() if configured
      - execute_challenge() - calls modulation module
      - report_completion()
   c. sleep(poll_interval)
   d. GOTO 5a
```

### Task Assignment Flow (from api.py)

```
1. Runner: GET /api/agents/{id}/task
2. Server: db.assign_task(runner_id)
   a. BEGIN IMMEDIATE (lock database)
   b. Find queued challenge matching capabilities
   c. UPDATE status to 'assigned'
   d. COMMIT (release lock)
3. Return challenge to runner
4. Other waiting runners get empty response
```

### WebUI Update Flow (from websocket.js)

```
1. Server: broadcast_event(type, data)
   a. Emits via socketio.emit('event', data)
2. Frontend websocket.js receives 'event'
3. Dispatches to registered listeners
4. Vue component receives and updates UI
5. No page refresh needed
```

---

## Common Search Patterns

**Find where challenges are assigned:**
- `/server/api.py` → `@require_api_key` → `assign_task()` endpoint
- `/server/database.py` → `assign_task()` method

**Find where spectrum paint executes:**
- `/runner/runner.py` → `run_spectrum_paint()` (optional before)
- `/runner/runner.py` → `execute_challenge()` → modulation == 'paint'
- `/challenges/spectrum_paint.py` → `spectrum_paint.main()`

**Find real-time updates:**
- `/frontend/src/websocket.js` → `WebSocketManager`
- `/server/api.py` → `broadcast_event()`
- `/frontend/src/views/*.vue` → `websocket.on()`

**Find authentication:**
- `/server/api.py` → `require_api_key()` decorator
- `/runner/runner.py` → `enroll()` and `register()`
- Multi-factor host validation in `database.py` → `find_runner_by_api_key()`

**Find database locking:**
- `/server/database.py` → `BEGIN IMMEDIATE` transactions
- `/server/database.py` → `assign_task()` critical section
- Lock timeout: 5 minutes per challenge

---

## Testing Entry Points

- `/tests/test_database.py` - Database tests
- `/tests/test_crypto.py` - Crypto tests
- `/tests/test_integration.py` - Integration tests
- `/frontend/src/*.spec.js` - Frontend unit tests

---

## Documentation References

- `/docs/DISTRIBUTED_ARCHITECTURE.md` - System architecture
- `/docs/wiki/Architecture.md` - Component details
- `/docs/DEPLOYMENT.md` - Deployment guide
- `/docs/wiki/Configuration-Reference.md` - Config options
- `/CODEBASE_ANALYSIS.md` - This comprehensive analysis
