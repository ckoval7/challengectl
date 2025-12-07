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
- **Python**: Version 3.9 or higher (Python 3.12 recommended)
- **Memory**: Minimum 512 MB RAM (1 GB recommended)
- **Storage**: 500 MB for application and cache
- **Network**: Outbound connectivity to the ChallengeCtl server
- **SDR Hardware**: HackRF, LimeSDR, or compatible device

### Required Software

The runner requires additional software for SDR operations:

- **GNU Radio**: Version 3.9 or higher (for signal generation and transmission)
- **gr-osmosdr**: For SDR hardware interface (required for all runners)
- **SoapySDR**: Universal SDR hardware abstraction layer (recommended)

**Modulation-specific modules:**
- **gr-rfhs**: Contains modules needed for CW, ASK, and LRS challenges (must be compiled from source)
- **gr-paint**: For spectrum painting challenges (must be compiled from source)
- **gr-mixalot**: For POCSAG paging challenges (must be compiled from source)

### Supported SDR Devices

ChallengeCtl runners support the following SDR devices:

- **HackRF One**: 1 MHz to 6 GHz, half-duplex
- **LimeSDR**: 100 kHz to 3.8 GHz, full-duplex
- **USRP**: Universal Software Radio Peripheral (various models)
- **bladeRF**: 47 MHz to 3.8 GHz

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

**Install build dependencies for GNU Radio modules:**

```bash
sudo apt-get install git cmake g++ libboost-all-dev libgmp-dev swig \
  python3-numpy python3-mako python3-sphinx python3-lxml doxygen \
  libfftw3-dev libsdl1.2-dev libgsl-dev libqwt-qt5-dev libqt5opengl5-dev \
  python3-pyqt5 liblog4cpp5-dev libzmq3-dev python3-yaml python3-click \
  python3-click-plugins python3-zmq python3-scipy python3-gi \
  python3-gi-cairo gobject-introspection gir1.2-gtk-3.0
```


**Install gr-rfhs (required core modules):**

```bash
cd /tmp
git clone https://github.com/ckoval7/gr-rfhs
cd gr-rfhs
mkdir build
cd build
cmake ..
make
sudo make install
sudo ldconfig
```

**Install gr-paint (required for spectrum painting challenges):**

```bash
cd /tmp
git clone https://github.com/drmpeg/gr-paint.git
cd gr-paint
mkdir build
cd build
cmake ..
make
sudo make install
sudo ldconfig
```

**Install gr-mixalot (required for POCSAG paging challenges):**

```bash
cd /tmp
git clone https://github.com/unsynchronized/gr-mixalot.git
cd gr-mixalot
mkdir build
cd build
cmake ..
make
sudo make install
sudo ldconfig
```

#### Fedora/RHEL

```bash
sudo dnf install python3 python3-pip
sudo dnf install gnuradio gr-osmosdr
sudo dnf install hackrf  # For HackRF

# Build dependencies
sudo dnf install git cmake gcc-c++ boost-devel gmp-devel swig \
  python3-numpy python3-mako python3-sphinx fftw-devel \
  SDL-devel gsl-devel qwt-qt5-devel python3-pyqt5 \
  log4cpp-devel zeromq-devel python3-pyyaml
```

Then compile gr-paint and gr-mixalot following the Ubuntu instructions above.

#### macOS

```bash
brew install python3
brew install gnuradio
brew install hackrf  # For HackRF
brew install limesuite  # For LimeSDR

# Build dependencies
brew install cmake boost gmp swig fftw sdl gsl qwt qt@5 log4cpp zeromq
```

Then compile gr-paint and gr-mixalot following the Ubuntu instructions above.

### Clone the Repository

```bash
git clone https://github.com/ckoval7/challengectl.git
cd challengectl
```

### Create a Virtual Environment

Create a Python virtual environment with access to system-installed GNU Radio libraries:

