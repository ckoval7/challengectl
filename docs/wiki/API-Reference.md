# API Reference

This document provides a comprehensive reference for the ChallengeCtl REST API. The API enables programmatic access to challenge management, runner coordination, and system monitoring.

## Table of Contents

- [Overview](#overview)
- [Authentication](#authentication)
- [Response Format](#response-format)
- [API Endpoints](#api-endpoints)
  - [Health and Status](#health-and-status)
  - [Authentication](#authentication-endpoints)
  - [User Management](#user-management)
  - [Public Endpoints](#public-endpoints)
  - [Runner Operations](#runner-operations)
  - [Dashboard and Monitoring](#dashboard-and-monitoring)
  - [Runner Management](#runner-management)
  - [Runner Enrollment](#runner-enrollment)
  - [Provisioning API Keys](#provisioning-api-keys)
  - [Challenge Management](#challenge-management)
  - [Transmissions](#transmissions)
  - [System Control](#system-control)
  - [File Management](#file-management)
- [WebSocket Events](#websocket-events)
- [Error Codes](#error-codes)

## Overview

The ChallengeCtl API is a RESTful API served over HTTP/HTTPS. All endpoints return JSON-formatted responses unless otherwise specified.

**Base URL**: `http://your-server:8443/api`

**Example**: `http://192.168.1.100:8443/api/health`

## Authentication

The API uses three authentication methods depending on the endpoint:

### Runner Authentication

Runner endpoints require an API key passed in the `X-API-Key` header:

```http
GET /api/runners/runner-1/task HTTP/1.1
Host: challengectl.example.com
X-API-Key: ck_abc123def456ghi789
```

**Security Features:**
- API keys are stored as bcrypt hashes (never plaintext)
- Multi-factor host validation requiring at least 2 matching factors: MAC address, machine ID, or IP+hostname
- Automatic credential reuse detection for active runners (validates within 90 seconds of last heartbeat)

### Provisioning Key Authentication

Provisioning endpoints use Bearer token authentication with provisioning API keys. These keys have limited permissions (can only provision runners) and are ideal for automated deployments:

```http
POST /api/provisioning/provision HTTP/1.1
Host: challengectl.example.com
Authorization: Bearer ck_provisioning_abc123def456...
```

### Admin Authentication

Admin endpoints require session-based authentication with username/password and TOTP:

1. **Login**: POST credentials to `/api/auth/login`
2. **Verify TOTP**: POST TOTP code to `/api/auth/verify-totp`
3. **Use session**: Session cookie is automatically included in subsequent requests

```http
GET /api/dashboard HTTP/1.1
Host: challengectl.example.com
Cookie: session=eyJhbGciOiJIUzI1NiIsInR5cCI...
```

### No Authentication

Public endpoints (like `/api/health` and `/api/public/challenges`) require no authentication.

## Response Format

### Success Response

```json
{
  "status": "success",
  "data": {
    "key": "value"
  }
}
```

### Error Response

```json
{
  "error": "Error description",
  "details": "Additional error information"
}
```

HTTP status codes indicate the result:
- `200 OK` - Request succeeded
- `201 Created` - Resource created successfully
- `400 Bad Request` - Invalid request parameters
- `401 Unauthorized` - Authentication required or failed
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error

## API Endpoints

### Health and Status

#### GET /api/health

Check server health status. No authentication required.

**Request:**
```http
GET /api/health HTTP/1.1
```

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

---

### Authentication Endpoints

#### POST /api/auth/login

Authenticate with username and password.

**Rate limit**: 5 requests per 15 minutes

**Request:**
```http
POST /api/auth/login HTTP/1.1
Content-Type: application/json

{
  "username": "admin",
  "password": "password123"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Password verified, TOTP required",
  "temp_token": "temp_abc123..."
}
```

#### POST /api/auth/verify-totp

Verify TOTP code and complete authentication.

**Rate limit**: 5 requests per 15 minutes

**Request:**
```http
POST /api/auth/verify-totp HTTP/1.1
Content-Type: application/json

{
  "temp_token": "temp_abc123...",
  "totp_code": "123456"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Authentication successful",
  "user": {
    "username": "admin"
  }
}
```

Sets session cookie for subsequent requests.

#### GET /api/auth/session

Check current session status.

**Request:**
```http
GET /api/auth/session HTTP/1.1
Cookie: session=...
```

**Response:**
```json
{
  "authenticated": true,
  "user": {
    "username": "admin"
  }
}
```

#### POST /api/auth/logout

Log out and invalidate session.

**Request:**
```http
POST /api/auth/logout HTTP/1.1
Cookie: session=...
```

**Response:**
```json
{
  "status": "success",
  "message": "Logged out successfully"
}
```

#### POST /api/auth/change-password

Change the current user's password.

**Request:**
```http
POST /api/auth/change-password HTTP/1.1
Cookie: session=...
Content-Type: application/json

{
  "current_password": "oldpassword",
  "new_password": "newpassword123"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Password changed successfully"
}
```

---

### User Management

Requires admin authentication for all endpoints.

#### GET /api/users

List all admin users.

**Request:**
```http
GET /api/users HTTP/1.1
Cookie: session=...
```

**Response:**
```json
{
  "users": [
    {
      "username": "admin",
      "created_at": "2024-01-15T10:00:00Z"
    },
    {
      "username": "operator",
      "created_at": "2024-01-15T11:00:00Z"
    }
  ]
}
```

#### POST /api/users

Create a new admin user.

**Request:**
```http
POST /api/users HTTP/1.1
Cookie: session=...
Content-Type: application/json

{
  "username": "newuser",
  "password": "password123"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "User created successfully",
  "totp_secret": "JBSWY3DPEHPK3PXP",
  "totp_uri": "otpauth://totp/..."
}
```

#### PUT /api/users/\<username\>

Update a user's information.

**Request:**
```http
PUT /api/users/admin HTTP/1.1
Cookie: session=...
Content-Type: application/json

{
  "password": "newpassword123"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "User updated successfully"
}
```

#### DELETE /api/users/\<username\>

Delete a user account.

**Request:**
```http
DELETE /api/users/operator HTTP/1.1
Cookie: session=...
```

**Response:**
```json
{
  "status": "success",
  "message": "User deleted successfully"
}
```

#### POST /api/users/\<username\>/reset-totp

Reset a user's TOTP secret (generates new QR code).

**Request:**
```http
POST /api/users/admin/reset-totp HTTP/1.1
Cookie: session=...
```

**Response:**
```json
{
  "status": "success",
  "message": "TOTP secret reset successfully",
  "totp_secret": "NEWJBSWY3DPEHPK3",
  "totp_uri": "otpauth://totp/..."
}
```

#### POST /api/users/\<username\>/reset-password

Reset a user's password (admin function).

**Request:**
```http
POST /api/users/operator/reset-password HTTP/1.1
Cookie: session=...
Content-Type: application/json

{
  "new_password": "resetpassword123"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Password reset successfully"
}
```

---

### Public Endpoints

No authentication required.

#### GET /api/public/challenges

Get public information about challenges.

**Request:**
```http
GET /api/public/challenges HTTP/1.1
```

**Response:**
```json
{
  "challenges": [
    {
      "name": "NBFM_FLAG_1",
      "modulation": "nbfm",
      "frequency": 146550000,
      "enabled": true,
      "state": "waiting",
      "last_run": "2024-01-15T10:25:00Z"
    }
  ]
}
```

Fields shown depend on challenge `public_view` configuration.

---

### Runner Operations

Requires runner API key authentication.

#### POST /api/runners/register

Register a new runner with the server.

**Request:**
```http
POST /api/runners/register HTTP/1.1
X-API-Key: ck_abc123...
Content-Type: application/json

{
  "runner_id": "runner-1",
  "frequency_limits": [
    "144000000-148000000",
    "420000000-450000000"
  ]
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Runner registered successfully",
  "runner_id": "runner-1"
}
```

#### POST /api/runners/\<runner_id\>/heartbeat

Send heartbeat to indicate runner is alive.

**Request:**
```http
POST /api/runners/runner-1/heartbeat HTTP/1.1
X-API-Key: ck_abc123...
```

**Response:**
```json
{
  "status": "success",
  "message": "Heartbeat received"
}
```

#### POST /api/runners/\<runner_id\>/signout

Gracefully sign out and unregister from server.

**Request:**
```http
POST /api/runners/runner-1/signout HTTP/1.1
X-API-Key: ck_abc123...
```

**Response:**
```json
{
  "status": "success",
  "message": "Runner signed out successfully"
}
```

#### GET /api/runners/\<runner_id\>/task

Poll for a new task assignment.

**Request:**
```http
GET /api/runners/runner-1/task HTTP/1.1
X-API-Key: ck_abc123...
```

**Response (task available):**
```json
{
  "task": {
    "challenge_id": 1,
    "name": "NBFM_FLAG_1",
    "frequency": 146550000,
    "modulation": "nbfm",
    "flag_file": "challenges/voice.wav",
    "flag_hash": "abc123def456...",
    "parameters": {
      "wav_samplerate": 48000
    }
  }
}
```

**Response (no task):**
```json
{
  "task": null
}
```

#### POST /api/runners/\<runner_id\>/complete

Report task completion.

**Request:**
```http
POST /api/runners/runner-1/complete HTTP/1.1
X-API-Key: ck_abc123...
Content-Type: application/json

{
  "challenge_id": 1,
  "status": "success",
  "error": null
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Task completion recorded"
}
```

#### POST /api/runners/\<runner_id\>/log

Send log messages to server.

**Request:**
```http
POST /api/runners/runner-1/log HTTP/1.1
X-API-Key: ck_abc123...
Content-Type: application/json

{
  "level": "INFO",
  "message": "Challenge transmission completed successfully"
}
```

**Response:**
```json
{
  "status": "success"
}
```

---

### Dashboard and Monitoring

Requires admin authentication.

#### GET /api/dashboard

Get dashboard statistics and overview.

**Request:**
```http
GET /api/dashboard HTTP/1.1
Cookie: session=...
```

**Response:**
```json
{
  "stats": {
    "total_runners": 3,
    "active_runners": 2,
    "total_challenges": 10,
    "enabled_challenges": 8,
    "total_transmissions": 152,
    "recent_transmissions": [
      {
        "challenge_name": "NBFM_FLAG_1",
        "runner_id": "runner-1",
        "timestamp": "2024-01-15T10:30:00Z",
        "status": "success"
      }
    ]
  }
}
```

#### GET /api/logs

Get system logs.

**Request:**
```http
GET /api/logs HTTP/1.1
Cookie: session=...
```

**Query parameters**:
- `limit` (integer): Maximum number of log entries to return (default: 100)
- `offset` (integer): Number of entries to skip (default: 0)

**Response:**
```json
{
  "logs": [
    {
      "type": "log",
      "source": "server",
      "level": "INFO",
      "message": "Runner runner-1 registered successfully",
      "timestamp": "2024-01-15T10:30:00.000Z"
    }
  ]
}
```

---

### Runner Management

Requires admin authentication.

#### GET /api/runners

List all registered runners.

**Request:**
```http
GET /api/runners HTTP/1.1
Cookie: session=...
```

**Response:**
```json
{
  "runners": [
    {
      "runner_id": "runner-1",
      "status": "online",
      "last_heartbeat": "2024-01-15T10:30:00Z",
      "frequency_limits": ["144000000-148000000"],
      "current_task": "NBFM_FLAG_1"
    }
  ]
}
```

#### GET /api/runners/\<runner_id\>

Get details for a specific runner.

**Request:**
```http
GET /api/runners/runner-1 HTTP/1.1
Cookie: session=...
```

**Response:**
```json
{
  "runner": {
    "runner_id": "runner-1",
    "status": "online",
    "last_heartbeat": "2024-01-15T10:30:00Z",
    "frequency_limits": ["144000000-148000000"],
    "current_task": null,
    "registered_at": "2024-01-15T09:00:00Z"
  }
}
```

#### DELETE /api/runners/\<runner_id\>

Remove a runner (kicks it offline).

**Request:**
```http
DELETE /api/runners/runner-1 HTTP/1.1
Cookie: session=...
```

**Response:**
```json
{
  "status": "success",
  "message": "Runner removed successfully"
}
```

#### POST /api/runners/\<runner_id\>/enable

Enable a runner to receive tasks.

**Request:**
```http
POST /api/runners/runner-1/enable HTTP/1.1
Cookie: session=...
```

**Response:**
```json
{
  "status": "success",
  "message": "Runner enabled"
}
```

#### POST /api/runners/\<runner_id\>/disable

Disable a runner from receiving new tasks.

**Request:**
```http
POST /api/runners/runner-1/disable HTTP/1.1
Cookie: session=...
```

**Response:**
```json
{
  "status": "success",
  "message": "Runner disabled"
}
```

---

### Runner Enrollment

Endpoints for secure runner enrollment with bcrypt-hashed API keys and multi-factor host validation.

#### POST /api/enrollment/token

Generate an enrollment token for a new runner (admin only).

**Request:**
```http
POST /api/enrollment/token HTTP/1.1
Cookie: session=...
Content-Type: application/json

{
  "runner_name": "sdr-station-1",
  "expires_hours": 24
}
```

**Response:**
```json
{
  "token": "bXkLpQr7Ts...",
  "api_key": "vN3mK9fR2w...",
  "runner_name": "sdr-station-1",
  "expires_at": "2024-01-16T10:00:00Z",
  "expires_hours": 24
}
```

**Important Notes:**
- The token and API key are only displayed once. Copy them immediately!
- Enrollment tokens can be left in runner config files after enrollment - they will be ignored on subsequent runs
- API keys are stored as bcrypt hashes in the database (never in plaintext)

#### POST /api/enrollment/enroll

Enroll a new runner using an enrollment token (no authentication required).

**Request:**
```http
POST /api/enrollment/enroll HTTP/1.1
Content-Type: application/json

{
  "enrollment_token": "bXkLpQr7Ts...",
  "api_key": "vN3mK9fR2w...",
  "runner_id": "sdr-station-1",
  "hostname": "sdr-host-01",
  "devices": [
    {
      "name": "0",
      "model": "hackrf",
      "rf_gain": 14,
      "if_gain": 32,
      "frequency_limits": ["144000000-148000000", "420000000-450000000"]
    }
  ]
}
```

**Device Models:** `hackrf`, `bladerf`, `usrp`, `limesdr`

**Model-Specific Parameters:**
- **HackRF**: Supports `if_gain` parameter (0-47, default: 32)
- **All models**: Support `rf_gain` and optional `frequency_limits` array

**Response:**
```json
{
  "success": true,
  "runner_id": "sdr-station-1",
  "message": "Runner sdr-station-1 enrolled successfully"
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid or expired enrollment token
- `409 Conflict`: Runner ID already enrolled

**Host Validation:**

After enrollment, the runner is authenticated using multi-factor host validation:
- MAC address
- Machine ID
- IP address + hostname

When a runner is actively online (heartbeat within 90 seconds), authentication must match **at least two** of these factors to prevent credential reuse attacks. This ensures strong multi-factor authentication. Legacy runners with `None` values are automatically upgraded when they provide host identifiers.

#### POST /api/enrollment/re-enroll/\<runner_id\>

Generate new credentials for an existing runner (admin only). Used when re-deploying a runner to a different host or after credentials are compromised.

**Request:**
```http
POST /api/enrollment/re-enroll/sdr-station-1 HTTP/1.1
Cookie: session=...
Content-Type: application/json

{
  "expires_hours": 24
}
```

**Response:**
```json
{
  "token": "newTokenXYZ...",
  "api_key": "newKeyABC...",
  "runner_id": "sdr-station-1",
  "expires_at": "2024-01-16T10:00:00Z",
  "expires_hours": 24
}
```

**Note:** This invalidates the previous API key and generates fresh credentials. The runner must re-enroll using the new token and API key.

#### GET /api/enrollment/tokens

List all enrollment tokens (admin only).

**Request:**
```http
GET /api/enrollment/tokens HTTP/1.1
Cookie: session=...
```

**Response:**
```json
{
  "tokens": [
    {
      "token": "bXkLpQr7Ts...",
      "runner_name": "sdr-station-1",
      "created_by": "admin",
      "created_at": "2024-01-15T10:00:00Z",
      "expires_at": "2024-01-16T10:00:00Z",
      "used": false,
      "used_at": null,
      "used_by_runner_id": null
    }
  ]
}
```

#### DELETE /api/enrollment/token/\<token\>

Delete an enrollment token (admin only).

**Request:**
```http
DELETE /api/enrollment/token/bXkLpQr7Ts... HTTP/1.1
Cookie: session=...
```

**Response:**
```json
{
  "status": "deleted"
}
```

---

### Provisioning API Keys

**Recommended Method for Automated Deployments**

Provisioning API keys provide a secure, stateless method for automated runner deployment without requiring admin session authentication. These keys have limited permissions (can only provision runners) and are ideal for CI/CD pipelines, infrastructure-as-code, and automated deployments.

#### POST /api/provisioning/keys

Create a new provisioning API key (admin only).

**Request:**
```http
POST /api/provisioning/keys HTTP/1.1
Cookie: session=...
Content-Type: application/json

{
  "key_id": "ci-cd-pipeline",
  "description": "Jenkins CI/CD pipeline for automated runner provisioning"
}
```

**Key ID Format:** Alphanumeric characters, hyphens, and underscores only (`^[a-zA-Z0-9_-]+$`)

**Response:**
```json
{
  "key_id": "ci-cd-pipeline",
  "api_key": "ck_provisioning_abc123def456...",
  "description": "Jenkins CI/CD pipeline for automated runner provisioning"
}
```

**Important:** The API key is only shown once! Store it securely.

#### GET /api/provisioning/keys

List all provisioning API keys (admin only). Does not return the actual keys.

**Request:**
```http
GET /api/provisioning/keys HTTP/1.1
Cookie: session=...
```

**Response:**
```json
{
  "keys": [
    {
      "key_id": "ci-cd-pipeline",
      "description": "Jenkins CI/CD pipeline",
      "created_by": "admin",
      "created_at": "2024-01-15T10:00:00Z",
      "last_used_at": "2024-01-15T12:30:00Z",
      "enabled": true
    }
  ]
}
```

#### POST /api/provisioning/keys/\<key_id\>/toggle

Enable or disable a provisioning API key (admin only).

**Request:**
```http
POST /api/provisioning/keys/ci-cd-pipeline/toggle HTTP/1.1
Cookie: session=...
Content-Type: application/json

{
  "enabled": false
}
```

**Response:**
```json
{
  "status": "disabled"
}
```

#### DELETE /api/provisioning/keys/\<key_id\>

Delete a provisioning API key (admin only).

**Request:**
```http
DELETE /api/provisioning/keys/ci-cd-pipeline HTTP/1.1
Cookie: session=...
```

**Response:**
```json
{
  "status": "deleted"
}
```

#### POST /api/provisioning/provision

Provision a new runner - generates credentials and returns complete YAML configuration. Uses provisioning API key authentication (Bearer token).

**Rate limit:** 100 requests per hour

**Authentication:** Bearer token with provisioning API key

**Request:**
```http
POST /api/provisioning/provision HTTP/1.1
Authorization: Bearer ck_provisioning_abc123def456...
Content-Type: application/json

{
  "runner_name": "sdr-station-1",
  "runner_id": "sdr-station-1",
  "expires_hours": 24,
  "server_url": "https://challengectl.example.com",
  "verify_ssl": true,
  "devices": [
    {
      "name": "0",
      "model": "hackrf",
      "rf_gain": 14,
      "if_gain": 32,
      "frequency_limits": ["144000000-148000000", "420000000-450000000"]
    },
    {
      "name": "1",
      "model": "bladerf",
      "rf_gain": 43,
      "frequency_limits": ["144000000-148000000"]
    }
  ]
}
```

**Parameters:**
- `runner_name` (required): Name for the runner
- `runner_id` (optional): Unique ID, defaults to `runner_name`
- `expires_hours` (optional): Token expiration in hours, default: 24
- `server_url` (optional): Server URL, defaults to request origin
- `verify_ssl` (optional): SSL verification setting, default: true
- `devices` (optional): Array of device configurations

**Device Configuration:**
- `name`: Device identifier (e.g., "0", "1", or serial number)
- `model`: Device model - `hackrf`, `bladerf`, `usrp`, `limesdr`
- `rf_gain`: RF gain value (model-specific ranges)
- `if_gain`: IF gain (HackRF only, 0-47)
- `frequency_limits`: Array of frequency ranges (e.g., `["144000000-148000000"]`)

**Response:**
```json
{
  "enrollment_token": "tokenXYZ...",
  "api_key": "apiKeyABC...",
  "config_yaml": "---\n# ChallengeCtl Runner Configuration\n...",
  "runner_name": "sdr-station-1",
  "runner_id": "sdr-station-1",
  "expires_at": "2024-01-16T10:00:00Z"
}
```

The `config_yaml` field contains a complete, ready-to-use runner configuration file with:
- Enrollment credentials (token and API key)
- Server connection settings
- Device configurations
- Default radio parameters

**Usage Example:**
```bash
# Save config to file
curl -X POST https://challengectl.example.com/api/provisioning/provision \
  -H "Authorization: Bearer ck_provisioning_abc123..." \
  -H "Content-Type: application/json" \
  -d '{"runner_name":"my-runner"}' \
  | jq -r '.config_yaml' > runner-config.yml

# Deploy and start runner
./runner.py --config runner-config.yml
```

---

### Challenge Management

Requires admin authentication.

#### GET /api/challenges

List all challenges.

**Request:**
```http
GET /api/challenges HTTP/1.1
Cookie: session=...
```

**Response:**
```json
{
  "challenges": [
    {
      "challenge_id": 1,
      "name": "NBFM_FLAG_1",
      "frequency": 146550000,
      "modulation": "nbfm",
      "state": "waiting",
      "enabled": true,
      "last_run": "2024-01-15T10:25:00Z",
      "min_delay": 60,
      "max_delay": 90
    }
  ]
}
```

#### GET /api/challenges/\<challenge_id\>

Get details for a specific challenge.

**Request:**
```http
GET /api/challenges/1 HTTP/1.1
Cookie: session=...
```

**Response:**
```json
{
  "challenge": {
    "challenge_id": 1,
    "name": "NBFM_FLAG_1",
    "frequency": 146550000,
    "modulation": "nbfm",
    "flag_file": "challenges/voice.wav",
    "state": "waiting",
    "enabled": true,
    "last_run": "2024-01-15T10:25:00Z"
  }
}
```

#### PUT /api/challenges/\<challenge_id\>

Update challenge configuration.

**Request:**
```http
PUT /api/challenges/1 HTTP/1.1
Cookie: session=...
Content-Type: application/json

{
  "enabled": false,
  "min_delay": 120,
  "max_delay": 180
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Challenge updated successfully"
}
```

#### POST /api/challenges/\<challenge_id\>/enable

Enable a challenge.

**Request:**
```http
POST /api/challenges/1/enable HTTP/1.1
Cookie: session=...
```

**Response:**
```json
{
  "status": "success",
  "message": "Challenge enabled"
}
```

#### POST /api/challenges/\<challenge_id\>/trigger

Manually trigger a challenge transmission immediately.

**Request:**
```http
POST /api/challenges/1/trigger HTTP/1.1
Cookie: session=...
```

**Response:**
```json
{
  "status": "success",
  "message": "Challenge queued for immediate transmission"
}
```

#### POST /api/challenges/reload

Reload challenge configuration from file.

**Request:**
```http
POST /api/challenges/reload HTTP/1.1
Cookie: session=...
```

**Response:**
```json
{
  "status": "success",
  "message": "Configuration reloaded successfully",
  "challenges_loaded": 10
}
```

---

### Transmissions

Requires admin authentication.

#### GET /api/transmissions

Get transmission history.

**Request:**
```http
GET /api/transmissions HTTP/1.1
Cookie: session=...
```

**Query parameters**:
- `limit` (integer): Maximum number of entries (default: 100)
- `offset` (integer): Number of entries to skip (default: 0)
- `challenge_id` (integer): Filter by challenge ID
- `runner_id` (string): Filter by runner ID

**Response:**
```json
{
  "transmissions": [
    {
      "log_id": 152,
      "challenge_name": "NBFM_FLAG_1",
      "runner_id": "runner-1",
      "frequency": 146550000,
      "modulation": "nbfm",
      "status": "success",
      "timestamp": "2024-01-15T10:30:00Z",
      "error_message": null
    }
  ],
  "total": 152
}
```

---

### System Control

Requires admin authentication.

#### POST /api/control/pause

Pause challenge distribution system-wide.

**Request:**
```http
POST /api/control/pause HTTP/1.1
Cookie: session=...
```

**Response:**
```json
{
  "status": "success",
  "message": "System paused"
}
```

#### POST /api/control/resume

Resume challenge distribution.

**Request:**
```http
POST /api/control/resume HTTP/1.1
Cookie: session=...
```

**Response:**
```json
{
  "status": "success",
  "message": "System resumed"
}
```

---

### File Management

#### GET /api/files/\<file_hash\>

Download a challenge file by its SHA-256 hash. Requires runner API key authentication.

**Request:**
```http
GET /api/files/abc123def456... HTTP/1.1
X-API-Key: ck_abc123...
```

**Response:**
Binary file content with appropriate `Content-Type` header.

#### POST /api/files/upload

Upload a new challenge file. Requires admin authentication.

**Request:**
```http
POST /api/files/upload HTTP/1.1
Cookie: session=...
Content-Type: multipart/form-data

file=<binary data>
```

**Response:**
```json
{
  "status": "success",
  "message": "File uploaded successfully",
  "hash": "abc123def456...",
  "filename": "voice.wav"
}
```

**Restrictions**:
- Maximum file size: 100 MB
- Allowed extensions: .wav, .bin, .txt, .yml, .yaml, .py, .grc

---

## WebSocket Events

The server broadcasts real-time events via WebSocket. Connect to the WebSocket endpoint at the same host/port as the HTTP server.

**WebSocket URL**: `ws://your-server:8443/socket.io/`

### Event Types

All events are sent with this structure:

```json
{
  "type": "event_type",
  "data": { ... }
}
```

#### Log Event

```json
{
  "type": "log",
  "source": "server",
  "level": "INFO",
  "message": "Runner runner-1 registered successfully",
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

#### Challenge State Change

```json
{
  "type": "challenge_state",
  "challenge_id": 1,
  "challenge_name": "NBFM_FLAG_1",
  "state": "assigned",
  "runner_id": "runner-1",
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

#### Runner Status Change

```json
{
  "type": "runner_status",
  "runner_id": "runner-1",
  "status": "online",
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

#### Transmission Complete

```json
{
  "type": "transmission",
  "challenge_name": "NBFM_FLAG_1",
  "runner_id": "runner-1",
  "status": "success",
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

## Error Codes

| HTTP Status | Meaning | Common Causes |
|-------------|---------|---------------|
| 400 | Bad Request | Invalid JSON, missing required fields, invalid parameters |
| 401 | Unauthorized | Missing or invalid API key, session expired, invalid credentials |
| 403 | Forbidden | Valid credentials but insufficient permissions |
| 404 | Not Found | Resource (runner, challenge, file) does not exist |
| 409 | Conflict | Resource already exists (duplicate runner_id, challenge name) |
| 429 | Too Many Requests | Rate limit exceeded (login, TOTP verification) |
| 500 | Internal Server Error | Database error, file system error, unexpected exception |

## Rate Limiting

Certain endpoints are rate-limited to prevent abuse:

| Endpoint | Limit |
|----------|-------|
| POST /api/auth/login | 5 requests per 15 minutes per IP |
| POST /api/auth/verify-totp | 5 requests per 15 minutes per IP |

Rate limits are enforced per IP address. Exceeding limits returns `429 Too Many Requests`.

## Next Steps

Now that you understand the API, you can:

- [Review the Architecture](Architecture) to understand how API operations affect system state
- [Explore the Configuration Reference](Configuration-Reference) for server and runner setup
- Build custom integrations or monitoring tools
- Develop alternative runner implementations
