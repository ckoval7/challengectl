# ChallengeCtl Comprehensive Security Analysis Report

**Date:** 2025-11-17
**Analyzed by:** Comprehensive Security Analysis
**Scope:** Web UI, Authentication System, API, Backend, and Database

## Executive Summary

This comprehensive security analysis identified **3 CRITICAL**, **4 HIGH**, and **7 MEDIUM** severity vulnerabilities across the ChallengeCtl web application, authentication system, and API. The most critical findings include command injection vulnerabilities, insecure cookie configuration, and missing input validation controls.

### Risk Summary
- **Critical:** 3 issues requiring immediate attention
- **High:** 4 issues requiring prompt remediation
- **Medium:** 7 issues for scheduled remediation
- **Low/Info:** 5 observations and best practices

---

## Critical Vulnerabilities (Immediate Action Required)

### 1. Command Injection in FT8 Challenge Module 🔴 CRITICAL
**File:** `challenges/automate_ft8/run_response.py`
**Lines:** 30, 38, 52, 58, 60, 65

**Description:**
Multiple instances of command injection vulnerabilities exist where user-controlled input is passed directly to `os.system()` without sanitization.

**Vulnerable Code Examples:**
```python
# Line 30
os.system('python ft8_tx.py ' + tx_cycle)

# Lines 52, 58, 60, 65
os.system('./ft8encode "' + their_call + ' ' + my_call + ' ' + my_grid + '"')
os.system('./ft8encode "' + their_call + ' ' + my_call + ' R+' + str(snr).zfill(2) + '"')
```

**Attack Vector:**
An attacker could inject shell commands through `their_call`, `my_call`, or `my_grid` parameters:
```
their_call = 'TEST"; rm -rf / #'
```

**Exploitation Impact:**
- Remote Code Execution (RCE)
- Complete system compromise
- Data exfiltration
- Lateral movement to other systems

**Recommendation:**
```python
# Replace os.system() with subprocess.run() using argument lists
import subprocess
import shlex

# GOOD - Prevents command injection
subprocess.run(['./ft8encode', f'{their_call} {my_call} {my_grid}', '1000', '0', '0', '0', '0', '1', '47'])

# Or validate input strictly
import re
def validate_callsign(call):
    if not re.match(r'^[A-Z0-9]{3,6}$', call):
        raise ValueError("Invalid callsign")
    return call
```

---

### 2. Insecure Cookie Configuration (Session Hijacking Risk) 🔴 CRITICAL
**File:** `server/api.py`
**Lines:** 513, 569, 738

**Description:**
Session and CSRF cookies are configured with `SameSite=None` and `Secure=False`, making them vulnerable to CSRF and session hijacking attacks.

**Vulnerable Code:**
```python
# Lines 513, 569
response.set_cookie(
    'session_token',
    session_token,
    httponly=True,
    secure=False,      # ❌ Should be True in production
    samesite=None,     # ❌ Too permissive - allows CSRF
    max_age=86400
)
```

**Attack Vector:**
1. **CSRF:** Attacker can trigger authenticated requests from victim's browser
2. **Session Hijacking:** Session tokens transmitted over HTTP can be intercepted
3. **Cross-site attacks:** Cookies sent to all cross-origin requests

**Recommendation:**
```python
# Detect if running on HTTPS
is_secure = request.is_secure or request.headers.get('X-Forwarded-Proto') == 'https'

response.set_cookie(
    'session_token',
    session_token,
    httponly=True,
    secure=is_secure,        # ✅ True in production
    samesite='Strict',       # ✅ Prevent CSRF (or 'Lax' if needed)
    max_age=86400
)
```

---

### 3. WebSocket CORS Configuration Too Permissive 🔴 CRITICAL
**File:** `server/api.py`
**Line:** 117

**Description:**
WebSocket connections accept connections from any origin (`cors_allowed_origins="*"`), bypassing CORS protection.

