# ChallengeCtl Distributed Mode

This branch adds a distributed architecture to challengectl, enabling multiple SDR runner nodes controlled by a central server with a web interface.

## Quick Start

### 1. Start the Server

```bash
# Install dependencies
pip install -r requirements-server.txt

# Generate API keys
python3 generate-api-key.py --count 4

# Generate default config
cd server
python server.py

# Edit server-config.yml with your settings:
#   - Replace all API keys with generated ones
#   - Configure challenges
# Then start the server
python server.py
```

Server runs on `http://0.0.0.0:8443`

### 2. Start Runner(s)

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

### 3. Access WebUI

Open browser to `http://<server-ip>:8443`

**Default admin API key:** `change-this-admin-key-xyz999` (change in `server-config.yml`)

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
    admin: "admin-key"

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

### Logs
- Live log streaming
- Filter by level
- Auto-scroll
- Color-coded

## Security

- **API Key Authentication** - Each runner has unique key
- **TLS Support** - Use nginx reverse proxy for HTTPS
- **Database Locking** - Prevents race conditions
- **Timeout Protection** - Auto-recovery from failures

## Compatibility

- **Standalone Mode** - Existing `challengectl.py` still works
- **All Modulations** - CW, NBFM, SSB, FHSS, POCSAG, LRS, FreeDV, ASK
- **All Devices** - HackRF, BladeRF, USRP

## Limitations

- SQLite suitable for 2-10 runners (tested with 2-3)
- No built-in TLS (use nginx)
- Simple API key auth (consider mTLS for production)

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
