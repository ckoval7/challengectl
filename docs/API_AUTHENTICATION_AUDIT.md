# ChallengeCtl API Authentication Audit - Comprehensive Summary

## Executive Summary

ChallengeCtl uses a multi-layered authentication system with three distinct credential types, each designed for specific use cases and security contexts:

1. **Admin Session Authentication** - For web UI administrators (TOTP-protected)
2. **Runner API Keys** - For autonomous runners (bcrypt-hashed, multi-factor host validation)
3. **Provisioning API Keys** - For automated runner deployment (stateless Bearer tokens, limited permissions)

---

## 1. API ENDPOINTS OVERVIEW

### Route Organization in api.py (/home/user/challengectl/server/api.py)

#### Public Endpoints (No Authentication Required)
- `GET /api/health` (line 536) - Server health check
- `GET /api/public/challenges` (line 1122) - Public challenge information

#### Authentication Endpoints
- `POST /api/auth/login` (line 544) - Username/password authentication
- `POST /api/auth/verify-totp` (line 689) - TOTP code verification
- `GET /api/auth/session` (line 787) - Session validation
- `POST /api/auth/logout` (line 829) - Session destruction
- `POST /api/auth/change-password` (line 863) - Password change (requires admin auth)

#### Admin User Management (Admin Auth Required)
- `GET /api/users` (line 919) - List all users
- `POST /api/users` (line 926) - Create new user
- `PUT /api/users/<username>` (line 976) - Update user
- `DELETE /api/users/<username>` (line 1013) - Delete user
- `POST /api/users/<username>/reset-totp` (line 1035) - Reset user TOTP
- `POST /api/users/<username>/reset-password` (line 1074) - Reset user password

#### Runner Operations (Runner API Key Auth Required)
- `POST /api/runners/register` (line 1140) - Runner registration
- `POST /api/runners/<runner_id>/heartbeat` (line 1189) - Heartbeat reporting
- `POST /api/runners/<runner_id>/signout` (line 1213) - Graceful signout
- `GET /api/runners/<runner_id>/task` (line 1236) - Poll for task assignment
- `POST /api/runners/<runner_id>/complete` (line 1270) - Report task completion
- `POST /api/runners/<runner_id>/log` (line 1338) - Send log entries

#### Runner Enrollment (No Auth / Token-Based)
- `POST /api/enrollment/token` (line 1491) - Create enrollment token (admin auth required)
- `POST /api/enrollment/enroll` (line 1549) - Enroll runner (enrollment token required)
- `POST /api/enrollment/re-enroll/<runner_id>` (line 1661) - Re-enrollment (admin auth required)
- `GET /api/enrollment/tokens` (line 1642) - List tokens (admin auth required)
- `DELETE /api/enrollment/token/<token>` (line 1649) - Delete token (admin auth required)

#### Provisioning API Keys (Admin Auth Required for Management, Provisioning Key Auth for Provision)
- `POST /api/provisioning/keys` (line 1722) - Create provisioning key (admin auth + CSRF)
- `GET /api/provisioning/keys` (line 1771) - List provisioning keys (admin auth)
- `DELETE /api/provisioning/keys/<key_id>` (line 1778) - Delete key (admin auth + CSRF)
- `POST /api/provisioning/keys/<key_id>/toggle` (line 1790) - Enable/disable key (admin auth + CSRF)
- `POST /api/provisioning/provision` (line 1807) - Provision runner (provisioning key auth)

#### Challenge Management (Admin Auth Required)
- `GET /api/challenges` (line 1957) - List challenges
- `POST /api/challenges` (line 1964) - Create challenge
- `GET /api/challenges/<challenge_id>` (line 2010) - Get challenge details
- `PUT /api/challenges/<challenge_id>` (line 2021) - Update challenge
- `DELETE /api/challenges/<challenge_id>` (line 2056) - Delete challenge
- `POST /api/challenges/<challenge_id>/enable` (line 2070) - Enable challenge
- `POST /api/challenges/<challenge_id>/trigger` (line 2087) - Trigger challenge
- `POST /api/challenges/import` (line 2113) - Import challenges
- `POST /api/challenges/reload` (line 2242) - Reload from config