```bash
python3 -m venv --system-site-packages venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

**Important**: The `--system-site-packages` flag is required so the virtual environment can access GNU Radio and the gr-* modules installed system-wide.

### Install Python Dependencies

```bash
pip install -r requirements-runner.txt
```

### Verify Installation

Verify Python modules:

```bash
python -c "from challengectl.runner import runner; print('Installation successful')"
```

Verify GNU Radio modules:

```bash
python3 -c "from gnuradio import gr; print('GNU Radio OK')"
python3 -c "import osmosdr; print('gr-osmosdr OK')"
python3 -c "import paint; print('gr-paint OK')"
python3 -c "import mixalot; print('gr-mixalot OK')"
```

If any module fails to import, revisit the installation steps for that component.

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

### USB Device Monitoring (Linux)

ChallengeCtl uses event-driven USB device detection on Linux for immediate SDR device recognition. This feature provides real-time device detection without polling overhead.

**How it works**:
- Uses Linux udev via the pyudev library for real-time USB event monitoring
- Detects device plug/unplug events in <2 seconds (vs legacy 30-second polling)
- Automatically filters non-SDR devices (HID, storage, audio, etc.)
- Debounces rapid USB events (1-second coalesce interval)
- Zero CPU overhead when no USB events occur

**Supported SDR vendors**:
The runner automatically recognizes these SDR device vendors:
- **HackRF** (vendor ID 1d50)
- **BladeRF** (vendor ID 2cf0)
- **RTL-SDR** (vendor ID 0bda)
- **USRP** (vendor ID 2500, fffe)
- **AirSpy** (vendor ID 1d50)
- **FUNcube Dongle** (vendor ID 04d8)

**Requirements**:
- Linux operating system
- pyudev library (installed via `requirements-runner.txt`)
- udev permissions configured (see [Set USB Permissions](#set-usb-permissions-linux) above)

**Device filtering**:
The runner automatically filters out non-SDR devices to prevent false detections:

**Allowed**:
- Known SDR vendor IDs listed above
- Vendor-specific USB class (0xFF)
- Communications class (0x02)

**Blocked**:
- HID class (0x03) - keyboards, mice, game controllers
- Mass Storage class (0x08) - USB drives, external hard drives
- Audio class (0x01) - sound cards, audio interfaces
- Hub class (0x09) - USB hubs
- Other non-SDR device classes

**Monitoring behavior**:
1. **Initial probe**: At startup, discovers all connected SDR devices
2. **Event-driven probing**: When USB devices are added or removed, immediately probes for SDR devices
3. **Real-time updates**: Device list automatically updates and is sent to server in the next heartbeat
4. **Automatic cleanup**: USB handles are garbage collected after each probe to prevent resource leaks

**Performance**:
- Device detection: <2 seconds (vs 30-second polling in legacy systems)
- CPU usage when idle: 0% (event-driven, no polling loop)
- Memory overhead: Minimal (pyudev library is lightweight)

**Logging**:
The runner logs USB events for debugging:
```
INFO - USB event: device added (vendor=1d50, product=604b)
INFO - Probing devices...
INFO - Found 1 SDR device(s)
DEBUG - HackRF detected on /dev/bus/usb/001/004
```

**Workaround for non-Linux systems**:
USB event monitoring is Linux-only. On macOS and Windows, the runner uses periodic polling (30-second interval) for device detection.

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

### Enroll Your Runner

Runners use a secure enrollment process that stores API keys bcrypt-hashed in the database (one-way hashing like passwords) instead of in configuration files.

#### Step 1: Generate Enrollment Credentials

There are two ways to obtain enrollment credentials:

**Option A: Manual Enrollment (via Web UI)**

Have your server administrator:

1. Log in to the ChallengeCtl Web UI
2. Navigate to the **Runners** page
3. Click the **Add Runner** button
4. Enter a descriptive name for your runner (e.g., "sdr-station-1", "runner-west")
5. Select an expiration time (default: 24 hours)
6. Click **Generate Credentials**
7. Download or copy the complete configuration file

**Option B: Provisioning API Key (for automation)**

For automated deployments or CI/CD environments:

1. Administrator creates a provisioning API key in **Runners** → **Provisioning Keys** tab
2. Use the provisioning API to generate runner credentials programmatically
3. See the [Provisioning API Key Guide](../examples/provisioning-api-key-guide.md) for details

**What you receive:**
- **Enrollment Token**: A one-time use token (valid for the specified time period)
- **API Key**: A secure random key that will be bcrypt-hashed and stored in the database
- **Complete Configuration**: A ready-to-use YAML configuration file

**Security Note**: These credentials are only displayed once. Copy them immediately!

**Important Security Feature - Multi-Factor Host Validation**: The API key is tied to a specific runner_id and host machine. During enrollment, the server captures multiple host identifiers:
- IP address and hostname
- MAC address (primary network interface)
- Machine ID (from `/etc/machine-id` or system-specific identifier)

If the runner is actively online (heartbeat within last 90 seconds), authentication attempts from a different machine will be rejected unless at least **TWO** of these identifiers match:
- IP address + hostname (counted together as ONE factor)
- MAC address (ONE factor)
- Machine ID (ONE factor)

**Note**: On first authentication, if MAC address or machine ID were not captured during enrollment, the system will automatically upgrade the runner record with these values, but only if at least two factors match overall.

This multi-factor validation prevents credential reuse attacks if your config file is copied to another machine. To move a runner to a different host, use the **Re-enrollment** feature in the Web UI.

#### Step 2: Configure Your Runner

The administrator will give you both the enrollment token and API key. You'll use these in your configuration file for the initial enrollment.

### Create Configuration File

Create a `runner-config.yml` file in the runner's working directory:


```yaml
runner:
  runner_id: "sdr-station-1"  # Choose a unique ID for your runner
  server_url: "https://192.168.1.100:8443"

  # Enrollment credentials (provided by administrator)
  enrollment_token: "PASTE-ENROLLMENT-TOKEN-HERE"
  api_key: "PASTE-API-KEY-HERE"

  # Optional settings
  poll_interval: 10
  heartbeat_interval: 30
  cache_dir: "cache"
  verify_ssl: true

