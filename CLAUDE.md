# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ChallengeCtl is a distributed SDR (Software-Defined Radio) challenge management system for RF CTF competitions. It coordinates multiple SDR devices to transmit challenges across different frequencies and modulations while ensuring mutual exclusion (no duplicate transmissions).

The system consists of four main components:
- **Server** (`server/`): Flask-based REST API with SQLite database and WebSocket broadcasting
- **Runner** (`runner/`): Client that executes challenges on SDR hardware using GNU Radio
- **Listener** (`listener/`): Spectrum recording client that captures RF transmissions and generates waterfall images
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

### Listener Development
```bash
# Install listener dependencies
pip install -r requirements-listener.txt

# Run listener
cd listener
python listener.py --config listener-config.yml

# Test listener with verbose logging
python listener.py --config listener-config.yml --verbose
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
- `agents` - Unified table for both runner and listener agents with `agent_type` field
- `runners` - Legacy runner table (maintained for backward compatibility)
- `challenges` - Challenge definitions stored as JSON in `config` column; assignment tracking via `assigned_to`, `assigned_at`, `assignment_expires` columns
- `transmissions` - Historical log of all transmissions
- `recordings` - Waterfall images and metadata from listener captures
- `listener_assignments` - Recording assignments pushed to listeners via WebSocket
- `files` - Content-addressed storage (SHA-256 hashed)
- `users` - Admin accounts with bcrypt passwords and encrypted TOTP secrets
- `sessions` - Web session management (24-hour expiry)

**Important**: There is NO separate `assignments` table for runner tasks. Assignment state is tracked directly in the `challenges` table via `assigned_to`, `assigned_at`, and `assignment_expires` columns. However, listener recording assignments use a separate `listener_assignments` table for WebSocket-based coordination.

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

### USB Event-Driven Device Monitoring (Linux)

**Event-driven device detection** using Linux udev (no polling):
- **USB event monitoring**: pyudev monitors USB add/remove events via udev netlink socket
- **Smart filtering**: Automatically filters out non-SDR devices (HID, storage, etc.)
- **Immediate detection**: Device plug/unplug detected in <2 seconds (vs legacy 30s polling)
- **Zero CPU overhead**: No periodic polling - events trigger probing only when needed
- **Debouncing**: Rapid successive USB events coalesced into single probe (1s debounce interval)

**Device filtering rules:**
- **Allowed**: Known SDR vendor IDs (HackRF, BladeRF, RTL-SDR, USRP, AirSpy, FUNcube)
- **Allowed**: Vendor-specific USB class (0xFF) and Communications class (0x02)
- **Blocked**: HID (0x03), Mass Storage (0x08), Audio (0x01), Hub (0x09), etc.

**Implementation:**
- `USBEventMonitor` class in `device_manager.py` wraps pyudev
- `DeviceManager` probe loop waits on `threading.Event` (no time-based sleep)
- Initial probe at startup, then event-driven only
- USB handle cleanup (gc.collect()) preserved after each probe cycle

**Requirements:**
- Linux only (uses udev)
- pyudev>=0.24.0 (in requirements-runner.txt, requirements-listener.txt)

### Real-Time Updates

WebSocket events broadcast to all connected clients:
- `runner_status` - Runner online/offline/busy
- `runner_enabled` - Runner enabled/disabled
- `challenge_assigned` - Challenge assigned to runner
- `transmission_complete` - Transmission success/failure
- `log` - Real-time log streaming

### Listener Architecture (Spectrum Recording)

Listeners are specialized agents that capture and record RF transmissions:

**Communication model:**
- **Runners**: Poll via HTTP (every 10s) for task assignments
- **Listeners**: WebSocket push notifications for real-time recording coordination

**Priority-based recording:**
- Server calculates priority for each transmission based on:
  - Number of transmissions since last recording
  - Time elapsed since last recording (time multiplier: max 10x after 10 hours)
  - Challenge priority boost (0-100 scale, converted to 1.0x-11.0x multiplier)
- Recording threshold: **1.0** (transmissions with priority ≥ 1.0 are recorded)
- Never-recorded challenges: priority = 1000.0 (always recorded first time)

**Recording outlier blocking:**
Server supports optional outlier blocking to ensure fair listener resource distribution when one challenge has disproportionately high recording priority:

*Configuration:*
```yaml
server:
  recording_outlier_blocking_enabled: false  # Enable feature (default: false)
  recording_outlier_threshold: 2.0  # Block if max_priority > median_priority × threshold
