# Provisioning API Keys - Complete Guide

Provisioning API keys provide secure, automated runner deployment without requiring admin credentials or CSRF tokens. Perfect for CI/CD pipelines and infrastructure automation.

## Overview

**What are Provisioning API Keys?**
- Limited-permission API keys for runner enrollment only
- Stateless Bearer token authentication (no sessions)
- No CSRF tokens required
- Bcrypt-hashed storage (like passwords)
- Can be enabled/disabled without deletion

**Why use them instead of admin credentials?**
- ✅ Least privilege - only runner provisioning, no admin access
- ✅ Stateless - works in serverless/container environments
- ✅ Audit trail - track which key provisioned which runner
- ✅ Revocable - disable keys without affecting admins
- ✅ Scriptable - perfect for automation

## Quick Start

### Step 1: Create a Provisioning API Key (Admin)

Using the Web UI or API with admin credentials:

```bash
# Login as admin
curl -k -c cookies.txt \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"yourpassword"}' \
  https://localhost:8443/api/auth/login

# Get CSRF token
CSRF_TOKEN=$(grep csrf_token cookies.txt | awk '{print $7}')

# Create provisioning key
curl -k -b cookies.txt \
  -X POST \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -d '{
    "key_id": "ci-cd-pipeline",
    "description": "CI/CD runner deployment"
  }' \
  https://localhost:8443/api/provisioning/keys
```

**Response:**
```json
{
  "key_id": "ci-cd-pipeline",
  "api_key": "ck_prov_1234567890abcdef1234567890abcdef",
  "description": "CI/CD runner deployment"
}
```

**⚠️ IMPORTANT:** Save the `api_key` - it's only shown once!

### Step 2: Provision Runners (No Admin Credentials!)

Now anyone with the provisioning key can deploy runners:

```bash
# Set your provisioning API key
PROV_KEY="ck_prov_1234567890abcdef1234567890abcdef"

# Provision a runner
curl -k \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $PROV_KEY" \
  -d '{"runner_name":"sdr-station-1"}' \
  https://localhost:8443/api/provisioning/provision
```

**Response:**
```json
{
  "runner_name": "sdr-station-1",
  "runner_id": "sdr-station-1",
  "enrollment_token": "ABC123...",
  "api_key": "ck_runner_xyz789...",
  "expires_at": "2025-01-16T10:00:00Z",
  "config_yaml": "---\n# Complete YAML config here..."
}
```

The `config_yaml` field contains a complete, ready-to-use configuration file!

## API Endpoints

### Admin Endpoints (require admin auth + CSRF)

#### Create Provisioning Key

```http
POST /api/provisioning/keys
Content-Type: application/json
Cookie: session_token=...
X-CSRF-Token: ...

{
  "key_id": "my-key",
  "description": "Optional description"
}
```

**Response:**
```json
{
  "key_id": "my-key",
  "api_key": "ck_prov_...",
  "description": "Optional description"
}
```

#### List Provisioning Keys

```http
GET /api/provisioning/keys
Cookie: session_token=...
```

**Response:**
```json
{
  "keys": [
    {
      "key_id": "ci-cd-pipeline",
      "description": "CI/CD runner deployment",
      "created_by": "admin",
      "created_at": "2025-01-15T10:00:00Z",
      "last_used_at": "2025-01-15T12:30:00Z",
      "enabled": true
    }
  ]
}
```

#### Delete Provisioning Key

```http
DELETE /api/provisioning/keys/my-key
Cookie: session_token=...
X-CSRF-Token: ...
```

#### Enable/Disable Provisioning Key

```http
POST /api/provisioning/keys/my-key/toggle
Content-Type: application/json
Cookie: session_token=...
X-CSRF-Token: ...

{
  "enabled": false
}
```

### Provisioning Endpoint (requires provisioning API key)

#### Provision Runner

```http
POST /api/provisioning/provision
Content-Type: application/json
Authorization: Bearer ck_prov_...

{
  "runner_name": "sdr-station-1",
  "runner_id": "sdr-station-1",          // Optional, defaults to runner_name
  "expires_hours": 24,                    // Optional, default 24
  "server_url": "https://myserver:8443", // Optional, uses request origin
  "verify_ssl": true                      // Optional, default true
}
```

**Response:**
```json
{
  "runner_name": "sdr-station-1",
  "runner_id": "sdr-station-1",
  "enrollment_token": "enrollment-token-here",
  "api_key": "ck_runner_...",
  "expires_at": "2025-01-16T10:00:00Z",
  "config_yaml": "complete YAML configuration..."
}
```

## Usage Examples

### Bash Script

```bash
#!/bin/bash
PROV_KEY="ck_prov_abc123..."
SERVER="https://localhost:8443"

# Provision runner
RESPONSE=$(curl -sk \
  -H "Authorization: Bearer $PROV_KEY" \
  -H "Content-Type: application/json" \
  -d '{"runner_name":"my-runner"}' \
  "$SERVER/api/provisioning/provision")

# Extract and save config
echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data['config_yaml'])
" > runner-config.yml

echo "Config saved to runner-config.yml"
```

### Python

