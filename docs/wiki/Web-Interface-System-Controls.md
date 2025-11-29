# System Controls

System controls affect the entire ChallengeCtl server and all connected runners, providing system-wide operational management.

## Accessing System Controls

System control buttons are located in the header bar at the top of every page for easy access regardless of which section of the interface you are viewing. The Pause button appears when the system is running normally, displayed in yellow to indicate the available action. The Resume button appears when the system is paused, displayed in green and replacing the Pause button to show the inverse action is available. Button state synchronizes in real-time across all connected admin sessions via WebSocket, ensuring all administrators see the current system state. The initial state is loaded when the page loads, ensuring the button always displays the correct state immediately.

## Pause vs Disable

Understanding the differences between these operations is critical for effective system management.

### Pause System

The pause operation provides a controlled system-wide halt of challenge distribution. When you pause the system, it stops queuing new challenges while allowing currently executing transmissions to complete normally. Runners remain connected to the server and continue sending heartbeats, maintaining their registration. The web interface remains fully accessible for monitoring and configuration. No data is lost during pause, as all state is preserved in the database.

Use the pause operation when taking a break during a CTF event, waiting for an issue to be resolved before resuming operations, coordinating activities with CTF participants, or performing non-invasive maintenance that does not require stopping runners. To resume from a pause, click the "Resume" button. Challenge queueing resumes immediately and the system returns to normal operation without any additional steps required.

The pause operation affects different system components in specific ways. Active transmissions continue to completion normally, ensuring no partial or interrupted transmissions occur. Waiting challenges remain in the waiting state and are not reassigned, preserving their place in the queue. Queued challenges stop advancing to the waiting state until the system is resumed. Runners stay connected and idle, ready to accept work as soon as the system resumes. The web UI remains fully functional throughout the pause, allowing monitoring and configuration changes.

To shut down the ChallengeCtl server entirely, use Control-C in the terminal where the server is running, or use `systemctl stop challengectl` if running as a systemd service. Pause does not shut down the server.

### Disable (Runner-specific)

The disable operation affects only a specific runner rather than the entire system. When you disable a runner, it prevents that specific runner from receiving new tasks while leaving it connected to the system. The runner remains connected and continues sending heartbeats to maintain registration. Any active transmission on that runner completes normally. Other runners in the system are completely unaffected and continue normal operation.

Use runner disable when troubleshooting a specific runner, performing SDR hardware maintenance on that device, adjusting antenna or device settings for that runner, or testing with a subset of runners while keeping others operational. To resume, click the "Enable" button on the specific runner.

The disable operation affects system components differently than pause. The disabled runner's active transmission completes normally without interruption. The disabled runner receives no new task assignments until re-enabled. Other runners continue normal operation and receive tasks as usual. The system as a whole continues normal operation without interruption.

## Comparison Table

| Operation | New Tasks | Active Tasks | Runners Connected | Web UI | Restart Required |
|-----------|-----------|--------------|-------------------|--------|------------------|
| **Pause** | Stopped | Complete | Yes | Yes | No |
| **Stop** | Stopped | Requeued | Yes | Yes | No |
| **Disable Runner** | Stopped (1 runner) | Complete | Yes | Yes | No |

## Reload Configuration

The reload configuration operation provides runtime configuration updates without requiring a server restart. When you reload configuration, the server reads the server-config.yml file from disk and updates challenge definitions accordingly. This operation adds new challenges defined in the configuration file to the system. It updates parameters for existing challenges that are defined in the config file. The operation does not require stopping the server or disconnecting runners.

Use reload configuration when adding new challenges during an event without interrupting operations, adjusting minimum and maximum delay values to fine-tune transmission frequency, enabling or disabling challenges through the config file rather than the web UI, or fixing challenge file paths that were incorrectly specified.

The reload operation does not affect certain aspects of the system. Runner connections remain active and unchanged. Active transmissions continue to completion without interruption. Server settings such as port and CORS configuration cannot be changed without restart. Database state remains unchanged by this operation. User accounts and authentication configuration require restart to modify.

Reload configuration has several limitations that require full server restart to address. You cannot change the server port or network binding through reload. You cannot change the database location or connection parameters. You cannot modify API keys, as these are loaded only at startup. Any changes to these settings require stopping and restarting the server process.

## Conference Settings

The Conference Settings card on the Dashboard allows you to configure conference-specific features including daily operating hours, countdown timers, and automatic pause and resume functionality.

### Accessing Conference Settings

Conference Settings are located on the Dashboard page in a dedicated card positioned below the Runners table in the left column. This placement provides easy access to frequently-used event management controls.

### Conference Name and Countdown

