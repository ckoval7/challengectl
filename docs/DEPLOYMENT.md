# ChallengeCtl Deployment Guide

This guide covers deploying the distributed challengectl system.

## Overview

The distributed system consists of three components:
- **Frontend** - Vue.js web interface (admin and public dashboard)
- **Server** - Coordinates challenges and manages runners
- **Runners** - Execute challenges on SDR hardware

All components run from the `challengectl` directory. For production, use nginx as a reverse proxy for TLS/HTTPS.

## Quick Reference

**Configuration Files:**
- `server-config.yml` - Server configuration
- `runner-config.yml` - Runner configuration (one per runner)

**Service Files (optional):**
- `docs/challengectl-server.service` - Systemd service for server
- `docs/challengectl-runner.service` - Systemd service for runner

**Nginx:**
- `docs/nginx-challengectl.conf` - Reverse proxy configuration

## Frontend Deployment

### Build the Frontend

```bash
cd frontend

# Install dependencies
npm install

# Build for production
npm run build

# Built files will be in frontend/dist/
```

### Serve with Nginx

The frontend is a static site. Nginx will serve the built files and proxy API requests to the backend server.

See the "Nginx Setup" section below for configuration.

### Development Mode

For development, run the frontend dev server:

```bash
cd frontend
npm run dev
```

This runs on `http://localhost:5173` with hot reload.

## Server Deployment

### Basic Setup

```bash
cd server

# Copy example config
cp ../server-config.example.yml server-config.yml

# Edit configuration (change all API keys, configure challenges, set conference details)
# Use your preferred text editor
```

### Install Dependencies

```bash
# Install Python dependencies
pip3 install -r requirements-server.txt
```

### Run the Server

```bash
# Run from server directory
cd server
python3 server.py -c server-config.yml

# Server logs to: challengectl.server.log
# Database: challengectl.db
# Challenge files: files/
```

### Systemd Service (Optional)

For production deployments, you can run the server as a systemd service.

Edit `docs/challengectl-server.service` and update paths:
- Change `WorkingDirectory` to your challengectl directory
- Change `ExecStart` paths to match your installation
- Change `--config` to point to your config file

```bash
# Copy service file
sudo cp docs/challengectl-server.service /etc/systemd/system/

# Edit paths in service file (WorkingDirectory, ExecStart, config path)
# Use your preferred text editor

# Reload systemd
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable challengectl-server
sudo systemctl start challengectl-server

# Check status
sudo systemctl status challengectl-server
sudo journalctl -u challengectl-server -f
```

## Runner Deployment

### Basic Setup

```bash
cd runner

# Copy example config
cp ../runner-config.example.yml runner-config.yml

# Edit configuration (set runner_id, server_url, api_key, configure SDR devices)
# Use your preferred text editor
```

The runner creates local directories for cache and temporary files:
- `cache/` - Downloaded challenge files
- `temp/` - Temporary files (LRS generation, etc)
- `challengectl.runner.log` - Log file

### Install Dependencies

```bash
# System packages
sudo apt-get update
sudo apt-get install -y python3 python3-pip gnuradio gr-osmosdr

# Python dependencies
pip3 install -r requirements-runner.txt

# SDR-specific packages
# For HackRF:
sudo apt-get install -y hackrf libhackrf-dev

# For BladeRF:
sudo apt-get install -y bladerf libbladerf-dev

# For USRP:
sudo apt-get install -y uhd-host libuhd-dev
```

### Run the Runner

```bash
# Run from runner directory
cd runner
python3 runner.py -c runner-config.yml

# Logs to: challengectl.runner.log
```

### SDR Device Access

Runners need access to USB SDR devices. Add your user to the `plugdev` group:

```bash
sudo usermod -a -G plugdev $USER

# Log out and back in for group change to take effect
```

You may also need udev rules for your specific hardware:

```bash
# Example for HackRF:
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="6089", GROUP="plugdev", MODE="0660"' | \
  sudo tee /etc/udev/rules.d/52-hackrf.rules

# Reload udev
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### Systemd Service (Optional)

Edit `docs/challengectl-runner.service` and update paths:

```bash
# Copy service file
sudo cp docs/challengectl-runner.service /etc/systemd/system/

# Edit paths (WorkingDirectory, ExecStart, config path)
# Use your preferred text editor

# Reload systemd
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable challengectl-runner
sudo systemctl start challengectl-runner

# Check status
sudo systemctl status challengectl-runner
sudo journalctl -u challengectl-runner -f
```

## Nginx Setup

Nginx serves the frontend and proxies API/WebSocket requests to the backend server.

### Install Nginx

```bash
sudo apt-get install nginx
```

### Get TLS Certificates

You'll need TLS certificates for HTTPS. Options include:

**Let's Encrypt (acme.sh or certbot):**
```bash
# Using certbot
sudo apt-get install certbot python3-certbot-nginx
sudo certbot certonly --nginx -d challengectl.example.com

