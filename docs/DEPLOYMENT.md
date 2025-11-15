# ChallengeCtl Deployment Guide

This guide covers deploying the distributed challengectl system for production use.

## Quick Reference

**Configuration Files:**
- `server-config.yml` - Server configuration
- `runner-config.yml` - Runner configuration (one per runner)
- `.env.local` - Frontend environment (for development)

**Service Files:**
- `challengectl-server.service` - Systemd service for server
- `challengectl-runner.service` - Systemd service for runner

**Nginx:**
- `nginx-challengectl.conf` - Reverse proxy with TLS

## Server Deployment

### 1. System Setup

```bash
# Create user
sudo useradd -r -s /bin/false challengectl

# Create directories
sudo mkdir -p /opt/challengectl/{server,runner,frontend}
sudo mkdir -p /var/lib/challengectl/{files,cache}
sudo mkdir -p /var/log/challengectl
sudo mkdir -p /etc/challengectl

# Set permissions
sudo chown -R challengectl:challengectl /opt/challengectl
sudo chown -R challengectl:challengectl /var/lib/challengectl
sudo chown -R challengectl:challengectl /var/log/challengectl
```

### 2. Install Dependencies

```bash
# System packages
sudo apt-get update
sudo apt-get install -y python3 python3-pip nginx certbot python3-certbot-nginx

# Python dependencies for server
pip3 install -r requirements-server.txt
```

### 3. Deploy Server Files

```bash
# Copy server files
sudo cp -r server/* /opt/challengectl/server/
sudo cp server-config.example.yml /etc/challengectl/server-config.yml

# Edit configuration
sudo nano /etc/challengectl/server-config.yml
# Change all API keys!
# Configure challenges
# Set conference details
```

### 4. Install Systemd Service

```bash
# Copy service file
sudo cp docs/challengectl-server.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable challengectl-server
sudo systemctl start challengectl-server

# Check status
sudo systemctl status challengectl-server
sudo journalctl -u challengectl-server -f
```

### 5. Setup TLS with Let's Encrypt

```bash
# Get certificate
sudo certbot certonly --nginx -d challengectl.example.com

# Copy nginx config
sudo cp docs/nginx-challengectl.conf /etc/nginx/sites-available/challengectl

# Edit config to match your domain
sudo nano /etc/nginx/sites-available/challengectl

# Enable site
sudo ln -s /etc/nginx/sites-available/challengectl /etc/nginx/sites-enabled/

# Test config
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

### 6. Firewall Configuration

```bash
# Allow HTTP, HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Optional: Allow direct access to server (for runners on internal network)
sudo ufw allow from 192.168.1.0/24 to any port 8443

# Enable firewall
sudo ufw enable
```

## Runner Deployment

### 1. System Setup

```bash
# Create user and add to plugdev group (for USB devices)
sudo useradd -r -s /bin/false -G plugdev challengectl

# Create directories
sudo mkdir -p /opt/challengectl/runner
sudo mkdir -p /var/cache/challengectl
sudo mkdir -p /etc/challengectl

