# ChallengeCtl Architecture Flow Diagrams

## Complete Challenge Execution Flow

```
SERVER SIDE                          RUNNER SIDE                    HARDWARE
────────────────                     ──────────────                 ─────────

Challenge in                                                       
Database                             Runner polling loop
(status=queued)                       ┌─────────────────────┐
    │                                 │ while running:      │
    │                           ┌────▶│ every 10s:          │
    │                           │     │ GET /task           │
    │                           │     └─────────────────────┘
    │                           │              │
    │◀──────────────────────────┘              │
    │                                          │
    ├─ API: GET /api/task                      │
    │     (require_api_key)                    │
    │                                          │
    ├─ Call: assign_task(runner_id)             │
    │                                          │
    │  [BEGIN IMMEDIATE - DB LOCK]
    │  [SELECT challenge WHERE status=queued]
    │  [UPDATE status=assigned]
    │  [COMMIT - RELEASE LOCK]
    │                                          │
    └──────────────────────────────────────────▶ Task received
                                                │
                                            ┌───▼──────────────┐
                                            │ Download files   │
                                            │ (if needed)      │
                                            │ SHA-256 verify   │
                                            │ Cache locally    │
                                            └───┬──────────────┘
                                                │
                                            ┌───▼──────────────────────┐
                                            │ execute_challenge()      │
                                            │  - Select device         │
                                            │  - Optional spectrum     │
                                            │    paint first           │
                                            │  - Call modulation module│
                                            │    (cw, nbfm, ssb, ...)  │
                                            └───┬──────────────────────┘
                                                │                      ┌──────────────┐
                                                │                      │              │
                                                └─────────────────────▶│ GNU Radio TX │
                                                                       │              │
                                                                       │ ┌──────────┐ │
                                                                       │ │ osmocom  │ │
                                                                       │ │ SDR sink │─┼──▶ RF Output
                                                                       │ └──────────┘ │
                                                                       │              │
                                                                       └──────────────┘

                                            ┌───▼──────────────┐
                                            │ Report completion│
                                            │ POST /complete   │
                                            │ (success/failure)│
                                            └───┬──────────────┘
                                                │
    ┌───────────────────────────────────────────┘
    │
    ├─ API: POST /complete
    │     (require_api_key)
    │
    ├─ Update challenge:
    │   status=waiting
    │   last_tx_time=now
    │   transmission_count++
    │   assigned_to=NULL
    │
    ├─ Insert transmissions record
    │
    └─ broadcast_event('transmission_complete')
            │
            └──────────────────┐
                               │
           FRONTEND SIDE       │
           ──────────────      │
           Vue.js browser      │
           │                   │
           │◀──────────────────┘
           │
           ├─ WebSocket listener
           │  (websocket.js)
           │
           ├─ Update Dashboard.vue
           │  - Success count++
           │  - Success rate recalc
           │  - Update recent list
           │
           └─ No page refresh!
```

## Task Assignment with Mutual Exclusion

```
Runner 1                    Database (SQLite)           Runner 2
────────                    ──────────────              ────────

GET /task                                              GET /task
   │                                                      │
   │────────────────────────────────────────────────────▶ │
   │         Both request simultaneously                  │
   │                                                      │
   │          BEGIN IMMEDIATE transaction
   │          (First to lock wins)                    
   │                                                      │
   │                    ✓ Lock acquired                   │
   │                                                      │
   │          SELECT challenge WHERE                      │
   │            status='queued'                           │
   │            AND enabled=1                             │
   │          (Challenge A)                               │
   │                                                      │
   │          UPDATE Challenge A                          │
   │            SET status='assigned'                     │
   │            assigned_to='runner-1'                    │
   │            assigned_at=NOW()                         │
   │          (Atomic update)                             │
   │                                                      │
   │          COMMIT (Release lock)                       │
   │          ════════════════════════                    │
   │                                                      │
   │◀─────────────────────────────────────────────────────│
   │          Returns Challenge A                         │
   │                                                      │
   │                                                      │
   │                                            ✓ Lock acquired
   │                                            (After runner-1)
   │
   │                                            SELECT challenge WHERE
   │                                              status='queued'
   │                                              AND enabled=1
   │                                            (Challenge B - A is assigned)
   │
   │                                            UPDATE Challenge B
   │                                              SET status='assigned'
   │                                              assigned_to='runner-2'
   │
   │                                            COMMIT (Release lock)
   │
   │                                            Returns Challenge B
                                                   │
                                                   │
                                                   └──▶
```

**Result**: Runner 1 gets Challenge A, Runner 2 gets Challenge B. 
No duplicates, no races. GUARANTEED by database locking.