#### Admin Dashboard (Admin Auth Required)
- `GET /api/dashboard` (line 1368) - Dashboard statistics
- `GET /api/logs` (line 1396) - System logs
- `GET /api/transmissions` (line 2284) - Transmission history

#### Runner Management (Admin Auth Required)
- `GET /api/runners` (line 1416) - List all runners
- `GET /api/runners/<runner_id>` (line 1427) - Runner details
- `DELETE /api/runners/<runner_id>` (line 1439) - Remove runner
- `POST /api/runners/<runner_id>/enable` (line 1456) - Enable runner
- `POST /api/runners/<runner_id>/disable` (line 1473) - Disable runner

#### System Control (Admin Auth Required)
- `POST /api/control/pause` (line 2292) - Pause system
- `POST /api/control/resume` (line 2306) - Resume system

#### File Management
- `GET /api/files/<file_hash>` (line 2321) - Download file (runner API key auth)
- `POST /api/files/upload` (line 2338) - Upload file (admin auth + CSRF)

---

## 2. AUTHENTICATION MECHANISMS

### 2.1 Admin Session Authentication

**Location**: Lines 388-425 (api.py) - `require_admin_auth()` decorator

**Authentication Flow**:
1. POST to `/api/auth/login` with username/password
2. System performs password verification using bcrypt (constant-time)
3. If user has TOTP configured:
   - Create unauthenticated session (totp_verified=False)
   - Return `totp_required: True`
4. If no TOTP:
   - Create fully authenticated session (totp_verified=True)
   - Update last login timestamp
5. POST to `/api/auth/verify-totp` with TOTP code
6. System marks session as TOTP verified

**Session Storage**: SQLite database (persistent)
- Table: `sessions` (database.py, lines 197-205)
- Fields: session_token, username, expires, totp_verified, created_at
- Expiry: 24 hours, renewed on activity (sliding window)

**Cookie Security**:
- Session token: httpOnly cookie (XSS protection)
- CSRF token: Regular cookie (JavaScript needs to read)
- Both have `Secure` flag in production (auto-detected via X-Forwarded-Proto)
- SameSite=Lax (prevents CSRF while allowing redirects)

**TOTP Implementation**:
- Library: pyotp
- Code validity: ±1 time window (90 seconds total)
- Replay protection: In-memory tracking to prevent code reuse
- Secret storage: Encrypted in database using `crypto.py`

**Rate Limiting**: 5 requests per 15 minutes per IP

**CSRF Protection**: 
- Required for all state-changing operations (POST, PUT, DELETE)
- Token sent as X-CSRF-Token header + csrf_token cookie
- Both must match

### 2.2 Runner API Keys

**Location**: Lines 256-302 (api.py) - `require_api_key()` decorator

**Key Generation**:
- Generated using `secrets.token_urlsafe(48)` - 48-byte random token
- Stored as bcrypt hash in database (never plaintext)
- Table: `runners.api_key_hash` (database.py, line 68)

**Authentication Method**:
- Bearer token in Authorization header: `Authorization: Bearer <api_key>`
- Each runner is identified by its api_key_hash

**Key Verification Process** (database.py, lines 437-542):
1. Extract API key from Authorization header
2. Retrieve runner's bcrypt hash from database
3. Use bcrypt.checkpw() to verify (constant-time)
4. Perform multi-factor host validation:
   - Check IP address (from request.remote_addr)
   - Check hostname (from request.json body)
   - Check MAC address (from X-Runner-MAC header)
   - Check machine ID (from X-Runner-Machine-ID header)

**Multi-Factor Host Validation** (lines 479-542):
- Active runners (heartbeat within 90 seconds) require **at least 2 matching factors**
- Matching factors:
  1. IP + Hostname (together)
  2. MAC Address
  3. Machine ID