radios:
  devices:
    - name: 0
      model: hackrf
      frequency_limits:
        - "144000000-148000000"  # 2m band
        - "420000000-450000000"  # 70cm band
```

**Note**: The `enrollment_token` can be left in the configuration file. After the first successful enrollment, it will be ignored on subsequent runs. Only the API key is used for authentication once enrolled.

## Configuration Parameters

#### Runner Section

- **runner_id**: Unique identifier for this runner (alphanumeric, hyphens, underscores allowed)
- **server_url**: Full URL to the ChallengeCtl server (including port)
- **enrollment_token**: One-time enrollment token (can be left in config, will be ignored once enrolled)
- **api_key**: API key for authentication
- **poll_interval**: Seconds between polling for new tasks (default: 10)
- **heartbeat_interval**: Seconds between heartbeat messages (default: 30)
- **cache_dir**: Directory for caching challenge files (default: "cache")
- **verify_ssl**: Enable SSL certificate verification (default: true)
- **ca_cert**: Path to custom CA certificate file (optional)

#### Devices Section

Each runner can manage one or more SDR devices. For each device, you can use one of two configuration formats:

**Legacy Format (single antenna per device):**
- **name**: Device identifier (typically 0, 1, 2, or serial number)
- **model**: Device type (`hackrf`, `limesdr`, `usrp`, `bladerf`)
- **antenna**: Antenna name (optional, device-specific)
- **frequency_limits**: Array of frequency ranges in Hz (format: "start-end")

**New Format (per-antenna frequency limits and gain for multi-antenna devices):**
- **name**: Device identifier (typically serial number for precision)
- **model**: Device type (`hackrf`, `limesdr`, `usrp`, `bladerf`)
- **rf_gain**: Device-level RF gain (optional, used as fallback if not specified per-antenna)
- **antennas**: Dictionary of antenna configurations, where each antenna can have:
  - **enabled**: Boolean to enable/disable antenna (default: true)
  - **rf_gain**: RF gain value for this antenna (optional, overrides device-level)
  - **frequency_limits**: Array of frequency ranges for this specific antenna

### Frequency Limits

Frequency limits define which challenges this runner can accept. The runner will only be assigned challenges whose transmission frequencies fall within its configured ranges.

**Legacy Format Example (device-level frequency limits):**
```yaml
devices:
  - name: 0
    model: hackrf
    frequency_limits:
      - "144000000-148000000"   # 2-meter amateur band
      - "420000000-450000000"   # 70-centimeter amateur band
