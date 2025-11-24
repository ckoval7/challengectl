# Agents Management

The Agents page displays all registered agents (runners and listeners) and their current status. The page includes three tabs:

1. **Runners**: View and manage runner (transmitter) agents (available to all users)
2. **Listeners**: View and manage listener (receiver) agents for spectrum capture (available to all users)
3. **Provisioning**: Create and manage enrollment tokens and provisioning API keys for automated agent deployment (requires `create_provisioning_key` permission)

## Runner List

Each runner shows:

**Runner ID**: Unique identifier for the runner

**Status**: Current connection state
- **Online** (green): Runner is active and sending heartbeats
- **Busy** (yellow): Runner is currently executing a transmission
- **Offline** (red): Runner has stopped sending heartbeats or disconnected

**Last Heartbeat**: Timestamp of the most recent heartbeat
- Updates in real-time
- Shows "Never" if runner registered but never sent a heartbeat

**Frequency Limits**: Supported frequency ranges
- Displayed as frequency ranges in Hz
- Determines which challenges this runner can accept

**Current Task**: Name of challenge currently being executed
- Shows "None" when idle
- Shows challenge name when busy

## Adding a New Runner

The **Add Runner** button allows you to enroll new runner agents through the web interface.

### Enrollment Steps

1. **Click "Add Runner"** button in the Runners tab
2. **Configure Runner Details**:
   - **Runner Name**: Unique identifier (e.g., `sdr-station-1`)
   - **Token Expiry**: Choose expiration time (1 hour, 6 hours, 24 hours, or 7 days)
   - **Verify SSL**: Enable/disable SSL verification (disable only for development)
3. **Configure SDR Devices** (optional):
   - Add one or more SDR devices
   - Select device model (HackRF, BladeRF, USRP, LimeSDR)
   - Configure RF gain, IF gain (HackRF only)
   - Set frequency limits
4. **Click "Generate Token"**

### Enrollment Credentials

After generation, you'll receive:
- **Enrollment Token**: Single-use token for initial registration
- **API Key**: Permanent credential for the runner
- **Complete YAML Configuration**: Ready-to-use `runner-config.yml`

**Important**: Copy or download these credentials immediately - they're only shown once!

### Using the Credentials

**Option 1 - Copy Configuration**:
- Click "Copy Configuration" to copy the complete YAML
- Save to `runner-config.yml` on your runner machine
- Start the runner: `python -m challengectl.runner.runner`

**Option 2 - Download File**:
- Click "Download as File" to save `runner-config.yml`
- Transfer to your runner machine
- Start the runner

The runner will automatically enroll on first connection using the enrollment token.

## Runner Actions

**Enable Runner**: Allow the runner to receive task assignments
- Enabled runners will be included in task distribution
- Button shows "Enabled" when active

**Disable Runner**: Prevent the runner from receiving new tasks
- Disabled runners remain connected but won't receive assignments
- Currently executing tasks continue to completion
- Use this for maintenance or troubleshooting
- Button shows "Disabled" when inactive

**Kick Runner**: Forcibly disconnect the runner
- Immediately removes the runner from the system
- Any assigned tasks are requeued
- The runner can re-register automatically
- Use this to resolve stuck runners or force a reconnection

## When to Disable vs Kick

**Disable a runner when**:
- Performing maintenance on the SDR hardware
- Troubleshooting signal quality issues
- Temporarily taking the device offline
- Testing with a subset of runners

**Kick a runner when**:
- The runner appears stuck or unresponsive
- Forcing a clean reconnection
- The runner's configuration has changed
- Clearing a stuck state

**Key difference**: Disabled runners stay connected but idle. Kicked runners are forcibly disconnected and must re-register.

## Listener List

The Listeners tab displays all registered listener agents and their spectrum capture status.

Each listener shows:

**Listener ID**: Unique identifier for the listener

**Status**: Current connection state
- **Online** (green): Listener is active and sending heartbeats
- **Offline** (red): Listener has stopped sending heartbeats or disconnected

**WebSocket**: Real-time connection status
- **Connected** (green badge): WebSocket active, can receive recording assignments
- **Disconnected** (yellow badge): WebSocket offline, cannot receive assignments
- Listeners require WebSocket connection for real-time recording coordination

**Last Heartbeat**: Timestamp of the most recent heartbeat
- Updates in real-time
- Shows "Never" if listener registered but never sent a heartbeat

**Recordings**: Total number of recordings captured by this listener

## Adding a New Listener

The **Add Listener** button allows you to enroll new listener agents through the web interface.

### Enrollment Steps

1. **Click "Add Listener"** button in the Listeners tab
2. **Configure Listener Details**:
   - **Listener Name**: Unique identifier (e.g., `listener-1`)
   - **Token Expiry**: Choose expiration time (1 hour, 6 hours, 24 hours, or 7 days)
