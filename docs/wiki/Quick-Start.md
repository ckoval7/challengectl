# Quick Start Guide

This guide will help you get ChallengeCtl up and running in the shortest time possible. For more detailed setup instructions, refer to the [Server Setup](Server-Setup) and [Runner Setup](Runner-Setup) guides.

## Prerequisites

Before you begin, ensure you have the following:

- Python 3.8 or higher
- For runners: SDR hardware (HackRF, LimeSDR, or compatible device)
- For runners: GNU Radio 3.8 or higher with gr-osmosdr, gr-paint, and gr-mixalot
- Basic understanding of software defined radio concepts

**Note**: Runners require additional GNU Radio modules that must be compiled from source. See the [Runner Setup Guide](Runner-Setup#install-system-dependencies) for detailed installation instructions.

## Step 1: Install Dependencies

Clone the repository and install the required Python packages:

```bash
git clone https://github.com/ckoval7/challengectl.git
cd challengectl

# For server only
pip install -r requirements-server.txt

# For runners, also install GNU Radio and compile gr-paint and gr-mixalot
# See the Runner Setup guide for detailed instructions
pip install -r requirements-runner.txt
```

**Important for runners**: You must install GNU Radio, gr-osmosdr, gr-paint, and gr-mixalot before running a runner. These cannot be installed via pip. See the [Runner Setup Guide](Runner-Setup) for complete instructions.

## Step 2: Set Up the Server

### Configure the Server

Create a `server-config.yml` file with minimal configuration:

```yaml
server:
  bind: "0.0.0.0"
  port: 8443
```

**Note**: Challenges can be configured through the Web UI or in the YAML file. See [Challenge Management](Challenge-Management) for details on using the Web UI.

To configure challenges in the YAML file, you can add them like this:

```yaml
challenges:
  - name: NBFM_Example
    frequency: 146550000
    modulation: nbfm
    flag: challenges/example.wav
    min_delay: 60
    max_delay: 120
    enabled: true
```

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

2. **Navigate to** `http://localhost:8443` in your web browser

3. **Log in** with the temporary credentials

4. **Complete the setup wizard**:
   - Create your admin user with a strong password
   - Set up TOTP two-factor authentication by scanning the QR code
   - Log out and log back in with your new account

5. **Enroll your first runner**:
   - Go to the **Runners** page in the Web UI
   - Click **"Add Runner"**
   - Enter a runner name (e.g., "runner-1")
   - Optionally configure SDR devices (model, RF gain, IF gain, frequency limits)
   - Click **"Generate Token"**
   - **IMPORTANT**: Copy both the enrollment token and API key - they're only shown once!
   - You can also copy the complete YAML configuration from the dialog
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

Create a `runner-config.yml` file using the credentials from Step 2:

```yaml
runner:
  runner_id: "runner-1"
  server_url: "http://localhost:8443"
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

**Note**: The `enrollment_token` can be left in the config file. After the first successful enrollment, it will be ignored on subsequent runs.

### Start the Runner

```bash
python -m challengectl.runner.runner
```

The runner will register with the server and begin polling for tasks.

## Step 4: Configure Challenges

Now that the server and runner are connected, you can configure challenges through the Web UI:

1. **Navigate to "Configure Challenges"**: Click the "Configure Challenges" menu item in the left sidebar.

2. **Create your first challenge**:
   - Select the **"Create Challenge"** tab
   - Fill in the form:
     - Name: `NBFM_TEST`
     - Modulation: `NBFM (Narrowband FM)`
     - Frequency: `146550000` (146.55 MHz)
     - Flag: Upload a WAV file or enter a path
     - Min Delay: `60` seconds
     - Max Delay: `120` seconds
     - Enabled: Check the box
   - Click **"Create Challenge"**

3. **Alternative: Import from YAML**:
   - Select the **"Import from YAML"** tab
   - Upload a YAML file with your challenges
   - Optionally upload associated audio or binary files
   - Click **"Import Challenges"**

For detailed information on challenge configuration, see the [Challenge Management Guide](Challenge-Management).

## Step 5: Verify Operation

1. **Log in to the Web Interface**: Navigate to `http://localhost:8443` and log in with your admin credentials.

2. **Check Runner Status**: Go to the Runners page to verify that your runner is connected and showing a green status.

3. **Monitor Transmissions**: Visit the Dashboard to see live statistics and the transmission feed.

4. **View Logs**: Check the Logs page for real-time output from the server and runners.

## Next Steps

Now that you have a basic setup running, you can:

- **Add more challenges** using the Configure Challenges page
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
- At least one challenge is enabled (check the Challenges page or Configure Challenges page)
- The runner's frequency limits include the challenge frequency
- Challenge files exist in the specified locations
- The runner device is properly connected

For more troubleshooting help, see the [Troubleshooting Guide](Troubleshooting).
