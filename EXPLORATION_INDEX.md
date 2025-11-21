# ChallengeCtl Codebase Exploration - Complete Index

## Three Comprehensive Documentation Files Created

This exploration created **1,724 lines** of detailed documentation across three files:

### 1. CODEBASE_ANALYSIS.md (802 lines, 24 KB)
**Complete technical breakdown of all systems**

Contents:
- Challenge Execution Architecture (workflow, states, frequency configuration)
- Spectrum Painting Implementation (OFDM technique, GNU Radio flow graph)
- Distributed Architecture (client-server, polling, WebSocket, transmitter/receiver)
- Challenge Management UI (Vue.js components, WebSocket events, CORS)
- Listener/Monitoring Infrastructure (logging, background tasks, statistics)
- Database Schema (complete with all tables and relationships)
- Challenge Workflow (timeline from start to completion)
- Key Design Decisions (SQLite, polling, Flask, Vue.js choices)
- Current Limitations and Scalability Paths

**Best for**: Understanding system design, architecture decisions, database relationships

---

### 2. KEY_FILES_REFERENCE.md (437 lines, 12 KB)
**Quick reference guide to important code locations**

Contents:
- Server Components (server.py, api.py, database.py, crypto.py)
- Runner Components (runner.py, challenge execution)
- Challenge Implementations (spectrum_paint.py, nbfm.py, cw.py)
- Frontend Components (websocket.js, Dashboard, Runners, Challenges, Logs)
- Configuration Files (server-config.yml, runner-config.yml)
- Database Access Patterns (critical mutual exclusion method)
- Common Search Patterns
- Testing Entry Points

**Best for**: Locating specific code, understanding file organization, quick lookups

---

### 3. ARCHITECTURE_FLOWS.md (485 lines, 23 KB)
**Visual diagrams showing how components interact**

Contents:
- Complete Challenge Execution Flow (end-to-end with all systems)
- Task Assignment with Mutual Exclusion (2-runner race condition prevention)
- Real-Time WebSocket Event Flow (instant UI updates)
- Challenge State Machine (queued → assigned → waiting cycle)
- Runner Lifecycle (startup through shutdown)
- File Caching Strategy (SHA-256 content addressing)
- Authentication & Security Flow (enrollment, host validation, TOTP)
- Configuration Frequency Specification (3 methods)

**Best for**: Understanding interactions, visual learners, tracing execution paths

---

## Quick Navigation

### I want to understand:

**Real-time updates**
→ ARCHITECTURE_FLOWS.md - WebSocket Event Flow section
→ KEY_FILES_REFERENCE.md - /frontend/src/websocket.js

**Challenge assignment (mutual exclusion)**
→ ARCHITECTURE_FLOWS.md - Task Assignment diagram
→ CODEBASE_ANALYSIS.md - Mutual Exclusion Mechanism section
→ KEY_FILES_REFERENCE.md - database.py assign_task() method

**Spectrum painting**
→ CODEBASE_ANALYSIS.md - Spectrum Painting Implementation section
→ KEY_FILES_REFERENCE.md - /challenges/spectrum_paint.py
→ ARCHITECTURE_FLOWS.md - Complete Challenge Execution Flow

**How challenges are executed**
→ ARCHITECTURE_FLOWS.md - Complete Challenge Execution Flow
→ KEY_FILES_REFERENCE.md - /runner/runner.py execute_challenge()
→ CODEBASE_ANALYSIS.md - Challenge Execution Architecture section

**WebUI and monitoring**
→ CODEBASE_ANALYSIS.md - Challenge Management UI structure section
→ KEY_FILES_REFERENCE.md - /frontend/src/views/
→ ARCHITECTURE_FLOWS.md - Real-Time WebSocket Event Flow

**Database design**
→ CODEBASE_ANALYSIS.md - Database Schema section
→ KEY_FILES_REFERENCE.md - Database Access Patterns
→ ARCHITECTURE_FLOWS.md - Task Assignment diagram

**Security and authentication**
→ CODEBASE_ANALYSIS.md - Database Schema (users, sessions, API keys)
→ ARCHITECTURE_FLOWS.md - Authentication & Security Flow
→ KEY_FILES_REFERENCE.md - Authentication section

**System workflow from start to finish**
→ CODEBASE_ANALYSIS.md - Challenge Workflow: Start to Completion
→ ARCHITECTURE_FLOWS.md - All diagrams show end-to-end flow
→ KEY_FILES_REFERENCE.md - Common Search Patterns section

---

## Key Findings Summary

### Architecture
- **Distributed**: Server controls, runners execute on separate machines
- **Polling-based**: Runners pull work every 10 seconds (firewall-friendly)
- **Fire-and-forget**: No listening/receiving for flag verification
- **Real-time UI**: WebSocket (Socket.IO) for instant updates

### Technology Stack
- **Server**: Python (Flask, SQLite, APScheduler)
- **Runners**: Python (GNU Radio, osmocom SDR drivers)
- **Frontend**: Vue.js 3 with Element Plus UI components
- **Communication**: HTTP REST API + WebSocket (Socket.IO)

### Critical Components
1. **Mutual Exclusion**: SQLite `BEGIN IMMEDIATE` transaction locks (database.py)
2. **Task Assignment**: Atomic challenge assignment prevents duplicates
3. **Challenge Execution**: Modulation-specific GNU Radio flow graphs
4. **Real-time Updates**: WebSocket broadcast to all connected browsers
5. **File Caching**: SHA-256 content addressing for efficient distribution

