# ChallengeCtl Distributed Architecture

This document describes the distributed architecture for challengectl, enabling multiple SDR runner nodes controlled by a central server.

## Architecture Overview

```
                    ┌──────────────────┐
                    │   Web Browser    │
                    │   (Admin UI)     │
                    └────────┬─────────┘
                             │ HTTPS
                             ▼
                    ┌──────────────────┐
                    │ challengectl-    │
                    │     server       │
                    │  - REST API      │
                    │  - WebUI (SPA)   │
                    │  - SQLite DB     │
                    │  - WebSocket     │
                    │  Port 8443       │
                    └────────┬─────────┘
                             │
         ┌───────────────────┼──────────────┐
         │ mTLS/API Key      │              │
         ▼                   ▼              ▼
    ┌─────────┐        ┌─────────┐    ┌─────────┐
    │ runner-1│        │ runner-2│    │ runner-3│
    │ 2x SDRs │        │ 1x SDR  │    │ 2x SDRs │
    └─────────┘        └─────────┘    └─────────┘
```

## Components

### 1. Server (`challengectl-server`)

**Location:** `/server/`

The central controller that:
- Manages challenge queue and scheduling
- Tracks registered runners and their status
- Assigns challenges with mutual exclusion (no duplicates)
- Serves challenge files
- Provides WebUI and admin API
- Aggregates logs and metrics

**Key Files:**
- `server.py` - Main entry point and background tasks
- `api.py` - Flask REST API and WebSocket server
- `database.py` - SQLite database management

**Database Schema:**
- `runners` - Registered runner nodes
- `challenges` - Challenge definitions and state
- `transmissions` - History of all transmissions
- `files` - Challenge file metadata
- `system_state` - Global configuration

### 2. Runner (`challengectl-runner`)

**Location:** `/runner/`

Client that runs on each SDR host to:
- Register with server and send heartbeats
- Poll for challenge assignments
- Download required files (WAV, etc.)
- Execute challenges on local SDR devices
- Report completion status

**Key Files:**
- `runner.py` - Main runner implementation

**Supported Modulations:**
All existing challengectl-v2 modulations:
- CW (Morse code)
- ASK (Amplitude shift keying)
- NBFM (Narrowband FM)
- SSB (Single sideband - LSB/USB)
- FHSS (Frequency hopping)
- POCSAG (Pager)
- LRS (Pager)
- FreeDV (Digital voice)

### 3. WebUI (`challengectl-frontend`)

**Location:** `/frontend/`

Vue.js 3 single-page application with:
- **Dashboard** - Real-time system overview
- **Runners** - Manage connected runners
- **Challenges** - Enable/disable/trigger challenges
- **Logs** - Live log streaming

**Technology Stack:**
- Vue.js 3
- Element Plus (UI components)
- Axios (HTTP client)
- Socket.IO (WebSocket)
- Vite (build tool)

## Installation

### Server Setup

1. Install Python dependencies:
```bash
pip install flask flask-socketio flask-cors pyyaml requests apscheduler
```

2. Create server configuration:
```bash
cd server
python server.py --config server-config.yml
# Edit the generated server-config.yml
```

3. Start server:
```bash
python server.py
```

Server will listen on `http://0.0.0.0:8443`

### Runner Setup

1. Install on each SDR host:
```bash
cd runner
python runner.py --config runner-config.yml
# Edit the generated runner-config.yml with:
#   - runner_id (unique identifier)
#   - server_url (server address)
#   - api_key (from server config)
#   - SDR devices
```

2. Start runner:
```bash
python runner.py
```

### WebUI Setup

1. Install Node.js dependencies:
```bash
cd frontend
npm install
```

2. Development mode:
```bash
npm run dev
# Access at http://localhost:3000
```

3. Production build:
```bash
npm run build
# Static files output to frontend/dist/
# Server serves these automatically
```

## Configuration

### Server Configuration (`server-config.yml`)

```yaml
server:
  bind: "0.0.0.0"
  port: 8443

  # API keys for authentication
  api_keys:
    runner-1: "secret-key-1"
    runner-2: "secret-key-2"
    admin: "admin-key"

conference:
  name: "ExampleCon 2025"
  start: "2025-04-05 09:00:00"
  stop: "2025-04-07 18:00:00"

challenges:
  - name: NBFM_FLAG_1
    frequency: 146550000
    modulation: nbfm
    flag: challenges/voice.wav
    min_delay: 60
    max_delay: 90
    enabled: true
  # ... more challenges
```

### Runner Configuration (`runner-config.yml`)

```yaml
runner:
  runner_id: "runner-1"
  server_url: "https://192.168.1.100:8443"
  api_key: "secret-key-1"

  cache_dir: "/var/cache/challengectl"
  heartbeat_interval: 30
  poll_interval: 10

radios:
  models:
  - model: hackrf
    rf_gain: 14
    bias_t: true

  devices:
  - name: 0
    model: hackrf
    frequency_limits:
      - "144000000-148000000"
      - "420000000-450000000"
```

## API Reference

### Public Endpoints (No Authentication Required)

- `GET /api/health` - Health check
- `GET /api/public/challenges` - Public challenge status dashboard
  - Returns enabled challenges with configurable visibility
  - Never exposes flag content, file paths, or sensitive information
  - Respects per-challenge `public_view` settings

### Runner Endpoints (Requires Runner API Key)

- `POST /api/runners/register` - Register runner
- `POST /api/runners/{id}/heartbeat` - Send heartbeat
- `GET /api/runners/{id}/task` - Get next challenge
- `POST /api/runners/{id}/complete` - Report completion
- `GET /api/files/{hash}` - Download file