- If runner is offline (>90 sec without heartbeat): no host validation needed
- **Credential Reuse Attack Prevention**: Prevents use of same API key from different machines
- Auto-upgrade: Stores new MAC/machine IDs for legacy runners

**Runner Registration Flow**:
1. Admin creates enrollment token via `/api/enrollment/token`
2. API returns: enrollment_token + api_key
3. Runner calls `/api/enrollment/enroll` with:
   - enrollment_token
   - api_key (as plaintext to be hashed)
   - runner_id, hostname, devices
4. System verifies token and stores bcrypt hash of api_key
5. Future requests use Bearer token with original api_key for authentication

**Rate Limiting**:
- Register: 100 per minute
- Heartbeat: 1000 per minute (frequent polling)
- Task get/complete/log: 1000 per minute

### 2.3 Provisioning API Keys

**Location**: Lines 358-386 (api.py) - `require_provisioning_key()` decorator

**Key Generation**:
- Generated using `secrets.token_urlsafe(48)` - same as runner keys
- Stored as bcrypt hash in database
- Table: `provisioning_api_keys` (database.py, lines 110-122)

**Key Creation** (database.py, lines 1311-1338):
```
- Admin only - requires admin auth + CSRF
- Key ID format: alphanumeric, hyphens, underscores only (^[a-zA-Z0-9_-]+$)
- Can store description and creator
- Has enabled/disabled state
```

**Authentication Method**:
- Bearer token: `Authorization: Bearer <provisioning_api_key>`
- No CSRF required (stateless authentication)
- No session cookies needed

**Key Verification** (database.py, lines 1340-1373):
1. Extract API key from Authorization header
2. Iterate through all enabled provisioning_api_keys
3. Compare with bcrypt hash for each key
4. Return key_id if valid
5. Update last_used_at timestamp

**Permissions** (Limited Scope):
- CAN: Generate enrollment credentials for runners
- CAN: Return complete runner configuration YAML
- CANNOT: Access/modify existing runners
- CANNOT: Create/modify/delete challenges
- CANNOT: Access administrative functions
- CANNOT: Read sensitive system data

**Provisioning Endpoint** (lines 1807-1955):
```
POST /api/provisioning/provision
Authorization: Bearer <provisioning_api_key>
Content-Type: application/json

Request:
{
  "runner_name": "sdr-station-1",
  "runner_id": "sdr-station-1",  // optional, defaults to runner_name
  "expires_hours": 24,            // optional, default 24
  "server_url": "https://...",    // optional, defaults to request origin
  "verify_ssl": true,             // optional, default true
  "devices": [...]                // optional device configs
}

Response:
{
  "runner_name": "sdr-station-1",
  "runner_id": "sdr-station-1",
  "enrollment_token": "...",
  "api_key": "...",
  "expires_at": "ISO timestamp",
  "config_yaml": "complete YAML configuration"
}
```

**Rate Limiting**: 100 requests per hour

**Key Management**:
- Enable/Disable: Toggle without deletion (allows revocation)
- Delete: Permanent removal
- Track: last_used_at timestamp for audit

---

## 3. MIDDLEWARE AND AUTHENTICATION DECORATORS

### 3.1 Decorator Stack in api.py

**require_admin_auth** (lines 388-425):
- Validates session token from httpOnly cookie
- Checks session exists in database
- Verifies expiry (UTC timestamps)
- Verifies TOTP was completed
- Renews session (sliding window)
- Adds `request.admin_username` to context

**require_api_key** (lines 256-302):
- Extracts Bearer token from Authorization header
- Performs bcrypt verification
- Multi-factor host validation
- Adds `request.runner_id` to context

**require_provisioning_key** (lines 358-386):
- Extracts Bearer token from Authorization header
- Verifies against all enabled keys
- Adds `request.provisioning_key_id` to context

**require_csrf** (lines 332-356):
- Validates CSRF token in header
- Compares with CSRF token in cookie
- Skips for GET, HEAD, OPTIONS
- Returns 403 if mismatch

