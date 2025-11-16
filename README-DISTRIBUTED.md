# ChallengeCtl Distributed Mode

This branch adds a distributed architecture to challengectl, enabling multiple SDR runner nodes controlled by a central server with a web interface.

## Quick Start

### 1. Start the Server

```bash
# Install dependencies
pip install -r requirements-server.txt

# Generate runner API keys
python3 generate-api-key.py --count 3

# Generate default config
cd server
python server.py

# Edit server-config.yml with your settings:
#   - Replace all runner API keys with generated ones
#   - Configure challenges
# Then start the server
python server.py
```

### 2. Initial Setup (First Login)

On first startup, the server automatically creates a default admin user with a **random password**.

Check the server logs for the credentials:

```
================================================================================
DEFAULT ADMIN USER CREATED
================================================================================
Username: admin
Password: <16-character random password>

IMPORTANT: Log in with these credentials to create your admin account.
You will be prompted to create a new user with TOTP 2FA on first login.
After setup, you can delete this default admin account.
================================================================================
```

**Initial Setup Flow:**
1. Log in at `http://server-ip:8443/login` with the default admin credentials from the logs
2. You'll be redirected to the **Initial Setup** page
3. Create your personal admin account:
   - Choose your username
   - Set a strong password (minimum 8 characters)
   - Scan the QR code with your authenticator app (Google Authenticator, Authy, etc.)
   - Verify your TOTP setup by entering a code
4. You're automatically logged in with your new account
5. (Optional) Delete the default `admin` account from the Users page

Server runs on `http://0.0.0.0:8443`

### 3. Start Runner(s)

On each SDR host:

```bash
# Install dependencies
pip install -r requirements-runner.txt

# Generate default config
cd runner
python runner.py

# Edit runner-config.yml with:
#   - Unique runner_id
#   - Server URL
#   - API key (from server config)
#   - SDR devices

# Start runner
python runner.py
```

### 4. Access WebUI

Open browser to `http://<server-ip>:8443`

**Authentication:**
- Public dashboard (no auth required): `http://<server-ip>:8443/public`
- Admin login: `http://<server-ip>:8443/login`
  - Login with the username/password you created
  - Enter the 6-digit TOTP code from your authenticator app

## Features

✅ **Central Control** - Single server manages all runners
✅ **Web Dashboard** - Real-time monitoring and control
✅ **Mutual Exclusion** - No duplicate transmissions
✅ **Auto Failover** - Requeue on runner failure
✅ **File Sync** - Automatic WAV/file distribution
✅ **Live Logs** - Real-time log streaming
✅ **Manual Triggers** - Force challenge transmission
✅ **Stop** - Instant shutdown of all transmissions

## Architecture

- **Server:** Python Flask + SQLite + WebSocket
- **Runner:** Python client + existing challenge modules
- **WebUI:** Vue.js 3 + Element Plus

See [docs/DISTRIBUTED_ARCHITECTURE.md](docs/DISTRIBUTED_ARCHITECTURE.md) for full documentation.

## Configuration

### Server Config (`server-config.yml`)

```yaml
server:
  api_keys:
    runner-1: "unique-key-1"
    runner-2: "unique-key-2"
    # Note: API keys are only for runners
    # Admin users authenticate via username/password/TOTP

challenges:
  - name: NBFM_FLAG_1
    frequency: 146550000
    modulation: nbfm
    flag: challenges/voice.wav
    min_delay: 60
    max_delay: 90
```

### Runner Config (`runner-config.yml`)

```yaml
runner:
  runner_id: "runner-1"
  server_url: "http://192.168.1.100:8443"
  api_key: "unique-key-1"

radios:
  devices:
  - name: 0
    model: hackrf
```

## WebUI Screenshots

### Dashboard
- Live runner status
- Challenge queue statistics
- Recent transmissions
- Success rate metrics

### Runners
- View all connected runners
- Device inventory
- Kick offline runners

### Challenges
- Enable/disable challenges
- Manual trigger
- Transmission history
- Reload from config

**Challenge Status Values:**
- **queued** - Challenge is ready and waiting to be assigned to a runner
- **assigned** - Challenge is currently assigned to a runner and being transmitted
- **disabled** - Challenge is disabled (not in transmission queue)