### Admin Endpoints (Requires Admin API Key)

- `GET /api/dashboard` - Dashboard statistics
- `GET /api/runners` - List all runners
- `GET /api/challenges` - List all challenges
- `POST /api/challenges/{id}/trigger` - Trigger challenge now
- `POST /api/control/pause` - Pause system
- `POST /api/control/resume` - Resume system
- `POST /api/control/emergency-stop` - Emergency stop

### WebSocket Events

Server broadcasts these events to WebUI:
- `runner_status` - Runner online/offline
- `challenge_assigned` - Challenge assigned to runner
- `transmission_complete` - Transmission finished
- `log` - Log entry from runner or server

## Security

### Authentication

- **API Keys:** Pre-shared keys in configuration
- **TLS:** Use reverse proxy (nginx) for TLS in production
- Each runner has unique API key
- Admin key for WebUI access

### Mutual Exclusion

Challenges use **pessimistic locking** in SQLite:
1. Runner requests task
2. Server locks database with `BEGIN IMMEDIATE`
3. Finds available challenge
4. Atomically marks as `assigned`
5. Commits transaction
6. Returns challenge to runner

**Result:** Two runners will NEVER get the same challenge simultaneously.

### Timeout Handling

- Runners send heartbeats every 30 seconds
- Server marks offline after 90 seconds of missed heartbeats
- Challenge assignments timeout after 5 minutes
- Stale assignments automatically requeued

## File Management

### Content-Addressed Storage

Files identified by SHA-256 hash:
1. Server stores files in `files/` directory
2. Challenge references file by hash
3. Runner checks local cache
4. If missing, downloads from server
5. Verifies SHA-256 after download

### Cache Directory

Runner maintains cache at `/var/cache/challengectl/`:
- Downloaded files persist across runs
- Hash verification on every use
- No manual cleanup needed (files are small)

## Operational Workflows

### Starting the System

1. Start server: `python server/server.py`
2. Verify WebUI accessible at `http://server:8443`
3. Start each runner: `python runner/runner.py -c runner-N-config.yml`
4. Verify runners appear online in WebUI

### Adding Challenges

1. Edit `server-config.yml`
2. Add challenge to `challenges:` section
3. Click "Reload from Config" in WebUI
4. Or restart server

### Manual Challenge Trigger

1. Go to Challenges page in WebUI
2. Click "Trigger Now" next to challenge
3. Next available runner will execute it

### Emergency Stop

1. Click "Emergency Stop" in WebUI header
2. All runners stop polling for tasks
3. All assigned challenges requeued
4. System marked as paused

### Monitoring

- **Dashboard:** Real-time stats and recent activity
- **Runners:** Check online/offline status
- **Logs:** Live stream of all events

## Troubleshooting

### Runner Won't Connect

- Check `server_url` in runner config
- Verify API key matches server config
- Check network connectivity
- Check server logs for authentication errors

### No Challenges Assigned

- Check challenges are `enabled: true` in config
- Verify system not paused (WebUI header)
- Check `next_tx_time` hasn't been delayed
- Check runner device capabilities match challenge frequencies

### File Download Fails

- Verify file exists in server `files/` directory
- Check file registered in database
- Verify hash matches filename
- Check runner has write access to cache directory

### Transmission Errors

- Check SDR device is available (not in use)
- Verify antenna settings for BladeRF
- Check bias-tee configuration
- Review runner logs for GNU Radio errors

## Future Enhancements

Possible improvements:
- [ ] Certificate-based auth (mTLS)
- [ ] Multi-server failover
- [ ] Frequency coordination (avoid collisions)
- [ ] Priority-based scheduling
- [ ] Prometheus metrics export
- [ ] Challenge result verification
- [ ] Bandwidth throttling for file transfers
- [ ] Device capability matching (auto-assign)

## Architecture Decisions

### Why SQLite?

- Simple deployment (single file)
- Good enough for 2-3 runners
- Built-in transactions for locking
- No separate database server needed

### Why Polling (not Push)?

- Simpler firewall rules (runners initiate)
- Easier NAT traversal
- Runners can cache work offline
- More reliable than server-push

### Why Flask (not FastAPI)?

- Simpler for synchronous workloads
- Better Flask-SocketIO integration
- Widely deployed and stable

### Why Vue.js (not React)?

- Simpler learning curve for this use case
- Great for admin panels
- Excellent component library (Element Plus)
- Single-file components

## Performance

Expected performance with this architecture:

| Metric | Value |
|--------|-------|
| Max runners | 10-20 (SQLite limit) |
| Challenges/hour | 100+ per runner |
| API latency | <50ms (local network) |
| Heartbeat overhead | ~1 KB/30s per runner |
| Assignment latency | <100ms (lock acquisition) |
| File transfer | Limited by network |

For larger deployments (>20 runners), consider:
- PostgreSQL instead of SQLite
- Redis for caching and locking
- Load-balanced server instances
- CDN for file distribution

## Testing

### Manual Testing

1. Start server
2. Start 2 runners with different IDs
3. Add challenges to config
4. Observe in WebUI:
   - Both runners show online
   - Challenges assigned alternately
   - No duplicate assignments
5. Stop one runner
   - Verify marked offline after 90s
   - Assignments requeued
6. Test emergency stop
   - Verify all transmissions halt

### Integration Testing

(TODO: Add automated tests)

## License

Same as main challengectl project.
