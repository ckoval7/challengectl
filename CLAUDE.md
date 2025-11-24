# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ChallengeCtl is a distributed SDR (Software-Defined Radio) challenge management system for RF CTF competitions. It coordinates multiple SDR devices to transmit challenges across different frequencies and modulations while ensuring mutual exclusion (no duplicate transmissions).

The system consists of three main components:
- **Server** (`server/`): Flask-based REST API with SQLite database and WebSocket broadcasting
- **Runner** (`runner/`): Client that executes challenges on SDR hardware using GNU Radio
- **Frontend** (`frontend/`): Vue.js 3 web interface for administration and monitoring

## Common Commands

### Server Development
```bash
# Install server dependencies
pip install -r requirements-server.txt

# Run server (development)
cd server
python server.py

# Run server with specific config
python server.py --config server-config.yml

# Run tests (from root)
pytest tests/ -v
pytest tests/ --cov=server --cov-report=html --cov-report=term-missing

# Run specific test file
pytest tests/test_database.py -v

# Run by marker
pytest tests/ -m unit
pytest tests/ -m integration
```

### Runner Development
```bash
# Install runner dependencies
pip install -r requirements-runner.txt

# Run runner
cd runner
python runner.py --config runner-config.yml

# Test runner configuration
python runner.py --config runner-config.yml --test
```

### Frontend Development
```bash
cd frontend

# Install dependencies
npm ci

# Development server (hot reload)
npm run dev

# Production build
npm run build

# Run tests
npm run test
npm run test:ui
npm run test:coverage

# Linting
npm run lint
npm run lint:fix
```

### User Management
```bash
# Create admin user with TOTP 2FA
python manage-users.py --create <username>

# List all users
python manage-users.py --list

# Disable/enable user
python manage-users.py --disable <username>
python manage-users.py --enable <username>

# Change password
python manage-users.py --change-password <username>

# Delete user
python manage-users.py --delete <username>
```

### Database Management
```bash
# Reset database (WARNING: destructive)
./reset-database.sh

# Migrate TOTP encryption (after updating encryption key)
python migrate-totp-encryption.py
```

## Architecture

### Distributed Client-Server Model

The system uses a polling-based architecture where runners periodically request work from the server:

1. **Runners poll every 10 seconds** (configurable) for available challenges
2. **Server assigns challenges atomically** using database transactions with pessimistic locking
3. **Mutual exclusion guarantee**: Only one runner can transmit a challenge at a time (prevents RF interference)
4. **Heartbeat mechanism**: Runners send heartbeats every 30 seconds; server marks offline after 90 seconds
5. **Automatic recovery**: Stale assignments (>5 minutes) are automatically requeued

### Database Schema (SQLite)

**Key tables:**
- `runners` - Registered runner nodes with status (online/offline/busy)
- `challenges` - Challenge definitions stored as JSON in `config` column; assignment tracking via `assigned_to`, `assigned_at`, `assignment_expires` columns
- `transmissions` - Historical log of all transmissions
- `files` - Content-addressed storage (SHA-256 hashed)
- `users` - Admin accounts with bcrypt passwords and encrypted TOTP secrets
- `sessions` - Web session management (24-hour expiry)

**Important**: There is NO separate `assignments` table. Assignment state is tracked directly in the `challenges` table via `assigned_to`, `assigned_at`, and `assignment_expires` columns.

### Challenge State Machine

Challenges cycle through states:
- `queued` → `assigned` → `waiting` → (delay expires) → `queued`
- Delay between transmissions: average of `min_delay` and `max_delay`

### File Synchronization

Content-addressed storage using SHA-256:
- Files stored in `files/` directory on server
- Runners cache files locally in `cache/` directory (default: `cache/` relative to runner working directory)
- Hash verification on download and before use
- Multiple challenges can reference the same file

### Authentication & Security