The conference name and countdown timer appear in both the admin and public page headers, providing consistent visibility of event timing. The admin header displays the conference name and countdown in the format "ChallengeCtl Control Center - ExampleCon" with "Ends in: 1d 12h 30m 45s". The public dashboard header shows "Live Challenge Status" with countdown information such as "Starts in: 2d 5h 30m 45s".

The countdown displays different states based on the conference timeline. Before conference start, it shows "Starts in: X" and counts down to the conference start time defined in the configuration. During the conference, it shows "Ends in: X" and counts down to the conference end time. An additional timer appears when operating within configured daily hours, as described below. After the conference concludes, it displays "ExampleCon RFCTF has ended" in red text, clearly indicating event completion.

### Daily Operating Hours

Daily operating hours configuration creates a countdown cycle for multi-day conferences, providing fine-grained control over event timing.

#### Day Start Time

The day start time setting defines when daily operating hours begin each day. To configure this, use the time picker to select a time at 15-minute intervals. The format follows HH:MM notation, such as "09:00". The timezone used is the conference timezone specified in config.yml. For example, set this to "09:00" for a 9 AM daily start.

#### End of Day Time

The end of day time setting defines when daily operating hours conclude each day. Use the time picker to select a time at 15-minute intervals in HH:MM format, such as "17:00". The timezone follows the conference timezone from config.yml. For example, set this to "17:00" for a 5 PM daily end.

#### Daily Countdown Cycle

When both day start and end times are configured, the countdown behavior changes based on the current time of day. During daily hours, such as 9 AM to 5 PM, the countdown displays "Ends in: 1d 12h 30m | Day ends: 4h 30m 15s". The main countdown shows time until the conference ends entirely. The secondary countdown shows time until the end of the current day's operating hours.

Outside daily hours, such as 5 PM to 9 AM, the countdown displays "Day starts in: 15h 30m 45s", showing the countdown to when the next day begins. This countdown only appears during the conference period, not before or after the overall event.

The system handles overnight ranges correctly, supporting configurations such as 10:00 PM to 6:00 AM. The countdown automatically calculates the correct time remaining across the midnight boundary.

#### Saving Daily Times

The Save button applies both day start and end of day times when clicked. Changes take effect immediately without requiring any server restart. The countdown updates for all users in real-time via WebSocket. No service interruption occurs when saving these settings.

The Clear Both button removes both day start and end of day settings simultaneously. This disables the daily countdown cycle entirely, reverting the interface to display only the simple conference-wide countdown without daily hour tracking.

The system validates time inputs to ensure correctness. Times must be in HH:MM format following 24-hour clock notation. Invalid times result in an error message preventing submission. Both times can be set independently, though both are required for daily countdown cycle functionality.

### Auto-Pause Daily

Auto-pause daily functionality automatically pauses and resumes the system based on configured daily operating hours, reducing manual intervention for multi-day events.

#### How Auto-Pause Works

When enabled, the system automatically pauses at the configured end of day time. The system automatically resumes at the configured day start time. This process runs in the background every 30 seconds, checking whether auto-pause actions are needed. The functionality operates across multiple days during the conference period without manual intervention.

Timezone handling ensures correct operation regardless of server location. Auto-pause uses the conference timezone specified in config.yml rather than the server's local timezone. The timezone offset is extracted from the conference start time, such as extracting "-5" from "2024-04-05 09:00:00 -5". Daily times like 09:00 and 17:00 are interpreted in this conference timezone. The system correctly handles pause and resume timing regardless of the server's local timezone setting.

For auto-pause to function, several requirements must be met. Both day start and end of day times must be configured. The auto-pause toggle must be enabled in the interface. The conference timezone must be specified in the config.yml start time field using the offset notation.

#### Enabling Auto-Pause

The auto-pause toggle switch is located below the day time pickers in the Conference Settings card. Click the switch to enable or disable the functionality. Changes save immediately without confirmation dialogs. The switch label reads "Automatically pause transmissions outside daily hours" to clearly indicate its purpose.

When enabled, the system automatically pauses at end of day time, such as 5:00 PM in the conference timezone. The system automatically resumes at day start time, such as 9:00 AM in the conference timezone. Live UI updates occur via WebSocket, showing the pause state change to all connected administrators. All connected admins see notifications when auto-pause or auto-resume occurs.

When disabled, the system runs continuously 24 hours per day, 7 days per week. Manual pause and resume functionality still works normally. The daily countdown continues to function if configured, providing timing information without affecting system state.

#### Manual Override