# Certificates will be in /etc/letsencrypt/live/challengectl.example.com/
```

**FreeIPA:**
- Request a certificate from your FreeIPA server
- Copy cert and key to your nginx configuration directory

**Self-signed (development/testing only):**
```bash
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/ssl/private/challengectl.key \
    -out /etc/ssl/certs/challengectl.crt
```

### Configure Nginx

```bash
# Copy example config
sudo cp docs/nginx-challengectl.conf /etc/nginx/sites-available/challengectl

# Edit configuration (update server_name, ssl_certificate paths, root path, proxy_pass URL)
# Use your preferred text editor

# Enable site
sudo ln -s /etc/nginx/sites-available/challengectl /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

### Firewall

```bash
# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable
```

## Configuration

### Server Configuration

Key settings in `server-config.yml`:

```yaml
server:
  bind: "0.0.0.0"
  port: 8443

  # API keys for authentication
  api_keys:
    runner-1: "unique-key-for-runner-1"
    runner-2: "unique-key-for-runner-2"
    admin: "unique-admin-key"

conference:
  name: "Your CTF Name"
  start: "2025-01-01 09:00:00 -5"
  stop: "2025-01-03 18:00:00 -5"

challenges:
  - default_min_delay: 60
    default_max_delay: 90

  - name: EXAMPLE_CHALLENGE
    frequency: 146550000
    modulation: nbfm
    flag: challenges/example.wav
    enabled: true
```

### Runner Configuration

Key settings in `runner-config.yml`:

```yaml
runner:
  runner_id: "runner-1"
  server_url: "https://challengectl.example.com:8443"
  api_key: "unique-key-for-runner-1"

  verify_ssl: true
  cache_dir: "cache"

radios:
  models:
    - model: hackrf
      rf_gain: 14
      if_gain: 32

  devices:
    - name: 0
      model: hackrf
      frequency_limits:
        - "144000000-148000000"
        - "420000000-450000000"
```

## Public Dashboard

The public dashboard shows challenge status without authentication.

**Access:**
- URL: `https://challengectl.example.com/public`
- No login required
- Auto-refreshes every 30 seconds

**Configure Visibility:**

Each challenge can control what information is shown publicly:

```yaml
challenges:
  - name: EXAMPLE_CHALLENGE
    # ... other settings ...
    public_view:
      show_frequency: true       # Show frequency (default: true)
      show_last_tx_time: false   # Show last TX time (default: false)
      show_active_status: true   # Show active status (default: true)
```

**Kiosk Mode:**

```bash
chromium-browser --kiosk --disable-infobars https://challengectl.example.com/public
```

## Logging

All components write logs to local files with automatic rotation:

**Server:** `challengectl.server.log`
- Rotated on restart: `challengectl.server.YYYYMMDD_HHMMSS.log`

**Runner:** `challengectl.runner.log`
- Rotated on restart: `challengectl.runner.YYYYMMDD_HHMMSS.log`

**View Logs:**

```bash
# Real-time
tail -f challengectl.server.log
tail -f challengectl.runner.log

# With systemd
sudo journalctl -u challengectl-server -f
sudo journalctl -u challengectl-runner -f
```

**Log Levels:**

```bash
# Server
python3 server.py --log-level DEBUG
python3 server.py --log-level INFO    # Default

# Runner
python3 runner.py --log-level DEBUG
```

**Cleanup:**

```bash
# Remove old logs (older than 30 days)
find . -name "challengectl.*.log" -mtime +30 -delete
```

## Troubleshooting

### Server Issues

```bash
# Check if server is running
ps aux | grep server.py

# Check logs
tail -n 100 challengectl.server.log

# Check database
sqlite3 challengectl.db "SELECT * FROM runners;"

# Test API
curl http://localhost:8443/api/health
```

### Runner Issues

```bash
# Check if runner is connected
tail -n 50 challengectl.runner.log

# Test SDR device
hackrf_info
bladeRF-cli -p
uhd_find_devices

# Check USB permissions
lsusb
ls -la /dev/bus/usb/
```

### Nginx Issues

```bash
# Test configuration
sudo nginx -t

# Check logs
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log

# Verify backend is running
curl http://localhost:8443/api/health
```

### Frontend Issues

```bash
# Rebuild frontend
cd frontend
npm run build

# Check nginx is serving files
ls -la frontend/dist/

# Verify nginx configuration
sudo nginx -t
```

## Performance

### Database

```bash
# Optimize database periodically
sqlite3 challengectl.db "VACUUM; ANALYZE;"
```

### Nginx

Add to nginx http block:

```nginx
worker_processes auto;
worker_connections 4096;
client_max_body_size 100M;
```

## Security Checklist

- [ ] All API keys changed from defaults
- [ ] TLS enabled with valid certificate
- [ ] Firewall configured
- [ ] Regular backups configured
- [ ] System updates applied
- [ ] Unused ports closed

## Support

For issues:
1. Check logs
2. Verify configuration
3. Test connectivity
4. Review [DISTRIBUTED_ARCHITECTURE.md](DISTRIBUTED_ARCHITECTURE.md)
5. Open GitHub issue with logs