3. **Configure SDR Devices** (optional):
   - Add one or more SDR receiver devices
   - For each device:
     - **Device Name**: Device index (0, 1, 2) or serial number
     - **Model**: Select SDR type (RTL-SDR, HackRF, USRP, BladeRF)
     - **Gain**: RF gain in dB (0-100, typical: 20-50)
     - **Frequency Limits**: Comma-separated ranges in Hz (optional)
   - Click **"Add Another Device"** to configure multiple receivers
   - Click **"Remove"** to remove a device from the configuration
4. **Click "Generate Token"**

### Enrollment Credentials

After generation, you'll receive:
- **Enrollment Token**: Single-use token for initial registration
- **API Key**: Permanent credential for the listener
- **Complete YAML Configuration**: Ready-to-use `listener-config.yml`

The generated configuration includes all required settings:
- Agent configuration (agent_id, server_url, api_key, WebSocket settings)
- Recording parameters (sample_rate: 2 MHz, fft_size: 1024, frame_rate: 20)
- SDR device configuration (multiple devices with gain and frequency limits)
- Pre/post roll buffers (5 seconds each)
- Logging configuration

**Multi-Device Support**: The configuration now supports multiple SDR receivers, allowing you to monitor different frequency bands simultaneously or provide redundancy.

**Important**: Copy or download these credentials immediately - they're only shown once!

### Using the Credentials

**Option 1 - Copy Configuration**:
- Click "Copy Configuration" to copy the complete YAML
- Save to `listener-config.yml` on your listener machine
- Install GNU Radio and dependencies (see [Listener Setup](Listener-Setup))
- Start the listener: `./listener/listener.py --config listener-config.yml`

**Option 2 - Download File**:
- Click "Download as File" to save `listener-config.yml`
- Transfer to your listener machine
- Install GNU Radio and dependencies
- Start the listener

The listener will automatically enroll on first connection using the enrollment token and connect via WebSocket for real-time recording assignments.

### Listener Actions

**Enable Listener**: Allow the listener to receive recording assignments
- Enabled listeners will be assigned recordings based on priority
- Button shows "Enabled" when active

**Disable Listener**: Prevent the listener from receiving new assignments
- Disabled listeners remain connected but won't receive recording tasks
- Currently executing recordings continue to completion
- Use this for maintenance or troubleshooting
- Button shows "Disabled" when inactive

**Kick Listener**: Forcibly disconnect the listener
- Immediately removes the listener from the system
- Any assigned recordings are marked as cancelled
- The listener can re-register automatically
- Use this to resolve stuck listeners or force a reconnection

### When to Disable vs Kick a Listener

**Disable a listener when**:
- Performing maintenance on the SDR hardware
- Adjusting antenna configuration
- Temporarily taking the device offline
- Testing with a subset of listeners

**Kick a listener when**:
- The listener appears stuck or unresponsive
- WebSocket connection is stale
- Forcing a clean reconnection
- The listener's configuration has changed
- Clearing a stuck state

## Real-Time Updates

The Agents page updates automatically via WebSocket connections:

**Runners tab**:
- Runner status changes (online, busy, offline)
- Last heartbeat timestamps
- Current task assignments

**Listeners tab**:
- Listener status changes (online, offline)
- WebSocket connection status
- Last heartbeat timestamps
- Recording counts

All changes are reflected in real-time without page refreshes.

## Troubleshooting

### Runner Issues

**Runner won't go online**:
1. Check the Runners tab for the runner
2. If listed but offline, check last heartbeat time
3. Check [Logs page](Web-Interface-Logs) for connection errors from that runner ID
4. Verify API key is correct
5. Consider kicking and letting it re-register

**Runner stuck in busy state**:
1. Check logs for errors from that runner
2. Verify the challenge hasn't stalled
3. Kick the runner to force a reconnection
4. Check runner system resources (CPU, SDR device)

### Listener Issues

**Listener won't go online**:
1. Check the Listeners tab for the listener
2. If listed but offline, check last heartbeat time
3. Check [Logs page](Web-Interface-Logs) for connection errors
4. Verify listener process is running on the listener machine
5. Consider kicking and letting it re-register

**WebSocket shows "Disconnected"**:
1. Check listener logs for WebSocket errors
2. Verify firewall allows outbound WebSocket connections
3. Check server logs for connection rejections
4. Restart listener process
5. Kick listener from web UI to force reconnection

**No recordings being assigned**:
1. Verify listener is enabled (not disabled)
2. Check WebSocket shows "Connected"
3. Verify transmissions are occurring (check Dashboard)
4. Recording priority may be below threshold (see [Architecture](Architecture#recording-priority-algorithm))
5. Check listener logs for assignment messages

## Related Guides

- [Dashboard](Web-Interface-Dashboard) - View agent statistics and transmission feed
- [Challenges](Web-Interface-Challenges) - Manage challenges assigned to runners
- [Logs](Web-Interface-Logs) - View agent log output
- [Runner Setup](Runner-Setup) - Configure and deploy runner agents
- [Listener Setup](Listener-Setup) - Configure and deploy listener agents
- [System Controls](Web-Interface-System-Controls) - Pause system to stop task assignment