**Vulnerable Code:**
```python
# Line 117
self.socketio = SocketIO(self.app, cors_allowed_origins="*")
```

**Attack Vector:**
- Malicious website can establish WebSocket connection to server
- Can send commands or receive sensitive data
- Bypasses Same-Origin Policy

**Recommendation:**
```python
# Use the same CORS origins as the REST API
self.socketio = SocketIO(
    self.app,
    cors_allowed_origins=allowed_origins,  # Same as REST API
    cookie='session_token'  # Tie to session cookie
)
```

---

## High Severity Vulnerabilities

### 4. Missing File Upload Restrictions 🟠 HIGH
**File:** `server/api.py`
**Lines:** 1575-1617

**Description:**
File upload endpoint lacks size limits, type validation, and malware scanning.

**Vulnerable Code:**
```python
@self.app.route('/api/files/upload', methods=['POST'])
@self.require_api_key
def upload_file():
    file_data = file.read()  # ❌ No size limit
    # ❌ No file type validation
    # ❌ No malware scanning
```

**Attack Vector:**
1. **Resource exhaustion:** Upload massive files to consume disk space
2. **Malicious file storage:** Upload malware that could be executed later
3. **ZIP bombs:** Compressed files that expand to enormous size

**Recommendation:**
```python
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
ALLOWED_EXTENSIONS = {'.wav', '.bin', '.txt', '.yml', '.yaml'}

def upload_file():
    file = request.files['file']

    # Validate file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    if file_size > MAX_FILE_SIZE:
        return jsonify({'error': 'File too large'}), 413

    # Validate file extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({'error': 'Invalid file type'}), 400

    # Read and process file...
```

---

### 5. Missing Rate Limiting on Most Endpoints 🟠 HIGH
**File:** `server/api.py`
**Lines:** 119-128

**Description:**
Rate limiting is only applied to `/auth/login` and `/auth/verify-totp`. Other endpoints are vulnerable to abuse.

**Current Configuration:**
```python
# Only these endpoints are rate-limited:
@self.limiter.limit("5 per 15 minutes")
def login(): ...

@self.limiter.limit("5 per 15 minutes")
def verify_totp(): ...

# Everything else: NO RATE LIMITING
```

**Attack Vector:**
1. **API abuse:** Unlimited requests to `/api/challenges`, `/api/runners`, etc.
2. **DoS:** Exhaust server resources with rapid requests
3. **Data scraping:** Extract all data without restrictions
4. **WebSocket flooding:** Spam WebSocket connections

**Recommendation:**
```python
# Add default rate limits
self.limiter = Limiter(
    app=self.app,
    key_func=get_remote_address,
    default_limits=["100 per minute", "1000 per hour"],  # ✅ Default limits
    storage_uri="memory://",
    strategy="fixed-window"
)

# Stricter limits for sensitive endpoints
@self.limiter.limit("5 per 15 minutes")  # Login
@self.limiter.limit("10 per minute")     # API reads
@self.limiter.limit("5 per minute")      # API writes
```

---

### 6. SQL Injection Risk from Dynamic Query Construction 🟠 HIGH
**File:** `server/server.py`
**Lines:** 153-157

**Description:**
While most queries use parameterization correctly, there's a dynamic SQL construction in the startup routine that could be risky if modified.

**Vulnerable Pattern:**
```python
# Line 153-157
cursor.execute('''
    SELECT challenge_id FROM challenges
    WHERE status IN ('assigned', 'waiting')
      AND enabled = 1
''')
```

**Current Status:** ✅ Currently safe (hardcoded values)

**Risk:** If someone modifies this to use variables without parameterization:
```python
# ❌ DANGEROUS - Don't do this
status_filter = request.args.get('status')
cursor.execute(f"SELECT * FROM challenges WHERE status = '{status_filter}'")
```

**Recommendation:**
1. Add code review guidelines prohibiting string interpolation in SQL
2. Use an ORM like SQLAlchemy for type safety
3. Add static analysis tools (e.g., Bandit) to CI/CD

