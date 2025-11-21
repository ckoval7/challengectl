# Challenge Management

The Manage Challenges page provides a unified interface for monitoring, creating, importing, editing, and controlling your challenges. This combines real-time monitoring with configuration management in a single location.

## Overview

The Manage Challenges page has four tabs:

1. **Live Status**: Monitor and control active challenges in real-time
2. **Create Challenge**: Form-based interface for creating individual challenges
3. **Import from YAML**: Batch import challenges from YAML files with file uploads
4. **Manage Challenges**: View, edit, and delete existing challenges

**When to use each tab**:
- **Live Status**: For monitoring challenge execution, enabling/disabling, and triggering transmissions
- **Create Challenge**: For adding one challenge at a time with guided validation
- **Import from YAML**: For batch operations, migration, or automation
- **Manage Challenges**: For editing existing challenges or removing old ones

For comprehensive documentation on challenge configuration, see the [Challenge Management Guide](Challenge-Management).

## Live Status Tab

**Purpose**: Real-time monitoring and control of challenge execution.

**Key Features**:
- Auto-refresh every 15 seconds
- Enable/disable toggle switches
- Manual trigger controls
- Real-time status updates
- Transmission count tracking
- Reload from config functionality

### Displayed Information

**Challenge Name**: Unique identifier

**Modulation**: Modulation type (CW, NBFM, SSB, FHSS, etc.)

**Frequency**: Transmission frequency in Hz (displayed as MHz)

**Status**: Current challenge state with color-coded tags
- **Queued** (green): Waiting for delay period to elapse
- **Waiting** (orange): Ready to be assigned to a runner
- **Assigned** (default): Currently being executed by a runner
- **Disabled** (gray): Challenge is not active

**Enabled**: Toggle switch to activate/deactivate the challenge
- Enabled challenges will be queued for transmission
- Disabled challenges will not be queued

**TX Count**: Number of times the challenge has been transmitted
- Updates in real-time as transmissions complete

**Last TX**: Timestamp of most recent transmission
- Shows relative time (e.g., "2 minutes ago")
- Updates automatically

### Actions Available

**Reload from Config**:
- Reloads challenges from server-config.yml
- Adds new challenges from config file
- Does not affect database-stored challenges
- Use when adding challenges via config file

**Enable/Disable Toggle**:
- Click switch to activate or deactivate a challenge
- Enabled challenges enter the transmission queue
- Disabled challenges are skipped
- Changes take effect immediately

**Trigger Now**:
- Manually queue the challenge for immediate transmission
- Bypasses the delay timer
- Queues the challenge as "waiting" immediately
- The next available compatible runner will execute it
- Use this for testing or demonstrations
- Does not affect the regular scheduling cycle

### Challenge Workflow

1. **Disabled**: Challenge exists but is inactive
2. **Enabled**: Challenge is activated and enters the queue
3. **Queued**: Waiting for random delay period (between min_delay and max_delay)
4. **Waiting**: Ready for assignment, available to compatible runners
5. **Assigned**: A runner has claimed the task and is executing
6. **Completed**: Transmission finished, returns to queued state

**Note**: The cycle repeats continuously for enabled challenges.

## Create Challenge Tab

**Purpose**: Create a single challenge using a guided form interface.

**Key Features**:
- Dynamic form fields based on modulation type
- Built-in validation for required fields
- File upload for audio and binary files
- Modulation-specific parameter configuration
- Public field visibility configuration

### Workflow

1. Enter basic information (name, modulation, frequency)
2. Configure challenge content (flag text or file upload)
3. Set timing parameters (min/max delay, priority)
4. Configure public dashboard visibility (select which fields are visible on public dashboard)
5. Configure modulation-specific settings (if applicable)
6. Click "Create Challenge"

### Priority Field

- Priority range: 0-100
- Higher number = higher priority
- Higher priority challenges are transmitted first
- Default: 0 (normal priority)
- Use for time-sensitive or important challenges

### Public Dashboard Visibility

- Select which fields are visible on the public dashboard
- Available fields: name, modulation, frequency, status, last TX time
- Default: name, modulation, frequency, status
- Allows you to control what information participants can see

### Example Use Case

- Creating a new NBFM challenge during a CTF event
- Testing different CW speeds to find the right difficulty
- Quickly adding a challenge without editing YAML files

## Import from YAML Tab

**Purpose**: Batch import multiple challenges from a YAML configuration file.

**Key Features**:
- Upload YAML file with challenge definitions
- Upload associated media files (WAV, binary, etc.)
- Automatic file path mapping
- Import statistics and error reporting
- API documentation for automation

### Workflow