```python
import requests

PROV_KEY = "ck_prov_abc123..."
SERVER = "https://localhost:8443"

response = requests.post(
    f"{SERVER}/api/provisioning/provision",
    headers={"Authorization": f"Bearer {PROV_KEY}"},
    json={"runner_name": "my-runner"},
    verify=False
)

data = response.json()

# Save configuration
with open('runner-config.yml', 'w') as f:
    f.write(data['config_yaml'])

print(f"Runner '{data['runner_id']}' provisioned!")
print(f"Config saved to runner-config.yml")
```

### Terraform

```hcl
resource "null_resource" "provision_runner" {
  provisioner "local-exec" {
    command = <<EOF
      curl -sk \
        -H "Authorization: Bearer ${var.provisioning_key}" \
        -H "Content-Type: application/json" \
        -d '{"runner_name":"${var.runner_name}"}' \
        ${var.server_url}/api/provisioning/provision \
        | jq -r '.config_yaml' > runner-config.yml
    EOF
  }
}
```

### GitHub Actions

```yaml
name: Deploy Runner

on:
  workflow_dispatch:
    inputs:
      runner_name:
        description: 'Runner name'
        required: true

jobs:
  provision:
    runs-on: ubuntu-latest
    steps:
      - name: Provision Runner
        env:
          PROV_KEY: ${{ secrets.CHALLENGECTL_PROV_KEY }}
          SERVER: ${{ secrets.CHALLENGECTL_SERVER }}
        run: |
          curl -sk \
            -H "Authorization: Bearer $PROV_KEY" \
            -H "Content-Type: application/json" \
            -d "{\"runner_name\":\"${{ github.event.inputs.runner_name }}\"}" \
            "$SERVER/api/provisioning/provision" \
            | jq -r '.config_yaml' > runner-config.yml

      - name: Upload Config
        uses: actions/upload-artifact@v3
        with:
          name: runner-config
          path: runner-config.yml
```

## Security Best Practices

### 1. Key Management

**DO:**
- ✅ Store keys in secret managers (Vault, AWS Secrets Manager, etc.)
- ✅ Use environment variables for keys in CI/CD
- ✅ Create separate keys for different environments (dev, staging, prod)
- ✅ Use descriptive key_id values (e.g., "prod-terraform", "staging-ci")
- ✅ Rotate keys periodically

**DON'T:**
- ❌ Commit keys to git repositories
- ❌ Share keys in plain text (email, Slack, etc.)
- ❌ Use the same key across multiple environments
- ❌ Give provisioning keys to end users

### 2. Key Rotation

```bash
# Disable old key
curl -k -b cookies.txt \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -d '{"enabled":false}' \
  https://localhost:8443/api/provisioning/keys/old-key/toggle

# Create new key
curl -k -b cookies.txt \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -d '{"key_id":"new-key","description":"Rotated key"}' \
  https://localhost:8443/api/provisioning/keys

# Update your automation
# ...

# Delete old key after verification
curl -k -b cookies.txt -X DELETE \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  https://localhost:8443/api/provisioning/keys/old-key
```

### 3. Monitoring

Check key usage:

```bash
curl -k -b cookies.txt \
  https://localhost:8443/api/provisioning/keys
```

Look for:
- Unexpected `last_used_at` times
- Keys that haven't been used (inactive)
- Multiple keys with similar descriptions (duplicates)

### 4. Principle of Least Privilege

Provisioning keys can **ONLY**:
- Generate enrollment credentials
- Return runner configuration YAML

Provisioning keys **CANNOT**:
- Access existing runners
- Modify challenges
- Access admin functions
- Read sensitive data
- Delete or modify anything

## Comparison: Admin Auth vs Provisioning Keys

| Feature | Admin Auth | Provisioning Key |
|---------|------------|------------------|
| Authentication | Session + CSRF | Bearer token |
| Permissions | Full admin access | Runner provisioning only |
| State | Stateful (cookies) | Stateless |
| Expiry | 24 hours | No expiry (until disabled) |
| Revocation | Logout only | Enable/disable |
| Audit Trail | Username | Key ID |
| CI/CD Friendly | ❌ No (requires TOTP) | ✅ Yes |
| Rotation | Change password | Create new key |

## Troubleshooting

### Error: "Invalid provisioning API key"

**Causes:**
- Wrong API key
- Key has been disabled
- Key has been deleted

**Solution:**
```bash
# List all keys (as admin)
curl -k -b cookies.txt \
  https://localhost:8443/api/provisioning/keys

# Check if key is enabled
# Create new key if needed
```

### Error: "Missing required field: runner_name"

**Cause:** Request body missing `runner_name`

**Solution:**
```bash
# Correct request
curl -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"runner_name":"my-runner"}' \
  https://localhost:8443/api/provisioning/provision
```

### Error: 429 Too Many Requests

**Cause:** Rate limit exceeded (100/hour per key)

**Solution:**
- Wait before retrying
- Create additional provisioning keys if needed
- Batch your provisioning operations

## See Also

- [Runner Setup Guide](../wiki/Runner-Setup.md)
- [API Reference](../wiki/API-Reference.md)
- [Security Best Practices](../wiki/Security.md)
