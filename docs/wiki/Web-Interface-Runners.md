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