### 3.2 Session Management (api.py)

**create_session** (lines 427-444):
- Generates token using secrets.token_urlsafe(32)
- Sets 24-hour expiry
- Optionally marks TOTP as verified
- Stores in database

**update_session_totp** (lines 446-448):
- Marks session as totp_verified=True

**renew_session** (lines 450-457):
- Extends expiry by 24 hours
- Called on every authenticated request

**invalidate_user_sessions** (lines 469-480):
- Invalidates all sessions for a user (except optional current token)
- Called when password changes to log out other clients

**cleanup_expired_sessions** (lines 463-467):
- Periodic cleanup (every 60 seconds)
- Removes expired sessions from database

### 3.3 TOTP Management (api.py)

**is_totp_code_used** (lines 482-495):
- In-memory tracking of used codes
- Prevents replay attacks

**mark_totp_code_used** (lines 497-513):
- Adds code to used set with timestamp

**cleanup_expired_totp_codes** (lines 515-530):
- Removes codes older than 2 minutes
- Runs periodically

---

## 4. CREDENTIAL TYPES AND EXPECTED BEHAVIORS

### 4.1 Enrollment Token + API Key (for Runner Registration)

**Purpose**: One-time secure runner enrollment

**Lifecycle**:
1. Generated by admin via `/api/enrollment/token`
2. Token expires after specified hours (default 24)
3. Single use only - marked as used after enrollment
4. Can be deleted before use
5. Re-enrollment tokens can target specific runners

**Database Table** (database.py, lines 86-108):
```
enrollment_tokens:
- token (PK)
- runner_name
- created_by
- created_at
- expires_at
- used (boolean)
- used_at
- used_by_runner_id
- re_enrollment_for (for re-enrollment)
```

**Enrollment Flow** (api.py, lines 1549-1640):
```
POST /api/enrollment/enroll (no auth required)
{
  "enrollment_token": "...",
  "api_key": "...",      // plaintext to be hashed
  "runner_id": "...",
  "hostname": "...",
  "mac_address": "...",  // optional
  "machine_id": "...",   // optional
  "devices": [...]
}

Returns:
{
  "success": true,
  "runner_id": "...",
  "message": "..."
}
```

**Security**:
- No authentication required (public endpoint)
- Rate limited: 10 per hour
- Token must be valid and not expired
- Token must not already be used
- Runner ID cannot already be enrolled (unless re-enrollment)
- API key is hashed before storage
- System logs enrollment with host identifiers

### 4.2 Runner API Key (for Ongoing Operations)

**Purpose**: Authenticate all runner operations

**Lifecycle**:
1. Created during enrollment
2. Stored as bcrypt hash in runners.api_key_hash
3. Valid for life of runner (until re-enrollment)
4. Only plaintext value returned once during enrollment
5. Can be invalidated by re-enrollment

**Usage**:
```
Authorization: Bearer <api_key_hash>
X-Runner-MAC: <mac_address>  // optional, for host validation
X-Runner-Machine-ID: <machine_id>  // optional, for host validation
```

**Valid for**:
- POST /api/runners/register
- POST /api/runners/<runner_id>/heartbeat
- POST /api/runners/<runner_id>/signout
- GET /api/runners/<runner_id>/task
- POST /api/runners/<runner_id>/complete
- POST /api/runners/<runner_id>/log
- GET /api/files/<file_hash>

**Host Validation Rules**:

If runner is **actively online** (heartbeat within 90 seconds):
- Requires **at least 2 matching factors** from:
  1. IP address + Hostname (must match together)
  2. MAC address
  3. Machine ID
- Logs warning and rejects if <2 factors match
- Prevents credential reuse on different machines

If runner is **offline** (no heartbeat for 90+ seconds):
- No host validation required
- Allows reconnection from any network location

**Auto-Upgrade**:
- If runner has NULL MAC/machine ID but provides new ones, stores them
- Logs upgrade for audit trail

