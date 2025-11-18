# Server Setup Guide

This comprehensive guide covers everything you need to know about setting up and running the ChallengeCtl server. The server acts as the central coordinator for challenge distribution, runner management, and provides both a REST API and web interface for administration.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Database Setup](#database-setup)
- [User Management](#user-management)
- [Challenge Configuration](#challenge-configuration)
- [Starting the Server](#starting-the-server)
- [Production Deployment](#production-deployment)
- [Monitoring and Maintenance](#monitoring-and-maintenance)

## Prerequisites

### System Requirements

- **Operating System**: Linux (recommended), macOS, or Windows
- **Python**: Version 3.8 or higher
- **Memory**: Minimum 512 MB RAM (1 GB recommended)
- **Storage**: 1 GB for application and database
- **Network**: Open port for server communication (default: 8443)

### Software Dependencies

The server requires the following Python packages (installed via `requirements.txt`):

- Flask 2.3.0 or higher
- Flask-SocketIO 5.3.0 or higher
- SQLAlchemy 2.0.0 or higher
- PyYAML 6.0 or higher
- pyotp (for TOTP two-factor authentication)
- python-socketio

## Installation

### Clone the Repository

```bash
git clone https://github.com/ckoval7/challengectl.git
cd challengectl
```

### Create a Virtual Environment

It's recommended to use a Python virtual environment to isolate dependencies:

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Verify Installation

Check that the server module can be imported:

```bash
python -c "from challengectl.server import server; print('Installation successful')"
```

## Database Setup

ChallengeCtl uses SQLite for data persistence. The database stores runner registrations, challenge states, transmission history, user accounts, and sessions.

### Automatic Database Initialization

The database is automatically created when you first start the server. No manual initialization is required.

By default, the database file `challengectl.db` is created in the server's working directory.

### Custom Database Location

To use a custom database location, set the `DATABASE_PATH` environment variable before starting the server:

```bash
export DATABASE_PATH=/var/lib/challengectl/challengectl.db
python -m challengectl.server.server
```

### Database Schema

The database includes the following tables:

- **runners**: Registered runners with heartbeat tracking
- **challenges**: Challenge definitions and state (assignments tracked here)
- **transmissions**: Historical record of all transmissions
- **files**: Content-addressed storage for challenge files
- **system_state**: Key-value store for system-wide state
- **users**: Admin user accounts with hashed passwords
- **sessions**: Web interface session management

**Note**: Runner API keys are stored encrypted in the database when using the recommended enrollment process. Legacy deployments may still have API keys in `server-config.yml` for backwards compatibility.

## Initial Setup and User Management

### First-Time Setup

When you start the server for the first time, it automatically creates a default admin account with a randomly generated password. This password is logged to the server log file for security.

**Check the server logs** for the initial credentials:

```bash
# If running in terminal, you'll see it in the output
# Or check the log file:
cat challengectl.server.log | grep "DEFAULT ADMIN USER"
```

You'll see output like:

```
================================================================================
DEFAULT ADMIN USER CREATED
================================================================================
Username: admin
Password: aB3xK9mN2pQ7rT5w

IMPORTANT: Log in with these credentials to create your admin account.
You will be prompted to create a new user with TOTP 2FA on first login.
After setup, you can delete this default admin account.
================================================================================
```

### Creating Your Admin Account

1. **Navigate to the web interface**: `http://localhost:8443` (or your server URL)

2. **Log in with the temporary credentials** shown in the server logs

3. **Complete the initial setup wizard**:
   - You'll be prompted to create a new admin user
   - Choose a strong username and password
   - Set up TOTP two-factor authentication
   - Scan the QR code with your authenticator app (Google Authenticator, Authy, 1Password, etc.)

4. **Log out and log in** with your new account

5. **Optional**: Delete the default admin account through the web interface for security

### Managing Users Through Web Interface

After initial setup, all user management is done through the web interface:

- **Add users**: Go to Users page → Add User button
- **Change passwords**: Users page → Edit user
- **Reset TOTP**: Users page → Reset TOTP button
- **Enable/Disable users**: Users page → Enable/Disable button
- **Delete users**: Users page → Delete button

See the [Web Interface Guide](Web-Interface-Guide#user-management) for detailed instructions.

### Managing Runner Enrollment

**Recommended Approach**: Use the secure enrollment process through the Web UI.

#### Enrolling Runners via Web UI

1. **Log in to the Web UI** at your server's URL

2. **Navigate to the Runners page**

3. **Click "Add Runner"**

4. **Enter runner details**:
   - Runner name (e.g., "sdr-station-1")
   - Token expiry time (default: 24 hours)

5. **Generate credentials**:
   - Click "Generate Token"
   - The system creates both an enrollment token and API key
   - **IMPORTANT**: These are only displayed once - copy them immediately

6. **Provide credentials to runner administrator**:
   - Share the enrollment token and API key securely
   - They will add these to their `runner-config.yml`

7. **Runner enrollment process**:
   - Runner starts with both `enrollment_token` and `api_key` in config
   - On first run, runner self-enrolls using the token
   - After successful enrollment, remove `enrollment_token` from config
   - Runner continues using only the `api_key`

#### Security Features

The enrollment process provides several security benefits:

- **Encrypted Storage**: API keys are encrypted in the database
- **One-Time Display**: Credentials shown only once during generation
- **Token Expiration**: Enrollment tokens expire after configured time
- **Host Validation**: Prevents API key reuse on multiple machines
- **Audit Trail**: Tracks which admin created each enrollment token

#### Legacy Method (Not Recommended)

For backwards compatibility, you can still add API keys to `server-config.yml`:

```bash
# Generate API keys
python3 generate-api-key.py --count 3
```

Edit `server-config.yml`:

```yaml
server:
  api_keys:
    runner-1: "ck_a3f8b9c2d1e4f5a6b7c8d9e0f1a2b3c4"  # Legacy method
```

**Restart the server** to apply changes:

```bash
sudo systemctl restart challengectl
```

**Important**: The legacy YAML method is maintained for backwards compatibility only. New deployments should use the Web UI enrollment process for better security.

## Challenge Configuration

Challenges are defined in a YAML configuration file. By default, the server looks for `server-config.yml` in the current directory.

### Basic Configuration

Create a `server-config.yml` file:

```yaml
challenges:
  - name: CW_FLAG_1
    frequency: 146520000
    modulation: cw
    flag: challenges/cw_message.txt
    min_delay: 120
    max_delay: 180
    enabled: true

  - name: NBFM_FLAG_2
    frequency: 146550000
    modulation: nbfm
    flag: challenges/voice_flag.wav
    min_delay: 60
    max_delay: 90
    enabled: true
```

### Challenge Parameters

Each challenge requires the following parameters:

- **name**: Unique identifier for the challenge
- **frequency**: Transmission frequency in Hz (e.g., 146520000 for 146.52 MHz)
- **modulation**: Modulation type (see supported types below)
- **flag**: Path to the challenge file (relative to server working directory)
- **min_delay**: Minimum seconds between transmissions
- **max_delay**: Maximum seconds between transmissions
- **enabled**: Whether the challenge is currently active (true/false)

### Supported Modulation Types

ChallengeCtl supports the following modulation types:

| Modulation | Description | Typical File Type |
|------------|-------------|-------------------|
| `cw` | Continuous Wave (Morse Code) | `.txt` |
| `ask` | Amplitude Shift Keying | `.bin` |
| `nbfm` | Narrowband FM | `.wav` |
| `ssb` | Single Sideband | `.wav` |
| `fhss` | Frequency Hopping Spread Spectrum | `.bin` |
| `pocsag` | POCSAG Paging | `.txt` |
| `lrs` | LoRa Spread Spectrum | `.bin` |
| `freedv` | FreeDV Digital Voice | `.raw` |
| `paint` | SSTV/Paint | `.png` or `.jpg` |

### Challenge File Organization

Create a `challenges/` directory to store your challenge files:

```bash
mkdir challenges
```

Place all challenge files referenced in your configuration in this directory. The server will calculate SHA-256 hashes of these files and runners will download them automatically.

### Custom Configuration Location

To use a custom configuration file location:

```bash
export CONFIG_PATH=/etc/challengectl/server-config.yml
python -m challengectl.server.server
```

## Starting the Server

### Basic Startup

Start the server with default settings:

```bash
python -m challengectl.server.server
```

The server will:
1. Load the configuration file
2. Connect to the database
3. Start background tasks for cleanup and monitoring
4. Launch the Flask web server on port 8443
5. Begin broadcasting status updates via WebSocket

### Command-Line Options

The server accepts the following environment variables:

- `CONFIG_PATH`: Path to server configuration file (default: `server-config.yml`)
- `DATABASE_PATH`: Path to SQLite database (default: `challengectl.db`)
- `PORT`: HTTP server port (default: 8443)
- `HOST`: Bind address (default: `0.0.0.0`)

Example with custom settings:

```bash
export CONFIG_PATH=/etc/challengectl/config.yml
export DATABASE_PATH=/var/lib/challengectl/db.sqlite
export PORT=8080
python -m challengectl.server.server
```

### Accessing the Web Interface

Once the server is running, access the web interface at:

```
http://localhost:8443
```

Or replace `localhost` with your server's IP address or hostname.

### Stopping the Server

To stop the server gracefully, press `Ctrl+C`. The server will:
1. Complete any in-progress requests
2. Close database connections
3. Shut down background tasks
4. Exit cleanly

## Production Deployment

For production use, follow these best practices:

### Use a Process Manager

Instead of running the server directly, use a process manager like systemd to ensure automatic restarts and proper logging.

Create `/etc/systemd/system/challengectl.service`:

```ini
[Unit]
Description=ChallengeCtl Server
After=network.target

[Service]
Type=simple
User=challengectl
Group=challengectl
WorkingDirectory=/opt/challengectl
Environment="CONFIG_PATH=/etc/challengectl/server-config.yml"
Environment="DATABASE_PATH=/var/lib/challengectl/challengectl.db"
ExecStart=/opt/challengectl/venv/bin/python -m challengectl.server.server
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl enable challengectl
sudo systemctl start challengectl
```

### Use a Reverse Proxy

Run the server behind nginx or Apache for improved security and TLS termination.

Example nginx configuration:

```nginx
server {
    listen 443 ssl http2;
    server_name challengectl.example.com;

    ssl_certificate /etc/letsencrypt/live/challengectl.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/challengectl.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8443;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Secure File Permissions

Ensure proper file permissions for security:

```bash
chmod 600 /etc/challengectl/server-config.yml
chmod 600 /var/lib/challengectl/challengectl.db
chown challengectl:challengectl /var/lib/challengectl/challengectl.db
```

### Regular Backups

Back up your database regularly:

```bash
# Daily backup script
cp /var/lib/challengectl/challengectl.db \
   /var/backups/challengectl/challengectl-$(date +%Y%m%d).db
```

### Log Rotation

Configure log rotation to prevent disk space issues. The server logs to stdout/stderr, so configure your process manager to handle log rotation.

For systemd, logs are automatically managed by journald. To view logs:

```bash
sudo journalctl -u challengectl -f
```

## Monitoring and Maintenance

### Health Check Endpoint

The server provides a health check endpoint at `/health`:

```bash
curl http://localhost:8443/health
```

Returns:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Database Maintenance

The server automatically performs cleanup tasks:

- Removes stale assignments (no heartbeat in 90 seconds)
- Requeues timed-out tasks (assigned for more than 5 minutes)
- Maintains transmission history

To manually compact the database:

```bash
sqlite3 /var/lib/challengectl/challengectl.db "VACUUM;"
```

### Monitoring Runner Status

Monitor runner health through the web interface or via the API:

```bash
curl -X GET http://localhost:8443/api/runners \
  -H "Content-Type: application/json"
```

### Performance Tuning

For high-traffic scenarios:

1. **Increase database timeout**: Modify the database connection string to allow longer lock waits
2. **Adjust cleanup intervals**: Reduce background task frequency if needed
3. **Use connection pooling**: For multiple server instances, consider PostgreSQL instead of SQLite
4. **Monitor resource usage**: Use tools like `htop` to track CPU and memory usage

## Next Steps

Now that your server is set up, you can:

- [Configure and deploy runners](Runner-Setup)
- [Explore the API reference](API-Reference)
- [Understand the system architecture](Architecture)
- [Review troubleshooting tips](Troubleshooting)