**Runner authentication:**
- API keys in `Authorization: Bearer <key>` header
- Keys stored bcrypt-hashed in database
- Multi-factor host validation: MAC address, machine ID, IP address, hostname
- At least ONE host identifier must match for authentication
- Immediate enforcement (no grace period)

**Admin authentication:**
- Username + password (bcrypt hashed)
- TOTP two-factor authentication (encrypted with AES-256 using server master key in `server/.encryption_key`)
- Session cookies (24-hour expiry)
- CSRF protection on state-changing operations

### Real-Time Updates

WebSocket events broadcast to all connected clients:
- `runner_status` - Runner online/offline/busy
- `runner_enabled` - Runner enabled/disabled
- `challenge_assigned` - Challenge assigned to runner
- `transmission_complete` - Transmission success/failure
- `log` - Real-time log streaming

## Challenge Development

When adding a new modulation type:

1. **Create GNU Radio flowgraph** in GNU Radio Companion
   - Use **Parameters** (not Variables) for runtime configuration
   - Required parameters: `tx_freq`, `sample_rate`, `rf_gain`, `if_gain`, `device_string`, `audio_file` or `flag_file`
   - Configure osmocom Sink block for SDR output
   - Set Generate Options: `No GUI` (required for headless operation)
   - Save `.grc` file in `challenges/` directory

2. **Generate Python code** from flowgraph (F5 in GRC)
   - Creates a class that accepts your parameters

3. **Create fire function** in `challenges/your_modulation.py`
   - Import generated flowgraph class
   - Implement `main(frequency, device_string, flag_file, antenna=None, rf_gain=14, if_gain=32, sample_rate=2000000, **kwargs)` function
   - Return 0 on success, non-zero on error
   - Use logging for status messages
   - Handle exceptions and cleanup in finally block

4. **Register in runner** (`runner/runner.py`)
   - Import your module: `from challenges import your_modulation`
   - Add to `MODULATION_MAP`: `'your_modulation': your_modulation.main`

5. **Update configuration schema** in `modulation_parameters.yml`

See `docs/wiki/Challenge-Development.md` for detailed guide.

## Testing Strategy

### Backend Tests
- `tests/test_database.py` - Database operations and schema
- `tests/test_crypto.py` - Cryptographic utilities
- `tests/test_integration.py` - End-to-end workflows

Run with: `pytest tests/ -v --cov=server --cov-report=html`

