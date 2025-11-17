# Runner Setup Guide

This comprehensive guide covers setting up and configuring ChallengeCtl runners. Runners are client applications that connect to the ChallengeCtl server, receive challenge assignments, and execute radio frequency transmissions using SDR hardware.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [SDR Hardware Setup](#sdr-hardware-setup)
- [Configuration](#configuration)
- [Starting the Runner](#starting-the-runner)
- [Verification and Testing](#verification-and-testing)
- [Production Deployment](#production-deployment)
- [Advanced Configuration](#advanced-configuration)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **Operating System**: Linux (recommended for SDR support), macOS, or Windows
- **Python**: Version 3.8 or higher
- **Memory**: Minimum 512 MB RAM (1 GB recommended)
- **Storage**: 500 MB for application and cache
- **Network**: Outbound connectivity to the ChallengeCtl server
- **SDR Hardware**: HackRF, LimeSDR, or compatible device

### Required Software

The runner requires additional software for SDR operations:

- **GNU Radio**: Version 3.8 or higher (for signal generation and transmission)
- **gr-osmosdr**: For SDR hardware interface
- **SoapySDR**: Universal SDR hardware abstraction layer (recommended)

### Supported SDR Devices

ChallengeCtl runners support the following SDR devices:

- **HackRF One**: 1 MHz to 6 GHz, half-duplex
- **LimeSDR**: 100 kHz to 3.8 GHz, full-duplex
- **USRP**: Universal Software Radio Peripheral (various models)
- **RTL-SDR**: Receive-only (limited transmit support via mod)
- **bladeRF**: 300 MHz to 3.8 GHz

## Installation

### Install System Dependencies

#### Ubuntu/Debian

```bash
sudo apt-get update
sudo apt-get install python3 python3-pip python3-venv
sudo apt-get install gnuradio gr-osmosdr
sudo apt-get install hackrf libhackrf-dev  # For HackRF
sudo apt-get install limesuite liblimesuite-dev  # For LimeSDR
```

#### Fedora/RHEL

```bash
sudo dnf install python3 python3-pip
sudo dnf install gnuradio gr-osmosdr
sudo dnf install hackrf  # For HackRF
```

#### macOS

```bash
brew install python3
brew install gnuradio
brew install hackrf  # For HackRF
brew install limesuite  # For LimeSDR
```

### Clone the Repository

```bash
git clone https://github.com/ckoval7/challengectl.git
cd challengectl
```

### Create a Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Install Python Dependencies

```bash
pip install -r requirements.txt
```

### Verify Installation

```bash
python -c "from challengectl.runner import runner; print('Installation successful')"
```

## SDR Hardware Setup

### Connect Your SDR Device

Connect your SDR hardware to a USB port. Verify the device is recognized:

#### HackRF

```bash
hackrf_info
```

Expected output:
```
Found HackRF
Serial number: 0000000000000000457863c8234e375f
Firmware Version: 2018.01.1
```

#### LimeSDR

```bash
LimeUtil --find
```

Expected output:
```
* [LimeSDR-USB, media=USB 3.0, module=FT601, addr=1d50:6108, serial=0009072003F01234]
```

### Set USB Permissions (Linux)

Create a udev rule to allow non-root access to SDR devices:

```bash
sudo nano /etc/udev/rules.d/52-sdr.rules
```

Add the following content:

```
# HackRF
SUBSYSTEM=="usb", ATTR{idVendor}=="1d50", ATTR{idProduct}=="6089", MODE="0666"

# LimeSDR
SUBSYSTEM=="usb", ATTR{idVendor}=="1d50", ATTR{idProduct}=="6108", MODE="0666"
```

Reload udev rules:

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Reconnect your SDR device.

### Test SDR Transmission

Before configuring the runner, verify your SDR can transmit:

#### HackRF Test

```bash
hackrf_transfer -t /dev/zero -f 146000000 -s 2000000 -a 1 -x 20
```

This transmits on 146 MHz for a few seconds. Monitor with a spectrum analyzer or SDR receiver.

#### LimeSDR Test

```bash
LimeUtil --make=test --args="freq=146000000"
```

**Safety Note**: Always use appropriate antennas or terminate with a dummy load when testing. Follow local regulations for radio frequency transmissions.

## Configuration

### Obtain an API Key

Before configuring the runner, you need an API key from the server administrator. The key is generated using:

```bash
python -m challengectl.server.database add-runner-key runner1
```

Save the generated key (format: `ck_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`).

### Create Configuration File

Create a `runner-config.yml` file in the runner's working directory:

```yaml
runner:
  runner_id: "runner-1"
  server_url: "http://192.168.1.100:8443"
  api_key: "ck_a3f8b9c2d1e4f5a6b7c8d9e0f1a2b3c4"
  poll_interval: 5
  heartbeat_interval: 30
  log_level: "INFO"

devices:
  - name: 0
    model: hackrf
    frequency_limits:
      - "144000000-148000000"
      - "420000000-450000000"
```

### Configuration Parameters

#### Runner Section

- **runner_id**: Unique identifier for this runner (alphanumeric, hyphens allowed)
- **server_url**: Full URL to the ChallengeCtl server (including port)
- **api_key**: API key obtained from the server administrator
- **poll_interval**: Seconds between polling for new tasks (default: 5)
- **heartbeat_interval**: Seconds between heartbeat messages (default: 30)
- **log_level**: Logging verbosity (DEBUG, INFO, WARNING, ERROR)

#### Devices Section

Each runner can manage one or more SDR devices. For each device:

- **name**: Device identifier (typically 0, 1, 2, etc.)
- **model**: Device type (`hackrf`, `limesdr`, `usrp`, `bladerf`)
- **frequency_limits**: Array of frequency ranges in Hz (format: "start-end")

### Frequency Limits

Frequency limits define which challenges this runner can accept. A runner will only be assigned challenges whose transmission frequencies fall within its configured ranges.

Example:
```yaml
frequency_limits:
  - "144000000-148000000"   # 2-meter amateur band
  - "420000000-450000000"   # 70-centimeter amateur band
  - "902000000-928000000"   # 33-centimeter band
```

**Important**: Only configure frequency ranges that are legal to transmit on in your jurisdiction and for which you have the appropriate license.

## Starting the Runner

### Basic Startup

Start the runner with default settings:

```bash
python -m challengectl.runner.runner
```

The runner will:
1. Load the configuration file
2. Register with the server
3. Begin sending heartbeats
4. Poll for task assignments
5. Download and cache challenge files
6. Execute transmissions as assigned

### Custom Configuration Location

To use a custom configuration file:

```bash
export CONFIG_PATH=/etc/challengectl/runner-config.yml
python -m challengectl.runner.runner
```

### Startup Messages

Upon successful startup, you should see:

```
2024-01-15 10:30:00 - INFO - Runner starting...
2024-01-15 10:30:00 - INFO - Loaded configuration for runner 'runner-1'
2024-01-15 10:30:01 - INFO - Registered with server successfully
2024-01-15 10:30:01 - INFO - Starting heartbeat thread (interval: 30s)
2024-01-15 10:30:01 - INFO - Starting poll loop (interval: 5s)
```

### Stopping the Runner

To stop the runner gracefully, press `Ctrl+C`. The runner will:
1. Send a signout message to the server
2. Cancel any in-progress transmissions
3. Exit cleanly

## Verification and Testing

### Check Runner Status on Server

Log in to the server web interface and navigate to the Runners page. Your runner should appear with:

- Green status indicator
- Recent last heartbeat timestamp
- List of supported frequency ranges

### Monitor Runner Logs

The runner logs all operations to stdout. Monitor these logs for:

- Successful heartbeats
- Task assignments
- File downloads
- Transmission execution
- Any errors or warnings

### Test a Transmission

Use the server web interface to manually trigger a challenge:

1. Go to the Challenges page
2. Find a challenge within your runner's frequency limits
3. Click the "Trigger Now" button
4. Monitor the runner logs for execution
5. Verify the transmission in the Transmission Feed

## Production Deployment

### Use a Process Manager

For production deployments, use systemd to manage the runner:

Create `/etc/systemd/system/challengectl-runner.service`:

```ini
[Unit]
Description=ChallengeCtl Runner
After=network.target

[Service]
Type=simple
User=challengectl
Group=challengectl
WorkingDirectory=/opt/challengectl
Environment="CONFIG_PATH=/etc/challengectl/runner-config.yml"
ExecStart=/opt/challengectl/venv/bin/python -m challengectl.runner.runner
Restart=on-failure
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl enable challengectl-runner
sudo systemctl start challengectl-runner
```

View logs:

```bash
sudo journalctl -u challengectl-runner -f
```

### Dedicated User Account

Create a dedicated user for running the service:

```bash
sudo useradd -r -s /bin/false challengectl
sudo usermod -a -G plugdev challengectl  # For SDR access
```

### Automatic Restart on Failure

The systemd configuration above automatically restarts the runner if it crashes. The 30-second delay prevents rapid restart loops.

### Resource Limits

For production systems, set resource limits:

```ini
[Service]
MemoryLimit=1G
CPUQuota=50%
```

## Advanced Configuration

### Multiple Devices

Configure multiple SDR devices on a single runner:

```yaml
devices:
  - name: 0
    model: hackrf
    frequency_limits:
      - "144000000-148000000"

  - name: 1
    model: limesdr
    frequency_limits:
      - "420000000-450000000"
      - "902000000-928000000"
```

The runner will handle devices independently and can execute transmissions on multiple devices simultaneously.

### Custom Cache Directory

By default, the runner caches downloaded files in `./cache/`. To use a custom location:

```yaml
runner:
  cache_dir: "/var/cache/challengectl"
```

### Tuning Poll and Heartbeat Intervals

Adjust these values based on your network conditions and responsiveness requirements:

```yaml
runner:
  poll_interval: 3        # Check for tasks every 3 seconds
  heartbeat_interval: 20  # Send heartbeat every 20 seconds
```

**Considerations**:
- Lower poll intervals increase responsiveness but add network traffic
- Lower heartbeat intervals improve failure detection but increase server load
- Server timeout is 90 seconds (3x default heartbeat interval)

### Debug Logging

Enable debug logging for troubleshooting:

```yaml
runner:
  log_level: "DEBUG"
```

This provides detailed information about:
- HTTP requests and responses
- File hash calculations
- Task execution steps
- Signal generation parameters

## Troubleshooting

### Runner Won't Start

**Problem**: Runner exits immediately or fails to start.

**Solutions**:
- Verify configuration file syntax with a YAML validator
- Check that the API key is correct
- Ensure the server URL is accessible (try `curl $SERVER_URL/health`)
- Review logs for specific error messages

### Runner Can't Connect to Server

**Problem**: Registration fails or heartbeats time out.

**Solutions**:
- Verify network connectivity: `ping <server-ip>`
- Check firewall rules on both runner and server
- Confirm the server is running: `curl http://<server-ip>:8443/health`
- Verify the API key exists in the server database

### SDR Device Not Found

**Problem**: Runner reports "Device not found" or similar error.

**Solutions**:
- Verify the device is connected: `lsusb` (look for your SDR)
- Test with manufacturer tools (`hackrf_info`, `LimeUtil --find`)
- Check USB permissions (see [Set USB Permissions](#set-usb-permissions-linux))
- Try a different USB port or cable
- Reboot the system

### No Tasks Assigned

**Problem**: Runner is connected but never receives tasks.

**Solutions**:
- Verify challenges are enabled on the server
- Check that challenge frequencies match your frequency_limits
- Review the Challenges page on the server for challenge states
- Ensure at least one challenge is queued or waiting

### File Download Failures

**Problem**: Runner reports errors downloading challenge files.

**Solutions**:
- Check server logs for file serving errors
- Verify challenge files exist in the correct location
- Check SHA-256 hashes match between server config and actual files
- Ensure adequate disk space in the cache directory

### Transmission Failures

**Problem**: Tasks are assigned but transmissions fail.

**Solutions**:
- Verify SDR hardware is functioning (test with manufacturer tools)
- Check GNU Radio installation: `gnuradio-config-info --version`
- Review runner debug logs for signal generation errors
- Ensure the device is not in use by another process
- Check that the frequency is within device capabilities

### High CPU Usage

**Problem**: Runner consumes excessive CPU resources.

**Solutions**:
- Reduce poll interval (increase time between polls)
- Check for stuck transmission processes
- Monitor with `top` or `htop` to identify specific processes
- Verify signal generation parameters are reasonable

### Runner Keeps Disconnecting

**Problem**: Runner shows as offline intermittently.

**Solutions**:
- Check network stability (look for packet loss)
- Increase heartbeat interval slightly
- Review server logs for timeout messages
- Verify system resources are adequate (CPU, memory)
- Check for process suspensions or scheduling issues

## Next Steps

Now that your runner is configured, you can:

- [Review the Architecture documentation](Architecture) to understand how runners interact with the server
- [Explore the Configuration Reference](Configuration-Reference) for all available options
- [Use the Troubleshooting guide](Troubleshooting) for common issues
- Deploy additional runners for redundancy and load distribution