### 4.3 Provisioning API Key (for Automated Deployment)

**Purpose**: Automated, stateless runner provisioning (ideal for CI/CD)

**Lifecycle**:
1. Created by admin via `/api/provisioning/keys`
2. No expiry (until disabled/deleted)
3. Can be enabled/disabled without deletion
4. Tracks last_used_at for audit

**Database Table** (database.py, lines 110-122):
```
provisioning_api_keys:
- key_id (PK)
- key_hash (bcrypt)
- description
- created_by
- created_at
- last_used_at
- enabled (boolean)
```

**Expected Behavior**:

1. **Creation** (lines 1722-1769):
```
POST /api/provisioning/keys (admin auth + CSRF)
{
  "key_id": "ci-cd-pipeline",
  "description": "Jenkins deployment"
}

Response:
{
  "key_id": "ci-cd-pipeline",
  "api_key": "ck_provisioning_...",  // Only shown once!
  "description": "..."
}
```

2. **Provisioning** (lines 1807-1955):
```
POST /api/provisioning/provision (provisioning key auth)
{
  "runner_name": "runner-1",
  "runner_id": "runner-1",
  "expires_hours": 24,
  "server_url": "https://...",
  "verify_ssl": true,
  "devices": [...]
}

Response:
{
  "runner_name": "runner-1",
  "runner_id": "runner-1",
  "enrollment_token": "...",
  "api_key": "...",
  "expires_at": "...",
  "config_yaml": "complete YAML ready for deployment"
}
```

3. **Management** (lines 1771-1804):
- List keys (without actual key values)
- Enable/disable keys
- Delete keys
- All require admin auth + CSRF

**Security Properties**:
- Stateless (no session/cookies)
- Limited permissions (provisioning only)
- Bcrypt hashed storage
- Can be rotated easily
- Audit trail via key_id and created_by
- Rate limited: 100 per hour
- Can be disabled without deletion

---

## 5. RESPONSE FORMATS AND ERROR CODES

### 5.1 Success Responses

**Standard Format** (api.py uses jsonify):
```json
{
  "status": "success/authenticated/registered/etc",
  "data": { ... }  // varies by endpoint
}
```

**HTTP Status Codes**:
- `200 OK` - Successful operation
- `201 Created` - Resource created (enrollment, provisioning)
- `204 No Content` - Successful operation with no content

### 5.2 Error Responses

**Standard Error Format**:
```json
{
  "error": "Error description",
  "details": "Additional information (optional)"
}
```

**Error HTTP Status Codes**:
- `400 Bad Request` - Invalid parameters, missing fields
- `401 Unauthorized` - Invalid credentials, expired tokens
- `403 Forbidden` - Valid credentials but insufficient permissions
- `404 Not Found` - Resource not found
- `409 Conflict` - Resource already exists (duplicate runner_id)
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error

### 5.3 Common Authentication Error Scenarios

**Admin Auth**:
- Missing session_token: `401 Unauthorized - Missing or invalid session`
- Invalid session: `401 Unauthorized - Invalid or expired session`
- TOTP not verified: `401 Unauthorized - TOTP verification required`
- Bad password: `401 Unauthorized - Invalid credentials` (generic, prevents user enumeration)
- Disabled account: `401 Unauthorized - Invalid credentials` (generic)

**Runner API Key**:
- Missing Authorization header: `401 Unauthorized - Missing or invalid authorization header`
- Invalid key: `401 Unauthorized - Invalid API key`
- Host validation failed: `401 Unauthorized - Invalid API key` (generic, logs details)

**Provisioning API Key**:
- Missing Authorization header: `401 Unauthorized - Missing or invalid authorization header`
- Invalid key: `401 Unauthorized - Invalid provisioning API key`
- Disabled key: `401 Unauthorized - Invalid provisioning API key` (generic)

**CSRF**:
- Missing token: `403 Forbidden - CSRF token missing`
- Mismatched token: `403 Forbidden - CSRF token invalid`

---

