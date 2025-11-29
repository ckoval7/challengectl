# Agents Management

The Agents page displays all registered agents, including both runners and listeners, along with their current status. The page organizes this information across three tabs to provide clear access to different agent types and provisioning functionality.

The Runners tab displays all runner (transmitter) agents and is available to all users. The Listeners tab shows all listener (receiver) agents for spectrum capture and is also available to all users. The Provisioning tab allows creation and management of enrollment tokens and provisioning API keys for automated agent deployment, but requires the `create_provisioning_key` permission.

## Runner List

Each runner in the list displays comprehensive information about its current state. The Runner ID serves as a unique identifier for the runner. The Status field shows the current connection state using color-coded indicators. An online status displayed in green indicates the runner is active and sending heartbeats. A busy status shown in yellow means the runner is currently executing a transmission. An offline status in red indicates the runner has stopped sending heartbeats or disconnected from the system.

The Last Heartbeat field displays the timestamp of the most recent heartbeat, updating in real-time. If a runner has registered but never sent a heartbeat, this field shows "Never". The Frequency Limits field shows the supported frequency ranges in hertz, which determine which challenges this runner can accept. The Current Task field displays the name of the challenge currently being executed, or shows "None" when the runner is idle.

## Adding a New Runner

The Add Runner button in the Runners tab allows you to enroll new runner agents through the web interface. To add a runner, click the "Add Runner" button and configure the runner details in the dialog that appears.

Begin by entering a unique identifier for the runner in the Runner Name field, such as "sdr-station-1". Select an expiration time for the enrollment token from the options provided, which include one hour, six hours, 24 hours, or seven days. Choose whether to verify SSL certificates, disabling this option only for development environments where self-signed certificates are in use.

You can optionally configure SDR devices during the enrollment process. Add one or more SDR devices by selecting the device model from the available options, which include HackRF, BladeRF, USRP, and LimeSDR. Configure the RF gain and IF gain (for HackRF only) according to your hardware requirements. Set the frequency limits that define the operational range for this device. Click "Generate Token" when configuration is complete.

After generation, the system displays enrollment credentials that you must copy or download immediately, as they are shown only once. The enrollment token provides single-use authentication for initial registration. The API key serves as a permanent credential for the runner after enrollment. The system also provides a complete YAML configuration that is ready to use as your `runner-config.yml` file.

To use these credentials, you have two options. For the first option, click "Copy Configuration" to copy the complete YAML to your clipboard. Save this content to `runner-config.yml` on your runner machine, then start the runner using `python -m challengectl.runner.runner`. For the second option, click "Download as File" to save the configuration as `runner-config.yml` directly. Transfer this file to your runner machine and start the runner. The runner will automatically enroll on first connection using the enrollment token.

## Runner Actions

The interface provides several actions for managing runners. The Enable Runner action allows the runner to receive task assignments, including it in task distribution. When enabled, the button displays "Enabled" to indicate the active state.

The Disable Runner action prevents the runner from receiving new tasks while keeping it connected. Disabled runners remain connected but will not receive assignments, and currently executing tasks continue to completion. Use this action for maintenance or troubleshooting purposes. When disabled, the button displays "Disabled" to indicate the inactive state.

The Kick Runner action forcibly disconnects the runner from the system. This immediately removes the runner, requeues any assigned tasks, and allows the runner to re-register automatically. Use this action to resolve stuck runners or force a clean reconnection.

## When to Disable vs Kick

Understanding when to use each action helps maintain system stability. Disable a runner when performing maintenance on the SDR hardware, troubleshooting signal quality issues, temporarily taking the device offline, or testing with a subset of runners. Disabled runners stay connected but idle, making them immediately available when re-enabled.

Kick a runner when it appears stuck or unresponsive, when forcing a clean reconnection is necessary, when the runner's configuration has changed and needs to be reloaded, or when clearing a stuck state. The key difference is that disabled runners stay connected but idle, while kicked runners are forcibly disconnected and must re-register to continue operating.

## Listener List

The Listeners tab displays all registered listener agents along with their spectrum capture status. Each listener entry provides detailed information about its operational state.

The Listener ID serves as a unique identifier for the listener. The Status field shows the current connection state using color-coded indicators. An online status displayed in green indicates the listener is active and sending heartbeats. An offline status in red means the listener has stopped sending heartbeats or disconnected from the system.

The WebSocket field displays the real-time connection status with distinct visual indicators. A connected status shown with a green badge means the WebSocket is active and the listener can receive recording assignments. A disconnected status displayed with a yellow badge indicates the WebSocket is offline and the listener cannot receive assignments. Listeners require an active WebSocket connection for real-time recording coordination.

The Last Heartbeat field shows the timestamp of the most recent heartbeat, updating in real-time. If a listener has registered but never sent a heartbeat, this field displays "Never". The Recordings field shows the total number of recordings captured by this listener.

## Adding a New Listener

The Add Listener button in the Listeners tab enables enrollment of new listener agents through the web interface. To add a listener, click the "Add Listener" button and configure the listener details in the dialog.

Enter a unique identifier for the listener in the Listener Name field, such as "listener-1". Select an expiration time for the enrollment token from the available options of one hour, six hours, 24 hours, or seven days.