## Real-Time WebSocket Event Flow

```
Server Process               SocketIO Broadcast          Frontend Browsers
──────────────              ──────────────────          ────────────────

Transmission completes
(report_completion called)
    │
    │
    ├─ Update database
    │  - Challenge status
    │  - Insert transmission
    │
    │
    ├─ Call: broadcast_event('transmission_complete', {
    │       runner_id: 'runner-1',
    │       challenge_id: 'CHALLENGE_1',
    │       status: 'success',
    │       frequency: 146550000,
    │       timestamp: '2025-11-21T...'
    │   })
    │
    │
    └─ socketio.emit('event', data)
            │
            ├─────────────────────────────────────────▶ Browser 1 (Dashboard.vue)
            │   Real-time event received                  │
            │                                             │
            │                                             ├─ Log event:
            │                                             │  "Transmission complete"
            │                                             │
            │                                             ├─ Listener triggered:
            │                                             │  websocket.on('log', callback)
            │                                             │
            │                                             ├─ Update local state:
            │                                             │  stats.total_transmissions++
            │                                             │  stats.success_rate recalc
            │                                             │
            │                                             └─ Re-render (Vue reactivity)
            │
            ├─────────────────────────────────────────▶ Browser 2 (Challenges.vue)
            │   Real-time event received                  │
            │                                             │
            │                                             ├─ Listener triggered
            │                                             │
            │                                             ├─ Update challenge status
            │                                             │
            │                                             └─ Re-render table
            │
            └─────────────────────────────────────────▶ Browser 3 (Logs.vue)
                Real-time event received                  │
                                                          ├─ Listener triggered
                                                          │
                                                          ├─ Add log to buffer
                                                          │
                                                          └─ Append to log view
```

**Result**: All 3 browser windows update INSTANTLY without refresh.

## Challenge State Machine

```
                    [START]
                        │
                        ▼
        ┌───────────────────────────────┐
        │   CREATED (status=disabled)   │
        │   - In config                 │
        │   - Not running yet           │
        │   - Enable via WebUI or API   │
        └───────────┬───────────────────┘
                    │
                    │ [ENABLE]
                    │
                    ▼
        ┌───────────────────────────────┐
        │   QUEUED (status=queued)      │
        │   - Ready for transmission    │
        │   - Waiting for runner        │
        └───────────┬───────────────────┘
                    │
                    │ [Runner polls, gets task]
                    │ DB lock: BEGIN IMMEDIATE
                    │ UPDATE status='assigned'
                    │
                    ▼
        ┌───────────────────────────────┐
        │ ASSIGNED (status=assigned)    │
        │   - Executing on runner       │
        │   - assignment_expires set    │
        │   - 5-minute timeout          │
        └───────────┬─────────┬─────────┘
                    │         │
        [Success]   │         │   [Timeout/Fail]
                    ▼         ▼
        ┌──────────────────────────────┐
        │ WAITING (status=waiting)     │
        │   - Delay timer active       │
        │   - delay=(min+max)/2 secs   │
        │   - not assignable           │
        └───────────┬──────────────────┘
                    │
                    │ [Delay expires]
                    │ Background cleanup runs
                    │ UPDATE status='queued'
                    │
                    ▼
        ┌───────────────────────────────┐
        │   QUEUED (back to top)        │
        │   - Next runner gets task     │
        └───────────────────────────────┘

    [DISABLE] (from any state)
                    │
                    ▼
        ┌───────────────────────────────┐
        │ DISABLED (status=disabled)    │
        │   - No runners assigned       │
        │   - Not in queue              │
        │   - Requires re-enable        │
        └───────────────────────────────┘
```

## Runner Lifecycle