## 6. SECURITY FEATURES

### 6.1 Password and Hash Storage

**Technology**: bcrypt with gensalt()
- Library: bcrypt (Python package)
- Work factor: Default (currently 12 rounds)
- Constant-time comparison: automatic with bcrypt.checkpw()

**User Passwords** (database.py, line 187):
- Stored in `users.password_hash`
- Hashed with bcrypt during creation
- Verified during login with constant-time comparison
- Prevents timing attacks on user enumeration

**API Keys**:
- Runner keys: Stored in `runners.api_key_hash`
- Provisioning keys: Stored in `provisioning_api_keys.key_hash`
- Same bcrypt hashing as passwords
- Never transmitted or logged in plaintext

### 6.2 TOTP (Time-Based One-Time Password)

**Implementation**: 
- Library: pyotp
- Secret storage: Encrypted in database using crypto.py
- Code validity: ±1 time window (30-second codes, 90-second window)
- Replay protection: In-memory tracking with cleanup

**TOTP Secret Encryption** (api.py):
- Encrypted using crypto.encrypt_totp_secret()
- Stored in `users.totp_secret` (encrypted)
- Requires password verification to reset

### 6.3 CSRF Protection

**Implementation**:
- Token generation: secrets.token_urlsafe(32)
- Dual cookie validation: Header + Cookie comparison
- Applies to: POST, PUT, DELETE
- Exempts: GET, HEAD, OPTIONS
- SameSite=Lax setting

### 6.4 Rate Limiting

**Implementation**: Flask-Limiter with memory backend

**Limits Applied**:
- Login: 5 per 15 minutes (brute force protection)
- TOTP verification: 5 per 15 minutes (brute force protection)
- Registration: 100 per minute (enrollment)
- Heartbeat: 1000 per minute (high frequency)
- Provisioning: 100 per hour (API rate limit)

### 6.5 Session Management

**Sliding Window Expiry**:
- Initial expiry: 24 hours from creation
- Renewed: Every authenticated request adds 24 hours
- Prevents: Unattended sessions from persisting

**Persistent Storage**:
- Stored in SQLite sessions table
- Survives server restarts
- Per-user invalidation possible
- Indexed by username and expiry time for efficient cleanup

### 6.6 Host Validation (Credential Reuse Prevention)

**Problem Addressed**: Prevents use of stolen API key from different machines

**Solution**:
- Multi-factor host identifiers: IP, hostname, MAC, machine ID
- Requires **at least 2 matches** for active runners
- No validation for offline runners (allows reconnection)
- Auto-upgrade for legacy runners

**Factors**:
1. IP + Hostname (pair - must both match)
2. MAC Address (individual - must match)
3. Machine ID (individual - must match)

**Example Scenarios**:
- Runner moves to different WiFi: IP changes, but hostname + machine ID match → **Accepted**
- Stolen key used on different hardware: IP + MAC + machine ID all different → **Rejected**
- Legacy runner (no MAC stored): Provides MAC on auth → **Auto-upgraded and accepted**

### 6.7 Security Headers and Cookie Settings

**CORS Configuration** (api.py, lines 89-118):
- Restricted to configured origins
- Supports credentials (cookies included)
- Allow headers: Content-Type, X-CSRF-Token

**Cookie Security** (api.py, lines 312-330):
- Auto-detection: Checks request.is_secure and X-Forwarded-Proto
- HTTPS (production): Secure=True, SameSite=Lax
- HTTP (development): Secure=False, SameSite=Lax
- Both session and CSRF cookies match settings

---

## 7. DATABASE SCHEMA

### 7.1 Key Tables

**users** (database.py, lines 184-193):
```
username (PK) TEXT
password_hash TEXT
totp_secret TEXT (encrypted)
enabled BOOLEAN DEFAULT 1
password_change_required BOOLEAN DEFAULT 0
created_at TIMESTAMP
last_login TIMESTAMP
```