---

### 7. Weak Default Password Entropy (Initial Setup) 🟠 HIGH
**File:** `server/database.py`
**Lines:** 170-183

**Description:**
Default admin password uses `secrets.choice()` correctly, but the character set could be stronger.

**Current Code:**
```python
# Line 176-177
alphabet = string.ascii_letters + string.digits  # ❌ No special characters
default_password = ''.join(secrets.choice(alphabet) for _ in range(16))
```

**Recommendation:**
```python
# ✅ Include special characters for stronger passwords
import string
import secrets

alphabet = string.ascii_letters + string.digits + string.punctuation
default_password = ''.join(secrets.choice(alphabet) for _ in range(20))
```

---

## Medium Severity Vulnerabilities

### 8. Information Disclosure in Error Messages 🟡 MEDIUM
**File:** `server/api.py`
**Lines:** Various

**Description:**
Error messages may leak sensitive information about system internals.

**Example:**
```python
# Line 1616
except Exception as e:
    logger.error(f"Error uploading file: {e}")
    return jsonify({'error': str(e)}), 500  # ❌ Leaks exception details
```

**Recommendation:**
```python
except Exception as e:
    logger.error(f"Error uploading file: {e}")
    return jsonify({'error': 'Internal server error'}), 500  # ✅ Generic message
```

---

### 9. Missing Security Headers 🟡 MEDIUM
**Description:**
The application doesn't set important security headers.

**Missing Headers:**
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Strict-Transport-Security: max-age=31536000`
- `Content-Security-Policy`
- `Permissions-Policy`

**Recommendation:**
```python
# Add to Flask app initialization
from flask_talisman import Talisman

# Configure security headers
csp = {
    'default-src': "'self'",
    'script-src': "'self' 'unsafe-inline'",  # Vue.js may need unsafe-inline
    'style-src': "'self' 'unsafe-inline'",
    'img-src': "'self' data:",
    'connect-src': "'self' ws: wss:"
}

Talisman(
    self.app,
    force_https=True,
    strict_transport_security=True,
    content_security_policy=csp,
    x_content_type_options=True,
    x_frame_options='DENY'
)
```

---

### 10. Insufficient Session Timeout Validation 🟡 MEDIUM
**File:** `server/api.py`
**Lines:** 697-701

**Description:**
Session expiry checks use local system time, which can be manipulated in certain scenarios.

**Recommendation:**
- Use UTC timestamps consistently
- Add server-side session timeout enforcement
- Implement sliding session expiration

---

### 11. Missing Input Validation on Challenge Config 🟡 MEDIUM
**File:** `server/api.py`
**Lines:** 1385-1409

**Description:**
Challenge configuration updates accept arbitrary JSON without schema validation.

**Recommendation:**
```python
import jsonschema

CHALLENGE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "maxLength": 100},
        "frequency": {"type": "integer", "minimum": 0},
        "modulation": {"type": "string", "enum": ["nbfm", "cw", "ssb", ...]},
        # ... more fields
    },
    "required": ["name", "frequency", "modulation"]
}

def update_challenge(challenge_id):
    config = data.get('config')

    # Validate against schema
    try:
        jsonschema.validate(config, CHALLENGE_SCHEMA)
    except jsonschema.ValidationError as e:
        return jsonify({'error': f'Invalid config: {e.message}'}), 400
```

---

### 12. TOTP Window Too Large 🟡 MEDIUM
**File:** `server/api.py`
**Line:** 637

**Description:**
TOTP validation uses `valid_window=1`, accepting codes from ±30 seconds (90-second total window).

**Current Code:**
```python
# Line 637
if not totp.verify(totp_code, valid_window=1):  # ±1 period = ±30s
```

**Recommendation:**
```python
# Use valid_window=0 for strict validation (30-second window only)
if not totp.verify(totp_code, valid_window=0):
    return jsonify({'error': 'Invalid TOTP code'}), 401