The manual Pause/Resume button in the header always works and can override auto-pause behavior when needed. When you manually pause the system at any time, it pauses immediately regardless of daily hour configuration. The system will not automatically resume when you have manually paused, respecting your explicit override. You must click "Resume" to start transmissions again when ready.

When you manually resume during an auto-pause period, the system resumes immediately allowing operations outside normal hours. Auto-pause will pause again at the next end of day time if you are still outside configured hours. This allows manual override for testing or special events while maintaining automatic scheduling.

Auto-pause behavior follows specific rules to prevent conflicts. Auto-pause only auto-resumes if it was the system that initiated the pause. The system will not override manual pause with auto-resume functionality. Manual resume during off-hours is explicitly allowed for testing and special circumstances.

#### WebSocket Notifications and State Sync

All connected admin users receive real-time notifications and button state updates when auto-pause actions occur. When an auto-pause event occurs, all administrators see an informational notification reading "System auto-paused (outside daily hours)". The Pause button changes to a Resume button for all connected administrators simultaneously. The notification appears in blue indicating informational status.

When an auto-resume event occurs, all administrators see an informational notification reading "System auto-resumed (within daily hours)". The Resume button changes to a Pause button for all connected administrators simultaneously. The notification appears in blue indicating informational status.

Manual pause and resume operations use standard success messages displayed in green. These messages do not include the "auto" prefix, distinguishing them from automatic actions. Button state synchronizes across all connected admin sessions via WebSocket, ensuring consistent interface state. If one administrator pauses the system, all administrators immediately see the Resume button without requiring page refresh.

Initial state loading occurs when you load any page. The pause button state is fetched from the server to ensure accuracy. The button always shows the correct current state, either Pause or Resume. No manual refresh is needed to see the current system state.

### Configuration Workflow

A typical conference setup follows a logical sequence. First, set conference times in config.yml by defining the conference section with name, start time, and stop time. The start and stop times should include timezone offset notation, such as "2024-04-05 09:00:00 -5" and "2024-04-07 17:00:00 -5".

Next, configure daily hours through the Dashboard interface. Set the day start time, such as 09:00 for a 9 AM start. Set the end of day time, such as 17:00 for a 5 PM end. Click the "Save" button to apply these times to the system.

Optionally enable auto-pause functionality by toggling the "Auto-Pause Daily" switch to the on position. The system will now automatically pause and resume based on the configured hours.

Monitor the system by checking the countdown in the header to verify correct configuration. Watch for auto-pause notifications at the configured times to confirm operation. Use manual pause and resume as needed to override automatic behavior for special circumstances.

### Runtime Configuration

All conference settings support runtime configuration without requiring server restart. Changing day start and end times takes effect immediately when you click Save. Toggling auto-pause on or off applies instantly without delay. Updates propagate to all users in real-time via WebSocket. All administrators see changes immediately without manual refresh.

Settings are persistently stored in the database using the system_state table, ensuring they survive server restarts. Settings can be changed during live events without service interruption. Config.yml values serve as defaults when database settings are not present, providing a fallback mechanism.

The override order follows a clear hierarchy. First priority is the database setting from the web UI, allowing runtime changes. Second priority is the config.yml setting, serving as a fallback if no database value exists. If neither is set, the feature is disabled entirely.

### Best Practices

When setting daily hours, match your event schedule such as 9 AM to 5 PM for typical work hours. Account for setup and teardown time by extending hours slightly beyond core event times. Consider participant time zones when selecting hours for geographically distributed events. Test the configuration using manual trigger before enabling auto-pause to ensure correct operation.

When using auto-pause, enable this feature for multi-day events with clearly defined operating hours. Automatic pause reduces power consumption overnight when no operations are occurring. It prevents confusion about "dead air" periods when participants expect challenges. Use manual override for testing challenges outside normal hours without disabling the feature.

During active events, avoid changing times during active hours to prevent disruption. Wait for breaks or off-hours periods to adjust configuration. Manual pause and resume remain always available regardless of auto-pause configuration. Monitor WebSocket notifications to confirm auto-pause is functioning as expected. Check that the countdown displays correct times to validate timezone configuration.

For testing new configuration, set day times close to the current time, such as current time plus 2 minutes, to verify behavior without waiting. Enable auto-pause and observe system behavior. Wait for the auto-pause notification to confirm the feature is working. Test manual resume override to ensure manual control remains functional. Adjust times to the actual schedule once testing is complete and behavior is verified.

## Related Guides

For viewing the conference settings card interface, see the Dashboard guide. To understand the effect of pause on challenge execution and queueing, consult the Challenges guide. For understanding how pause affects runner task assignment and status, review the Runners guide. To learn about WebSocket notifications for auto-pause events, see the Advanced Topics guide.
