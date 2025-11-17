# Documentation Review - Inconsistencies Found

This document lists discrepancies between the wiki documentation and the actual codebase implementation.

## Critical Inconsistencies

### 1. Database Schema

**Documentation claimed**: Separate tables for runner_keys, assignments, transmission_log

**Actual implementation**:
- **No separate `runner_keys` table**: API keys are stored in `server-config.yml` under `server.api_keys`, not in the database
- **No separate `assignments` table**: Challenge assignments are tracked via columns in the `challenges` table (`assigned_to`, `assigned_at`, `assignment_expires`)
- **Table is named `transmissions`, not `transmission_log`**
- **Additional tables not documented**: `files`, `system_state`, `sessions`

**Actual schema**:
```sql
runners:
  - runner_id (PK)
  - hostname
  - ip_address
  - status
  - enabled
  - last_heartbeat
  - devices (JSON)
  - created_at
  - updated_at

challenges:
  - challenge_id (PK)
  - name (UNIQUE)
  - config (JSON) -- ALL challenge config in one blob
  - status
  - priority
  - last_tx_time
  - next_tx_time
  - transmission_count
  - assigned_to (FK to runners)
  - assigned_at
  - assignment_expires
  - enabled
  - created_at

transmissions:
  - transmission_id (PK)
  - challenge_id (FK)
  - runner_id (FK)
  - device_id
  - frequency
  - started_at
  - completed_at
  - status
  - error_message

files:
  - file_hash (PK)
  - filename
  - size
  - mime_type
  - file_path
  - created_at

system_state:
  - key (PK)
  - value
  - updated_at

users:
  - username (PK, not user_id)
  - password_hash
  - totp_secret
  - enabled
  - password_change_required
  - created_at
  - last_login

sessions:
  - session_token (PK)
  - username (FK)
  - expires
  - totp_verified
  - created_at
```

### 2. API Key Management

**Documentation claimed**:
- API keys stored in database
- Commands like `python -m challengectl.server.database add-runner-key`
- API keys can be managed through the database

**Actual implementation**:
- API keys stored in `server-config.yml` configuration file
- Format: `server.api_keys: { runner-1: "key", runner-2: "key" }`
- Must edit config file and restart server to change API keys
- `generate-api-key.py` only generates keys, doesn't store them
- No database commands for API key management

### 3. Challenge Storage

**Documentation claimed**:
- Individual columns for frequency, modulation, flag_file, flag_hash, min_delay, max_delay, etc.

**Actual implementation**:
- All challenge configuration stored in a JSON blob in the `config` column
- Only metadata columns are: status, priority, last_tx_time, next_tx_time, transmission_count, assigned_to, assigned_at, assignment_expires, enabled

### 4. System Control: "Stop" Function

**Documentation claimed** (Web Interface Guide):
> **Stop System**:
> - Initiates graceful server shutdown
> - Completes active transmissions first
> - Disconnects all runners
> - Closes database connections
> - Stops the web server
> - Web interface becomes inaccessible

**Actual implementation**:
```python
@self.app.route('/api/control/stop', methods=['POST'])
def stop_system():
    """Stop all operations."""
    self.db.set_system_state('paused', 'true')
    # Requeue all assigned challenges
    # ... requeues challenges ...
    return jsonify({'status': 'stopped'}), 200
```

**Reality**: "Stop" just pauses the system and requeues assigned challenges. It does NOT shut down the server. The server only shuts down via SIGINT/SIGTERM (Ctrl+C or systemctl stop).

### 5. User Management Commands

**Documentation claimed**:
- `python -m challengectl.server.database add-user admin`
- `python -m challengectl.server.database add-runner-key runner1`
- `python -m challengectl.server.database list-users`
- `python -m challengectl.server.database remove-user admin`

**Actual implementation**:
- User management is done via `manage-users.py` script (not database module)
- Runner API keys are in config file (no database commands exist for them)
- Correct commands:
  - `python3 manage-users.py create <username>` (not "add-user")
  - `python3 manage-users.py list` (not "list-users")
  - `python3 manage-users.py disable <username>`
  - `python3 manage-users.py enable <username>`
  - `python3 manage-users.py change-password <username>`
  - `python3 manage-users.py reset-totp <username>`
- **No "remove" or "delete" command exists** - must delete from database manually

## Minor Inconsistencies

### 6. Challenge State Names

**Documentation may use**: queued, waiting, assigned, disabled

**Actual implementation**: Need to verify exact state names match

### 7. Frequency Limits Storage

**Documentation implied**: Simple array or separate table

**Actual implementation**: Stored in JSON blob within `devices` column in runners table

### 8. Background Task Intervals

**Not explicitly documented**: Background cleanup tasks run every 30 seconds

**Actual implementation**:
```python
scheduler.add_job(cleanup_stale_runners, 'interval', seconds=30)
scheduler.add_job(cleanup_stale_assignments, 'interval', seconds=30)
scheduler.add_job(cleanup_expired_sessions, 'interval', seconds=60)
scheduler.add_job(cleanup_expired_totp_codes, 'interval', seconds=60)
```

### 9. Session Management

**Not documented**: Server uses database-backed sessions with 24-hour expiry

**Actual implementation**: `sessions` table with automatic cleanup

### 10. Module Import Structure

**Documentation doesn't specify**: How challengectl is structured as a module

**Actual implementation**:
- Not a Python package with `__init__.py`
- Standalone scripts: `challengectl.py`, `manage-users.py`, `generate-api-key.py`
- Server directory: `server/server.py`, `server/api.py`, `server/database.py`
- Runner directory: `runner/runner.py`
- Cannot import as `python -m challengectl.server.database`

## Accuracy Confirmations

The following were documented correctly:

✅ Heartbeat timeout: 90 seconds
✅ Assignment timeout: 5 minutes (300 seconds)
✅ Pause functionality: Stops new task queueing, runners stay connected
✅ Enable/Disable runner: Affects task assignment, runner stays connected
✅ Kick runner: Forcibly disconnects runner
✅ Manual trigger: Immediately queues a challenge
✅ API endpoint paths and methods
✅ WebSocket events
✅ Real-time updates via WebSocket
✅ TOTP two-factor authentication
✅ Session duration: 24 hours
✅ Runner polling and heartbeat intervals (configurable)

## Recommendations

### High Priority Fixes

1. **Update Architecture.md**: Correct database schema documentation
2. **Update API Reference.md**: Fix database-related endpoints (remove non-existent ones)
3. **Update Server Setup.md**:
   - Remove database commands for API keys
   - Explain API keys are in config file
   - Show how to use `manage-users.py` instead of database commands
4. **Update Web Interface Guide**: Correct the "Stop" function description

### Medium Priority Fixes

5. **Update Quick Start.md**: Fix command examples for user management
6. **Add to Configuration Reference.md**: Document that challenge config is JSON blob
7. **Add to Architecture.md**: Document background task intervals

### Low Priority Additions

8. **Document `manage-users.py`** script properly
9. **Document `files` and `system_state` tables** in Architecture
10. **Document session management** system

## Testing Needed

The following should be tested to verify behavior:

- [ ] Verify exact challenge state names (queued/waiting/assigned/disabled)
- [ ] Confirm challenge workflow matches documentation
- [ ] Test pause vs stop behavior in web UI
- [ ] Verify runner kick vs disable behavior
- [ ] Check if `manage-users.py` has all the functions documented
- [ ] Verify which database commands actually exist