```

**Note:** This may affect user experience if clocks are slightly out of sync.

---

### 13. No Account Lockout Mechanism 🟡 MEDIUM
**Description:**
While rate limiting exists, there's no permanent account lockout after repeated failed attempts.

**Recommendation:**
```python
# Add failed login tracking
def login():
    user = self.db.get_user(username)

    # Check if account is locked
    if user and user.get('locked_until'):
        if datetime.now() < datetime.fromisoformat(user['locked_until']):
            return jsonify({'error': 'Account temporarily locked'}), 403

    # Track failed attempts
    if not password_valid:
        failed_attempts = user.get('failed_login_attempts', 0) + 1
        self.db.increment_failed_attempts(username, failed_attempts)

        # Lock account after 5 failed attempts
        if failed_attempts >= 5:
            lock_until = datetime.now() + timedelta(minutes=30)
            self.db.lock_account(username, lock_until)
            return jsonify({'error': 'Account locked due to repeated failures'}), 403
```

---

### 14. Encryption Key Management 🟡 MEDIUM
**File:** `server/crypto.py`
**Lines:** 40-63

**Description:**
Encryption key is stored in a file without external key management system.

**Current Implementation:**
```python
# Key stored in server/.encryption_key with 600 permissions
# ⚠️ Single point of failure
# ⚠️ Not backed up securely
# ⚠️ No key rotation mechanism
```

**Recommendation:**
1. Use environment variable or secrets manager (AWS KMS, HashiCorp Vault, etc.)
2. Implement key rotation mechanism
3. Consider using different keys for different purposes (data encryption, TOTP, etc.)

---

## Low Severity / Informational Findings

### 15. CORS Configuration Complexity ℹ️ INFO
**File:** `server/api.py`
**Lines:** 85-114

**Observation:**
CORS configuration has multiple fallbacks (config file → env var → localhost defaults), which could lead to misconfigurations.

**Recommendation:**
Document CORS configuration clearly and validate on startup.

---

### 16. Verbose Logging May Leak Sensitive Data ℹ️ INFO
**Examples:**
```python
# Line 484 - Logs failed login reason
logger.warning(f"... reason={reason} ...")  # Could help attackers

# Line 641 - Logs partial TOTP code
logger.warning(f"... code={totp_code[:2]}** ...")
```

**Recommendation:**
Review logs for sensitive data leakage before production deployment.

---

### 17. WebSocket Authentication Bypass for Public Namespace ℹ️ INFO
**File:** `server/api.py`
**Lines:** 1702-1719

**Observation:**
Public WebSocket namespace (`/public`) has no authentication, which is by design but should be documented.

**Status:** ✅ Acceptable for public dashboard

---

### 18. Password Complexity Not Enforced ℹ️ INFO
**File:** `server/api.py`
**Lines:** 768, 832

**Description:**
Only minimum length (8 characters) is enforced. No complexity requirements.

**Current Code:**
```python
if len(new_password) < 8:
    return jsonify({'error': 'Password must be at least 8 characters'}), 400
```

**Recommendation:**
```python
def validate_password_strength(password):
    if len(password) < 12:
        return False, "Password must be at least 12 characters"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain uppercase letters"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain lowercase letters"
    if not re.search(r'\d', password):
        return False, "Password must contain numbers"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain special characters"
    return True, ""
```

---

### 19. No Content Security Policy on Frontend ℹ️ INFO
**File:** `frontend/index.html`

**Observation:**
HTML doesn't include CSP meta tags.

**Recommendation:**
```html
<meta http-equiv="Content-Security-Policy"
      content="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';">
