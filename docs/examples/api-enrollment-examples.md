# ChallengeCtl API - Runner Enrollment Examples

This document provides curl examples for programmatically enrolling runners via the ChallengeCtl API.

## Quick Start Script

For a complete automated workflow, use the provided script:

```bash
./enroll-runner-api.sh https://localhost:8443 admin password sdr-station-1 sdr-station-1
```

## Manual API Workflow

### Prerequisites

- Admin account credentials
- Server URL (e.g., `https://localhost:8443`)
- TOTP disabled (or handle TOTP verification separately)

### Step 1: Authenticate

Login to get a session cookie:

```bash
curl -k -c cookies.txt \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"yourpassword"}' \
  https://localhost:8443/api/auth/login
```

**Response:**
```json
{
  "status": "success",
  "username": "admin"
}
```

**Note:** The session cookie is stored in `cookies.txt` and includes the CSRF token.

### Step 2: Extract CSRF Token

The CSRF token is stored in the cookies. Extract it:

```bash
CSRF_TOKEN=$(grep csrf_token cookies.txt | awk '{print $7}')
echo $CSRF_TOKEN
```

### Step 3: Generate Enrollment Credentials

Create an enrollment token and API key for your runner:

```bash
curl -k -b cookies.txt \
  -X POST \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -d '{
    "runner_name": "sdr-station-1",
    "expires_hours": 24
  }' \
  https://localhost:8443/api/enrollment/token
```

**Response:**
```json
{
  "token": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnop",
  "api_key": "ck_1234567890abcdef1234567890abcdef",
  "runner_name": "sdr-station-1",
  "expires_at": "2025-01-16T10:00:00.000000+00:00",
  "expires_hours": 24
}
```

**Important:** Save the `token` and `api_key` - they're only shown once!

### Step 4: Enroll the Runner

Use the enrollment token and API key to register the runner with the server:

```bash
# Set your credentials
ENROLLMENT_TOKEN="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnop"
API_KEY="ck_1234567890abcdef1234567890abcdef"

# Get host information
HOSTNAME=$(hostname)
MAC_ADDRESS=$(ip link show | awk '/link\/ether/ {print $2; exit}')
MACHINE_ID=$(cat /etc/machine-id 2>/dev/null || echo "fallback-id")

curl -k \
  -X POST \
  -H "Content-Type: application/json" \
  -d "{
    \"enrollment_token\": \"$ENROLLMENT_TOKEN\",
    \"api_key\": \"$API_KEY\",
    \"runner_id\": \"sdr-station-1\",
    \"hostname\": \"$HOSTNAME\",
    \"mac_address\": \"$MAC_ADDRESS\",
    \"machine_id\": \"$MACHINE_ID\",
    \"devices\": [{
      \"device_id\": 0,
      \"model\": \"hackrf\",
      \"name\": \"0\",
      \"frequency_limits\": [\"144000000-148000000\", \"420000000-450000000\"]
    }]
  }" \
  https://localhost:8443/api/enrollment/enroll
```

**Response:**
```json
{
  "success": true,
  "runner_id": "sdr-station-1",
  "message": "Runner sdr-station-1 enrolled successfully"
}
```

## Re-enrollment (Moving to Different Host)

To re-enroll an existing runner on a different host:

### Generate Re-enrollment Credentials

```bash
curl -k -b cookies.txt \
  -X POST \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -d '{
    "expires_hours": 24
  }' \
  https://localhost:8443/api/enrollment/re-enroll/sdr-station-1
```

**Response:**
```json
{
  "token": "XYZABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijk",
  "api_key": "ck_newkey7890abcdef1234567890abcdef",
  "runner_id": "sdr-station-1",
  "expires_at": "2025-01-16T10:00:00.000000+00:00",
  "expires_hours": 24
}
```

Use these new credentials with the enrollment endpoint (Step 4 above) on the new host.

## Complete Configuration File

After enrollment, create a `runner-config.yml` file:

```yaml
---
runner:
  runner_id: "sdr-station-1"
  server_url: "https://localhost:8443"

  # Enrollment token can be left in config, it will be ignored once enrolled
  enrollment_token: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnop"
  api_key: "ck_1234567890abcdef1234567890abcdef"

  ca_cert: ""
  verify_ssl: true
  heartbeat_interval: 30
  poll_interval: 10
  cache_dir: "cache"
  spectrum_paint_before_challenge: true

radios:
  models:
  - model: hackrf
    rf_gain: 14
    if_gain: 32
    bias_t: true
    rf_samplerate: 2000000
    ppm: 0

  devices:
  - name: 0
    model: hackrf
    rf_gain: 14
    if_gain: 32
    frequency_limits:
      - "144000000-148000000"
      - "420000000-450000000"
```

## Testing Authentication

After enrollment, test the runner's API key:

```bash
API_KEY="ck_1234567890abcdef1234567890abcdef"
MAC_ADDRESS=$(ip link show | awk '/link\/ether/ {print $2; exit}')
MACHINE_ID=$(cat /etc/machine-id 2>/dev/null || echo "fallback-id")

curl -k \
  -H "Authorization: Bearer $API_KEY" \
  -H "X-Runner-MAC: $MAC_ADDRESS" \
  -H "X-Runner-Machine-ID: $MACHINE_ID" \
  https://localhost:8443/api/agents/{agent_id}/heartbeat
```

**Response (if successful):**
```json
{
  "status": "ok"
}
```

## Error Handling

### 401 Unauthorized
- Check API key is correct
- Verify enrollment was successful
- Check host identifiers match enrollment (MAC, machine ID)

### 409 Conflict
- Runner ID already enrolled
- Use re-enrollment endpoint instead

### 403 Forbidden (CSRF)
- CSRF token missing or invalid
- Re-login to get fresh CSRF token

### 429 Too Many Requests
- Rate limit exceeded
- Wait before retrying

## Security Notes

1. **Use HTTPS in production** - Always use TLS/SSL certificates
2. **Protect credentials** - Store API keys securely, never commit to git
3. **CSRF tokens required** - All admin state-changing operations need CSRF
4. **Host validation** - API keys are bound to host (MAC, machine ID, IP, hostname)
5. **Session expiry** - Admin sessions expire after 24 hours

## Integration Examples

### Python

```python
import requests

# Login
session = requests.Session()
response = session.post(
    'https://localhost:8443/api/auth/login',
    json={'username': 'admin', 'password': 'password'},
    verify=False
)

# Get CSRF token
csrf_token = session.cookies.get('csrf_token')

# Generate enrollment credentials
response = session.post(
    'https://localhost:8443/api/enrollment/token',
    headers={'X-CSRF-Token': csrf_token},
    json={'runner_name': 'sdr-station-1', 'expires_hours': 24},
    verify=False
)

credentials = response.json()
print(f"Token: {credentials['token']}")
print(f"API Key: {credentials['api_key']}")
```

### Ansible

```yaml
- name: Enroll ChallengeCtl Runner
  block:
    - name: Login to server
      uri:
        url: "https://{{ server_url }}/api/auth/login"
        method: POST
        body_format: json
        body:
          username: "{{ admin_user }}"
          password: "{{ admin_password }}"
        validate_certs: no
      register: login_response

    - name: Generate enrollment credentials
      uri:
        url: "https://{{ server_url }}/api/enrollment/token"
        method: POST
        headers:
          X-CSRF-Token: "{{ login_response.cookies.csrf_token }}"
        body_format: json
        body:
          runner_name: "{{ runner_name }}"
          expires_hours: 24
        validate_certs: no
      register: enrollment

    - name: Save credentials
      set_fact:
        enrollment_token: "{{ enrollment.json.token }}"
        api_key: "{{ enrollment.json.api_key }}"
```

## See Also

- [Runner Setup Guide](../wiki/Runner-Setup.md)
- [API Reference](../wiki/API-Reference.md)
- [Troubleshooting](../wiki/Troubleshooting.md)