```

**New Format Example (per-antenna frequency limits and gain):**
```yaml
devices:
  - name: "1234567890abcdef"
    model: bladerf
    rf_gain: 43  # Default gain (used if not specified per-antenna)
    antennas:
      TX1:
        enabled: true  # Optional, defaults to true
        rf_gain: 43    # Optimal gain for VHF/UHF
        frequency_limits:
          - "144000000-148000000"   # 2m on TX1
          - "420000000-450000000"   # 70cm on TX1
      TX2:
        enabled: true
        rf_gain: 50    # Higher gain for 900 MHz/2.4 GHz
        frequency_limits:
          - "900000000-915000000"   # 900 MHz on TX2
          - "2400000000-2500000000" # 2.4 GHz on TX2
```

**Automatic Antenna Selection:**

When using the new per-antenna format, the runner automatically selects the appropriate antenna based on the challenge frequency. The server validates frequency compatibility before assigning challenges, and the runner double-checks before executing transmissions.

**Disabling Antennas:**

You can temporarily disable antennas by setting `enabled: false`. This is useful for:
- Antenna maintenance or repairs
- Testing specific configurations
- Temporarily taking an antenna offline without removing its configuration

Example with disabled antenna:
```yaml
devices:
  - name: "abcdef1234567890"
    model: bladerf
    antennas:
      TX1:
        enabled: true
        frequency_limits:
          - "144000000-148000000"
          - "420000000-450000000"
      TX2:
        enabled: false  # Temporarily disabled (e.g., maintenance)
        frequency_limits:
          - "900000000-915000000"
          - "2400000000-2500000000"
```

Disabled antennas will be skipped during automatic antenna selection.

###  RF Gain Configuration

RF gain controls the transmission power of the SDR device. You can configure gain at two levels:

**Device-Level Gain (Legacy and Fallback):**
- Specified at the device level using `rf_gain` (and `if_gain` for HackRF)
- Applies to all transmissions on that device
- Used as fallback if per-antenna gain is not specified

**Per-Antenna Gain (Recommended for Multi-Antenna Devices):**
- Specified within each antenna configuration
- Allows optimizing gain for different frequency bands
- Overrides device-level gain for that specific antenna

Example with different gains per antenna:
```yaml
devices:
  - name: "1234567890abcdef"
    model: bladerf
    rf_gain: 43  # Fallback gain
    antennas:
      TX1:
        rf_gain: 43    # Lower gain for VHF/UHF (144-450 MHz)
        frequency_limits:
          - "144000000-148000000"
          - "420000000-450000000"
      TX2:
        rf_gain: 55    # Higher gain for microwave (900 MHz, 2.4 GHz)
        frequency_limits:
          - "900000000-915000000"
          - "2400000000-2500000000"
```

**Gain Value Guidelines:**
- HackRF: rf_gain (0-47 dB), if_gain (0-40 dB)
- BladeRF: rf_gain (0-66 dB), no if_gain
- USRP: rf_gain (device-dependent), no if_gain
- Higher frequencies often require higher gain for same effective range
- Adjust based on antenna characteristics and transmission requirements
- Too high gain can cause distortion; too low reduces transmission range

**Important**: Only configure frequency ranges that are legal to transmit on in your jurisdiction and for which you have the appropriate license.

## Starting the Runner

### Basic Startup

Start the runner with default settings:

```bash
python -m challengectl.runner.runner
```

The runner will:
1. Load the configuration file
2. If an enrollment token is present, enroll with the server (first run only)
3. Register with the server
4. Begin sending heartbeats
5. Poll for task assignments
6. Download and cache challenge files
7. Execute transmissions as assigned

**First-time enrollment output:**
```
Enrollment token detected. Enrolling with server...
Successfully enrolled as sdr-station-1

IMPORTANT: Remove 'enrollment_token' from your runner-config.yml and restart the runner.

