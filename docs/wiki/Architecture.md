# Architecture Overview

This document provides a technical overview of the ChallengeCtl system architecture, explaining how components interact, how data flows through the system, and the key design decisions that enable reliable challenge distribution.

## Table of Contents

- [System Overview](#system-overview)
- [Component Architecture](#component-architecture)
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
│  └──────────────┘  └──────────────┘  └───────────┘ │
│  ┌──────────────────────────────────────────────┐   │
│  │        Background Tasks                      │   │
│  │  - Cleanup stale assignments                 │   │
│  │  - Requeue timed-out tasks                   │   │
│  │  - Monitor runner health                     │   │
│  └──────────────────────────────────────────────┘   │
└──────────────────┬──────────────────────────────────┘
                   │ HTTP (Polling)
         ┌─────────┼─────────┬─────────────┐
         ▼         ▼         ▼             ▼
    ┌────────┐ ┌────────┐ ┌────────┐  ┌────────┐
    │Runner 1│ │Runner 2│ │Runner 3│  │Runner N│
    │(HackRF)│ │(LimeSDR│ │(USRP)  │  │  ...   │
    └────────┘ └────────┘ └────────┘  └────────┘
         │         │         │             │
         ▼         ▼         ▼             ▼
      [Radio]  [Radio]  [Radio]       [Radio]
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
- **Runners**: List of registered runners with status and controls
- **Challenges**: Challenge management and manual triggering
- **Logs**: Real-time log streaming from server and runners

The frontend communicates with the server via:
- REST API for data retrieval and actions
- WebSocket for real-time updates (no polling required)

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

### runners

Stores registered runners and their status.

| Column | Type | Description |
|--------|------|-------------|
| `runner_id` | TEXT PRIMARY KEY | Unique runner identifier |
| `hostname` | TEXT | Runner machine hostname |
| `ip_address` | TEXT | Runner IP address |
| `status` | TEXT | online, offline, or busy |
| `enabled` | BOOLEAN | Whether runner can receive tasks |
| `last_heartbeat` | TIMESTAMP | Last received heartbeat |
| `devices` | TEXT | JSON array of SDR devices and their capabilities |
| `created_at` | TIMESTAMP | Initial registration time |
| `updated_at` | TIMESTAMP | Last update time |

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
