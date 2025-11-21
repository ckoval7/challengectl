# System Controls

System controls affect the entire ChallengeCtl server and all runners.

## Accessing System Controls

System control buttons are located in the **header bar** at the top of every page:

- **Pause button**: Visible when system is running normally (yellow)
- **Resume button**: Visible when system is paused (green, replaces Pause button)
- Button state syncs in real-time across all connected admin sessions via WebSocket
- Initial state is loaded when the page loads to show correct button

## Pause vs Disable

Understanding the differences between these operations is critical:

### Pause System

**What it does**:
- Stops queuing new challenges
- Allows currently executing transmissions to complete
- Runners remain connected and send heartbeats
- Web interface remains accessible
- No data is lost

**When to use**:
- Taking a break during a CTF event
- Waiting for an issue to be resolved
- Coordinating with CTF participants
- Performing non-invasive maintenance

**How to resume**:
- Click "Resume" button
- Challenge queueing resumes immediately
- System returns to normal operation

**Effect on**:
- **Active transmissions**: Continue to completion
- **Waiting challenges**: Remain in waiting state (not reassigned)
- **Queued challenges**: Stop advancing to waiting state
- **Runners**: Stay connected and idle
- **Web UI**: Fully functional

**Note**: To shut down the ChallengeCtl server, use `Ctrl+C` in the terminal or `systemctl stop challengectl` if running as a service.

### Disable (Runner-specific)

**What it does**:
- Prevents a specific runner from receiving new tasks
- Runner remains connected
- Runner continues sending heartbeats
- Active transmission on that runner completes
- Other runners are unaffected

**When to use**:
- Troubleshooting a specific runner
- SDR hardware maintenance
- Adjusting antenna or device settings
- Testing with subset of runners

**How to resume**:
- Click "Enable" on the runner

**Effect on**:
- **This runner's active transmission**: Completes normally
- **This runner's new tasks**: None assigned
- **Other runners**: Unaffected
- **System**: Continues normal operation

## Comparison Table

| Operation | New Tasks | Active Tasks | Runners Connected | Web UI | Restart Required |
|-----------|-----------|--------------|-------------------|--------|------------------|
| **Pause** | Stopped | Complete | Yes | Yes | No |
| **Stop** | Stopped | Requeued | Yes | Yes | No |
| **Disable Runner** | Stopped (1 runner) | Complete | Yes | Yes | No |

## Reload Configuration

**What it does**:
- Reloads `server-config.yml` from disk
- Updates challenge definitions
- Adds new challenges
- Updates parameters for existing challenges
- Does not require server restart

**When to use**:
- Adding new challenges during an event
- Adjusting min/max delays
- Enabling/disabling challenges via config file
- Fixing challenge file paths

**What it doesn't affect**:
- Runner connections
- Active transmissions
- Server settings (port, CORS, etc.)
- Database state
- User accounts

**Limitations**:
- Cannot change server port or binding
- Cannot change database location
- Cannot modify API keys (requires restart)

## Conference Settings

The Conference Settings card on the Dashboard allows you to configure conference-specific features including daily operating hours, countdown timers, and automatic pause/resume.

### Accessing Conference Settings

Conference Settings are located on the **Dashboard** page in a dedicated card below the Runners table (left column).

### Conference Name and Countdown

The conference name and countdown timer appear in both the admin and public page headers:

**Admin Header**:
```
ChallengeCtl Control Center - ExampleCon
Ends in: 1d 12h 30m 45s
```

**Public Dashboard Header**:
```
Live Challenge Status
Starts in: 2d 5h 30m 45s
```

The countdown displays different states based on the conference timeline:

**Before Conference Start**:
- Shows: `Starts in: X`
- Counts down to conference start time from config

**During Conference**:
- Shows: `Ends in: X`
- Counts down to conference end time
- Additional timer when within daily hours (see below)

**After Conference**:
- Shows: `ExampleCon RFCTF has ended`
- Red text indicating event completion

### Daily Operating Hours

Configure daily start and end times to create a countdown cycle for multi-day conferences.

#### Day Start Time

**Purpose**: When the daily operating hours begin each day.

**Configuration**:
- Use the time picker to select a time (15-minute intervals)
- Format: HH:MM (e.g., "09:00")
- Timezone: Conference timezone (from config.yml)

**Example**: Set to "09:00" for a 9 AM daily start

#### End of Day Time

**Purpose**: When the daily operating hours end each day.

**Configuration**:
- Use the time picker to select a time (15-minute intervals)
- Format: HH:MM (e.g., "17:00")
- Timezone: Conference timezone (from config.yml)

**Example**: Set to "17:00" for a 5 PM daily end

#### Daily Countdown Cycle

When both day start and end times are configured, the countdown changes based on time of day:

**During Daily Hours** (e.g., 9 AM - 5 PM):
```
Ends in: 1d 12h 30m | Day ends: 4h 30m 15s
```
- Main countdown: Time until conference ends
- Secondary countdown: Time until end of day

**Outside Daily Hours** (e.g., 5 PM - 9 AM):
```
Day starts in: 15h 30m 45s
```
- Countdown to when the next day begins
- Only shown during conference (not before/after)

**Overnight Support**:
- Handles overnight ranges (e.g., 10:00 PM - 6:00 AM)
- Automatically calculates correct countdown

#### Saving Daily Times