Registering with server...
Registration successful
```

After seeing this message, edit `runner-config.yml` and remove the `enrollment_token` line, then restart the runner.

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

## Re-enrolling a Runner

If you need to move your runner to a different host machine or refresh compromised credentials, use the **Re-enrollment** feature instead of copying your existing configuration.

### Why Re-enroll?

Due to multi-factor host validation, you cannot simply copy your runner configuration to a new machine. The API key is bound to the original host's identifiers (MAC address, machine ID, IP, hostname). Attempting to use the same credentials on a different machine will be rejected by the server.

### Re-enrollment Process

1. **In the Web UI**, navigate to the Runners page
2. Click the **"Re-enroll"** button next to your runner
3. Click **"Generate Credentials"** to create fresh enrollment credentials
4. **Download or copy** the complete configuration file
5. **On the new host**, save the configuration as `runner-config.yml`
6. Customize the `radios` section for your SDR devices
7. Start the runner: `python -m challengectl.runner.runner`
8. After successful enrollment, remove the `enrollment_token` line from the config
9. The old runner instance will be automatically disconnected

**Important Notes:**
- The old API key remains valid until the re-enrollment completes
- You can run both old and new runners temporarily during migration
- Once the new runner enrolls, the host identifiers are updated
- The old runner will be rejected on its next authentication attempt
- Re-enrollment credentials are only shown once - download immediately!

### Re-enrollment vs New Enrollment

| Feature | New Enrollment | Re-enrollment |
|---------|---------------|---------------|
| Runner ID | New ID assigned | Same runner_id maintained |
| History | No previous history | Preserves runner history |
| Devices | Must reconfigure | Maintains device configuration |
| Use Case | Adding new runner | Migrating existing runner |

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

**Legacy Format:**
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

**Multi-Antenna Format:**
```yaml
devices:
  - name: 0
    model: hackrf
    frequency_limits:
      - "144000000-148000000"

  - name: "1234567890abcdef"
    model: bladerf
    antennas:
      TX1:
        frequency_limits:
          - "420000000-450000000"
      TX2:
        frequency_limits:
          - "900000000-928000000"
          - "2400000000-2500000000"
```

The runner will handle devices independently and can execute transmissions on multiple devices simultaneously. When using per-antenna frequency limits, the runner automatically selects the correct antenna for each challenge based on the transmission frequency.

### Mixed Configuration

You can mix legacy single-antenna devices with multi-antenna devices in the same runner:

```yaml
devices:
  # HackRF with legacy format (single antenna)
  - name: 0
    model: hackrf
    frequency_limits:
      - "144000000-148000000"
      - "420000000-450000000"

  # BladeRF with multi-antenna format
  - name: "1234567890abcdef"
    model: bladerf
    antennas:
      TX1:
        enabled: true
        frequency_limits:
          - "144000000-148000000"
      TX2:
        enabled: true
        frequency_limits:
          - "2400000000-2500000000"
```

This flexibility allows you to migrate to the new format gradually or use it only for devices that actually have multiple antennas.

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
- Check that challenge frequencies match your frequency_limits or antenna frequency_limits
- If using per-antenna configuration, ensure at least one antenna is enabled for the required frequency
- Verify that antennas are not all disabled (`enabled: false`)
- Review the Challenges page on the server for challenge states
- Ensure at least one challenge is queued or waiting
- Check runner logs for "doesn't support frequency" messages

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

### Antenna Selection Issues

**Problem**: Runner reports "No antenna supporting frequency" or similar errors.

**Solutions**:
- Verify that at least one antenna in your configuration supports the challenge frequency
- Check that the antenna is enabled (`enabled: true` or field omitted)
- Review your `frequency_limits` for each antenna to ensure they cover the required range
- Ensure frequency ranges don't have typos (use format "144000000-148000000")
- If using legacy format, verify `frequency_limits` at device level are correct
- Check runner logs for which antenna was attempted and why it was rejected

**Problem**: Wrong antenna is being selected for transmissions.

**Solutions**:
- Review the frequency_limits for each antenna - they may overlap
- The runner selects the first matching antenna, so order matters in the config
- Consider reorganizing frequency_limits to avoid overlaps
- Enable debug logging to see antenna selection decisions

**Problem**: Disabled antenna is still being used.

**Solutions**:
- Verify the `enabled: false` flag is properly formatted in YAML
- Restart the runner after configuration changes
- Check for YAML syntax errors (indentation, etc.)
- Review runner startup logs to confirm antenna configuration was loaded correctly

## Next Steps

Now that your runner is configured, you can:

- [Review the Architecture documentation](Architecture) to understand how runners interact with the server
- [Explore the Configuration Reference](Configuration-Reference) for all available options
- [Use the Troubleshooting guide](Troubleshooting) for common issues
- Deploy additional runners for redundancy and load distribution