# Set permissions
sudo chown -R challengectl:plugdev /opt/challengectl/runner
sudo chown -R challengectl:plugdev /var/cache/challengectl
```

### 2. Install Dependencies

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

### 3. Deploy Runner Files

```bash
# Copy runner files
sudo cp -r runner/* /opt/challengectl/runner/
sudo cp runner-config.example.yml /etc/challengectl/runner-config.yml

# Edit configuration
sudo nano /etc/challengectl/runner-config.yml
# Set unique runner_id
# Set server_url
# Set api_key (must match server)
# Configure SDR devices
# Set ca_cert if using custom CA
```

### 4. Install Systemd Service

```bash
# Copy service file
sudo cp docs/challengectl-runner.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable challengectl-runner
sudo systemctl start challengectl-runner

# Check status
sudo systemctl status challengectl-runner
sudo journalctl -u challengectl-runner -f
```

### 5. Test SDR Access

```bash
# Test as challengectl user
sudo -u challengectl hackrf_info
sudo -u challengectl bladeRF-cli -p
sudo -u challengectl uhd_find_devices

# If permission denied, add udev rules
sudo nano /etc/udev/rules.d/52-challengectl.rules

# Add for HackRF:
# SUBSYSTEM=="usb", ATTRS{idVendor}=="1d50", ATTRS{idProduct}=="6089", GROUP="plugdev", MODE="0660"

# Reload udev
sudo udevadm control --reload-rules
sudo udevadm trigger
```

## Frontend Deployment

### Option 1: Build and Serve via Nginx (Recommended)

```bash
# Install Node.js
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Build frontend
cd frontend
npm install
npm run build

# Copy to server static directory
sudo cp -r dist/* /opt/challengectl/frontend/dist/

# Nginx will serve these files automatically
```

### Option 2: Development Mode (Not for Production)

```bash
cd frontend
npm install

# Create .env.local
cp .env.example .env.local
nano .env.local
# Set VITE_API_KEY to match server admin key

# Run dev server
npm run dev
# Access at http://localhost:3000
```

## TLS/SSL Configuration

You have two options for enabling TLS:

1. **Direct Server TLS** - Server runs with HTTPS directly (good for small deployments, testing)
2. **Nginx Reverse Proxy** - Recommended for production (better performance, features)

### Option 1: Direct Server TLS

The server can run with TLS directly without nginx.

#### Self-Signed Certificates (Development/Testing)

```bash
# Generate self-signed certificate
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/challengectl/server.key \
    -out /etc/challengectl/server.crt \
    -subj "/CN=challengectl.local"

# Update server-config.yml
sudo nano /etc/challengectl/server-config.yml

# Add TLS configuration:
# server:
#   tls:
#     cert: "/etc/challengectl/server.crt"
#     key: "/etc/challengectl/server.key"

# Restart server
sudo systemctl restart challengectl-server

# Server now runs on https://
```

#### Let's Encrypt Certificates (Production)

```bash
# Install certbot (standalone mode, not nginx)
sudo apt-get install certbot

# Stop server temporarily
sudo systemctl stop challengectl-server

# Get certificate (certbot will bind to port 80)
sudo certbot certonly --standalone -d challengectl.example.com

# Certificates will be in /etc/letsencrypt/live/challengectl.example.com/

# Update server-config.yml
sudo nano /etc/challengectl/server-config.yml

# Add TLS configuration:
# server:
#   tls:
#     cert: "/etc/letsencrypt/live/challengectl.example.com/fullchain.pem"
#     key: "/etc/letsencrypt/live/challengectl.example.com/privkey.pem"

# Give challengectl user read access to certificates
sudo setfacl -R -m u:challengectl:rX /etc/letsencrypt/live
sudo setfacl -R -m u:challengectl:rX /etc/letsencrypt/archive

# Restart server
sudo systemctl start challengectl-server

# Auto-renewal: Create renewal hook
sudo nano /etc/letsencrypt/renewal-hooks/post/challengectl-restart.sh

#!/bin/bash
systemctl restart challengectl-server

sudo chmod +x /etc/letsencrypt/renewal-hooks/post/challengectl-restart.sh

# Test renewal:
sudo certbot renew --dry-run
```

#### Command Line TLS Options

You can also specify certificates via command line:

```bash
# Run with TLS
python3 server/server.py \
    --ssl-cert /etc/challengectl/server.crt \
    --ssl-key /etc/challengectl/server.key
```

### Option 2: Nginx Reverse Proxy (Recommended for Production)

For production deployments with higher load or advanced features (load balancing, caching, etc.):

#### Using Let's Encrypt with Nginx

```bash
# Install certbot with nginx plugin
sudo apt-get install certbot python3-certbot-nginx

# Get certificate (certbot will auto-configure nginx)
sudo certbot --nginx -d challengectl.example.com

# Auto-renewal is set up automatically
# Test renewal:
sudo certbot renew --dry-run
```

#### Manual Nginx TLS Configuration

```bash
# Generate self-signed cert (for testing)
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/challengectl.key \
    -out /etc/nginx/ssl/challengectl.crt \
    -subj "/CN=challengectl.local"

# Update nginx config to use these certificates
# See docs/nginx-challengectl.conf for example
```

### Custom CA Certificate (For Runners)

If using custom CA for internal network:

```bash
# On each runner:
# 1. Copy CA certificate
sudo cp ca.crt /etc/challengectl/ca.crt

# 2. Update runner-config.yml:
sudo nano /etc/challengectl/runner-config.yml

# runner:
#   ca_cert: "/etc/challengectl/ca.crt"
#   verify_ssl: true

# 3. Restart runner
sudo systemctl restart challengectl-runner
```

### TLS Troubleshooting

**Server won't start with TLS:**
```bash
# Check certificate files exist and are readable
ls -la /etc/challengectl/server.{crt,key}
sudo -u challengectl cat /etc/challengectl/server.crt

# Check logs
sudo journalctl -u challengectl-server -n 50
```

**Runner can't connect:**
```bash
# Test TLS connection
openssl s_client -connect server-ip:8443 -showcerts

# If using custom CA, verify CA cert is accessible
sudo -u challengectl cat /etc/challengectl/ca.crt

# For development, can disable SSL verification:
# runner:
#   verify_ssl: false  # DEVELOPMENT ONLY!
```

## Monitoring

### System Logs

```bash
# Server logs
sudo journalctl -u challengectl-server -f

# Runner logs
sudo journalctl -u challengectl-runner -f

# Nginx logs
sudo tail -f /var/log/nginx/challengectl-access.log
sudo tail -f /var/log/nginx/challengectl-error.log
```

### Health Checks

```bash
# Server health
curl https://challengectl.example.com/api/health

# Database status
sudo -u challengectl sqlite3 /var/lib/challengectl/challengectl.db "SELECT COUNT(*) FROM runners;"
```

### Resource Monitoring

```bash
# System resources
htop

# Service status
systemctl status challengectl-server
systemctl status challengectl-runner

# Disk usage
df -h /var/lib/challengectl
du -sh /var/lib/challengectl/*
```

## Backup and Recovery

### Database Backup

```bash
# Backup script
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
sudo -u challengectl sqlite3 /var/lib/challengectl/challengectl.db \
    ".backup /var/backups/challengectl/challengectl_${DATE}.db"

# Retention (keep last 7 days)
find /var/backups/challengectl/ -name "*.db" -mtime +7 -delete
```

### Configuration Backup

```bash
# Backup configs
sudo tar czf /var/backups/challengectl/config_${DATE}.tar.gz \
    /etc/challengectl/ \
    /opt/challengectl/server/server-config.yml
```

### Restore

```bash
# Restore database
sudo systemctl stop challengectl-server
sudo -u challengectl cp /var/backups/challengectl/challengectl_YYYYMMDD.db \
    /var/lib/challengectl/challengectl.db
sudo systemctl start challengectl-server
```

## Troubleshooting

### Server Won't Start

```bash
# Check logs
sudo journalctl -u challengectl-server -n 50

# Common issues:
# - Port 8443 already in use: lsof -i :8443
# - Database permission: ls -la /var/lib/challengectl/
# - Missing config: ls -la /etc/challengectl/
```

### Runner Won't Connect

```bash
# Check logs
sudo journalctl -u challengectl-runner -n 50

# Test connectivity
curl -k https://server-ip:8443/api/health

# Check API key
grep api_key /etc/challengectl/runner-config.yml

# Test SSL
openssl s_client -connect server-ip:8443
```

### WebUI Not Loading

```bash
# Check nginx
sudo nginx -t
sudo systemctl status nginx

# Check frontend build
ls -la /opt/challengectl/frontend/dist/

# Check nginx logs
sudo tail -f /var/log/nginx/challengectl-error.log
```

### SDR Device Access Issues

```bash
# Check USB permissions
lsusb
ls -la /dev/bus/usb/

# Check udev rules
ls -la /etc/udev/rules.d/

# Test as correct user
sudo -u challengectl hackrf_info
```

## Security Checklist

- [ ] All API keys changed from defaults
- [ ] TLS enabled with valid certificate
- [ ] Firewall configured
- [ ] Services running as non-root user
- [ ] Regular backups configured
- [ ] Log rotation enabled
- [ ] System updates applied
- [ ] Unused ports closed
- [ ] Strong passwords for system accounts

## Performance Tuning

### Database Optimization

```sql
-- Run periodically
VACUUM;
ANALYZE;
```

### Nginx Tuning

```nginx
# Add to http block in /etc/nginx/nginx.conf
worker_processes auto;
worker_connections 4096;
client_max_body_size 100M;
```

### File Cleanup

```bash
# Clean old logs (older than 30 days)
find /var/log/challengectl/ -name "*.log" -mtime +30 -delete

# Clean runner cache (if needed)
# Be careful - this removes downloaded challenge files
sudo -u challengectl rm -rf /var/cache/challengectl/*
```

## Scaling Considerations

For >10 runners, consider:
- **PostgreSQL** instead of SQLite
- **Redis** for caching and locking
- **Load balancer** for multiple server instances
- **CDN/Object Storage** (S3) for challenge files
- **Prometheus + Grafana** for metrics
- **ELK Stack** for log aggregation

## Support

For issues:
1. Check logs (`journalctl -u challengectl-*`)
2. Verify configuration
3. Test connectivity
4. Review [DISTRIBUTED_ARCHITECTURE.md](DISTRIBUTED_ARCHITECTURE.md)
5. Open GitHub issue with logs