1. Prepare a YAML file with your challenges
2. Click "Select YAML File" and choose your file
3. (Optional) Click "Add Files" to upload media files
4. Click "Import Challenges"
5. Review import results (added, updated, errors)

### File Handling

- Files are uploaded and stored by SHA-256 hash
- System automatically maps uploaded files to challenge configs
- If YAML references `example.wav` and you upload `example.wav`, it's linked automatically

### Example Use Case

- Migrating challenges from server config to database
- Sharing challenge sets between ChallengeCtl instances
- Version-controlling challenges in git and importing
- Restoring from backup

## Manage Challenges Tab

**Purpose**: View, edit, and delete existing challenges.

**Key Features**:
- Table view of all configured challenges
- Filter and search capabilities
- JSON editor for advanced configuration
- Delete with confirmation dialog

### Displayed Information

- Challenge name
- Modulation type
- Frequency (formatted as MHz/GHz)
- Status (Enabled/Disabled)
- Transmission count

### Actions Available

**Refresh List**:
- Reloads challenges from database
- Use after importing or creating challenges elsewhere

**Edit**:
- Opens JSON editor dialog
- Shows complete challenge configuration
- Make changes directly to JSON
- Click "Save" to apply changes
- Validates JSON syntax before saving

**Delete**:
- Removes challenge permanently
- Confirmation dialog prevents accidental deletion
- Deletes challenge config and transmission history
- Does NOT delete referenced media files (other challenges may use them)

### Example Use Case

- Adjusting min/max delays during an event
- Changing frequency after testing
- Removing old or unused challenges
- Copying configuration to create similar challenges

## API Automation

The Import from YAML tab includes documentation for API-based automation:

**cURL Example**:
```bash
curl -X POST http://localhost:8080/api/challenges/import \
  -H "X-CSRF-Token: YOUR_CSRF_TOKEN" \
  -b "session=YOUR_SESSION_COOKIE" \
  -F "yaml_file=@challenges.yml" \
  -F "example_voice.wav=@/path/to/example_voice.wav"
```

**Python Example**:
```python
import requests

url = "http://localhost:8080/api/challenges/import"
files = {
    'yaml_file': open('challenges.yml', 'rb'),
    'example_voice.wav': open('example_voice.wav', 'rb'),
}
cookies = {'session': 'YOUR_SESSION_COOKIE'}
headers = {'X-CSRF-Token': 'YOUR_CSRF_TOKEN'}

response = requests.post(url, files=files, cookies=cookies, headers=headers)
print(response.json())
```

**Use Cases for API Automation**:
- CI/CD pipeline integration
- Automated challenge rotation
- Dynamic challenge generation from scripts
- Remote challenge management

## Best Practices

**Creating Challenges**:
- Use descriptive names (e.g., `NBFM_EASY_1` not `FLAG1`)
- Start disabled, test with "Trigger Now", then enable
- Set appropriate delays based on event duration
- Verify frequency is within runner limits

**Importing Challenges**:
- Test YAML file syntax before importing
- Keep YAML files under version control
- Upload all referenced media files together
- Review import results for errors

**Managing Challenges**:
- Disable rather than delete during events
- Back up configuration before bulk edits
- Use JSON validation tools when editing directly
- Test changes with "Trigger Now" before re-enabling

**File Management**:
- Use meaningful filenames (e.g., `flag_morse_slow.wav`)
- Keep media files organized in directories
- Don't delete files that might be used by multiple challenges
- Track file hashes for deduplication

## Typical Workflow

The unified Manage Challenges interface streamlines challenge management:

1. **Create/Import**: Use the **Create Challenge** or **Import from YAML** tabs to add challenges
2. **Configure**: Set up timing, priority, and public visibility settings
3. **Monitor**: Switch to **Live Status** tab to monitor execution
4. **Control**: Use **Live Status** to enable/disable or trigger challenges
5. **Edit**: Use **Manage Challenges** tab to edit or delete existing challenges

This unified approach eliminates the need to switch between separate pages for configuration and monitoring.

## Troubleshooting

**Challenge won't transmit**:
1. Check **Manage Challenges > Live Status** tab for the challenge state
2. Verify at least one runner is online and enabled
3. Check runner frequency limits include the challenge frequency
4. Look for errors in [Logs page](Web-Interface-Logs)
5. Try manual trigger from Live Status tab to test

## Related Guides

- [Challenge Management Guide](Challenge-Management) - Detailed challenge configuration
- [Runners Management](Web-Interface-Runners) - Ensure runners can execute challenges
- [Dashboard](Web-Interface-Dashboard) - Monitor transmission activity
- [Logs](Web-Interface-Logs) - Debug challenge issues