**Save Button**:
- Click to apply both day start and end of day times
- Changes take effect immediately
- Updates countdown for all users in real-time
- No server restart required

**Clear Both Button**:
- Removes both day start and end of day settings
- Disables the daily countdown cycle
- Reverts to simple conference-wide countdown

**Validation**:
- Times must be in HH:MM format
- Invalid times show an error message
- Both times can be set independently

### Auto-Pause Daily

Automatically pause and resume the system based on daily operating hours.

#### How Auto-Pause Works

**When Enabled**:
1. System automatically pauses at end of day time
2. System automatically resumes at day start time
3. Runs in background every 30 seconds
4. Works across multiple days during conference

**Timezone Handling**:
- Auto-pause uses the **conference timezone** from config.yml
- Timezone offset is extracted from conference start time (e.g., `-5` from `"2024-04-05 09:00:00 -5"`)
- Daily times (e.g., 09:00, 17:00) are interpreted in this conference timezone
- System correctly handles pause/resume regardless of server's local timezone

**Requirements**:
- Both day start and end of day times must be set
- Auto-pause toggle must be enabled
- Conference timezone must be specified in config.yml start time

#### Enabling Auto-Pause

**Toggle Switch**:
- Located below the day time pickers
- Click to enable or disable
- Changes save immediately
- Shows "Automatically pause transmissions outside daily hours" description

**When Enabled**:
- System pauses at end of day (e.g., 5:00 PM)
- System resumes at day start (e.g., 9:00 AM)
- Live UI updates via WebSocket
- All connected admins see notifications

**When Disabled**:
- System runs continuously (24/7)
- Manual pause/resume still works
- Daily countdown still functions

#### Manual Override

The manual Pause/Resume button in the header **always works** and overrides auto-pause:

**Manual Pause**:
- Click "Pause" button at any time
- System pauses immediately
- Auto-pause will **not** auto-resume (respects manual override)
- Click "Resume" to start transmissions again

**Manual Resume**:
- Click "Resume" button during auto-pause period
- System resumes immediately
- Auto-pause will pause again at next end of day (if still outside hours)

**Auto-Pause Behavior**:
- Only auto-resumes if it was the one that paused
- Won't override manual pause with auto-resume
- Manual resume during off-hours is allowed (for testing, etc.)

#### WebSocket Notifications and State Sync

All connected admin users receive real-time notifications and button state updates:

**Auto-Pause Event**:
```
ℹ System auto-paused (outside daily hours)
```
- Appears when auto-pause triggers
- Pause button changes to Resume button for **all connected admins**
- Blue info notification

**Auto-Resume Event**:
```
ℹ System auto-resumed (within daily hours)
```
- Appears when auto-resume triggers
- Resume button changes to Pause button for **all connected admins**
- Blue info notification

**Manual Pause/Resume**:
- Uses standard success messages (green)
- No "auto" prefix in notification
- Button state syncs across all connected admin sessions via WebSocket
- If one admin pauses, all admins see the Resume button immediately

**Initial State Loading**:
- When you load the page, the pause button state is fetched from the server
- Ensures the button always shows the correct state (Pause or Resume)
- No refresh needed to see current system state

### Configuration Workflow

**Typical Setup**:

1. **Set Conference Times** (in config.yml):
   ```yaml
   conference:
     name: ExampleCon
     start: "2024-04-05 09:00:00 -5"
     stop: "2024-04-07 17:00:00 -5"
   ```

2. **Configure Daily Hours** (in Dashboard):
   - Day Start: 09:00
   - End of Day: 17:00
   - Click "Save"

3. **Enable Auto-Pause** (optional):
   - Toggle "Auto-Pause Daily" on
   - System will pause/resume automatically

4. **Monitor**:
   - Check countdown in header
   - Watch for auto-pause notifications
   - Use manual pause/resume as needed

### Runtime Configuration

All conference settings are **runtime configurable**:

**No Restart Required**:
- Change day start/end times anytime
- Toggle auto-pause on/off instantly
- Updates apply immediately
- All users see changes in real-time

**Persistent Storage**:
- Settings stored in database (system_state table)
- Survive server restarts
- Can be changed during live events
- Config.yml values serve as defaults

**Override Order**:
1. Database setting (from web UI)
2. Config.yml setting (fallback)
3. No setting (feature disabled)

### Best Practices

**Setting Daily Hours**:
- Match your event schedule (e.g., 9 AM - 5 PM)
- Account for setup/teardown time
- Consider participant time zones
- Test with manual trigger before enabling

**Using Auto-Pause**:
- Enable for multi-day events with defined hours
- Reduces power consumption overnight
- Prevents confusion about "dead air" periods
- Use manual override for testing outside hours

**During Events**:
- Don't change times during active hours (wait for breaks)
- Manual pause/resume always available
- Monitor WebSocket notifications
- Check countdown shows correct times

**Testing**:
1. Set day times (e.g., current time + 2 minutes)
2. Enable auto-pause
3. Wait for auto-pause notification
4. Test manual resume override
5. Adjust times to actual schedule

## Related Guides

- [Dashboard](Web-Interface-Dashboard) - View conference settings card
- [Challenges](Web-Interface-Challenges) - Understand pause effect on challenges
- [Runners](Web-Interface-Runners) - Understand pause effect on runners
- [Advanced Topics](Web-Interface-Advanced) - WebSocket notifications
