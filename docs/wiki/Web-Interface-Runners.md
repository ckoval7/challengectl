# Runners Management

The Runners page displays all registered runners and their current status. The page includes two tabs:

1. **Runners**: View and manage runner connections (available to all users)
2. **Provisioning Keys**: Create and manage provisioning API keys for automated runner deployment (requires `create_provisioning_key` permission)

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

## Real-Time Updates

The Runners page updates automatically via WebSocket connections:
- Runner status changes (online, busy, offline)
- Last heartbeat timestamps
- Current task assignments

All changes are reflected in real-time without page refreshes.

## Troubleshooting

**Runner won't go online**:
1. Check the Runners page for the runner
2. If listed but offline, check last heartbeat time
3. Check [Logs page](Web-Interface-Logs) for connection errors from that runner ID
4. Consider kicking and letting it re-register

**Runner stuck in busy state**:
1. Check logs for errors from that runner
2. Verify the challenge hasn't stalled
3. Kick the runner to force a reconnection
4. Check runner system resources

## Related Guides

- [Dashboard](Web-Interface-Dashboard) - View runner statistics
- [Challenges](Web-Interface-Challenges) - Manage challenges assigned to runners
- [Logs](Web-Interface-Logs) - View runner log output
- [System Controls](Web-Interface-System-Controls) - Pause system to stop task assignment