```

---

## Positive Security Findings ✅

The following security controls are **correctly implemented**:

1. ✅ **SQL Injection Protection:** All database queries use parameterized statements (database.py:57-947)
2. ✅ **XSS Protection:** Vue.js templates auto-escape output (no `v-html` usage found)
3. ✅ **Password Hashing:** bcrypt with proper salt (api.py:471, 782, 838)
4. ✅ **TOTP 2FA:** pyotp implementation with replay protection (api.py:627-652)
5. ✅ **Session Management:** httpOnly cookies prevent XSS token theft (api.py:509, 565)
6. ✅ **CSRF Protection:** Double-submit cookie pattern correctly implemented (api.py:278-302)
7. ✅ **Timing Attack Prevention:** Constant-time password comparison with dummy hash (api.py:460-475)
8. ✅ **TOTP Secret Encryption:** Fernet encryption for TOTP secrets at rest (crypto.py:65-105)
9. ✅ **Authentication Guards:** Vue Router properly guards protected routes (router.js:79-116)
10. ✅ **Path Traversal Prevention:** File downloads use hash-based lookup (api.py:1559-1573)

---

## Remediation Priority

### Immediate (This Week)
1. **Fix command injection** in FT8 challenge module (CRITICAL)
2. **Update cookie configuration** to use `SameSite=Strict` and `Secure=True` (CRITICAL)
3. **Fix WebSocket CORS** to use same origin list as REST API (CRITICAL)

### Short-term (This Month)
4. Add file upload restrictions (size, type, scanning)
5. Implement comprehensive rate limiting
6. Add security headers (Talisman or custom middleware)
7. Review and sanitize error messages

### Medium-term (Next Quarter)
8. Implement account lockout mechanism
9. Add input validation schemas for all endpoints
10. Migrate to external key management system
11. Add password complexity requirements
12. Implement security monitoring and alerting

---

## Testing Recommendations

### Security Testing to Perform:
1. **Penetration Testing:** Hire external firm to test for vulnerabilities
2. **Static Analysis:** Run Bandit, Semgrep, or similar tools in CI/CD
3. **Dynamic Analysis:** Use OWASP ZAP or Burp Suite for automated scanning
4. **Dependency Scanning:** Monitor for vulnerable dependencies (Dependabot, Snyk)
5. **Code Review:** Implement security-focused code review process

### Test Cases to Add:
```python
# Test command injection prevention
def test_no_command_injection():
    malicious_call = "TEST\"; rm -rf / #"
    with pytest.raises(ValueError):
        answer_cq(malicious_call, "MYCALL", "GRID")

# Test session hijacking prevention
def test_secure_cookies():
    response = client.post('/api/auth/login', json={...})
    assert 'Secure' in response.headers['Set-Cookie']
    assert 'SameSite=Strict' in response.headers['Set-Cookie']

# Test file upload size limit
def test_file_upload_size_limit():
    large_file = b'A' * (101 * 1024 * 1024)  # 101 MB
    response = client.post('/api/files/upload', data={'file': large_file})
    assert response.status_code == 413
```

---

## Compliance Considerations

If this system handles sensitive data, consider compliance with:
- **GDPR:** User data protection, right to erasure, breach notification
- **SOC 2:** Security controls, access management, logging
- **PCI DSS:** If handling payment data
- **NIST Cybersecurity Framework:** Risk management best practices

---

## Conclusion

ChallengeCtl demonstrates **strong security fundamentals** in authentication, session management, and database security. However, **3 critical vulnerabilities** require immediate attention:

1. Command injection in FT8 module
2. Insecure cookie configuration
3. Permissive WebSocket CORS

Once these are addressed, the application will have a significantly improved security posture. Regular security testing, dependency updates, and code reviews should be part of the ongoing maintenance process.

---

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [Flask Security Best Practices](https://flask.palletsprojects.com/en/latest/security/)
- [Vue.js Security Guide](https://vuejs.org/guide/best-practices/security.html)
- [NIST Password Guidelines](https://pages.nist.gov/800-63-3/)

---

**Report Generated:** 2025-11-17
**Next Review:** Recommended within 30 days after remediation