```
START
  │
  ├─ Load config (runner-config.yml)
  │
  ├─ Initialize logging
  │  - File: challengectl.runner.log
  │  - Handler: ServerLogHandler (forwards to server)
  │
  ├─ Enroll (one-time, with enrollment_token)
  │  POST /api/enrollment/enroll
  │  - Host validation (MAC, Machine ID)
  │  - API key stored in database
  │
  ├─ Register with server
  │  POST /api/agents/register
  │  - Send device info
  │  - Receive acknowledgment
  │
  ├─ Start background thread: heartbeat_loop()
  │  POST /api/agents/{id}/heartbeat (every 30s)
  │
  ├─ Main loop: while running:
  │
  │  ┌─ Sleep(poll_interval = 10s)
  │  │
  │  ├─ get_task()
  │  │  GET /api/agents/{id}/task
  │  │
  │  ├─ IF task received:
  │  │  │
  │  │  ├─ Download files (if needed)
  │  │  │  GET /api/files/{hash}
  │  │  │  Verify SHA-256
  │  │  │  Save to cache/
  │  │  │
  │  │  ├─ run_spectrum_paint() [optional]
  │  │  │  (if enabled, for 3-5 seconds)
  │  │  │
  │  │  ├─ execute_challenge()
  │  │  │  Based on modulation type:
  │  │  │  - Select GNU Radio module (cw, nbfm, etc.)
  │  │  │  - Call main() with parameters
  │  │  │  - Wait for completion
  │  │  │
  │  │  └─ report_completion()
  │  │     POST /api/agents/{id}/complete
  │  │     (success/failure + error message)
  │  │
  │  ├─ ELSE: continue to next iteration
  │  │
  │  └─ Repeat
  │
  ├─ [SIGINT/SIGTERM received]
  │
  ├─ signout()
  │  POST /api/agents/{id}/signout
  │  (graceful shutdown, clear assignment)
  │
  └─ EXIT
```

## File Caching Strategy

```
Runner wants to execute challenge with flag file

    Challenge config:
    {
      "modulation": "nbfm",
      "flag": "sha256:a1b2c3d4..."
    }

    │
    ├─ resolve_file_path()
    │  Check if path starts with "sha256:"
    │
    ├─ IF hash-based (starts with "sha256:"):
    │  │
    │  ├─ Check cache/a1b2c3d4...
    │  │
    │  ├─ IF file exists AND hash matches:
    │  │  │
    │  │  └─ Use cached file ✓ (fast)
    │  │
    │  └─ ELSE:
    │     │
    │     ├─ download_file(hash)
    │     │  GET /api/files/a1b2c3d4...
    │     │  Stream to cache/{hash}.tmp
    │     │
    │     ├─ Verify SHA-256 matches
    │     │
    │     ├─ Rename to cache/{hash}
    │     │
    │     └─ Return path ✓
    │
    └─ IF local path (challenges/file.wav):
       │
       └─ Use local path directly ✓
```

**Benefits**:
- Avoid re-downloading same files
- Multiple challenges can share same file
- Fast local execution after first run
- Survive runner restarts

## Authentication & Security Flow

```
Runner Authentication:

  1. Initial Enrollment (one-time):
     ┌─────────────────────────────┐
     │ enrollment_token (from UI)  │
     │ POST /enrollment/enroll     │
     │ - Collect MAC address       │
     │ - Collect Machine ID        │
     │ - API key stored (bcrypt)   │
     │ - Host identifiers stored   │
     └─────────────────────────────┘

  2. Subsequent Requests:
     ┌─────────────────────────────┐
     │ Authorization header:       │
     │ "Bearer {api_key}"          │
     │                             │
     │ Custom headers:             │
     │ X-Runner-MAC: aa:bb:cc...   │
     │ X-Runner-Machine-ID: ...    │
     │                             │
     │ Server validates:           │
     │ - API key hash matches      │
     │ - Host identifiers match    │
     │   (at least 1-2 factors)    │
     └─────────────────────────────┘

Admin Authentication:

  1. Login:
     username + password (bcrypt hashed)
     ↓
     Password verified ✓
     ↓
     Session created (24 hour expiry)
     ↓
     TOTP code required (2FA)
     
  2. Session operations:
     Authorization: session_token cookie
     CSRF token on state-changing requests
```

## Configuration Frequency Specification

```
Challenge frequency configuration (3 options):

┌─────────────────────────────────────────────┐
│ Option 1: Single Fixed Frequency            │
├─────────────────────────────────────────────┤
│ frequency: 146550000                        │
│ ↓                                           │
│ Always uses 146.55 MHz                      │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ Option 2: Named Frequency Ranges            │
├─────────────────────────────────────────────┤
│ frequency_ranges: [ham_144, ham_440]        │
│ ↓                                           │
│ Picks random range from list                │
│ ↓                                           │
│ Picks random frequency within range         │
│ ↓                                           │
│ Each transmission uses different freq       │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ Option 3: Manual Frequency Range            │
├─────────────────────────────────────────────┤
│ manual_frequency_range:                     │
│   min_hz: 146000000                         │
│   max_hz: 148000000                         │
│ ↓                                           │
│ Picks random frequency in range             │
│ ↓                                           │
│ Each transmission uses different freq       │
└─────────────────────────────────────────────┘
```

Named ranges defined in config:
```yaml
frequency_ranges:
  - name: ham_144
    min_hz: 144000000
    max_hz: 148000000
    description: 2-meter amateur radio band
```

---

These flow diagrams show how all the components interact to form a cohesive
distributed RF challenge transmission system.