Markers:
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.slow` - Slow-running tests

### Frontend Tests
Vitest framework with Vue Test Utils:
```bash
cd frontend
npm run test          # Run tests
npm run test:ui       # Interactive UI
npm run test:coverage # With coverage report
```

### CI/CD Pipeline
- **Backend CI**: Tests on Python 3.9, 3.12, 3.13; coverage threshold 40%
- **Frontend CI**: Tests on Node 20.x, 22.x; coverage threshold 50%
- **Integration tests**: Run separately after unit tests pass

## Key Files and Locations

**Server:**
- `server/server.py` - Main application entry point, background tasks
- `server/api.py` - REST API endpoints and WebSocket handlers
- `server/database.py` - Database operations with pessimistic locking
- `server/crypto.py` - Encryption utilities for TOTP secrets
- `server/.encryption_key` - Master encryption key (auto-generated, gitignored)

**Runner:**
- `runner/runner.py` - Main runner implementation, challenge execution

**Frontend:**
- `frontend/src/App.vue` - Root component with routing
- `frontend/src/views/` - Page components (Dashboard, Runners, Challenges, Logs)
- `frontend/src/components/` - Reusable components
- `frontend/vite.config.js` - Build configuration with manual chunks

**Challenges:**
- `challenges/*.py` - Fire functions for each modulation type
- `challenges/*.grc` - GNU Radio Companion flowgraphs (source files)

**Configuration:**
- `server-config.yml` - Server configuration with challenge definitions
- `runner-config.yml` - Runner configuration with device capabilities
- `config.yml` - Example standalone configuration (legacy)

**Utilities:**
- `manage-users.py` - Admin user management CLI
- `generate-api-key.py` - Generate secure API keys
- `migrate-totp-encryption.py` - Migrate TOTP secrets to new encryption key
- `reset-database.sh` - Reset server database (destructive)

## Important Implementation Details

### Background Tasks (APScheduler)
Server runs periodic maintenance tasks:
- Cleanup stale runners (every 30s) - marks offline after 90s heartbeat timeout
- Cleanup stale assignments (every 30s) - requeues after 5 minute timeout
- Cleanup expired sessions (every 60s)
- Cleanup expired TOTP codes (every 60s)

### Transaction Patterns
Use `BEGIN IMMEDIATE` for write operations to acquire database lock:
```python
with db.begin_immediate():
    # SELECT ... FOR UPDATE
    # UPDATE with atomic state changes
    # COMMIT
```

### Challenge Assignment Flow
1. Runner polls `/api/task` with frequency capabilities
2. Server begins IMMEDIATE transaction
3. Finds `queued` or `waiting` (with expired delay) challenge matching runner's frequency limits
4. Atomically updates: `status='assigned'`, `assigned_to=runner_id`, `assigned_at=now()`, `assignment_expires=now()+5min`
5. Returns challenge details to runner
6. Runner downloads files (SHA-256 verified), executes transmission
7. Runner reports completion to `/api/complete`
8. Server updates: `status='waiting'`, clears assignment, sets `last_tx_time`, increments `transmission_count`

### Frequency Validation
Runner devices have `frequency_limits` in their config:
```yaml
frequency_limits:
  - "144000000-148000000"  # 2m band
  - "420000000-450000000"  # 70cm band
```
Server only assigns challenges within runner's frequency range.

### Error Handling
- Runner failures: Automatic requeue via heartbeat timeout or assignment expiry
- Server failures: SQLite is durable; runners retry with exponential backoff
- Network failures: Runners continue attempting heartbeats and polls

## Development Workflow

### Making Changes to Server
1. Modify code in `server/`
2. Run unit tests: `pytest tests/test_database.py -v`
3. Run integration tests: `pytest tests/test_integration.py -v -m integration`
4. Test with real runner: Start server, start runner, observe logs

### Making Changes to Frontend
1. Modify code in `frontend/src/`
2. Test in dev mode: `npm run dev` (hot reload)
3. Run tests: `npm run test`
4. Build production: `npm run build`
5. Server automatically serves from `frontend/dist/` if present

### Making Changes to Runner
1. Modify `runner/runner.py`
2. Test with test config: `python runner.py --config runner-config-test-1.yml`
3. Verify communication with server
4. Check logs for errors

### Adding New Challenge Modulation
1. Create flowgraph in GNU Radio Companion
2. Generate Python code (F5)
3. Create fire function in `challenges/`
4. Register in `runner/runner.py`
5. Test standalone: `python challenges/your_mod.py --frequency 146550000 --device hackrf=0 --input test.wav`
6. Add to configuration examples
7. Update `modulation_parameters.yml`

## Troubleshooting

**Runner not connecting:**
- Check `server_url` in runner config
- Verify API key matches server config
- Check network connectivity
- Review server logs for authentication errors

**No challenges assigned:**
- Ensure `enabled: true` in challenge config
- Check system not paused (WebUI header)
- Verify runner frequency limits match challenge frequency
- Check `next_tx_time` hasn't been delayed

**File download fails:**
- File must exist in `server/files/` directory
- Filename must match SHA-256 hash
- Runner needs write access to cache directory
- Check server logs for file registration errors

**Transmission errors:**
- SDR device must be available (not in use by other process)
- Verify antenna settings for BladeRF
- Check bias-tee configuration
- Review runner logs for GNU Radio errors

**Frontend build issues:**
- Delete `node_modules/` and run `npm ci` to reinstall
- Check for circular dependencies in manual chunks configuration (see commit d73d2a4)
- Ensure all imports use correct paths
