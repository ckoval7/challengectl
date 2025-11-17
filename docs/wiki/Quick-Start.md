# Quick Start Guide

This guide will help you get ChallengeCtl up and running in the shortest time possible. For more detailed setup instructions, refer to the [Server Setup](Server-Setup) and [Runner Setup](Runner-Setup) guides.

## Prerequisites

Before you begin, ensure you have the following:

- Python 3.8 or higher
- For runners: SDR hardware (HackRF, LimeSDR, or compatible device)
- Basic understanding of software defined radio concepts

## Step 1: Install Dependencies

Clone the repository and install the required Python packages:

```bash
git clone https://github.com/ckoval7/challengectl.git
cd challengectl
pip install -r requirements.txt
```

## Step 2: Set Up the Server

### Initialize the Database

```bash
python -m challengectl.server.database init
```

This creates a new SQLite database with the required schema.

### Create an Admin User

```bash
python -m challengectl.server.database add-user admin
```

You'll be prompted to set a password. The system will generate a TOTP secret for two-factor authentication. Save this secret in your authenticator app.

### Create a Runner API Key

```bash
python -m challengectl.server.database add-runner-key runner1
```

Save the generated API key. You'll need it to configure your runner.

### Configure the Server

Create a `server-config.yml` file:

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

The server will start on port 8443. Access the web interface at `http://localhost:8443`.

## Step 3: Set Up a Runner

### Configure the Runner

Create a `runner-config.yml` file:

```yaml
runner:
  runner_id: "runner-1"
  server_url: "http://localhost:8443"
  api_key: "your-api-key-from-step-2"
  poll_interval: 5
  heartbeat_interval: 30

devices:
  - name: 0
    model: hackrf
    frequency_limits:
      - "144000000-148000000"
```

Replace `your-api-key-from-step-2` with the API key you generated earlier.

### Start the Runner

```bash
python -m challengectl.runner.runner
```

The runner will register with the server and begin polling for tasks.

## Step 4: Verify Operation

1. **Log in to the Web Interface**: Navigate to `http://localhost:8443` and log in with your admin credentials.

2. **Check Runner Status**: Go to the Runners page to verify that your runner is connected and showing a green status.

3. **Monitor Transmissions**: Visit the Dashboard to see live statistics and the transmission feed.

4. **View Logs**: Check the Logs page for real-time output from the server and runners.

## Next Steps

Now that you have a basic setup running, you can:

- Add more challenges to your server configuration
- Deploy runners on additional SDR devices
- Configure frequency limits and device-specific settings
- Set up a production deployment with nginx as a reverse proxy

For detailed information on each of these topics, refer to the following guides:

- [Server Setup](Server-Setup) - Complete server configuration and deployment
- [Runner Setup](Runner-Setup) - Advanced runner configuration and troubleshooting
- [Configuration Reference](Configuration-Reference) - All available configuration options
- [Architecture Overview](Architecture) - Understanding how the system works

## Common Issues

### Runner Won't Connect

Verify that:
- The server URL in `runner-config.yml` is correct
- The API key matches one in the database
- The server is running and accessible from the runner machine
- No firewall is blocking port 8443

### No Challenges Are Transmitting

Check that:
- At least one challenge is enabled in `server-config.yml`
- The runner's frequency limits include the challenge frequency
- Challenge files exist in the specified locations
- The runner device is properly connected

For more troubleshooting help, see the [Troubleshooting Guide](Troubleshooting).
