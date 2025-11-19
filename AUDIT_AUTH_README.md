# API Authentication Audit Script

This script comprehensively audits the authentication of all ChallengeCtl API endpoints by testing them with different credential types.

## Purpose

The audit script tests each API endpoint with:
- ✅ Valid admin credentials (username/password/TOTP)
- ✅ Valid runner API key
- ✅ Valid provisioning API key
- ✅ Valid enrollment token
- ❌ Invalid/nonsense credentials
- ❌ No credentials at all

It reports **green (✓)** for expected responses and **red (✗)** for unexpected responses, helping identify potential security vulnerabilities.

## Prerequisites

1. Install server dependencies:
   ```bash
   pip install -r requirements-server.txt
   ```

2. Have a running ChallengeCtl server (or know the URL of one)

3. Obtain valid credentials for testing:
   - Admin username, password, and TOTP secret
   - Runner API key (from an enrolled runner)
   - Provisioning API key (create via WebUI or manage-users.py)
   - Enrollment token (create via WebUI or API)

## Usage

### Option 1: Command Line Arguments

```bash
./audit_api_auth.py \
  --url http://localhost:5000 \
  --admin-username admin \
  --admin-password yourpassword \
  --admin-totp-secret YOURTOTPSECRET \
  --runner-api-key your_runner_api_key_here \
  --provisioning-api-key your_provisioning_key_here \
  --enrollment-token your_enrollment_token_here
```

### Option 2: Environment Variables

```bash
export AUDIT_URL=http://localhost:5000
export AUDIT_ADMIN_USERNAME=admin
export AUDIT_ADMIN_PASSWORD=yourpassword
export AUDIT_ADMIN_TOTP_SECRET=YOURTOTPSECRET
export AUDIT_RUNNER_API_KEY=your_runner_api_key_here
export AUDIT_PROVISIONING_API_KEY=your_provisioning_key_here
export AUDIT_ENROLLMENT_TOKEN=your_enrollment_token_here

./audit_api_auth.py
```

### Partial Testing

You can run the audit with only some credentials. The script will skip tests for credentials you don't provide:

```bash
# Test only admin endpoints
./audit_api_auth.py \
  --url http://localhost:5000 \
  --admin-username admin \
  --admin-password yourpassword \
  --admin-totp-secret YOURTOTPSECRET
```

## Getting Test Credentials

### Admin Credentials

1. Create an admin user using `manage-users.py`:
   ```bash
   python manage-users.py --config config.yaml create-user admin
   ```

2. The script will output the TOTP secret for 2FA setup

### Runner API Key

1. Create an enrollment token (via WebUI or API)
2. Use the enrollment process to register a runner
3. The API key is generated during enrollment
4. You can also extract it from an existing runner's configuration

### Provisioning API Key

1. Log in to the WebUI as admin
2. Navigate to Settings → Provisioning API Keys
3. Create a new key and copy it immediately (it's only shown once)

Or use the API:
```bash
curl -X POST http://localhost:5000/api/provisioning/keys \
  -H "Cookie: session_token=YOUR_SESSION" \
  -H "X-CSRF-Token: YOUR_CSRF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "audit-key", "description": "For security audit"}'
```

### Enrollment Token

Via API (requires admin session):
```bash
curl -X POST http://localhost:5000/api/enrollment/token \
  -H "Cookie: session_token=YOUR_SESSION" \
  -H "X-CSRF-Token: YOUR_CSRF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"runner_name": "audit-runner"}'
```

## Understanding Results

### Expected Behavior

- **Public endpoints** (`/api/health`, `/api/public/challenges`): Should accept ANY authentication (including none)
- **Admin endpoints**: Should ONLY accept valid admin session credentials
- **Runner endpoints**: Should ONLY accept valid runner API keys
- **Provisioning endpoints**: Should accept admin OR provisioning API keys
- **Enrollment endpoints**: Should accept valid enrollment tokens

### Security Issues

The script will flag security issues with **red (✗)** markers. Common issues include:

❌ **Endpoint accessible without authentication when it shouldn't be**
   - This is a critical security vulnerability
   - The endpoint should return 401 or 403 for unauthenticated requests

❌ **Endpoint accessible with wrong credential type**
   - For example, a runner endpoint accepting admin credentials
   - This may indicate improper access control

### Exit Codes

- `0`: All tests passed - no security issues detected
- `1`: Some tests failed - potential security vulnerabilities found

## Example Output

```
================================================================================
ChallengeCtl API Authentication Audit
================================================================================

Base URL: http://localhost:5000
Admin credentials: ✓
Runner API key: ✓
Provisioning API key: ✓
Enrollment token: ✓

GET /api/health
  Health check endpoint
    ✓ admin           - Expected success, got 200
    ✓ runner          - Expected success, got 200
    ✓ provisioning    - Expected success, got 200
    ✓ enrollment      - Expected success, got 200
    ✓ invalid         - Expected success, got 200
    ✓ none            - Expected success, got 200

GET /api/users
  List all users
    ✓ admin           - Expected success, got 200
    ✓ runner          - Expected auth failure, got 401
    ✓ provisioning    - Expected auth failure, got 401
    ✓ enrollment      - Expected auth failure, got 401
    ✓ invalid         - Expected auth failure, got 401
    ✓ none            - Expected auth failure, got 401

...

================================================================================
Audit Summary
================================================================================
Total tests:   252
Passed tests:  252
Failed tests:  0
Skipped tests: 0
Pass rate:     100.0%

✓ All tests passed!
```

## Integration with CI/CD

You can integrate this script into your CI/CD pipeline to ensure authentication remains secure after changes:

```yaml
# .github/workflows/security-audit.yml
name: API Security Audit

on: [push, pull_request]

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements-server.txt
      - name: Start server
        run: |
          # Start server in background
          python server/main.py --config test-config.yaml &
          sleep 5
      - name: Run audit
        env:
          AUDIT_ADMIN_USERNAME: ${{ secrets.TEST_ADMIN_USERNAME }}
          AUDIT_ADMIN_PASSWORD: ${{ secrets.TEST_ADMIN_PASSWORD }}
          AUDIT_ADMIN_TOTP_SECRET: ${{ secrets.TEST_ADMIN_TOTP_SECRET }}
        run: ./audit_api_auth.py
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'pyotp'"

Install server dependencies:
```bash
pip install -r requirements-server.txt
```

### "Admin authentication failed"

- Verify username and password are correct
- Ensure TOTP secret is correct (32-character base32 string)
- Check that the server is running and accessible

### "Connection refused"

- Ensure the server is running at the specified URL
- Check firewall settings
- Verify the port is correct (default: 5000)

### Many tests skipped

- Provide more credentials to test more scenarios
- At minimum, provide admin credentials for comprehensive testing

## Security Best Practices

1. **Don't commit credentials** - Use environment variables or secure vaults
2. **Rotate test credentials** - Change them regularly
3. **Use test environment** - Don't run audits against production with real data
4. **Review failures immediately** - Any failed test is a potential vulnerability
5. **Re-run after changes** - Always audit after modifying authentication code

## Contributing

If you find endpoints not covered by this audit script, please add them to the `_get_endpoints_to_test()` method in `audit_api_auth.py`.