**runners** (database.py, lines 57-71):
```
runner_id (PK) TEXT
hostname TEXT
ip_address TEXT
mac_address TEXT (nullable, for legacy support)
machine_id TEXT (nullable, for legacy support)
status TEXT (offline|online)
enabled BOOLEAN DEFAULT 1
last_heartbeat TIMESTAMP
devices JSON
api_key_hash TEXT (bcrypt)
created_at TIMESTAMP
updated_at TIMESTAMP
```

**enrollment_tokens** (database.py, lines 87-100):
```
token (PK) TEXT
runner_name TEXT
created_by TEXT (FK: users.username)
created_at TIMESTAMP DEFAULT NOW
expires_at TIMESTAMP
used BOOLEAN DEFAULT 0
used_at TIMESTAMP (nullable)
used_by_runner_id TEXT (nullable, FK: runners)
re_enrollment_for TEXT (nullable)
```

**provisioning_api_keys** (database.py, lines 111-122):
```
key_id (PK) TEXT
key_hash TEXT (bcrypt)
description TEXT
created_by TEXT (FK: users.username)
created_at TIMESTAMP DEFAULT NOW
last_used_at TIMESTAMP (nullable)
enabled BOOLEAN DEFAULT 1
```

**sessions** (database.py, lines 197-205):
```
session_token (PK) TEXT
username TEXT (FK: users.username)
expires TIMESTAMP
totp_verified BOOLEAN DEFAULT 0
created_at TIMESTAMP DEFAULT NOW
```

**Indexes**:
- sessions.username (FK lookup)
- sessions.expires (cleanup queries)
- challenges.status, next_tx_time, enabled (task assignment)
- runners.status, last_heartbeat (cleanup queries)

---

## 8. INITIALIZATION AND DEFAULT SETUP

### 8.1 First-Time Initialization (database.py, lines 218-266)

**When no users exist**:
1. Creates default 'admin' user with random 16-character password
2. Sets password_change_required=False
3. Sets totp_secret=NULL (no 2FA initially)
4. Marks system as 'initial_setup_required'=true
5. Logs password to console and log file (visible once at startup)
6. Disables default admin after first user creation

**First Login**:
1. User logs in with default credentials
2. System detects no TOTP configured
3. Session created with totp_verified=True
4. User is prompted to create new admin account
5. Default admin account is disabled

### 8.2 Default Configuration (server.py)

**Server Defaults**:
- Bind: 0.0.0.0
- Port: 8443
- Heartbeat timeout: 90 seconds
- Assignment timeout: 5 minutes (300 seconds)

**CORS Defaults** (api.py, lines 92-108):
- Config file setting: server.cors_origins
- Environment variable: CHALLENGECTL_CORS_ORIGINS
- Development default: localhost:5173, localhost:5000, 127.0.0.1:5173, 127.0.0.1:5000

---

## 9. LOGGING AND AUDIT TRAILS

### 9.1 Security-Related Logging

**Authentication Events** (api.py):
- Successful login (line 651-653): username, IP, TOTP status
- Failed login (line 584-586): username, IP, reason (user_not_found|wrong_password|account_disabled)
- TOTP verification (lines 771-773): username, IP (code partially masked)
- TOTP replay (lines 733-735): username, IP (code partially masked)
- TOTP failure (lines 744-746): username, IP, code attempt (partially masked)

**Runner Events** (api.py):
- Runner registration (lines 1623-1624): runner_id, hostname, MAC, machine ID
- Enrollment (lines 1623-1624): runner_id, runner_name, hostname, IP
- Re-enrollment (line 1711): runner_id, username

**API Key Events** (api.py):
- Provisioning key creation (line 1763): key_id, username
- Provisioning request (line 1946): runner_name, key_id

**Security Events** (database.py):
- Credential reuse attempt (lines 532-537): runner_id, previous host, new host, matching factors
- Host validation pass (line 540): runner_id, matching factors

### 9.2 Log Storage

