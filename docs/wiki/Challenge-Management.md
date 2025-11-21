# Challenge Management Guide

This guide covers how to create, configure, import, and manage challenges using the ChallengeCtl web interface. Whether you prefer a graphical form, YAML configuration files, or API automation, this guide will help you manage your RF challenges effectively.

## Table of Contents

- [Overview](#overview)
- [Accessing Challenge Configuration](#accessing-challenge-configuration)
- [Creating Challenges via Form](#creating-challenges-via-form)
- [Importing Challenges from YAML](#importing-challenges-from-yaml)
- [Managing Existing Challenges](#managing-existing-challenges)
- [API Automation](#api-automation)
- [Challenge File Management](#challenge-file-management)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

ChallengeCtl provides multiple ways to manage challenges:

1. **Web Form**: Create challenges one at a time using an intuitive form interface
2. **YAML Import**: Batch import multiple challenges from YAML files with associated media files
3. **API Automation**: Programmatically manage challenges via REST API endpoints
4. **Direct Editing**: Modify challenge JSON configuration for advanced users

### When to Use Each Method

**Use the Web Form when**:
- Creating a single new challenge
- You prefer a guided interface with validation
- Testing different modulation parameters interactively
- You're new to ChallengeCtl configuration

**Use YAML Import when**:
- Migrating from server config file to database storage
- Importing multiple challenges at once
- Distributing challenge sets to other ChallengeCtl instances
- Working with pre-configured challenge templates

**Use API Automation when**:
- Integrating challenge creation into CI/CD pipelines
- Dynamically generating challenges from scripts
- Managing challenges from external tools
- Bulk operations on many challenges

**Use Direct Editing when**:
- Making advanced parameter adjustments
- Copying challenge configurations
- Troubleshooting configuration issues
- You're comfortable with JSON syntax

## Accessing Challenge Configuration

### Navigation

1. **Log in** to the ChallengeCtl web interface
2. Click **"Configure Challenges"** in the left sidebar navigation
3. You'll see three tabs:
   - **Create Challenge**: Form-based challenge creation
   - **Import from YAML**: Batch import from YAML files
   - **Manage Challenges**: View and edit existing challenges

### Permissions

Challenge configuration requires admin authentication:
- You must be logged in with an admin account
- TOTP two-factor authentication is required
- CSRF protection is enforced for all modifications

## Creating Challenges via Form

The Create Challenge form provides a guided interface for configuring new challenges.

### Basic Information

**Challenge Name** (required):
- Unique identifier for the challenge
- Examples: `NBFM_FLAG_1`, `MORSE_SECRET`, `FHSS_HOPPER`
- Must not conflict with existing challenge names
- Used in logs, dashboards, and runner task assignments

**Modulation** (required):
- Select the RF modulation type
- Available options:
  - **NBFM** (Narrowband FM) - Voice/audio challenges
  - **SSB** (Single Sideband) - Voice/audio challenges
  - **FreeDV** - Digital voice
  - **CW** (Morse Code) - Text-based challenges
  - **ASK** (Amplitude Shift Keying) - Digital data
  - **POCSAG** (Pager) - Pager messages
  - **FHSS** (Frequency Hopping) - Frequency hopping challenges
  - **LoRa** - Long-range low-power digital
- The form dynamically shows relevant fields based on modulation type

**Frequency Mode** (required):
ChallengeCtl supports three ways to specify frequencies for challenges:

1. **Single Frequency**: Specify an exact frequency in MHz
   - Use when you want a challenge to always transmit on the same frequency
   - Example: `146.550` MHz for 2m simplex calling frequency

2. **Named Ranges**: Select one or more predefined frequency ranges
   - System randomly selects a frequency from the configured ranges
   - Ranges are defined in `server-config.yml` under `frequency_ranges`
   - When multiple ranges are selected, one is chosen randomly, then a frequency within that range
   - Example ranges: "2 Meter Ham Band", "70 Centimeter Ham Band"
   - See [Configuration Reference](Configuration-Reference#frequency-ranges) for range definitions

3. **Manual Range**: Specify a custom minimum and maximum frequency in MHz
   - System randomly selects a frequency within your specified range
   - Use for custom frequency bands not in the predefined ranges
   - Example: `146.000` MHz to `146.100` MHz

All frequency inputs accept MHz with 0.001 MHz (1 kHz) precision. Frequencies must:
- Be within your country's amateur radio or ISM bands
- Match the frequency limits of at least one runner
- Be within your equipment's capabilities

**Enabled**:
- Toggle to enable/disable the challenge immediately
- Disabled challenges won't be queued for transmission
- Can be changed later from the Manage Challenges tab

### Challenge Content

The challenge content section changes based on the selected modulation type.

#### Audio-Based Modulations (NBFM, SSB, FreeDV, FHSS)

**Flag (Audio File)**:
- Path to WAV file: Enter a file path if the file is already on the server
- Upload file: Click "Choose File" to upload a WAV file
- Sample rate is configured separately (see below)
- File is stored by hash and deduplicated automatically

**WAV Sample Rate**:
- Sample rate of the audio file in Hz
- Common values: `8000`, `16000`, `22050`, `44100`, `48000`
- Must match the actual sample rate of your WAV file
- Default: `48000` Hz

#### Text-Based Modulations (CW, ASK, POCSAG)

**Flag (Text)**:
- Enter the text content to be transmitted
- For CW: Will be sent as Morse code
- For ASK: Encoded as digital data
- For POCSAG: Sent as a pager message
- No file upload needed

**CW-Specific: Speed (WPM)**:
- Morse code transmission speed in words per minute
- Range: 5-60 WPM
- Default: 35 WPM
- Lower = easier to decode, higher = more challenging

#### Binary File Modulations (LoRa)

**Flag (Binary File)**:
- Path to binary file or upload
- Click "Choose File" to upload a .bin file
- Used for raw digital data transmission

### Timing Configuration

**Min Delay** (seconds):
- Minimum time between transmissions
- Range: 1-3600 seconds
- Default: 60 seconds
- Prevents excessive transmissions

**Max Delay** (seconds):
- Maximum time between transmissions
- Range: 1-3600 seconds
- Must be greater than or equal to Min Delay
- Default: 90 seconds
- System randomly selects a delay in this range

**Priority**:
- Transmission priority (0-100)
- Higher priority challenges are transmitted first
- Default: 0 (normal priority)
- Use for time-sensitive or important challenges

### Modulation-Specific Settings

#### FHSS (Frequency Hopping Spread Spectrum)

**Channel Spacing** (Hz):
- Spacing between frequency channels
- Range: 1000-1000000 Hz
- Default: 10000 Hz (10 kHz)
- Larger spacing = wider bandwidth

**Hop Rate** (Hz):
- How fast the frequency hops
- Range: 1-1000 Hz
- Default: 10 Hz
- Higher = faster hopping

**Hop Time** (seconds):
- Total duration of the hopping sequence
- Range: 1-300 seconds
- Default: 60 seconds

**Seed**:
- Hopping sequence seed
- Same seed produces same hopping pattern
- Used for synchronized hopping
- Optional

#### LoRa Settings

**Spreading Factor**:
- LoRa spreading factor
- Range: 6-12
- Default: 7
- Higher = longer range, slower data rate

**Bandwidth** (Hz):
- LoRa bandwidth
- Options: 125 kHz, 250 kHz, 500 kHz
- Default: 125000 (125 kHz)
- Higher = faster data rate, shorter range

**Coding Rate**:
- Forward error correction coding rate
- Options: 4/5, 4/6, 4/7, 4/8
- Default: 4/5
- Higher denominator = more error correction, slower

### Submitting the Form

1. **Review your configuration**: Ensure all fields are correct
2. **Click "Create Challenge"**: Submit the form
3. **Success**: Challenge is created and appears in the Manage Challenges tab
4. **Error**: Review the error message and correct the indicated fields

**Common Errors**:
- "Challenge name already exists" - Choose a different name
- "Missing required field" - Fill in all required fields
- "Frequency out of range" - Check your frequency value

## Importing Challenges from YAML

The YAML import feature allows you to batch import challenges from configuration files.

### YAML File Format

Your YAML file can use either format:

**Format 1: List of challenges**
```yaml
# Single frequency example
- name: NBFM_FLAG_1
  frequency: 146550000  # Hz (146.550 MHz)
  modulation: nbfm
  flag: example_voice.wav
  wav_samplerate: 48000
  min_delay: 60
  max_delay: 90
  enabled: true

# Named frequency ranges example
- name: NBFM_FLAG_2
  frequency_ranges:  # Use one or more named ranges
    - ham_144
    - ham_220
  modulation: nbfm
  flag: example_voice.wav
  wav_samplerate: 48000
  min_delay: 60
  max_delay: 90
  enabled: true

# Manual frequency range example
- name: MORSE_FLAG_1
  manual_frequency_range:
    min_hz: 146000000  # 146.000 MHz
    max_hz: 146100000  # 146.100 MHz
  modulation: cw
  flag: 'SECRET MESSAGE'
  speed: 35
  min_delay: 60
  max_delay: 90
  enabled: true
```

**Format 2: Dict with challenges key**
```yaml
challenges:
  # Single frequency example
  - name: NBFM_FLAG_1
    frequency: 146550000  # Hz (146.550 MHz)
    modulation: nbfm
    flag: example_voice.wav
    wav_samplerate: 48000
    min_delay: 60
    max_delay: 90
    enabled: true

  # Named frequency ranges example
  - name: FHSS_FLAG_1
    frequency_ranges:  # Random frequency from these ranges
      - ham_440
      - ham_900
    modulation: fhss
    flag: hopping_voice.wav
    wav_samplerate: 48000
    channel_spacing: 10000
    hop_rate: 10
    hop_time: 60
    seed: RFHS
    min_delay: 60
    max_delay: 90
    enabled: true

  # Manual frequency range example
  - name: CW_FLAG_1
    manual_frequency_range:
      min_hz: 420000000  # 420.000 MHz
      max_hz: 450000000  # 450.000 MHz
    modulation: cw
    flag: 'CQ CQ CQ DE RFCTF K'
    speed: 35
    min_delay: 60
    max_delay: 90
    enabled: true
```

### Import Process

1. **Prepare your YAML file**: Create a YAML file with your challenges
2. **Prepare challenge files**: Gather any WAV, binary, or other media files
3. **Navigate to Import tab**: Click "Import from YAML" tab
4. **Select YAML file**: Click "Select YAML File" and choose your .yml or .yaml file
5. **Upload media files** (optional): Click "Add Files" to upload WAV, binary, or other files
6. **Click "Import Challenges"**: Begin the import process

### File Handling

**Automatic File Mapping**:
- Files uploaded are stored by SHA-256 hash
- If a challenge references a filename (e.g., `flag: example.wav`)
- And you upload a file named `example.wav`
- The system automatically updates the challenge to reference the uploaded file
- No need to manually update paths

**Supported File Types**:
- `.wav` - Audio files
- `.bin` - Binary data files
- `.txt` - Text files
- `.py` - Python scripts
- `.grc` - GNU Radio flowgraph files
- `.yml`, `.yaml` - Additional YAML files

**File Deduplication**:
- Files are stored by hash
- Uploading the same file multiple times doesn't create duplicates
- Saves storage space

### Import Results

After import completes, you'll see a summary:

```
Imported successfully: 5 added, 2 updated, 3 files uploaded
```

**Added**: New challenges created
**Updated**: Existing challenges modified (matched by name)
**Files uploaded**: Number of media files uploaded
**Errors**: Any challenges that failed to import (if applicable)

### Update Behavior

When importing challenges:
- **New challenges** (name doesn't exist): Created in database
- **Existing challenges** (name matches): Configuration updated
- **Disabled challenges**: Remain disabled unless YAML sets `enabled: true`

This allows you to:
- Add new challenges without affecting existing ones
- Update challenge parameters by re-importing
- Use YAML import for version control

## Managing Existing Challenges

The Manage Challenges tab displays all configured challenges and provides editing/deletion tools.

### Challenge List

Each challenge shows:

**Name**: Unique challenge identifier

**Modulation**: RF modulation type (NBFM, CW, etc.)

**Frequency**: Transmission frequency in Hz (displayed as MHz/GHz)

**Status**: Enabled or Disabled
- Green "Enabled" badge: Active, will be queued
- Gray "Disabled" badge: Inactive

**TX Count**: Number of times the challenge has been transmitted
- Updates in real-time
- Resets when challenge is deleted

### Challenge Actions

**Refresh List**:
- Click "Refresh List" to reload challenges from database
- Updates challenge list with latest data
- Use after importing or creating challenges

**Edit**:
- Click "Edit" button to modify a challenge
- Opens a dialog with JSON editor
- Shows the complete challenge configuration
- Make changes directly to the JSON
- Click "Save" to apply changes

**JSON Editing Examples**:

Single Frequency:
```json
{
  "name": "NBFM_FLAG_1",
  "frequency": 146550000,
  "modulation": "nbfm",
  "flag": "challenges/example.wav",
  "wav_samplerate": 48000,
  "min_delay": 60,
  "max_delay": 90,
  "enabled": true,
  "priority": 0
}
```

Named Frequency Ranges:
```json
{
  "name": "NBFM_FLAG_2",
  "frequency_ranges": ["ham_144", "ham_220"],
  "modulation": "nbfm",
  "flag": "challenges/example.wav",
  "wav_samplerate": 48000,
  "min_delay": 60,
  "max_delay": 90,
  "enabled": true,
  "priority": 0
}
```

Manual Frequency Range:
```json
{
  "name": "CW_FLAG_1",
  "manual_frequency_range": {
    "min_hz": 146000000,
    "max_hz": 146100000
  },
  "modulation": "cw",
  "flag": "CQ CQ CQ DE RFCTF K",
  "speed": 35,
  "min_delay": 60,
  "max_delay": 90,
  "enabled": true,
  "priority": 0
}
```

**Delete**:
- Click "Delete" button to remove a challenge
- Confirmation dialog appears
- Click "Confirm" to permanently delete
- Deletes:
  - Challenge configuration
  - Associated transmission history
  - Challenge timing state
- Does NOT delete:
  - Referenced media files (other challenges may use them)

**Warning**: Deletion is permanent and cannot be undone.

### Editing Challenges

**When to edit**:
- Adjust timing parameters (min/max delay)
- Change frequency
- Update file paths
- Modify modulation-specific parameters
- Change priority

**What not to edit**:
- Challenge name (use delete + recreate instead)
- Modulation type (may cause compatibility issues)

**Best practices**:
- Make small changes and test
- Use JSON validation tools if unsure
- Back up configuration before major edits
- Test with "Trigger Now" after editing

## API Automation

The challenge configuration API enables programmatic challenge management for automation and integration.

### API Endpoints

**Create Challenge**:
```
POST /api/challenges
Content-Type: application/json
```

Body:
```json
{
  "name": "NBFM_FLAG_1",
  "config": {
    "name": "NBFM_FLAG_1",
    "frequency": 146550000,
    "modulation": "nbfm",
    "flag": "challenges/example.wav",
    "wav_samplerate": 48000,
    "min_delay": 60,
    "max_delay": 90,
    "enabled": true
  }
}
```

Response:
```json
{
  "status": "created",
  "challenge_id": "a1b2c3d4-5e6f-7g8h-9i0j-k1l2m3n4o5p6"
}
```

**Update Challenge**:
```
PUT /api/challenges/<challenge_id>
Content-Type: application/json
```

Body:
```json
{
  "config": {
    "name": "NBFM_FLAG_1",
    "frequency": 146550000,
    "modulation": "nbfm",
    "flag": "challenges/example.wav",
    "wav_samplerate": 48000,
    "min_delay": 60,
    "max_delay": 120,
    "enabled": true
  }
}
```

**Delete Challenge**:
```
DELETE /api/challenges/<challenge_id>
```

**Import from YAML**:
```
POST /api/challenges/import
Content-Type: multipart/form-data
```

Fields:
- `yaml_file`: YAML file (required)
- Additional fields: Media files referenced in YAML

### Authentication

All challenge management endpoints require:

1. **Session cookie**: Obtained via `/api/auth/login`
2. **CSRF token**: Passed in `X-CSRF-Token` header
3. **Admin role**: Only admin users can manage challenges

### cURL Examples

**Create a challenge**:
```bash
curl -X POST http://localhost:8080/api/challenges \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: YOUR_CSRF_TOKEN" \
  -b "session=YOUR_SESSION_COOKIE" \
  -d '{
    "name": "TEST_CHALLENGE",
    "config": {
      "name": "TEST_CHALLENGE",
      "frequency": 146550000,
      "modulation": "cw",
      "flag": "HELLO WORLD",
      "speed": 35,
      "min_delay": 60,
      "max_delay": 90,
      "enabled": true
    }
  }'
```

**Import challenges from YAML**:
```bash
curl -X POST http://localhost:8080/api/challenges/import \
  -H "X-CSRF-Token: YOUR_CSRF_TOKEN" \
  -b "session=YOUR_SESSION_COOKIE" \
  -F "yaml_file=@challenges.yml" \
  -F "example_voice.wav=@/path/to/example_voice.wav" \
  -F "flag_data.bin=@/path/to/flag_data.bin"
```

**Delete a challenge**:
```bash
curl -X DELETE http://localhost:8080/api/challenges/a1b2c3d4-5e6f-7g8h-9i0j-k1l2m3n4o5p6 \
  -H "X-CSRF-Token: YOUR_CSRF_TOKEN" \
  -b "session=YOUR_SESSION_COOKIE"
```

### Python Automation Script

```python
#!/usr/bin/env python3
"""
Automated challenge management script.
"""

import requests

# Configuration
BASE_URL = "http://localhost:8080"
USERNAME = "admin"
PASSWORD = "your_password"
TOTP_CODE = "123456"  # From authenticator app

# Login
session = requests.Session()

# Step 1: Login with username/password
login_response = session.post(f"{BASE_URL}/api/auth/login", json={
    "username": USERNAME,
    "password": PASSWORD
})

if login_response.status_code != 200:
    print("Login failed")
    exit(1)

# Step 2: Complete TOTP verification
totp_response = session.post(f"{BASE_URL}/api/auth/verify-totp", json={
    "totp_code": TOTP_CODE
})

if totp_response.status_code != 200:
    print("TOTP verification failed")
    exit(1)

# Get CSRF token from cookie
csrf_token = session.cookies.get('csrf_token')

# Create a challenge
challenge_data = {
    "name": "AUTO_CHALLENGE_1",
    "config": {
        "name": "AUTO_CHALLENGE_1",
        "frequency": 146550000,
        "modulation": "cw",
        "flag": "AUTOMATED FLAG",
        "speed": 35,
        "min_delay": 60,
        "max_delay": 90,
        "enabled": True
    }
}

create_response = session.post(
    f"{BASE_URL}/api/challenges",
    json=challenge_data,
    headers={"X-CSRF-Token": csrf_token}
)

if create_response.status_code == 201:
    result = create_response.json()
    print(f"Challenge created: {result['challenge_id']}")
else:
    print(f"Failed to create challenge: {create_response.text}")

# Import challenges from YAML
files = {
    'yaml_file': open('challenges.yml', 'rb'),
    'example.wav': open('example.wav', 'rb')
}

import_response = session.post(
    f"{BASE_URL}/api/challenges/import",
    files=files,
    headers={"X-CSRF-Token": csrf_token}
)

if import_response.status_code == 200:
    result = import_response.json()
    print(f"Import complete: {result['added']} added, {result['updated']} updated")
else:
    print(f"Import failed: {import_response.text}")

# Logout
session.post(f"{BASE_URL}/api/auth/logout")
```

## Challenge File Management

### File Storage

**Location**: Files are stored in the server's `files/` directory

**Naming**: Files are stored by SHA-256 hash, not original filename
- Example: `a3f5b2c1d4e6f7...` (hash of file contents)
- Prevents filename conflicts
- Enables deduplication

**Database Tracking**: File metadata is stored in the database:
- Original filename
- SHA-256 hash
- File size
- MIME type
- File path

### Uploading Files

**Via Web UI**:
1. Use the form upload in Create Challenge tab
2. Or use the file upload in Import from YAML tab
3. Files are automatically registered in the database

**Via API**:
```bash
curl -X POST http://localhost:8080/api/files/upload \
  -H "Authorization: Bearer RUNNER_API_KEY" \
  -F "file=@example.wav"
```

Response:
```json
{
  "status": "uploaded",
  "file_hash": "a3f5b2c1d4e6f7...",
  "filename": "example.wav",
  "size": 1048576
}
```

### Referencing Files in Challenges

**Option 1: Use file path** (traditional):
```yaml
flag: challenges/example.wav
```
Runner will look for file at this path.

**Option 2: Use file hash**:
```yaml
flag_file_hash: a3f5b2c1d4e6f7...
```
Runner will download file by hash from server.

**Automatic mapping during import**:
- If you upload `example.wav` during import
- And your YAML references `flag: example.wav`
- System adds `flag_file_hash: <hash>` automatically

### File Cleanup

**Files are NOT automatically deleted when**:
- A challenge is deleted
- A challenge is updated to use a different file

**Reason**: Other challenges may reference the same file

**Manual cleanup**:
```bash
# List unused files (manual process)
# Delete files not referenced by any challenge
```

## Best Practices

### Challenge Naming

**Good names**:
- `NBFM_EASY_1` - Descriptive, indicates difficulty
- `CW_FAST_35WPM` - Includes key parameter
- `FHSS_WIDEBAND` - Describes characteristic

**Avoid**:
- `FLAG1`, `TEST`, `CHALLENGE` - Too generic
- `asdf`, `temp` - Not descriptive
- Names with spaces or special characters

### Frequency Selection

**Consider**:
- Amateur radio band regulations in your jurisdiction
- ISM bands for unlicensed operation
- Runner device frequency ranges
- Interference from nearby transmitters
- Receiver capabilities of participants

**Common bands**:
- 2m amateur: 144-148 MHz
- 70cm amateur: 420-450 MHz
- 33cm amateur: 902-928 MHz
- ISM: 433 MHz, 915 MHz, 2.4 GHz

### Timing Configuration

**Short delays (10-30 seconds)**:
- Good for: Active CTF events, testing
- Risk: May overwhelm runners, spectrum congestion

**Medium delays (60-120 seconds)**:
- Good for: Most CTF scenarios
- Balanced: Frequent enough to stay engaged, not overwhelming

**Long delays (300-600 seconds)**:
- Good for: Long-duration events, demonstration mode
- Risk: Participants may lose interest

### Challenge Difficulty

**Progressive difficulty**:
1. Start with simple modulations (NBFM, CW at slow speed)
2. Increase challenge (faster CW, FHSS, frequency offsets)
3. Advanced challenges (LoRa, complex hopping patterns)

**File size considerations**:
- Small files (< 1 MB): Fast transmission, quick to receive
- Large files (> 10 MB): Longer transmission, may timeout
- Balance file size with complexity

### Testing Challenges

**Before deploying**:
1. Create challenge as disabled
2. Test with "Trigger Now" from Challenges page
3. Verify signal on SDR receiver
4. Confirm decodability
5. Check runner logs for errors
6. Enable for automatic transmission

**Test checklist**:
- [ ] Challenge transmits successfully
- [ ] Signal is detectable
- [ ] Flag is decodable by participants
- [ ] Frequency is within runner limits
- [ ] File paths are correct
- [ ] Timing delays are appropriate
- [ ] No errors in logs

### Version Control

**YAML-based workflow**:
1. Maintain challenges in YAML files under version control (git)
2. Import to server via YAML import
3. Track changes through git commits
4. Easy rollback to previous configurations
5. Share challenge sets with other events

**Example git workflow**:
```bash
# challenges.yml
git add challenges.yml media/
git commit -m "Add new FHSS challenges for CTF"
git push

# Import to server
curl -X POST http://server:8080/api/challenges/import \
  -H "X-CSRF-Token: $TOKEN" \
  -b "session=$SESSION" \
  -F "yaml_file=@challenges.yml" \
  -F "flag1.wav=@media/flag1.wav"
```

## Troubleshooting

### Challenge Won't Create

**Symptom**: Form submission fails or returns error

**Possible causes**:
- Challenge name already exists
- Missing required fields
- Invalid frequency value
- Invalid file path

**Solutions**:
1. Check error message for specific field
2. Verify name is unique
3. Ensure all required fields are filled
4. Validate frequency is a number in Hz
5. Check file paths are absolute or relative to server

### YAML Import Fails

**Symptom**: Import returns error or partial success

**Common errors**:
- "Invalid YAML format" - YAML syntax error
- "Missing yaml_file" - No YAML file selected
- "File must be a YAML file" - Wrong file extension

**Solutions**:
1. Validate YAML syntax with online validator
2. Ensure file extension is .yml or .yaml
3. Check YAML contains list of challenges or dict with 'challenges' key
4. Verify challenge objects have required fields (name, frequency, modulation)

### Files Not Uploading

**Symptom**: Files upload fails or challenges can't find files

**Possible causes**:
- File extension not allowed
- File too large (>100 MB limit)
- Network timeout
- Disk space full on server

**Solutions**:
1. Check file extension is in allowed list (.wav, .bin, .txt, .py, .grc, .yml, .yaml)
2. Verify file size is under 100 MB
3. Try uploading smaller batches of files
4. Check server disk space

### Challenge Appears But Won't Transmit

**This is a different issue - see the [Challenges Management](Web-Interface-Guide#challenges-management) section**

The challenge configuration is correct, but transmission/runner issues prevent execution.

**Quick checks**:
1. Is challenge enabled? (Manage Challenges tab)
2. Are runners online? (Runners page)
3. Does runner frequency range include challenge frequency?
4. Check Logs page for errors

### API Authentication Fails

**Symptom**: 401 Unauthorized or 403 Forbidden errors

**Possible causes**:
- Not logged in
- Session expired
- Missing CSRF token
- Using runner API key instead of admin session

**Solutions**:
1. Log in via `/api/auth/login` first
2. Complete TOTP verification
3. Include CSRF token in `X-CSRF-Token` header
4. Use session cookie, not API key (API keys are for runners only)

## Next Steps

Now that you understand challenge management, you can:

- [Learn about Challenge Development](Challenge-Development) - Create new modulation types
- [Review the Web Interface Guide](Web-Interface-Guide) - Monitor challenge transmissions
- [Check the API Reference](API-Reference) - Full API documentation
- [Read the Configuration Reference](Configuration-Reference) - All configuration options

## Reference: Supported Modulations

| Modulation | Type | Flag Format | Key Parameters |
|------------|------|-------------|----------------|
| `nbfm` | Audio | WAV file | `wav_samplerate` |
| `ssb` | Audio | WAV file | `wav_samplerate` |
| `freedv` | Audio | WAV file | `wav_samplerate` |
| `cw` | Text | Text string | `speed` (WPM) |
| `ask` | Text | Text string | - |
| `pocsag` | Text | Text string | - |
| `fhss` | Audio | WAV file | `channel_spacing`, `hop_rate`, `hop_time`, `seed`, `wav_samplerate` |
| `lrs` | Binary | Binary file | `spreading_factor`, `bandwidth`, `coding_rate` |

## Reference: Required vs Optional Fields

**Required for all challenges**:
- `name` - Unique challenge identifier
- `frequency` OR `frequency_ranges` OR `manual_frequency_range` - See frequency options below
- `modulation` - Modulation type
- `min_delay` - Minimum seconds between transmissions
- `max_delay` - Maximum seconds between transmissions

**Frequency Options** (choose one):
- `frequency` - Single transmission frequency in Hz (e.g., `146550000` for 146.550 MHz)
- `frequency_ranges` - Array of named range identifiers (e.g., `["ham_144", "ham_440"]`)
- `manual_frequency_range` - Custom frequency range with `min_hz` and `max_hz` fields

**Optional for all challenges**:
- `enabled` - Enable/disable (default: true)
- `priority` - Transmission priority (default: 0)
- `rf_gain` - RF gain in dB
- `if_gain` - IF gain in dB

**Modulation-specific**:
- See table above for parameters specific to each modulation type
