# Troubleshooting Guide

This guide covers common issues you might encounter when running ChallengeCtl and provides solutions to resolve them.

## Table of Contents

- [Server Issues](#server-issues)
- [Runner Issues](#runner-issues)
- [Challenge Transmission Issues](#challenge-transmission-issues)
- [Authentication Issues](#authentication-issues)
- [Network and Connectivity Issues](#network-and-connectivity-issues)
- [Database Issues](#database-issues)
- [SDR Hardware Issues](#sdr-hardware-issues)
- [Performance Issues](#performance-issues)
- [Debugging Tips](#debugging-tips)

## Server Issues

### Server Won't Start

**Symptoms**: Server exits immediately or fails to start with an error.

**Possible Causes and Solutions**:

1. **Port already in use**
   ```
   Error: Address already in use
   ```
   **Solution**: Check if another process is using port 8443:
   ```bash
   sudo lsof -i :8443
   sudo netstat -tlnp | grep 8443
   ```
   Either stop the conflicting process or change the server port:
   ```yaml
   server:
     port: 8444
   ```

2. **Configuration file not found**
   ```
   Error: Could not find server-config.yml
   ```
   **Solution**: Ensure the configuration file exists or specify its location:
   ```bash
   export CONFIG_PATH=/path/to/server-config.yml
   python -m server.server
   ```

3. **Invalid YAML syntax**
   ```
   Error: YAML parse error
   ```
   **Solution**: Validate your YAML file:
   ```bash
   python -c "import yaml; yaml.safe_load(open('server-config.yml'))"
   ```
   Use a YAML linter or validator to check syntax.

4. **Database initialization failed**
   ```
   Error: Could not open database
   ```
   **Solution**: Ensure the database directory exists and has write permissions:
   ```bash
   mkdir -p /var/lib/challengectl
   chmod 755 /var/lib/challengectl
   python -m server.database init
   ```

5. **Missing Python dependencies**
   ```
   ModuleNotFoundError: No module named 'flask'
   ```
   **Solution**: Install required dependencies:
   ```bash
   pip install -r requirements-server.txt
   ```

### Server Crashes or Becomes Unresponsive

**Symptoms**: Server stops responding, crashes periodically, or consumes excessive resources.

**Possible Causes and Solutions**:

1. **Database lock timeout**
   ```
   Error: database is locked
   ```
   **Solution**: Increase the database timeout or reduce concurrent operations. Check for long-running queries:
   ```bash
   sqlite3 challengectl.db "PRAGMA busy_timeout = 10000;"
   ```

2. **Too many runners polling**
   **Solution**: Increase runner poll intervals to reduce load:
   ```yaml
   runner:
     poll_interval: 15  # Increase from 5 to 15 seconds
   ```

3. **Memory exhaustion**
   **Solution**: Monitor memory usage and check for memory leaks:
   ```bash
   top -p $(pgrep -f "server.server")
   ```
   Consider adding memory limits in systemd:
   ```ini
   [Service]
   MemoryLimit=1G
   ```

4. **Log buffer overflow**
   **Solution**: Reduce log retention or implement log rotation:
   ```bash
   journalctl --vacuum-time=7d  # Keep only 7 days of logs
   ```

### Web Interface Not Loading

**Symptoms**: Cannot access web interface, blank page, or 404 errors.

**Possible Causes and Solutions**:

1. **Frontend not built**
   **Solution**: Build the Vue.js frontend:
   ```bash
   cd frontend
   npm install
   npm run build
   ```

2. **CORS errors in browser console**
   ```
   CORS policy: No 'Access-Control-Allow-Origin' header
   ```
   **Solution**: Add your domain to CORS origins:
   ```yaml
   server:
     cors_origins:
       - "http://localhost:5173"
       - "https://your-domain.com"
   ```

3. **Reverse proxy misconfiguration**
   **Solution**: Ensure nginx/Apache is configured to proxy WebSocket connections:
   ```nginx
   location / {
       proxy_http_version 1.1;
       proxy_set_header Upgrade $http_upgrade;
       proxy_set_header Connection "upgrade";
   }
   ```

## Runner Issues

### GNU Radio Module Import Errors

**Symptoms**: ImportError when runner tries to import GNU Radio modules.

**Possible Causes and Solutions**:

1. **gr-paint or gr-mixalot not installed**
   ```
   ModuleNotFoundError: No module named 'paint'
   ModuleNotFoundError: No module named 'mixalot'
   ```
   **Solution**: Compile and install the missing modules:
   ```bash
   # Install gr-paint
   cd /tmp
   git clone https://github.com/drmpeg/gr-paint.git
   cd gr-paint
   mkdir build && cd build
   cmake ..
   make
   sudo make install
   sudo ldconfig

   # Install gr-mixalot
   cd /tmp
   git clone https://github.com/unsynchronized/gr-mixalot.git
   cd gr-mixalot
   mkdir build && cd build
   cmake ..
   make
   sudo make install
   sudo ldconfig
   ```

2. **Virtual environment without system packages**
   ```
   ModuleNotFoundError: No module named 'gnuradio'
   ```
   **Solution**: Recreate the virtual environment with `--system-site-packages`:
   ```bash
   deactivate  # Exit current venv
   rm -rf venv
   python3 -m venv --system-site-packages venv
   source venv/bin/activate
   pip install -r requirements-runner.txt
   ```

3. **GNU Radio not in Python path**
   **Solution**: Verify GNU Radio installation:
   ```bash
   python3 -c "from gnuradio import gr; print(gr.version())"
   ```
   If this fails, reinstall GNU Radio:
   ```bash
   sudo apt-get install --reinstall gnuradio
   ```

4. **Library cache not updated**
   **Solution**: Update the library cache after installing GNU Radio modules:
   ```bash
   sudo ldconfig
   ```

### Runner Won't Connect to Server

**Symptoms**: Runner fails to register or connect to server.

**Possible Causes and Solutions**:

1. **Server unreachable**
   **Solution**: Test connectivity:
   ```bash
   curl http://server-ip:8443/api/health
   ping server-ip
   ```

2. **Invalid API key or enrollment issue**
   ```
   Error: 401 Unauthorized
   ```
   **Solution**: Check the enrollment status:
   - If first-time setup: Ensure both `enrollment_token` and `api_key` are in runner config
   - If already enrolled: Remove `enrollment_token` from config, keep only `api_key`
   - Verify the API key in the Web UI Runners page
   - Check server logs for authentication errors:
   ```bash
   journalctl -u challengectl | grep -i "runner-1"
   ```

3. **SSL verification failure**
   ```
   Error: SSL certificate verify failed
   ```
   **Solution**: For self-signed certificates in development:
   ```yaml
   runner:
     verify_ssl: false  # Development only!
   ```
   For production, use valid certificates or specify CA certificate:
   ```yaml
   runner:
     ca_cert: "/etc/ssl/certs/ca-bundle.crt"
   ```

4. **Firewall blocking connection**
   **Solution**: Check firewall rules:
   ```bash
   sudo iptables -L -n | grep 8443
   sudo ufw status
   ```
   Allow the port if needed:
   ```bash
   sudo ufw allow 8443/tcp
   ```

### Runner Keeps Disconnecting

**Symptoms**: Runner shows as offline intermittently, frequent reconnections.

**Possible Causes and Solutions**:

1. **Network instability**
   **Solution**: Check for packet loss:
   ```bash
   ping -c 100 server-ip
   mtr server-ip
   ```
   Increase heartbeat timeout on server:
   ```yaml
   server:
     heartbeat_timeout: 120  # Increase from 90 to 120 seconds
   ```

2. **Runner process suspended**
   **Solution**: Check system logs for suspensions:
   ```bash
   journalctl -u challengectl-runner | grep -i suspend
   ```
   Disable power management if on a laptop.

3. **Clock skew**
   **Solution**: Synchronize system clocks:
   ```bash
   sudo ntpdate pool.ntp.org
   sudo systemctl restart systemd-timesyncd
   ```

### Runner Not Receiving Tasks

**Symptoms**: Runner is online but never gets assigned challenges.

**Possible Causes and Solutions**:

1. **Frequency mismatch**
   **Solution**: Verify runner frequency limits include challenge frequencies:
   ```yaml
   # Runner config
   frequency_limits:
     - "144000000-148000000"  # Must include 146.55 MHz

   # Server config
   challenges:
     - frequency: 146550000  # 146.55 MHz
   ```

2. **No challenges enabled**
   **Solution**: Check challenge status:
   ```bash
   curl http://server-ip:8443/api/challenges
   ```
   Enable challenges in server configuration:
   ```yaml
   challenges:
     - enabled: true
   ```

3. **Challenges not queued**
   **Solution**: Manually trigger a challenge from the web interface or API:
   ```bash
   curl -X POST http://server-ip:8443/api/challenges/1/trigger \
     -H "Cookie: session=..."
   ```

4. **Other runners taking all tasks**
   **Solution**: Check runner priorities or add more challenges.

## Challenge Transmission Issues

### Transmissions Failing

**Symptoms**: Tasks assigned but transmissions fail with errors.

**Possible Causes and Solutions**:

1. **SDR device not found**
   ```
   Error: Device not found
   ```
   **Solution**: Verify device is connected:
   ```bash
   hackrf_info  # For HackRF
   LimeUtil --find  # For LimeSDR
   lsusb  # Check USB devices
   ```

2. **File download failed**
   ```
   Error: Could not download file
   ```
   **Solution**: Check file exists on server and hash is correct:
   ```bash
   # On server
   ls -la files/
   sha256sum files/challenge.wav
   ```

3. **Invalid modulation parameters**
   ```
   Error: Invalid parameter for modulation type
   ```
   **Solution**: Review challenge configuration against modulation requirements. See [Configuration Reference](Configuration-Reference#modulation-specific-parameters).

4. **GNU Radio error**
   ```
   Error: gr::log
   ```
   **Solution**: Check GNU Radio installation:
   ```bash
   gnuradio-config-info --version
   gnuradio-companion --version
   ```
   Reinstall if necessary:
   ```bash
   sudo apt install gnuradio gr-osmosdr
   ```

### No RF Output

**Symptoms**: Transmission completes successfully but no signal detected.

**Possible Causes and Solutions**:

1. **Antenna not connected**
   **Solution**: Connect an appropriate antenna for the frequency.

2. **Gain too low**
   **Solution**: Increase RF gain in runner configuration:
   ```yaml
   radios:
     devices:
       - rf_gain: 40  # Increase gain
   ```

3. **Wrong frequency**
   **Solution**: Verify challenge frequency and device tuning:
   ```bash
   # Monitor with SDR receiver on expected frequency
   ```

4. **Device not transmitting**
   **Solution**: Test device with manufacturer tools:
   ```bash
   hackrf_transfer -t /dev/zero -f 146000000 -s 2000000 -a 1 -x 20
   ```

### Signal Quality Issues

**Symptoms**: Signal transmitted but garbled, weak, or distorted.

**Possible Causes and Solutions**:

1. **Sample rate mismatch**
   **Solution**: Ensure WAV file sample rate matches configuration:
   ```yaml
   wav_samplerate: 48000  # Must match actual file
   ```
   Check file properties:
   ```bash
   soxi challenge.wav
   ```

2. **Gain too high (clipping)**
   **Solution**: Reduce RF gain to prevent distortion:
   ```yaml
   radios:
     devices:
       - rf_gain: 20  # Reduce from higher value
   ```

3. **Frequency offset**
   **Solution**: Calibrate PPM correction:
   ```yaml
   radios:
     devices:
       - ppm: -5  # Adjust based on your device
   ```

4. **Interference**
   **Solution**: Check for nearby transmitters, change frequency, or add filtering.

## Authentication Issues

### Cannot Log In to Web Interface

**Symptoms**: Login fails, incorrect credentials error.

**Possible Causes and Solutions**:

1. **First-time setup not completed**
   **Solution**: Check server logs for the temporary admin password:
   ```bash
   # If running in terminal, check the output
   # Or check log file:
   cat challengectl.server.log | grep "DEFAULT ADMIN USER"
   ```
   Use the credentials shown to log in and complete the initial setup wizard.

2. **Wrong username or password**
   **Solution**: If you have another admin account, log in with that account and reset the password through the Users page in the web interface. If you're completely locked out, you'll need to access the database directly:
   ```bash
   # Connect to the database
   sqlite3 challengectl.db
   # Delete the locked account
   DELETE FROM users WHERE username='your-username';
   # Exit
   .quit
   # Restart server - it will create a new default admin account
   ```

3. **TOTP code invalid**
   **Solution**: Ensure authenticator app time is synchronized:
   - Check device clock is accurate
   - Resync authenticator app
   - If another admin account exists: Use it to reset TOTP via Users page
   - If completely locked out: Access database directly:
   ```bash
   sqlite3 challengectl.db
   # Reset TOTP for a user
   UPDATE users SET totp_secret=NULL WHERE username='your-username';
   .quit
   # Log in - you'll be prompted to set up TOTP again
   ```

4. **Session expired**
   **Solution**: Log out and log in again. Sessions expire after 24 hours.

5. **Rate limit exceeded**
   ```
   Error: 429 Too Many Requests
   ```
   **Solution**: Wait 15 minutes before trying again. Maximum 5 login attempts per 15 minutes.

### Runner Authentication Fails

**Symptoms**: Runner cannot authenticate, 401 Unauthorized.

**Possible Causes and Solutions**:

1. **Enrollment not completed**
   **Solution**: Complete the enrollment process:
   ```bash
   # 1. In Web UI: Runners page → Add Runner → Generate credentials
   # 2. Add both enrollment_token and api_key to runner-config.yml
   # 3. Start runner (it will auto-enroll)
   # 4. Remove enrollment_token from config
   # 5. Restart runner
   ```

2. **API key mismatch**
   **Solution**: Regenerate enrollment credentials via Web UI:
   - Go to Runners page
   - Click "Add Runner"
   - Generate new enrollment token and API key
   - Update runner config with new credentials

3. **Host validation failure**
   **Solution**: If you moved the runner to a different machine:
   - The API key is tied to the original host
   - Wait 2 minutes for the old runner to go offline
   - Then start on new host, or
   - Generate new enrollment credentials for the new host

4. **Case sensitivity**
   **Solution**: Ensure runner_id matches exactly (case-sensitive):
   ```yaml
   runner:
     runner_id: "runner-1"  # Must match the name used during enrollment
   ```

## Network and Connectivity Issues

### Slow Response Times

**Symptoms**: API requests take long time, web interface sluggish.

**Possible Causes and Solutions**:

1. **Database performance**
   **Solution**: Compact and optimize database:
   ```bash
   sqlite3 challengectl.db "VACUUM;"
   sqlite3 challengectl.db "ANALYZE;"
   ```

2. **Too many log entries**
   **Solution**: Clear old transmission logs:
   ```bash
   sqlite3 challengectl.db "DELETE FROM transmission_log WHERE timestamp < datetime('now', '-30 days');"
   ```

3. **Network latency**
   **Solution**: Check network latency:
   ```bash
   ping -c 10 server-ip
   traceroute server-ip
   ```

### WebSocket Connection Fails

**Symptoms**: Real-time updates not working, dashboard not auto-refreshing.

**Possible Causes and Solutions**:

1. **Reverse proxy not forwarding WebSocket**
   **Solution**: Update nginx configuration:
   ```nginx
   location / {
       proxy_http_version 1.1;
       proxy_set_header Upgrade $http_upgrade;
       proxy_set_header Connection "upgrade";
       proxy_set_header Host $host;
   }
   ```

2. **Firewall blocking WebSocket**
   **Solution**: Ensure WebSocket traffic is allowed through firewall.

3. **Browser blocking mixed content**
   **Solution**: Use HTTPS for both server and WebSocket if accessing over HTTPS.

## Database Issues

### Database Locked Error

**Symptoms**: "Database is locked" errors in logs.

**Possible Causes and Solutions**:

1. **High concurrency**
   **Solution**: Increase busy timeout:
   ```python
   # In database.py, increase timeout
   conn.execute("PRAGMA busy_timeout = 10000")
   ```

2. **Stale lock**
   **Solution**: Restart server to release locks.

3. **Consider PostgreSQL**
   **Solution**: For deployments with many runners, migrate to PostgreSQL for better concurrent write performance.

### Database Corruption

**Symptoms**: "Database disk image is malformed" error.

**Possible Causes and Solutions**:

1. **Restore from backup**
   **Solution**: Restore from your backup:
   ```bash
   cp /var/backups/challengectl/challengectl-20240115.db challengectl.db
   ```

2. **Attempt repair**
   **Solution**: Try SQLite's integrity check and dump/restore:
   ```bash
   sqlite3 challengectl.db "PRAGMA integrity_check;"
   sqlite3 challengectl.db ".dump" > backup.sql
   sqlite3 challengectl-new.db < backup.sql
   mv challengectl.db challengectl-corrupted.db
   mv challengectl-new.db challengectl.db
   ```

## SDR Hardware Issues

### Device Permission Denied

**Symptoms**: "Permission denied" when accessing SDR device.

**Possible Causes and Solutions**:

1. **Udev rules not set**
   **Solution**: Create udev rules:
   ```bash
   sudo nano /etc/udev/rules.d/52-sdr.rules
   ```
   Add:
   ```
   SUBSYSTEM=="usb", ATTR{idVendor}=="1d50", ATTR{idProduct}=="6089", MODE="0666"
   ```
   Reload:
   ```bash
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   ```

2. **User not in plugdev group**
   **Solution**: Add user to group:
   ```bash
   sudo usermod -a -G plugdev $USER
   # Log out and back in
   ```

### Device Not Recognized

**Symptoms**: lsusb shows device but software can't find it.

**Possible Causes and Solutions**:

1. **Driver not loaded**
   **Solution**: Check and load kernel modules:
   ```bash
   lsmod | grep hackrf
   sudo modprobe hackrf
   ```

2. **USB port issue**
   **Solution**: Try different USB port, preferably USB 3.0 for better bandwidth.

3. **Firmware issue**
   **Solution**: Update device firmware:
   ```bash
   # HackRF
   hackrf_spiflash -w hackrf_one_usb.bin

   # LimeSDR
   LimeUtil --update
   ```

## Performance Issues

### High CPU Usage

**Symptoms**: Server or runner consuming excessive CPU.

**Possible Causes and Solutions**:

1. **Too frequent polling**
   **Solution**: Increase poll interval:
   ```yaml
   runner:
     poll_interval: 15  # Increase from 5
   ```

2. **Complex signal generation**
   **Solution**: Optimize GNU Radio flowgraphs, reduce sample rates if possible.

3. **Debug logging enabled**
   **Solution**: Reduce log level:
   ```yaml
   runner:
     log_level: "INFO"  # Change from DEBUG
   ```

### High Memory Usage

**Symptoms**: Process using excessive RAM.

**Possible Causes and Solutions**:

1. **Large log buffer**
   **Solution**: Limit log buffer size in server configuration.

2. **Memory leak**
   **Solution**: Restart service periodically using systemd:
   ```ini
   [Service]
   RuntimeMaxSec=86400  # Restart after 24 hours
   ```

3. **Large file caching**
   **Solution**: Clear runner cache:
   ```bash
   rm -rf cache/*
   ```

## Debugging Tips

### Enable Debug Logging

**Server**:
```bash
# Set log level in code or via environment
export LOG_LEVEL=DEBUG
python -m server.server
```

**Runner**:
```yaml
runner:
  log_level: "DEBUG"
```

### Monitor Real-Time Logs

```bash
# Server (systemd)
sudo journalctl -u challengectl -f

# Server (direct)
tail -f server.log

# Runner
tail -f runner.log
```

### Check System Resources

```bash
# CPU and memory
top
htop

# Disk space
df -h

# Network connections
netstat -an | grep 8443
ss -tulpn | grep 8443

# Process details
ps aux | grep challengectl
```

### Database Inspection

```bash
# Connect to database
sqlite3 challengectl.db

# Useful queries
.tables
SELECT * FROM runners;
SELECT * FROM challenges;
SELECT * FROM assignments;
SELECT * FROM transmission_log ORDER BY timestamp DESC LIMIT 10;
```

### Network Debugging

```bash
# Test server connectivity
curl -v http://server-ip:8443/api/health

# Test runner authentication
curl -v -H "X-API-Key: your-key" http://server-ip:8443/api/runners/runner-1/task

# Monitor network traffic
sudo tcpdump -i any port 8443
```

### Validate Configuration Files

```bash
# YAML syntax check
python -c "import yaml; print(yaml.safe_load(open('config.yml')))"

# JSON syntax check
python -c "import json; print(json.load(open('data.json')))"
```

## Getting Help

If you've tried the above solutions and still experience issues:

1. **Check the logs**: Server and runner logs often contain detailed error messages
2. **Search existing issues**: [GitHub Issues](https://github.com/ckoval7/challengectl/issues)
3. **Create a new issue**: Include:
   - ChallengeCtl version
   - Operating system and version
   - Complete error messages
   - Configuration files (redact sensitive info)
   - Steps to reproduce
4. **Join discussions**: Community forums or chat channels (if available)

## Next Steps

- [Review the Architecture](Architecture) to understand system internals
- [Read the Server Setup guide](Server-Setup) for deployment best practices
- [Check the Configuration Reference](Configuration-Reference) for all options
- [Explore the API Reference](API-Reference) for programmatic troubleshooting