### Challenge States
```
queued → assigned → waiting → [delay] → queued → ...
```

### Data Flow
```
Config → Database → Runner Polling → Atomic Assignment → File Download 
→ GNU Radio Execution → Completion Report → State Update → Delay Timer
```

---

## File Locations Quick Reference

```
Critical Server Code:
  /server/server.py               - Entry point, background tasks
  /server/api.py                  - REST API + WebSocket broadcasting
  /server/database.py             - SQLite schema, mutual exclusion

Critical Runner Code:
  /runner/runner.py               - Polling loop, task execution

Challenge Implementations:
  /challenges/spectrum_paint.py   - OFDM spectrum painting
  /challenges/nbfm.py             - Narrowband FM modulation
  /challenges/cw.py               - Morse code modulation
  /challenges/fhss_tx.py          - Frequency hopping

Frontend Code:
  /frontend/src/websocket.js      - Real-time event handling
  /frontend/src/views/Dashboard.vue
  /frontend/src/views/Runners.vue
  /frontend/src/views/Challenges.vue
  /frontend/src/views/Logs.vue

Configuration:
  server-config.yml               - Server configuration
  runner-config.yml               - Runner configuration

Documentation:
  /docs/DISTRIBUTED_ARCHITECTURE.md
  /docs/wiki/Architecture.md
  /docs/DEPLOYMENT.md
```

---

## Understanding the Flow

### From a Runner's Perspective:
1. Load config (runner-config.yml)
2. Enroll with server (one-time, using enrollment token)
3. Register and start heartbeat thread
4. Poll for tasks every 10 seconds
5. When task received: download files, execute challenge, report completion
6. Repeat step 4

### From a Challenge's Perspective:
1. Defined in config or created via WebUI
2. Loaded into database with status='queued'
3. Assigned to first available runner (atomic transaction)
4. Runner executes using appropriate GNU Radio module
5. Status changes to 'waiting' with delay timer
6. Background cleanup job requeues after delay expires
7. Repeat from step 3

### From WebUI's Perspective:
1. Connect to server WebSocket
2. Listen for real-time events
3. On event received: update local state, re-render component
4. No page refresh needed
5. All users see same data simultaneously

---

## Research Methods Used

This exploration used multiple techniques to understand the codebase:

1. **Documentation Reading** - DISTRIBUTED_ARCHITECTURE.md, Architecture.md, DEPLOYMENT.md
2. **File Structure Analysis** - Mapped all files by location and function
3. **Code Inspection** - Examined critical files (database.py, api.py, runner.py)
4. **Cross-Reference** - Traced code paths from entry points to execution
5. **Pattern Identification** - Found recurring patterns (Flask routes, Vue components)
6. **Flow Tracing** - Followed challenge from creation to completion

---

## For Developers

To modify the system, start with:

1. **Adding a new modulation**: Implement GNU Radio flow graph in `/challenges/new_modulation.py`
2. **Adding a new UI page**: Create Vue component in `/frontend/src/views/NewPage.vue`
3. **Changing frequency logic**: Edit `/server/api.py` select_random_frequency()
4. **Scaling to more runners**: Migrate database from SQLite to PostgreSQL
5. **Understanding real-time**: Study WebSocket flow in ARCHITECTURE_FLOWS.md

---

## Next Steps

1. **Read**: Start with CODEBASE_ANALYSIS.md for full context
2. **Reference**: Use KEY_FILES_REFERENCE.md to locate specific code
3. **Visualize**: Study ARCHITECTURE_FLOWS.md to see interactions
4. **Explore**: Read source files referenced in KEY_FILES_REFERENCE.md
5. **Experiment**: Use KEY_FILES_REFERENCE.md "Common Search Patterns" to find code

---

## Questions Answered by This Exploration

- How are challenges executed? → CODEBASE_ANALYSIS.md sections 1 & 7, ARCHITECTURE_FLOWS.md
- What is spectrum painting? → CODEBASE_ANALYSIS.md section 2
- How is mutual exclusion achieved? → CODEBASE_ANALYSIS.md section 6, ARCHITECTURE_FLOWS.md
- How does the WebUI update in real-time? → CODEBASE_ANALYSIS.md section 4, ARCHITECTURE_FLOWS.md
- What is the database schema? → CODEBASE_ANALYSIS.md section 6
- How do runners communicate with server? → CODEBASE_ANALYSIS.md section 3, ARCHITECTURE_FLOWS.md
- What modulations are supported? → KEY_FILES_REFERENCE.md runner.py section
- How are files distributed? → ARCHITECTURE_FLOWS.md File Caching Strategy
- How is authentication done? → ARCHITECTURE_FLOWS.md Authentication & Security Flow
- How does the system scale? → CODEBASE_ANALYSIS.md section 9

---

## Document Statistics

| Document | Lines | Size | Coverage |
|----------|-------|------|----------|
| CODEBASE_ANALYSIS.md | 802 | 24 KB | Complete technical breakdown |
| KEY_FILES_REFERENCE.md | 437 | 12 KB | Code location reference |
| ARCHITECTURE_FLOWS.md | 485 | 23 KB | Visual flow diagrams |
| **Total** | **1,724** | **59 KB** | Full system understanding |

---

*Generated by comprehensive codebase exploration on 2025-11-21*
*All file paths are absolute: /home/user/challengectl/*
