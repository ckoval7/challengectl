# Quick Start Guide

This guide will help you get ChallengeCtl up and running in the shortest time possible. For more detailed setup instructions, refer to the [Server Setup](Server-Setup) and [Runner Setup](Runner-Setup) guides.

## Prerequisites

Before you begin, ensure you have the following:

- Python 3.9 or higher (Python 3.12 recommended for optimal performance)
- For runners: SDR hardware (HackRF, LimeSDR, or compatible device)
- For runners: GNU Radio 3.9 or higher with gr-osmosdr, gr-paint, and gr-mixalot (GNU Radio 3.10 recommended)
- Basic understanding of software defined radio concepts

**Note**: Runners require additional GNU Radio modules that must be compiled from source. See the [Runner Setup Guide](Runner-Setup#install-system-dependencies) for detailed installation instructions.

## Step 1: Install Dependencies

Begin by cloning the repository and installing the required Python packages. The installation process differs depending on whether you're setting up a server, runner, or both.

```bash
git clone https://github.com/ckoval7/challengectlv2.git
cd challengectl

# For server deployments
pip install -r requirements-server.txt

# For runner deployments (after installing GNU Radio dependencies)
pip install -r requirements-runner.txt
```

**Important for runners**: Before installing Python dependencies for runners, you must first install GNU Radio, gr-osmosdr, gr-paint, and gr-mixalot from source. These components cannot be installed through pip and require compilation. Refer to the [Runner Setup Guide](Runner-Setup) for complete installation instructions and system-specific dependencies.

## Step 2: Set Up the Server

### Configure the Server

Create a `server-config.yml` file with minimal configuration:

```yaml
server:
  bind: "0.0.0.0"
  port: 8443
```

**Note**: Challenges can be configured through the Web UI or in the YAML file. See [Challenge Management](Challenge-Management) for details on using the Web UI.

To configure challenges in the YAML file, ChallengeCtl supports three ways to specify frequencies:

```yaml
challenges:
  # Option 1: Single frequency
  - name: NBFM_Example
    frequency: 146550000  # Hz (146.550 MHz)
    modulation: nbfm
    flag: challenges/example.wav
    min_delay: 60
    max_delay: 120
    enabled: true

  # Option 2: Named frequency ranges (random selection)
  - name: NBFM_Random
    frequency_ranges:  # System picks random frequency from these ranges
      - ham_144
      - ham_440
    modulation: nbfm
    flag: challenges/example.wav
    min_delay: 60
    max_delay: 120
    enabled: true

  # Option 3: Manual frequency range (custom range)
  - name: CW_CustomRange
    manual_frequency_range:
      min_hz: 146000000  # 146.000 MHz
      max_hz: 146100000  # 146.100 MHz
    modulation: cw
    flag: "CQ CQ CQ DE RFCTF K"
    speed: 35
    min_delay: 60
    max_delay: 120
    enabled: true
```

Named frequency ranges must be defined in the `frequency_ranges` section of your config. See [Configuration Reference](Configuration-Reference#frequency-ranges-section) for details.

Place your challenge files (like `example.wav`) in the `challenges/` directory.

### Start the Server

```bash
python -m challengectl.server.server
```

The server will start on port 8443 and automatically create a default admin account.

### Complete Initial Setup

1. **Check the server output** for the temporary admin credentials:
   ```
   ================================================================================
   DEFAULT ADMIN USER CREATED
   ================================================================================
   Username: admin
   Password: aB3xK9mN2pQ7rT5w
   ```

2. **Navigate to the server** in your web browser. Use the server's actual IP address or hostname (e.g., `http://192.168.1.100:8443`) rather than `localhost` if you plan to access it from other machines.

3. **Log in** with the temporary credentials shown in the server output.

4. **Complete the setup wizard**:
   - Create your personal admin account with a strong, unique password
   - Set up TOTP two-factor authentication by scanning the QR code with your authenticator app
   - **Important**: TOTP secrets are encrypted using a server-side master key stored in `server/.encryption_key`
   - The system will automatically log you in with your new personal account after setup completes

5. **Enroll your first runner**:
   - Navigate to the **Agents** page in the Web UI and select the **Runners** tab
   - Click **"Add Runner"** to begin the enrollment process
   - Enter a descriptive runner name (e.g., "runner-1")
   - Optionally configure SDR devices including model type, RF gain, IF gain, and frequency limits
   - Click **"Generate Token"** to create the enrollment credentials
   - **IMPORTANT**: Copy both the enrollment token and API key immediately - they are only displayed once for security
   - The dialog provides a complete YAML configuration that you can copy directly into your runner config file
   - Keep these credentials ready for Step 3

## Step 3: Set Up a Runner

**Prerequisites**: Before configuring a runner, ensure you have installed GNU Radio, gr-osmosdr, gr-paint, and gr-mixalot. See the [Runner Setup Guide](Runner-Setup#install-system-dependencies) for instructions.

### Create Virtual Environment with System Packages

Create a Python virtual environment that can access system-installed GNU Radio:

```bash
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install -r requirements-runner.txt
```

**Important**: The `--system-site-packages` flag allows the virtual environment to access GNU Radio and its modules.

### Configure the Runner

The easiest way to configure a runner is to use the YAML configuration provided by the Web UI during enrollment (Step 2, item 5). Simply copy the generated configuration into a new file named `runner-config.yml`.

Alternatively, you can create the configuration file manually using the credentials from Step 2:

```yaml
runner:
  runner_id: "runner-1"
  server_url: "http://YOUR-SERVER-IP:8443"  # Use actual server IP or hostname
  enrollment_token: "PASTE-ENROLLMENT-TOKEN-HERE"  # From Step 2
  api_key: "PASTE-API-KEY-HERE"                     # From Step 2
  poll_interval: 5
  heartbeat_interval: 30

radios:
  devices:
    - name: 0
      model: hackrf
      frequency_limits:
        - "144000000-148000000"
```

**Note**: The enrollment token can remain in the configuration file for reference. After the first successful enrollment, it will be ignored on subsequent runs.

### Start the Runner

```bash
python -m challengectl.runner.runner
```

The runner will register with the server and begin polling for tasks.

## Step 4: Set Up a Listener (Optional)

Listeners capture RF transmissions and generate waterfall images for spectrum visualization. This is optional but provides valuable visual confirmation of your transmissions.

**Note**: Listeners require SDR receiver hardware (RTL-SDR, HackRF, USRP, etc.) and GNU Radio. See the [Listener Setup Guide](Listener-Setup) for complete instructions.

### Quick Listener Setup

1. **Enroll the listener** via the Web UI:
   - Navigate to **Agents → Listeners** tab
   - Click **"Add Listener"** button
   - Enter listener name and configure SDR devices (model, gain, frequency limits)
   - Supports multiple receiver devices for simultaneous monitoring across different frequency ranges
   - Click **"Generate Token"**
   - Copy or download the generated `listener-config.yml`
2. **Install dependencies**: GNU Radio, gr-osmosdr, and Python packages (see [Listener Setup](Listener-Setup))
3. **Start the listener**: `./listener/listener.py --config listener-config.yml`

Listeners connect via WebSocket and receive recording assignments automatically based on transmission priority. Waterfall images are uploaded to the server and viewable in the web interface.

For detailed listener setup including GNU Radio installation and configuration, see the [Listener Setup Guide](Listener-Setup).

## Step 5: Configure Challenges

Now that the server and runner are connected, you can configure challenges through the Web UI:

1. **Navigate to "Manage Challenges"**: Click the "Manage Challenges" menu item in the left sidebar.

2. **Create your first challenge**:
   - Select the **"Create Challenge"** tab
   - Fill in the form:
     - Name: `NBFM_TEST`
     - Modulation: `NBFM (Narrowband FM)`
     - Frequency Mode: Choose one of:
       - **Single Frequency**: `146.550` MHz for a fixed frequency
       - **Named Ranges**: Select from predefined frequency ranges (e.g., "2 Meter Ham Band")
       - **Manual Range**: Specify custom min/max frequencies in MHz
     - Flag: Upload a WAV file or enter a path
     - Min Delay: `60` seconds
     - Max Delay: `120` seconds
     - Priority: `0` (higher number = higher priority)
     - Public Fields: Select which fields are visible on public dashboard
     - Enabled: Check the box
   - Click **"Create Challenge"**

3. **Alternative: Import from YAML**:
   - Select the **"Import from YAML"** tab
   - Upload a YAML file with your challenges
   - Optionally upload associated audio or binary files
   - Click **"Import Challenges"**

4. **Organize Challenges with Playlists** (Recommended):
   - Select the **"Playlist"** tab to group related challenges together
   - Create playlists to organize challenges by theme, difficulty, or frequency band
   - Enable or disable entire playlists at once for streamlined event management
   - Use playlists to create structured challenge rotations or themed segments during competitions

5. **Monitor Execution**:
   - Switch to the **"Live Status"** tab
   - View real-time challenge status and transmission counts
   - Use toggle switches to enable/disable individual challenges or entire playlists
   - Click "Trigger Now" to test transmissions immediately

For detailed information on challenge configuration, see the [Challenge Management Guide](Challenge-Management).

## Step 6: Verify Operation

1. **Log in to the Web Interface**: Navigate to your server (using the same address from Step 2) and log in with your admin credentials.

2. **View Logs for Troubleshooting**: Navigate to the Logs page to monitor real-time output from the server and all connected agents. This is particularly useful for diagnosing connection issues or transmission errors during initial setup.

3. **Check Agent Status**: Go to the Agents page to verify that your runner (and listener, if configured) is connected and showing a green status indicator.

4. **Monitor Transmissions**: Visit the Dashboard to see live statistics and the transmission feed, confirming that challenges are being assigned and transmitted successfully.

## Next Steps

Now that you have a basic setup running, you can:

- **Add more challenges** using the Manage Challenges page
- **Deploy runners** on additional SDR devices
- **Configure frequency limits** and device-specific settings
- **Set up a production deployment** with nginx as a reverse proxy

For detailed information on each of these topics, refer to the following guides:

- [Challenge Management](Challenge-Management) - Create and manage challenges via Web UI
- [Server Setup](Server-Setup) - Complete server configuration and deployment
- [Runner Setup](Runner-Setup) - Advanced runner configuration and troubleshooting
- [Web Interface Guide](Web-Interface-Guide) - Using the web dashboard
- [Configuration Reference](Configuration-Reference) - All available configuration options
- [Architecture Overview](Architecture) - Understanding how the system works

## Common Issues

### Runner Won't Connect

Verify that:
- The server URL in `runner-config.yml` is correct
- The enrollment token and API key were copied correctly from the Web UI
- The API key is correct (check the Web UI Runners page)
- The server is running and accessible from the runner machine
- No firewall is blocking port 8443
- Check runner logs for specific error messages

**Note**: The `enrollment_token` can be left in the config file - it's automatically ignored after successful enrollment.

### No Challenges Are Transmitting

Check that:
- At least one challenge is enabled (check Manage Challenges > Live Status tab)
- The runner's frequency limits include the challenge frequency
- Challenge files exist in the specified locations
- The runner device is properly connected

For more troubleshooting help, see the [Troubleshooting Guide](Troubleshooting).
