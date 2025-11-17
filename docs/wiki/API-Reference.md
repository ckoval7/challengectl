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

The API uses two authentication methods depending on the endpoint:

### Runner Authentication

Runner endpoints require an API key passed in the `X-API-Key` header:

```http
GET /api/runners/runner-1/task HTTP/1.1
Host: challengectl.example.com
X-API-Key: ck_abc123def456ghi789
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

#### POST /api/control/stop

Stop the server (graceful shutdown).

**Request:**
```http
POST /api/control/stop HTTP/1.1
Cookie: session=...
```

**Response:**
```json
{
  "status": "success",
  "message": "Server stopping..."
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