```

*How it works:*
1. When a transmission completes, server calculates recording priority for ALL enabled challenges
2. Never-recorded challenges (priority = 1000.0) are excluded from median calculation
3. Server calculates median priority across recorded-at-least-once challenges
4. If `max_priority > (median_priority × outlier_threshold)`:
   - **Block ALL recordings** except the outlier challenge itself and never-recorded challenges
   - Outlier challenge must be recorded to reduce its priority and lift the blocking
   - This ensures listener resources are reserved for the highest-priority challenge

*Example scenario:*
- Challenge A: priority = 4.5 (2 transmissions since last recording)
- Challenge B: priority = 5.2 (3 transmissions since last recording)
- Challenge C: priority = 4.8 (2 transmissions since last recording)
- Challenge D: priority = 12.0 (20 transmissions since last recording) ← **outlier**
- Challenge E: priority = 5.1 (3 transmissions since last recording)

Calculation:
- Median priority (excluding never-recorded): 5.1
- Max priority: 12.0
- Outlier check: 12.0 > (5.1 × 2.0) = 12.0 > 10.2 ✓ **BLOCKING ACTIVE**

Recording decisions while blocking is active:
- Challenge A completes → **BLOCKED** (not the outlier, resources reserved for D)
- Challenge B completes → **BLOCKED** (not the outlier)
- Challenge D completes → **ALLOWED** (is the outlier, needs recording to reduce priority)
- Challenge E completes → **BLOCKED** (not the outlier)
- Never-recorded challenge → **ALLOWED** (always record first transmission)

Once Challenge D is recorded, its priority drops and blocking is automatically lifted.

*Use cases:*
- Prevent wasting listener resources on low-priority challenges when a high-priority challenge is waiting
- Ensure high-priority challenges (those waiting longest for recording) get recorded promptly
- Maintain fair recording distribution across challenges over time

*Edge cases handled:*
- Feature disabled by default (must be explicitly enabled in config)
- No blocking with 0-1 enabled challenges (can't have outliers)
- No blocking when all challenges are never-recorded (can't calculate median)
- No blocking when only 1 challenge has been recorded (need ≥2 for median)
- Disabled challenges excluded from outlier calculation
- Manual "Trigger Now" recordings bypass blocking (treated as never-recorded, priority = 1000.0)

**Unified agent model:**
- Both runners and listeners stored in `agents` table with `agent_type` field
- Listeners have additional WebSocket tracking: `websocket_connected`, `websocket_last_connected`
- Agent enrollment via web UI: Agents → Provisioning tab

**Recording workflow:**
1. Server assigns challenge to runner (HTTP polling)
2. Server calculates recording priority for transmission
3. If priority ≥ threshold: Server finds available listener (online + WebSocket connected)
4. Server pushes `recording_assignment` event via WebSocket to listener
5. Listener waits for `expected_start` time, then captures RF with 5s pre-roll
6. Listener generates waterfall image from FFT data (matplotlib PNG)
7. Listener uploads image to server via HTTP POST
8. Recording visible in web UI under Recordings section

**Key differences from architecture doc** (see `LISTENER_IMPLEMENTATION_NOTES.md`):
- Priority threshold is 1.0 (not 10)
- Time multiplier has minimum of 1.0x (prevents zero priority)
- Priority boost is additive (1.0 + priority/10.0) not pure multiplication
- API uses RESTful structure: `/api/agents/{id}/recording/{recording_id}/complete`

See `listener/README.md` for setup and deployment details.

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

**Listener:**
- `listener/listener.py` - Main listener client with WebSocket management
- `listener/spectrum_listener.py` - GNU Radio flowgraph for spectrum capture
- `listener/waterfall_generator.py` - Waterfall image generation from FFT data
- `listener/listener-config.example.yml` - Example listener configuration

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

### Agent Enrollment & Provisioning

Server supports secure agent enrollment via the web UI (Agents → Provisioning tab):
- Generate enrollment tokens with configurable expiry and usage limits
- Agents register using enrollment token (one-time use or limited use)
- API key generated server-side and securely hashed (bcrypt) in database
- Multi-factor host validation enforced on registration and authentication:
  - Host identifiers collected: MAC address, machine ID, IP address, hostname
  - At least ONE identifier must match for successful authentication
  - Immediate enforcement (no grace period for host changes)
  - Re-enrollment process required for legitimate host migration
- Agent types: `runner` (transmit) or `listener` (receive/record)
- All agents stored in unified `agents` table with `agent_type` field

### Background Tasks (APScheduler)

Server runs periodic maintenance tasks:
- Cleanup stale agents (every 30s) - marks offline after 90s heartbeat timeout
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

### Frequency Validation and Per-Antenna Configuration

Runner devices support two configuration formats for frequency limits, gain, bias-t, and antenna selection:

**Legacy Format (single antenna per device):**
```yaml
devices:
  - name: 0
    model: hackrf
    rf_gain: 14  # Device-level gain
    if_gain: 32  # Device-level IF gain (HackRF only)
    bias_t: true  # Device-level bias-t
    antenna: ""
    frequency_limits:
      - "144000000-148000000"  # 2m band
      - "420000000-450000000"  # 70cm band