### Logs
- Live log streaming
- Filter by level
- Auto-scroll
- Color-coded

### Users
- **Web-based user management** - Create and manage users from the UI
- Create new admin users with auto-generated TOTP
- Enable/disable user accounts
- Reset TOTP secrets (QR code displayed)
- Delete users
- View user login history

## Security

- **Two-Factor Authentication** - Admin users use username/password + TOTP (Google Authenticator, Authy, etc.)
- **API Key Authentication** - Each runner has unique key
- **Separate Auth Domains** - Runners use API keys, admins use TOTP
- **Session Management** - 24-hour session expiry with TOTP verification
- **Password Hashing** - bcrypt for secure password storage
- **TLS Support** - Use nginx reverse proxy for HTTPS
- **Database Locking** - Prevents race conditions
- **Timeout Protection** - Auto-recovery from failures

## User Management

### Web UI (Recommended)

The easiest way to manage users is through the **Users** page in the web interface:

1. Log in to the admin interface
2. Click "Users" in the sidebar
3. Create, enable/disable, or delete users
4. Reset TOTP secrets with automatic QR code generation
5. View user status and login history

### Command Line (Alternative)

You can also use the `manage-users.py` script:

```bash
# Create a new admin user
python3 manage-users.py create <username>

# List all users
python3 manage-users.py list

# Disable a user account
python3 manage-users.py disable <username>

# Enable a user account
python3 manage-users.py enable <username>

# Change user password
python3 manage-users.py change-password <username>

# Reset TOTP secret (if user loses access to authenticator app)
python3 manage-users.py reset-totp <username>
```

**Setting up TOTP:**
1. Create a user (web UI or CLI)
2. Scan the QR code with your authenticator app (Google Authenticator, Authy, 1Password, etc.)
3. Save credentials securely and share with the user
4. User can change their password after first login

## Compatibility

- **Standalone Mode** - Existing `challengectl.py` still works
- **All Modulations** - CW, NBFM, SSB, FHSS, POCSAG, LRS, FreeDV, ASK
- **All Devices** - HackRF, BladeRF, USRP

## Limitations

- SQLite suitable for 2-10 runners (tested with 2-3)
- No built-in TLS (use nginx for HTTPS)

## Migration from Standalone

1. Keep existing `config.yml` for standalone mode
2. Create `server-config.yml` with same challenges
3. Start server
4. Runners execute challenges same as standalone

## Troubleshooting

**Runner won't connect:**
- Check `server_url` and `api_key`
- Verify server is running
- Check firewall rules

**No challenges assigned:**
- Verify challenges enabled in config
- Check system not paused
- Reload challenges from config

**File download fails:**
- Ensure files exist in server `files/` directory
- Check permissions on cache directory

## Development

### WebUI Development

```bash
cd frontend
npm install
npm run dev  # http://localhost:3000
```

### Server Development

```bash
cd server
python server.py --debug --log-level DEBUG
```

## Testing

```bash
# Start server
python server/server.py

# Start 2 test runners
python runner/runner.py -c runner-1-config.yml &
python runner/runner.py -c runner-2-config.yml &

# Watch dashboard for activity
```

## Production Deployment

### Server (with TLS)

```nginx
# /etc/nginx/sites-available/challengectl
server {
    listen 443 ssl;
    server_name challengectl.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8443;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

```bash
# Start server with gunicorn
gunicorn -k eventlet -w 1 -b 127.0.0.1:8443 server.api:app
```

### Systemd Service

```ini
# /etc/systemd/system/challengectl-server.service
[Unit]
Description=ChallengeCtl Server
After=network.target

[Service]
Type=simple
User=challengectl
WorkingDirectory=/opt/challengectl/server
ExecStart=/usr/bin/python3 server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/challengectl-runner.service
[Unit]
Description=ChallengeCtl Runner
After=network.target

[Service]
Type=simple
User=challengectl
WorkingDirectory=/opt/challengectl/runner
ExecStart=/usr/bin/python3 runner.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## Contributing

This is a major new feature. Testing and feedback welcome!

## License

GPL v3 (same as main project)
