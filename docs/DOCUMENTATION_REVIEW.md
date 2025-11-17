# Documentation Review - Updated Findings

This document lists discrepancies between the wiki documentation and the actual codebase implementation.

**Last Updated**: 2024-01-17 (Second Review)

## Status Summary

✅ **Fixed in Previous Updates**:
- Database schema tables (files, system_state, sessions added)
- API key management (corrected to config file, not database)
- Stop function behavior (pauses, doesn't shutdown)
- User management (web-based, manage-users.py references removed)
- Background task intervals documented

❌ **New Issues Found in Second Review**:
1. Challenge state flow documentation incorrect
2. Challenge ID type mismatch (INTEGER vs TEXT)
3. Cleanup behavior documentation incomplete

## Current Issues

### 1. Challenge State Flow (Architecture.md)

**Documentation claims** (lines 185-188):
```
1. Background Task Queues Challenge
   ├─ Checks if min_delay has elapsed since last transmission
   ├─ Marks challenge as "waiting" in database
   └─ Updates challenge state
```

**Actual implementation**:
- There is **NO background task that queues challenges**
- Challenge state flow is:
  1. Challenge completes → status = 'waiting' (delay timer starts)
  2. Runner polls for task → if delay expired, 'waiting' → 'queued' transition happens inline
  3. Challenge assigned → status = 'assigned'
  4. Challenge completes → back to 'waiting'

**Actual code** (database.py:478-488):
```python
# During get_next_challenge():
if row['status'] == 'waiting':
    # Update waiting -> queued if delay has passed
    cursor.execute('''
        UPDATE challenges
        SET status = 'queued'
        WHERE challenge_id = ?
    ''', (cid,))
```

**Actual code** (database.py:552-562, complete_challenge):
```python
# Update challenge status to waiting (delay timer active)
cursor.execute('''
    UPDATE challenges
    SET status = 'waiting',
        assigned_to = NULL,
        assigned_at = NULL,
        assignment_expires = NULL,
        transmission_count = transmission_count + 1,
        last_tx_time = CURRENT_TIMESTAMP
    WHERE challenge_id = ?
''', (challenge_id,))
```

**Impact**: Architecture.md Challenge Assignment Flow section is misleading.

### 2. Challenge ID Data Type

**Documentation** (Architecture.md line 263):
```
| `challenge_id` | INTEGER PRIMARY KEY | Auto-incrementing ID |
```

**Actual implementation** (database.py:75):
```python
CREATE TABLE IF NOT EXISTS challenges (
    challenge_id TEXT PRIMARY KEY,
    ...
)
```

**Reality**: `challenge_id` is TEXT (likely a slug or name-based ID), not an auto-incrementing INTEGER.

**Impact**: Architecture.md database schema table is incorrect.

### 3. Stale Assignment Cleanup Behavior

**Current documentation**: Architecture.md shows cleanup setting status to 'waiting'

**Actual implementation** (database.py:575-596):
```python
def cleanup_stale_assignments(self, timeout_minutes: int = 5) -> int:
    cursor.execute('''
        UPDATE challenges
        SET status = 'waiting',  # Not 'queued'
            assigned_to = NULL,
            assigned_at = NULL,
            assignment_expires = NULL
        WHERE status = 'assigned'
          AND assignment_expires < CURRENT_TIMESTAMP
    ''')
```

**Observation**: When an assignment times out, it goes to 'waiting' (respects delay timer) rather than immediately to 'queued'. This is actually documented correctly but worth noting explicitly.

### 4. Stop System Behavior

**Status**: ✅ FIXED in previous update

The documentation now correctly states that Stop:
- Pauses the system
- Requeues all assigned challenges (to 'queued', not 'waiting')
- Does NOT shut down the server

**Actual code** (api.py:1597-1621):
```python
def stop_system():
    self.db.set_system_state('paused', 'true')
    # Requeue all assigned challenges
    conn.execute('''
        UPDATE challenges
        SET status = 'queued',  # Goes directly to queued, bypassing delay
            assigned_to = NULL,
            assigned_at = NULL,
            assignment_expires = NULL
        WHERE status = 'assigned'
    ''')
```

**Note**: Stop button requeues to 'queued' (immediate availability), while timeout cleanup requeues to 'waiting' (respects delay). This distinction could be documented.

## Previously Fixed Issues

### ✅ 1. Database Schema (FIXED)

Architecture.md now correctly documents:
- No separate `runner_keys` table (keys in config file)
- No separate `assignments` table (tracked in challenges table)
- Correct table name `transmissions` (not transmission_log)
- Includes `files`, `system_state`, `sessions` tables
- Shows `username` as PK in users table (not user_id)

### ✅ 2. API Key Management (FIXED)

Documentation now correctly shows:
- API keys in `server-config.yml` under `server.api_keys`
- Use `generate-api-key.py` to create keys
- Edit config file and restart server to add/change keys
- No database commands for API key management

### ✅ 3. User Management (FIXED)

Documentation now correctly shows:
- Server creates default admin account on first run
- Temp credentials shown in server logs
- All user management through web interface
- No `manage-users.py` references
- Direct database access only for recovery scenarios

### ✅ 4. Background Task Intervals (FIXED)

Architecture.md now documents:
- Cleanup stale runners: every 30 seconds
- Cleanup stale assignments: every 30 seconds
- Cleanup expired sessions: every 60 seconds
- Cleanup expired TOTP codes: every 60 seconds

### ✅ 5. Database Auto-Initialization (FIXED)

Server-Setup.md now correctly shows:
- Database created automatically on first server start
- No manual `python -m challengectl.server.database init` needed

## Recommended Fixes

### High Priority

1. **Fix Challenge State Flow** (Architecture.md lines 185-188)
   - Remove "Background Task Queues Challenge" step
   - Accurately describe the 'waiting' → 'queued' → 'assigned' → 'waiting' cycle
   - Clarify that state transitions happen during get_next_challenge() polling

2. **Fix Challenge ID Type** (Architecture.md line 263)
   - Change from `INTEGER PRIMARY KEY` to `TEXT PRIMARY KEY`
   - Remove "Auto-incrementing ID" description
   - Note that challenge_id is a text identifier (usually the challenge name)

### Medium Priority

3. **Document Stop vs Timeout Behavior**
   - Stop button: assigned → 'queued' (immediate availability)
   - Timeout cleanup: assigned → 'waiting' (respects delay timer)
   - Explain why they differ

4. **Add Challenge State Diagram**
   - Visual diagram showing: queued → assigned → waiting → queued
   - Show when transitions occur (runner poll, completion, timeout)

### Low Priority

5. **Document Edge Cases**
   - What happens to 'waiting' challenges when delay expires
   - How priority affects challenge selection
   - Challenge timing mechanism (in-memory vs database)

## Verified Correct

The following are accurately documented:

✅ Runner heartbeat timeout: 90 seconds
✅ Assignment expiry timeout: 5 minutes
✅ Session duration: 24 hours
✅ Background task intervals: 30s and 60s
✅ Pause behavior: stops queueing, keeps runners connected
✅ Stop behavior: pauses + requeues all assigned challenges
✅ Database schema (tables and most columns)
✅ API endpoints (paths and methods verified)
✅ WebSocket event broadcasting
✅ TOTP two-factor authentication
✅ API key authentication (X-API-Key header)
✅ Session-based admin authentication
✅ File synchronization (SHA-256 content addressing)
✅ Mutual exclusion via pessimistic locking
✅ Automatic default admin account creation
✅ Initial setup wizard flow

## Testing Verification

Confirmed by code review:

- ✅ Challenge states: 'queued', 'waiting', 'assigned', 'disabled' (enabled=0)
- ✅ Runner statuses: 'online', 'offline', 'busy'
- ✅ Transmission statuses: 'success', 'failed'
- ✅ System state keys: 'paused', 'initial_setup_required'
- ✅ Cleanup intervals match documentation
- ✅ Database schema matches code
- ✅ API endpoints match route definitions
