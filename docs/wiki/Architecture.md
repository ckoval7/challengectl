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

### Runner Components

Each runner is a long-running Python process that:

1. **Registers** with the server using its API key
2. **Sends heartbeats** every 30 seconds to indicate it's alive
3. **Polls for tasks** every 5 seconds
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
1. Background Task Queues Challenge
   ├─ Checks if min_delay has elapsed since last transmission
   ├─ Marks challenge as "waiting" in database
   └─ Updates challenge state

2. Runner Polls for Task
   ├─ Sends GET request to /api/task
   ├─ Includes runner_id and frequency capabilities
   └─ Waits for server response

3. Server Assigns Task (Atomic)
   ├─ BEGIN IMMEDIATE transaction
   ├─ SELECT challenge WHERE state='waiting' FOR UPDATE
   ├─ Filter by runner's frequency limits
   ├─ SELECT first matching challenge
   ├─ UPDATE challenge SET state='assigned'
   ├─ INSERT assignment record
   ├─ COMMIT transaction
   └─ Return challenge details to runner

4. Runner Downloads Files
   ├─ Checks local cache for file (by SHA-256)
   ├─ If not cached: GET /api/file/<hash>
   ├─ Verifies SHA-256 hash
   └─ Saves to cache

5. Runner Executes Transmission
   ├─ Generates signal using GNU Radio
   ├─ Transmits via SDR hardware
   ├─ Monitors for errors
   └─ Logs execution details

6. Runner Reports Completion
   ├─ POST to /api/complete
   ├─ Includes success/failure status
   └─ Includes any error messages

7. Server Processes Completion
   ├─ BEGIN IMMEDIATE transaction
   ├─ UPDATE challenge SET state='queued'
   ├─ UPDATE challenge SET last_run=now()
   ├─ DELETE assignment record
   ├─ INSERT transmission_log entry
   ├─ COMMIT transaction
   └─ Broadcast WebSocket event
```

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
| `api_key` | TEXT | Hashed API key for authentication |
| `last_heartbeat` | TIMESTAMP | Last received heartbeat |
| `status` | TEXT | online, offline, or busy |
| `frequency_limits` | TEXT | JSON array of supported frequency ranges |
| `registered_at` | TIMESTAMP | Initial registration time |

### challenges

Stores challenge definitions and current state.

| Column | Type | Description |
|--------|------|-------------|
| `challenge_id` | INTEGER PRIMARY KEY | Auto-incrementing ID |
| `name` | TEXT UNIQUE | Challenge name |
| `frequency` | INTEGER | Transmission frequency (Hz) |
| `modulation` | TEXT | Modulation type |
| `flag_file` | TEXT | Path to challenge file |
| `flag_hash` | TEXT | SHA-256 hash of file |
| `min_delay` | INTEGER | Minimum seconds between runs |
| `max_delay` | INTEGER | Maximum seconds between runs |
| `state` | TEXT | queued, waiting, assigned, or disabled |
| `last_run` | TIMESTAMP | Last transmission time |
| `enabled` | BOOLEAN | Whether challenge is active |

### assignments

Tracks active task assignments to runners.

| Column | Type | Description |
|--------|------|-------------|
| `assignment_id` | INTEGER PRIMARY KEY | Auto-incrementing ID |
| `runner_id` | TEXT | Runner handling this task |
| `challenge_id` | INTEGER | Challenge being executed |
| `assigned_at` | TIMESTAMP | When task was assigned |

**Constraints**:
- `FOREIGN KEY (runner_id) REFERENCES runners(runner_id)`
- `FOREIGN KEY (challenge_id) REFERENCES challenges(challenge_id)`
- `UNIQUE (challenge_id)` - Each challenge can only be assigned once

### transmission_log

Historical record of all transmissions.

| Column | Type | Description |
|--------|------|-------------|
| `log_id` | INTEGER PRIMARY KEY | Auto-incrementing ID |
| `challenge_name` | TEXT | Name of challenge |
| `runner_id` | TEXT | Runner that executed |
| `frequency` | INTEGER | Transmission frequency |
| `modulation` | TEXT | Modulation type |
| `status` | TEXT | success or failure |
| `timestamp` | TIMESTAMP | Completion time |
| `error_message` | TEXT | Error details (if failed) |

### users

Admin user accounts.

| Column | Type | Description |
|--------|------|-------------|
| `user_id` | INTEGER PRIMARY KEY | Auto-incrementing ID |
| `username` | TEXT UNIQUE | Login username |
| `password_hash` | TEXT | Bcrypt password hash |
| `totp_secret` | TEXT | Encrypted TOTP secret |
| `created_at` | TIMESTAMP | Account creation time |

### runner_keys

API keys for runner authentication.

| Column | Type | Description |
|--------|------|-------------|
| `key_id` | TEXT PRIMARY KEY | Key identifier (runner name) |
| `api_key` | TEXT UNIQUE | Actual API key value |
| `created_at` | TIMESTAMP | Key generation time |

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
            "WHERE state = 'waiting' "
            "AND frequency BETWEEN ? AND ? "
            "ORDER BY RANDOM() LIMIT 1 "
            "FOR UPDATE"  # Row-level lock
        )

        if challenge:
            # Update state atomically
            db.execute(
                "UPDATE challenges SET state = 'assigned' "
                "WHERE challenge_id = ?",
                challenge.id
            )

            # Record assignment
            db.execute(
                "INSERT INTO assignments "
                "(runner_id, challenge_id, assigned_at) "
                "VALUES (?, ?, ?)",
                (runner_id, challenge.id, now())
            )

            return challenge

        return None  # No tasks available
```

**Key guarantees**:

1. **Atomicity**: State changes happen in a single transaction
2. **Isolation**: Other transactions wait until lock is released
3. **Consistency**: A challenge in "assigned" state always has an assignment record
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
            "UPDATE challenges SET state = 'waiting' "
            "WHERE challenge_id IN ("
            "  SELECT challenge_id FROM assignments "
            "  WHERE runner_id = ?"
            ")",
            runner.id
        )

        # Delete assignments
        db.execute(
            "DELETE FROM assignments WHERE runner_id = ?",
            runner.id
        )
```

### Task Timeout

Tasks that remain assigned for too long (5 minutes) are automatically requeued:

```python
def cleanup_stale_assignments():
    timeout = now() - 5_minutes

    stale = db.query(
        "SELECT * FROM assignments WHERE assigned_at < ?",
        timeout
    )

    for assignment in stale:
        # Requeue challenge
        db.execute(
            "UPDATE challenges SET state = 'waiting' "
            "WHERE challenge_id = ?",
            assignment.challenge_id
        )

        # Remove assignment
        db.execute(
            "DELETE FROM assignments WHERE assignment_id = ?",
            assignment.id
        )
```

### Server Failure Recovery

If the server crashes or restarts:

1. **Database state is preserved** (SQLite is durable)
2. **Runners continue heartbeats** and will reconnect
3. **Assigned tasks are preserved** in the assignments table
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
- API keys sent in `X-API-Key` header
- Keys stored hashed in database (bcrypt)
- Each runner has unique key for accountability

**Admin authentication**:
- Username + password (bcrypt hashed)
- TOTP two-factor authentication (encrypted secrets)
- Session cookies (24-hour expiry)
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
- API keys: Bcrypt hashed
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
