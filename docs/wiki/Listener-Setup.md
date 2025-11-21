# Listener Setup Guide

This guide covers the complete setup and configuration of ChallengeCtl listener agents. Listeners are SDR receiver agents that capture RF transmissions and generate waterfall images for spectrum visualization.

## Table of Contents

- [Overview](#overview)
- [Requirements](#requirements)
- [Installation](#installation)
- [Enrollment](#enrollment)
- [Configuration](#configuration)
- [Running the Listener](#running-the-listener)
- [Verifying Operation](#verifying-operation)
- [Advanced Configuration](#advanced-configuration)
- [Troubleshooting](#troubleshooting)

## Overview

Listener agents provide automatic spectrum capture and visualization for ChallengeCtl transmissions. When a runner is assigned a transmission task, the server can coordinate with listener agents to capture the spectrum and generate waterfall images.

### How It Works

1. **Real-Time Coordination**: Listeners connect via WebSocket for instant recording assignments (±1s precision)
2. **Priority-Based Recording**: Server intelligently selects which transmissions to record based on:
   - Number of transmissions since last recording
   - Time elapsed since last recording
   - Challenge priority settings
3. **Automatic Capture**: When assigned, listeners:
   - Wait for expected transmission start time
   - Capture RF signal with pre-roll buffer (5s before)
   - Generate waterfall image with matplotlib
   - Upload image to server
   - Report completion

### Use Cases

- **Visual Verification**: Confirm transmissions are occurring as expected
- **Signal Quality**: Analyze signal strength and spectral characteristics
- **Documentation**: Archive visual records of all transmissions
- **Debugging**: Troubleshoot transmission issues with spectrum analysis

## Requirements

### Hardware Requirements

- **SDR Receiver Device**: RTL-SDR, HackRF, USRP, or other osmosdr-compatible device
- **Antenna**: Appropriate for the frequency range being monitored
- **Computer**: Can be a Raspberry Pi or any Linux machine
- **Network Connection**: Access to ChallengeCtl server

**Note**: A single listener can monitor multiple frequency bands if your SDR supports it. Listeners can be co-located with runners or on separate machines.

### Software Requirements

```bash
# Python 3.8 or higher
python3 --version

# GNU Radio 3.8 or higher
gnuradio-config-info --version

# gr-osmosdr for SDR support
```

**Required Python packages**:
- pyyaml
- requests
- python-socketio
- matplotlib
- pillow
- numpy

**System packages**:
- gnuradio (3.8+)
- gr-osmosdr
- SDR drivers (rtl-sdr, hackrf, uhd-host, etc.)

## Installation

### 1. Install System Dependencies

#### Ubuntu/Debian

```bash
# Install GNU Radio and gr-osmosdr
sudo apt-get update
sudo apt-get install gnuradio gr-osmosdr

# Install SDR drivers based on your hardware
# For RTL-SDR:
sudo apt-get install rtl-sdr

# For HackRF:
sudo apt-get install hackrf

# For USRP:
sudo apt-get install uhd-host

# Add user to plugdev group for device access
sudo usermod -a -G plugdev $USER
# Log out and log back in for group change to take effect
```

#### Fedora/RHEL

```bash
sudo dnf install gnuradio gr-osmosdr rtl-sdr hackrf
sudo usermod -a -G plugdev $USER
```

### 2. Install Python Dependencies

```bash
cd challengectl/listener
pip install pyyaml requests python-socketio[client] matplotlib pillow numpy
```

**Note**: Use a virtual environment with `--system-site-packages` to access GNU Radio:

```bash
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install pyyaml requests python-socketio[client] matplotlib pillow numpy
```

### 3. Test SDR Device

Verify your SDR device is working before proceeding:

```bash
# For RTL-SDR
rtl_test

# For HackRF
hackrf_info

# List all osmosdr-compatible devices
osmocom_fft
```

Press Ctrl+C to stop the test. If you see "Found device" messages, your SDR is ready.

## Enrollment

Listeners use the same enrollment system as runners. You'll create an enrollment token via the web UI and use it to configure your listener.

### 1. Create Enrollment Token

1. Log into the ChallengeCtl web interface
2. Navigate to **Agents → Provisioning** tab
3. Click **"Create Enrollment Token"**
4. Enter listener details:
   - **Agent Name**: `listener-1` (or your preferred name)
   - **Agent Type**: Select "Listener"
5. Click **"Generate Token"**
6. **Copy the enrollment token and API key** - they're only shown once!

**Important**: Save both the enrollment token and API key. You'll need these for configuration.

### 2. Copy Configuration Template

```bash
cd listener
cp listener-config.example.yml listener-config.yml
```

### 3. Edit Configuration

Edit `listener-config.yml` with your enrollment credentials and SDR settings:

```yaml
agent:
  agent_id: "listener-1"
  server_url: "http://your-server:8443"
  api_key: "PASTE-API-KEY-HERE"  # From enrollment
  heartbeat_interval: 30
  websocket_enabled: true

  recording:
    output_dir: "recordings"
    sample_rate: 2000000  # 2 MHz
    fft_size: 1024
    frame_rate: 20
    gain: 40  # Adjust based on signal strength

    device:
      id: "rtlsdr=0"  # Your SDR device ID
      type: "rtlsdr"
```

**Device ID Examples**:
- RTL-SDR: `rtlsdr=0` or `rtlsdr=<serial>`
- HackRF: `hackrf=0`
- USRP: `uhd=0`

## Configuration

### Complete Configuration Options

```yaml
agent:
  # Unique identifier for this listener
  agent_id: "listener-1"

  # ChallengeCtl server URL
  server_url: "https://192.168.1.100:8443"

  # API key from enrollment (keep secure!)
  api_key: "your-api-key-here"

  # How often to send heartbeats (seconds)
  heartbeat_interval: 30

  # Enable WebSocket for real-time assignments
  websocket_enabled: true
  websocket_reconnect_delay: 5

  recording:
    # Where to save waterfall images
    output_dir: "recordings"

    # RF capture settings
    sample_rate: 2000000  # 2 MHz (adjust for your SDR)
    fft_size: 1024        # FFT bins (1024, 2048, 4096)
    frame_rate: 20        # Waterfall frames per second
    gain: 40              # RF gain in dB (0-50 typical)

    # Timing buffers
    pre_roll_seconds: 5   # Capture before transmission
    post_roll_seconds: 5  # Capture after transmission

    # SDR device configuration
    device:
      id: "rtlsdr=0"      # Device identifier
      type: "rtlsdr"      # Device type
      serial: "00000001"  # Optional serial number

logging:
  level: "INFO"           # DEBUG, INFO, WARNING, ERROR
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

### Configuration Tips

**Sample Rate**:
- Higher = more bandwidth captured, but more CPU usage
- 2 MHz is good for most applications
- Reduce to 1 MHz if experiencing performance issues

**Gain Settings**:
- Start with 40 dB and adjust based on signal strength
- Too low: weak signals, noise floor too high
- Too high: saturation, distortion
- Use `osmocom_fft` to test live and adjust

**FFT Size**:
- 1024: Good frequency resolution, fast processing
- 2048: Better frequency resolution, more CPU
- 4096: Excellent resolution, highest CPU usage

## Running the Listener

### Start the Listener

```bash
cd listener
./listener.py --config listener-config.yml
```

**With verbose logging**:
```bash
./listener.py --config listener-config.yml --verbose
```

### Expected Output

```
INFO - Starting ChallengeCtl Listener: listener-1
INFO - Server URL: http://your-server:8443
INFO - Registering with server...
INFO - Successfully registered as listener agent
INFO - Connecting to WebSocket...
INFO - WebSocket connected to /agents namespace
INFO - Joined agent room: agent_listener-1
INFO - Listener ready, waiting for recording assignments...
```

### During Operation

When a recording is assigned, you'll see:

```
INFO - Received recording assignment
INFO - Challenge: NBFM_TEST, Frequency: 146.55 MHz
INFO - Expected start: 2024-01-15 10:30:00
INFO - Waiting 12.5 seconds until start time...
INFO - Starting recording (duration: 10.0s with 5.0s pre/post roll)
INFO - Recording spectrum...
INFO - Captured 400 frames
INFO - Generating waterfall image...
INFO - Waterfall saved: recordings/NBFM_TEST_20240115_103000.png
INFO - Uploading waterfall to server...
INFO - Recording complete: recording_id 42
```

## Verifying Operation

### 1. Check Web Interface

1. Navigate to **Agents → Listeners** tab
2. Verify your listener shows:
   - Status: **Online** (green)
   - WebSocket: **Connected** (green badge)
   - Last Heartbeat: Recent timestamp

### 2. Verify Recording Assignment

1. Trigger a challenge transmission
2. Watch listener logs for recording assignment
3. Check **Recordings** section in web UI for waterfall image

### 3. Verify Local Files

Check that waterfall images are being saved:

```bash
ls -lh recordings/
# Should show PNG files:
# NBFM_TEST_20240115_103000.png
# CW_TEST_20240115_103500.png
```

### 4. Test Signal Quality

If you have two SDRs, you can test with one as a runner and one as a listener on the same machine:

1. Start a runner transmitting on a specific frequency
2. Start a listener with that frequency range
3. Trigger a test transmission
4. View the resulting waterfall to confirm good signal quality

## Advanced Configuration

### Multiple Listeners

Run multiple listeners on the same machine with different SDRs:

```bash
# Create separate configs
cp listener-config.yml listener-1-config.yml
cp listener-config.yml listener-2-config.yml

# Edit each config:
# - Different agent_id: "listener-1", "listener-2"
# - Different device.id: "rtlsdr=0", "rtlsdr=1"
# - Different output_dir: "recordings-1", "recordings-2"

# Run in separate terminals or as services
./listener.py --config listener-1-config.yml &
./listener.py --config listener-2-config.yml &
```

### Running as a SystemD Service

Create `/etc/systemd/system/challengectl-listener.service`:

```ini
[Unit]
Description=ChallengeCtl Spectrum Listener
After=network.target

[Service]
Type=simple
User=challengectl
WorkingDirectory=/home/challengectl/challengectl/listener
ExecStart=/usr/bin/python3 /home/challengectl/challengectl/listener/listener.py --config /home/challengectl/challengectl/listener/listener-config.yml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable challengectl-listener
sudo systemctl start challengectl-listener
sudo systemctl status challengectl-listener
```

View logs:

```bash
sudo journalctl -u challengectl-listener -f
```

### Frequency-Specific Listeners

You can deploy listeners optimized for specific frequency bands:

- **VHF Listener**: RTL-SDR with VHF antenna for 144-148 MHz
- **UHF Listener**: Different RTL-SDR with UHF antenna for 420-450 MHz
- **Wideband Listener**: HackRF or USRP for monitoring multiple bands

This allows optimal antenna selection and gain settings per band.

## Troubleshooting

### WebSocket Connection Fails

**Error**: `ERROR: Failed to connect WebSocket`

**Solutions**:
1. Verify server URL in config matches your server
2. Check firewall rules allow outbound WebSocket connections
3. Ensure API key is correct (check web UI Agents page)
4. Check server logs for connection rejection reasons
5. Test with verbose logging: `./listener.py --config ... --verbose`

### SDR Device Not Found

**Error**: `ERROR: osmosdr source failed to open device`

**Solutions**:
1. Verify device is connected: `lsusb | grep -i rtl` (for RTL-SDR)
2. Check device permissions:
   ```bash
   sudo usermod -a -G plugdev $USER
   # Then logout/login
   ```
3. Test device directly: `rtl_test` (for RTL-SDR)
4. Update device ID in config:
   - List devices with `osmocom_fft`
   - Update `device.id` in config

### Poor Signal Quality / No Signal Captured

**Solutions**:
1. **Increase RF gain** in config: `gain: 50` or higher
2. **Check antenna connection** and placement
3. **Verify frequency range** matches your antenna specs
4. **Check for RF interference** in your environment
5. **Monitor live** with `osmocom_fft` to verify signal is present
6. **Adjust sample rate** if using narrow signals

### High CPU Usage

**Solutions**:
1. **Reduce sample rate**: `sample_rate: 1000000` (1 MHz)
2. **Reduce frame rate**: `frame_rate: 10` (from 20)
3. **Reduce FFT size**: `fft_size: 512` (from 1024)
4. **Use dedicated hardware**: Move listener to a more powerful machine

### Images Not Uploading

**Error**: `ERROR: Failed to upload waterfall: 413 Request Entity Too Large`

**Solutions**:
1. Check server max file size settings
2. Reduce image resolution:
   - Lower `frame_rate` (fewer time samples)
   - Reduce recording duration
3. Check network bandwidth between listener and server
4. Verify server has sufficient disk space

### Listener Shows Offline

**Solutions**:
1. Check listener process is running: `ps aux | grep listener`
2. Check listener logs for errors
3. Verify heartbeat interval isn't too long
4. Check network connectivity to server
5. Restart listener: `systemctl restart challengectl-listener`

### No Recordings Being Assigned

**Possible Causes**:
1. **Priority too low**: Server uses priority algorithm, not all transmissions are recorded
2. **No online runners**: Listener assignments only happen when runners transmit
3. **Listener disabled**: Check "enabled" status in web UI
4. **WebSocket disconnected**: Verify WebSocket connection in web UI

**Solutions**:
1. Monitor web UI for transmission activity
2. Check priority settings in Architecture documentation
3. Verify listener is enabled in Agents page
4. Check WebSocket connection badge shows "Connected"

## Testing Without SDR Hardware

The listener includes a simulated mode for testing when SDR hardware is not available:

```bash
# Listener will automatically use simulated mode if GNU Radio is not available
./listener.py --config listener-config.yml
```

The simulated mode generates realistic spectrum data with noise and simulated signals, allowing you to:
- Test WebSocket communication
- Verify waterfall image generation
- Test upload functionality
- Develop and debug without hardware

**Note**: Simulated mode is detected automatically when GNU Radio imports fail.

## Next Steps

Now that your listener is operational:

- [View Recordings](Web-Interface-Guide) in the web interface
- [Understand the Architecture](Architecture) for how listeners coordinate with runners
- [Configure Recording Priority](Architecture#recording-priority-algorithm) to optimize resource usage
- [Monitor Listener Status](Web-Interface-Runners) in real-time

## Related Documentation

- [Architecture Overview](Architecture) - Understanding listener coordination
- [Web Interface Guide](Web-Interface-Guide) - Viewing recordings
- [API Reference](API-Reference) - Listener API endpoints
- [Troubleshooting](Troubleshooting) - Common issues and solutions
