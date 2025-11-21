# ChallengeCtl Spectrum Listener Agent

The spectrum listener agent captures RF transmissions and generates waterfall images for challenges as they're transmitted by runner agents. Listeners connect to the ChallengeCtl server via WebSocket to receive real-time recording assignments.

## Architecture

- **WebSocket Connection**: Listeners maintain a persistent WebSocket connection to receive real-time recording assignments from the server
- **Recording Priority**: Server uses a priority algorithm to decide which transmissions to record based on:
  - Number of transmissions since last recording
  - Time elapsed since last recording
  - Challenge priority settings
- **Coordinated Timing**: When a runner gets a transmission task, the server assigns an available listener and pushes a recording assignment via WebSocket with precise timing information

## Requirements

### Software Dependencies

```bash
# Python packages
pip install pyyaml requests python-socketio matplotlib pillow numpy

# GNU Radio (version 3.8+) and gr-osmosdr
sudo apt-get install gnuradio gr-osmosdr

# SDR drivers (choose based on your hardware)
sudo apt-get install rtl-sdr      # For RTL-SDR
sudo apt-get install hackrf        # For HackRF
sudo apt-get install uhd-host      # For USRP
```

### Hardware Requirements

- SDR device (RTL-SDR, HackRF, USRP, or other osmosdr-compatible device)
- Appropriate antenna for the frequency range being monitored
- Network connection to ChallengeCtl server

## Setup

### 1. Enroll the Listener

First, create an enrollment token on the ChallengeCtl server (via the web UI):

1. Log into the ChallengeCtl web interface
2. Navigate to Agents → Provisioning tab
3. Click "Create Enrollment Token"
4. Set agent name (e.g., "Listener 1")
5. Copy the generated token

### 2. Configure the Listener

```bash
# Copy the example configuration
cd listener
cp listener-config.example.yml listener-config.yml

# Edit the configuration
nano listener-config.yml
```

Key settings to configure:
- `agent_id`: Unique identifier for this listener (e.g., "listener-1")
- `server_url`: URL of your ChallengeCtl server
- `api_key`: API key from enrollment (or use enrollment token method)
- `sample_rate`: Adjust based on your SDR capabilities
- `gain`: RF gain setting (start with 40, adjust based on signal strength)
- `device.id`: Your SDR device identifier (e.g., "rtlsdr=0")

### 3. Test SDR Device

Verify your SDR device is working:

```bash
# For RTL-SDR
rtl_test

# For HackRF
hackrf_info

# List osmosdr devices
osmocom_fft
```

### 4. Run the Listener

```bash
# Run with your configuration
./listener.py --config listener-config.yml

# Enable verbose logging for debugging
./listener.py --config listener-config.yml --verbose
```

## Usage

Once running, the listener will:

1. Register with the ChallengeCtl server as a listener agent
2. Connect to the server via WebSocket
3. Send periodic heartbeats to maintain online status
4. Wait for recording assignments
5. When assigned:
   - Wait for the expected transmission start time
   - Capture RF signal with pre-roll buffer
   - Generate waterfall image
   - Upload image to server
   - Report recording completion

## Files Generated

Waterfall images are saved to the `recordings/` directory (configurable in `listener-config.yml`):

```
recordings/
├── ChallengeName_20250121_143022.png
├── AnotherChallenge_20250121_143145.png
└── ...
```

Images are also uploaded to the server and can be viewed in the web UI under the Recordings section.

## Troubleshooting

### WebSocket Connection Fails

```
ERROR: Failed to connect WebSocket: <error>
```

**Solutions:**
- Verify `server_url` in config matches your server
- Check firewall rules allow outbound WebSocket connections
- Ensure API key is correct
- Check server logs for connection rejection reasons

### SDR Device Not Found

```
ERROR: osmosdr source failed to open device
```

**Solutions:**
- Verify device is connected: `lsusb | grep -i rtl`  (for RTL-SDR)
- Check device permissions: `sudo usermod -a -G plugdev $USER` (then logout/login)
- Test device: `rtl_test` (for RTL-SDR)
- Update device ID in config (`device.id`)

### Poor Signal Quality / No Signal Captured

**Solutions:**
- Increase RF gain in config (`gain: 50` or higher)
- Check antenna connection and placement
- Verify frequency range matches your antenna
- Check for RF interference
- Monitor live with `osmocom_fft` to verify signal is present

### High CPU Usage During Recording

**Solutions:**
- Reduce `sample_rate` (e.g., from 2M to 1M)
- Reduce `frame_rate` (e.g., from 20 to 10 fps)
- Reduce `fft_size` (e.g., from 1024 to 512)

### Images Not Uploading

```
ERROR: Failed to upload waterfall: 413 Request Entity Too Large
```

**Solutions:**
- Check server max file size settings
- Reduce image resolution by lowering `frame_rate` or duration
- Check network bandwidth
- Verify server disk space

## Architecture Details

### WebSocket Events

**Received from Server:**
- `connected`: Connection acknowledgment
- `recording_assignment`: New recording task with:
  - `frequency`: Center frequency in Hz
  - `expected_start`: ISO timestamp of expected transmission start
  - `expected_duration`: Expected transmission duration in seconds
  - `challenge_id`, `challenge_name`, `transmission_id`: Identifiers

**Sent to Server:**
- `heartbeat`: Optional WebSocket heartbeat (in addition to HTTP heartbeats)

### HTTP Endpoints Used

- `POST /api/agents/register`: Register as listener agent
- `POST /api/agents/<id>/heartbeat`: Send heartbeat
- `POST /api/agents/<id>/signout`: Graceful shutdown
- `POST /api/agents/<id>/recording/start`: Notify recording started
- `POST /api/agents/<id>/recording/<id>/complete`: Notify recording complete
- `POST /api/agents/<id>/recording/<id>/upload`: Upload waterfall PNG

### Recording Flow

```
1. Server assigns challenge to runner agent
2. Server checks if recording priority threshold met
3. Server finds available listener (online + WebSocket connected)
4. Server creates listener_assignment and pushes via WebSocket
5. Listener waits for expected_start time
6. Listener starts GNU Radio flowgraph
7. Listener captures RF with pre-roll + duration + post-roll
8. Listener generates waterfall PNG with matplotlib
9. Listener uploads image to server
10. Listener reports completion
11. Recording visible in server UI
```

## Advanced Configuration

### Multiple SDR Devices

To run multiple listeners on the same machine:

```bash
# Create separate configs
cp listener-config.yml listener-1-config.yml
cp listener-config.yml listener-2-config.yml

# Edit configs with different:
# - agent_id (listener-1, listener-2)
# - device.id (rtlsdr=0, rtlsdr=1)
# - output_dir (recordings-1, recordings-2)

# Run in separate terminals or as services
./listener.py --config listener-1-config.yml &
./listener.py --config listener-2-config.yml &
```

### Running as a Service

Create a systemd service file `/etc/systemd/system/challengectl-listener.service`:

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

## Development

### Testing Without SDR

The listener includes a simulated mode for testing when GNU Radio is not available:

```python
# In spectrum_listener.py, when GNU Radio import fails:
# Uses simulated spectrum data with noise + signals
```

This allows development and testing of the listener client, WebSocket communication, and image generation without physical SDR hardware.

### Waterfall Generator Standalone Testing

```bash
# Generate test waterfall from simulated data
python3 waterfall_generator.py
# Creates: test_waterfall.png
```

## License

Part of the ChallengeCtl project. See main repository README for license information.