You can optionally configure SDR devices for the listener. Add one or more SDR receiver devices by specifying the device name, which can be a device index (0, 1, 2) or a serial number. Select the SDR type from the available models, including RTL-SDR, HackRF, USRP, and BladeRF. Configure the RF gain in decibels, typically ranging from zero to 100 with typical values between 20 and 50 dB. Optionally specify frequency limits as comma-separated ranges in hertz. Click "Add Another Device" to configure multiple receivers, or click "Remove" to remove a device from the configuration. When ready, click "Generate Token" to create the enrollment credentials.

After generation, the system provides enrollment credentials that must be copied or downloaded immediately. The enrollment token provides single-use authentication for initial registration. The API key serves as a permanent credential for the listener. The complete YAML configuration includes all required settings ready to use as your `listener-config.yml` file.

The generated configuration includes comprehensive settings for the listener. Agent configuration specifies the agent ID, server URL, API key, and WebSocket settings. Recording parameters define the sample rate at 2 MHz, FFT size at 1024, and frame rate at 20 frames per second. SDR device configuration includes all devices with their gain and frequency limits. Pre and post roll buffers are set to five seconds each. Logging configuration provides appropriate verbosity for troubleshooting.

Multi-device support allows the configuration to accommodate multiple SDR receivers, enabling you to monitor different frequency bands simultaneously or provide redundancy for critical monitoring tasks.

To use these credentials, click "Copy Configuration" to copy the complete YAML to your clipboard. Save this to `listener-config.yml` on your listener machine. Install GNU Radio and dependencies as described in the Listener Setup guide. Start the listener using `./listener/listener.py --config listener-config.yml`. Alternatively, click "Download as File" to save the configuration as `listener-config.yml` directly. Transfer this file to your listener machine, install GNU Radio and dependencies, and start the listener. The listener will automatically enroll on first connection using the enrollment token and connect via WebSocket for real-time recording assignments.

### Listener Actions

The interface provides several actions for managing listeners. The Enable Listener action allows the listener to receive recording assignments based on priority, with the button displaying "Enabled" when active.

The Disable Listener action prevents the listener from receiving new assignments while keeping it connected. Disabled listeners remain connected but will not receive recording tasks. Currently executing recordings continue to completion. Use this action for maintenance or troubleshooting purposes, with the button displaying "Disabled" when inactive.

The Kick Listener action forcibly disconnects the listener from the system. This immediately removes the listener, marks any assigned recordings as cancelled, and allows the listener to re-register automatically. Use this action to resolve stuck listeners or force a clean reconnection.

### When to Disable vs Kick a Listener

Disable a listener when performing maintenance on the SDR hardware, adjusting antenna configuration, temporarily taking the device offline, or testing with a subset of listeners. Kick a listener when it appears stuck or unresponsive, when the WebSocket connection is stale, when forcing a clean reconnection is necessary, when the listener's configuration has changed, or when clearing a stuck state.

## Real-Time Updates

The Agents page updates automatically via WebSocket connections, ensuring you always see current information without manual refreshing.

In the Runners tab, the interface automatically reflects runner status changes between online, busy, and offline states. Last heartbeat timestamps update continuously, and current task assignments appear immediately when runners begin work.

In the Listeners tab, the interface shows listener status changes between online and offline states in real-time. WebSocket connection status updates immediately when connections are established or lost. Last heartbeat timestamps update continuously, and recording counts increment as listeners complete captures.

All changes reflect in real-time without requiring page refreshes, providing an always-current view of your agent infrastructure.

## Troubleshooting

### Runner Issues

When a runner refuses to go online, start by checking the Runners tab for the runner entry. If the runner is listed but offline, check the last heartbeat time to determine how long it has been disconnected. Review the Logs page for connection errors from that runner ID. Verify that the API key configured on the runner matches the one stored in the database. Consider kicking the runner to force re-registration, which often resolves authentication or connection issues.

When a runner becomes stuck in busy state, first check the logs for errors from that runner. Verify that the assigned challenge has not stalled during execution. Kick the runner to force a reconnection and clear the stuck state. Check runner system resources including CPU usage and SDR device availability to ensure the hardware can support continued operation.

### Listener Issues

When a listener refuses to go online, check the Listeners tab for the listener entry. If listed but offline, examine the last heartbeat time to determine connection duration. Review the Logs page for connection errors from the listener. Verify that the listener process is running on the listener machine. Consider kicking the listener to allow re-registration.

When the WebSocket shows "Disconnected", first check listener logs for WebSocket errors that might indicate the cause. Verify that the firewall allows outbound WebSocket connections from the listener machine. Check server logs for connection rejections that might indicate authentication or authorization issues. Restart the listener process to re-establish the connection. Use the kick function from the web UI to force reconnection from the server side.

When no recordings are being assigned to a listener, verify the listener is enabled and not disabled. Check that the WebSocket shows "Connected", as this is required for receiving assignments. Verify that transmissions are occurring by checking the Dashboard's recent transmissions feed. Note that recording priority may be below the threshold for assignment, as described in the Architecture documentation under recording priority algorithm. Check listener logs for assignment messages that indicate whether the listener is receiving and processing recording requests.

## Related Guides

For viewing agent statistics and the transmission feed, see the Dashboard guide. For managing challenges assigned to runners, consult the Challenge Management guide. To view agent log output for troubleshooting, see the Logs guide. For instructions on configuring and deploying runner agents, review the Runner Setup guide. For configuring and deploying listener agents, see the Listener Setup guide. To pause the system and stop task assignment, refer to the System Controls guide.
