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

ChallengeCtl uses SQLite for data persistence. The database stores runner registrations, challenge states, transmission history, user accounts, and API keys.

### Initialize the Database

Create a new database with the required schema:

```bash
python -m challengectl.server.database init
```

By default, this creates `challengectl.db` in the current directory.

### Custom Database Location

To use a custom database location, set the `DATABASE_PATH` environment variable:

```bash
export DATABASE_PATH=/var/lib/challengectl/challengectl.db
python -m challengectl.server.database init
```

### Database Schema

The database includes the following tables:

- **runners**: Registered runners with heartbeat tracking
- **challenges**: Challenge definitions and state
- **assignments**: Active task assignments to runners
- **transmission_log**: Historical record of all transmissions
- **users**: Admin user accounts with hashed passwords
- **runner_keys**: API keys for runner authentication

## User Management

### Creating Admin Users

Admin users can access the web interface and manage the system. Create your first admin user:

```bash
python -m challengectl.server.database add-user admin
```

You'll be prompted to enter a password. The command will generate a TOTP secret for two-factor authentication:

```
Enter password for user 'admin':
TOTP Secret: JBSWY3DPEHPK3PXP
Add this to your authenticator app.
User 'admin' created successfully.
```

**Important**: Save the TOTP secret immediately. Add it to an authenticator app like Google Authenticator, Authy, or 1Password.

### Managing API Keys

Runners authenticate using API keys. Create an API key for each runner:

```bash
python -m challengectl.server.database add-runner-key runner1
```

This generates a unique API key:

```
API Key: ck_a3f8b9c2d1e4f5a6b7c8d9e0f1a2b3c4
```

**Important**: Save this key securely. You'll need it when configuring the runner. Each runner should have its own unique API key.

### Listing Users and Keys

To view all admin users:

```bash
python -m challengectl.server.database list-users
```

To view all API keys:

```bash
python -m challengectl.server.database list-keys
```

### Removing Users or Keys

Remove an admin user:

```bash
python -m challengectl.server.database remove-user admin
```

Remove an API key:

```bash
python -m challengectl.server.database remove-key ck_a3f8b9c2d1e4f5a6b7c8d9e0f1a2b3c4
```

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