**Format**: Structured logging with timestamps
- Syslog-compatible format in production
- Rotated log files (timestamped archives)
- WebSocket broadcast to connected clients
- In-memory buffer (last 500 entries)

---

## 10. TESTING AND VERIFICATION

### 10.1 Expected Test Scenarios

**Admin Authentication**:
- [ ] Login with correct credentials → session created
- [ ] Login with wrong password → 401 Unauthorized
- [ ] Non-existent user → 401 Unauthorized (generic)
- [ ] Disabled account → 401 Unauthorized (generic)
- [ ] TOTP code valid → 200 authenticated
- [ ] TOTP code invalid → 401 Unauthorized
- [ ] TOTP code reuse → 401 Unauthorized
- [ ] Session expiry → 401 on next request
- [ ] Session renewal on activity → expiry extends
- [ ] CSRF token mismatch → 403 Forbidden
- [ ] Missing CSRF token → 403 Forbidden

**Runner API Key**:
- [ ] Valid key + host validation pass → 200 success
- [ ] Invalid key → 401 Unauthorized
- [ ] Valid key, host validation fail → 401 Unauthorized
- [ ] Credential reuse from different host → 401 Unauthorized
- [ ] Offline runner, different host → 200 success (no validation)
- [ ] Host identifier upgrade (NULL→provided) → stored and success
- [ ] Rate limiting on heartbeat → 429 after limit

**Provisioning API Key**:
- [ ] Valid key, valid runner_name → 201 created
- [ ] Invalid key → 401 Unauthorized
- [ ] Disabled key → 401 Unauthorized
- [ ] Missing runner_name → 400 Bad Request
- [ ] Rate limiting → 429 after 100/hour
- [ ] Generated config_yaml → valid YAML format
- [ ] Enrollment token valid → runner can enroll

**Enrollment Token**:
- [ ] Valid token + API key → 201 runner enrolled
- [ ] Expired token → 401 Unauthorized
- [ ] Already-used token → 401 Unauthorized
- [ ] Invalid API key → enrollment fails
- [ ] Duplicate runner_id → 409 Conflict
- [ ] Re-enrollment token for different runner_id → 400 Bad Request

---

## 11. SECURITY CHECKLIST

- [x] Passwords hashed with bcrypt
- [x] API keys hashed with bcrypt (never plaintext)
- [x] TOTP codes validated with time windows
- [x] TOTP replay protection with code tracking
- [x] CSRF protection for state-changing operations
- [x] Rate limiting on brute-force targets
- [x] Constant-time password comparison (bcrypt)
- [x] User enumeration prevention (generic login errors)
- [x] Credential reuse detection (host validation)
- [x] Session expiry with sliding windows
- [x] CORS restriction to configured origins
- [x] Secure cookie flags (HttpOnly, Secure, SameSite)
- [x] HTTPS detection via reverse proxy headers
- [x] Per-user session invalidation on password change
- [x] Audit logging of security events
- [x] Host validation auto-upgrade for legacy runners
- [x] Provisioning keys with limited permissions
- [x] Encrypted TOTP secret storage

---

## 12. REFERENCES

**File Paths**:
- API Routes: `/home/user/challengectl/server/api.py` (lines 536-2444)
- Database Schema: `/home/user/challengectl/server/database.py` (lines 51-1426)
- Server Config: `/home/user/challengectl/server/server.py` (lines 1-489)

**Documentation**:
- API Reference: `/home/user/challengectl/docs/wiki/API-Reference.md`
- Provisioning Guide: `/home/user/challengectl/docs/examples/provisioning-api-key-guide.md`
- Architecture: `/home/user/challengectl/docs/wiki/Architecture.md`

**Key Functions**:
- Admin auth: api.py:388 (require_admin_auth)
- Runner auth: api.py:256 (require_api_key)
- Provisioning auth: api.py:358 (require_provisioning_key)
- API key verification: database.py:437 (verify_runner_api_key)
- Provisioning key verification: database.py:1340 (verify_provisioning_api_key)
- TOTP validation: api.py:689 (verify_totp)