```

**New Format (per-antenna frequency limits, gain, and bias-t):**
```yaml
devices:
  - name: "1234567890abcdef"
    model: bladerf
    rf_gain: 43  # Default gain (fallback if not specified per-antenna)
    bias_t: false  # Default bias-t (fallback if not specified per-antenna)
    antennas:
      TX1:
        enabled: true  # Optional, defaults to true
        bias_t: true   # Enable bias-t for VHF/UHF (powers LNA)
        rf_gain: 43    # Optimal gain for VHF/UHF
        frequency_limits:
          - "144000000-148000000"  # 2m on TX1
          - "420000000-450000000"  # 70cm on TX1
      TX2:
        enabled: false  # Temporarily disabled (e.g., maintenance)
        bias_t: false  # Disable bias-t for microwave (no LNA)
        rf_gain: 50    # Higher gain for microwave frequencies
        frequency_limits:
          - "900000000-915000000"  # 900 MHz on TX2
          - "2400000000-2500000000"  # 2.4 GHz on TX2
```

**Disabling Antennas:**
Antennas can be temporarily disabled by setting `enabled: false`. This is useful for:
- Antenna maintenance or repairs
- Testing specific antenna configurations
- Temporarily taking an antenna offline without removing its configuration

Disabled antennas are skipped during automatic antenna selection on both the runner and server side.

**Automatic Antenna Selection, Gain, and Bias-T Application:**
- Runner automatically selects the appropriate antenna based on challenge frequency
- Server validates frequency compatibility before assigning challenges to runners
- Runner double-checks frequency compatibility and refuses incompatible challenges
- If no antenna supports the required frequency, the challenge is refused and requeued
- Per-antenna `rf_gain` and `bias_t` are automatically applied when the antenna is selected
- Gain and bias-t values are passed to fire functions (NBFM, CW, spectrum_paint) for transmission
- Bias-t is added to the device string dynamically during challenge execution (e.g., `bladerf=1234567890abcdef,biastee=1`)

**Gain and Bias-T Configuration:**
- **Per-antenna rf_gain** (recommended): Optimize gain for different frequency bands
- **Device-level rf_gain**: Fallback value if not specified per-antenna
- **Per-antenna bias_t** (recommended for multi-antenna devices): Enable/disable bias-t per antenna
- **Device-level bias_t**: Fallback value if not specified per-antenna
- **if_gain** (HackRF only): Specified at device level, not per-antenna
- Device-level gains were previously configured but not used (bug fixed in gain implementation)

**Bias-T Use Cases:**
- Enable bias-t to power external LNAs (Low Noise Amplifiers) on VHF/UHF antennas
- Disable bias-t on antennas without LNAs or when LNA has separate power
- Per-antenna configuration allows different antennas to have different power requirements
- BladeRF bias-t is automatically disabled after each transmission to prevent accidental damage

This enables multi-antenna devices (like BladeRF with TX1/TX2) to use different antennas with optimal gain and bias-t values for different frequency bands, optimizing RF performance and preventing hardware damage from out-of-band transmissions or incorrect bias-t settings.

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

### Making Changes to Listener
1. Modify code in `listener/`
2. Test WebSocket connection: Check listener connects and receives assignments
3. Test recording workflow: Verify waterfall generation and upload
4. Check both listener logs and server logs for errors
5. Validate recording priority calculations in server logs
6. Test simulated mode (when GNU Radio not available): Listener includes fallback to simulated spectrum data

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

**Listener not connecting:**
- Verify `server_url` in listener config matches server
- Check WebSocket connectivity (firewall rules, proxy settings)
- Ensure API key is correct and agent is registered
- Review server logs for WebSocket connection rejections
- Check `agent_type: listener` in listener config

**Listener not receiving recording assignments:**
- Verify listener shows "WebSocket: Connected" in web UI (Agents tab)
- Check listener is enabled in web UI
- Ensure recording priority threshold is met (priority ≥ 1.0)
- Verify at least one runner is transmitting challenges
- Check server logs for priority calculation details

**Recording quality issues:**
- Increase RF gain in listener config (e.g., `gain: 50`)
- Verify antenna is appropriate for frequency range
- Check for RF interference using `osmocom_fft`
- Adjust sample_rate if needed (default: 2M samples/sec)
- Ensure SDR device is not being used by another process
- The server is running elsewhere