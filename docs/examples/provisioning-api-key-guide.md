# Provisioning API Keys - Complete Guide

Provisioning API keys provide secure, automated runner deployment without requiring admin credentials or CSRF tokens. They are ideal for CI/CD pipelines and infrastructure automation.

## Overview

### What are Provisioning API Keys?

Provisioning API keys are limited-permission credentials designed specifically for runner enrollment. They use stateless Bearer token authentication without requiring session cookies, CSRF tokens, or admin privileges. These keys are stored using bcrypt hashing (similar to password storage) and can be enabled or disabled without deletion, providing flexible access control.

### Why use them instead of admin credentials?

Provisioning keys follow the principle of least privilege by granting only the permissions needed for runner provisioning, without exposing full administrative access. They are stateless, making them ideal for serverless and containerized environments. Each key maintains an audit trail that tracks which runners were provisioned, and keys can be revoked independently without affecting admin accounts. This makes them perfect for automation scenarios where you need secure, scriptable runner deployment.

## Quick Start

### Step 1: Create a Provisioning API Key

**Recommended Method: Web UI**

The easiest way to create provisioning keys is through the Web UI:

1. Log in to the ChallengeCtl web interface as an administrator.
2. Navigate to the **Runners** page.
3. Click on the **Provisioning Keys** tab.
4. Click the **Create Provisioning Key** button.
5. Enter a unique **Key ID** (e.g., "ci-cd-pipeline", "prod-terraform").
6. Optionally, add a **Description** to document the key's purpose.
7. Click **Create Key**.
8. The API key will be displayed once. Copy it immediately and store it securely.
9. A usage example with curl will be provided for quick reference.

**IMPORTANT:** The API key is only displayed once during creation. Make sure to copy it before closing the dialog.

**Alternative Method: API**

If you need to automate key creation or prefer using the API directly, you can use curl commands. See the "Creating Keys via API" section below for details.

### Step 2: Provision Runners (No Admin Credentials Required)

Once you have a provisioning key, anyone with access to it can deploy runners without admin credentials:

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

The `config_yaml` field contains a complete, ready-to-use configuration file that can be saved directly to disk.

## Creating Keys via API

If you need to automate key creation or cannot use the Web UI, you can create provisioning keys using the API:

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

Save the `api_key` value securely. It will not be displayed again.

## Managing Keys via Web UI

The Web UI provides a complete interface for managing provisioning keys:

**Viewing Keys:**
- Navigate to **Runners** → **Provisioning Keys** tab
- View all keys with their status, creation date, and last usage
- See which administrator created each key

**Disabling Keys:**
- Click **Disable** to temporarily revoke access without deleting the key
- Disabled keys can be re-enabled later
- Useful for key rotation or incident response

**Deleting Keys:**
- Click **Delete** to permanently remove a key
- Requires confirmation to prevent accidental deletion
- Cannot be undone

## API Endpoints Reference

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

### Key Management

**Recommended practices:**
- Store keys in secret managers such as HashiCorp Vault, AWS Secrets Manager, or Azure Key Vault.
- Use environment variables for keys in CI/CD pipelines rather than hardcoding them.
- Create separate keys for different environments (development, staging, production) to limit blast radius.
- Use descriptive key_id values that clearly indicate purpose and environment (e.g., "prod-terraform", "staging-ci").
- Rotate keys periodically according to your organization's security policy.

**Practices to avoid:**
- Never commit keys to git repositories or version control systems.
- Do not share keys in plain text through email, Slack, or other messaging platforms.
- Avoid using the same key across multiple environments or teams.
- Do not distribute provisioning keys to end users; they are intended for automated systems only.

### Key Rotation

To rotate a provisioning key, first disable the old key, create a new one, update your automation, and then delete the old key after verification:

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

# Update your automation with the new key
# ...

# Delete old key after verification
curl -k -b cookies.txt -X DELETE \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  https://localhost:8443/api/provisioning/keys/old-key
```

### Monitoring

Regularly check key usage to identify potential security issues:

```bash
curl -k -b cookies.txt \
  https://localhost:8443/api/provisioning/keys
```

Review the response for:
- Unexpected `last_used_at` times that might indicate unauthorized access.
- Keys that have not been used recently, which may be candidates for deletion.
- Multiple keys with similar descriptions that could indicate duplication.

### Principle of Least Privilege

Provisioning keys have strictly limited permissions to reduce security risk.

**Provisioning keys can:**
- Generate enrollment credentials for new runners.
- Return runner configuration YAML files.

**Provisioning keys cannot:**
- Access or modify existing runners.
- Create, modify, or delete challenges.
- Access administrative functions.
- Read sensitive system data.
- Delete or modify system configuration.

## Comparison: Admin Auth vs Provisioning Keys

| Feature | Admin Auth | Provisioning Key |
|---------|------------|------------------|
| Authentication | Session + CSRF | Bearer token |
| Permissions | Full admin access | Runner provisioning only |
| State | Stateful (cookies) | Stateless |
| Expiry | 24 hours | No expiry (until disabled) |
| Revocation | Logout only | Enable/disable |
| Audit Trail | Username | Key ID |
| CI/CD Friendly | No (requires TOTP) | Yes |
| Rotation | Change password | Create new key |

## Troubleshooting

### Error: "Invalid provisioning API key"

**Possible causes:**
- The API key is incorrect or has been modified.
- The key has been disabled by an administrator.
- The key has been deleted from the system.

**Solution:**
```bash
# List all keys (as admin)
curl -k -b cookies.txt \
  https://localhost:8443/api/provisioning/keys

# Check if your key is enabled
# Create a new key if needed
```

### Error: "Missing required field: runner_name"

**Cause:** The request body is missing the required `runner_name` field.

**Solution:**
```bash
# Correct request format
curl -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"runner_name":"my-runner"}' \
  https://localhost:8443/api/provisioning/provision
```

### Error: 429 Too Many Requests

**Cause:** You have exceeded the rate limit of 100 requests per hour per key.

**Solution:**
- Wait before retrying your request.
- Create additional provisioning keys if you need higher throughput.
- Batch your provisioning operations to reduce the total number of API calls.

## See Also

- [Runner Setup Guide](../wiki/Runner-Setup.md)
- [API Reference](../wiki/API-Reference.md)
- [Security Best Practices](../wiki/Security.md)
