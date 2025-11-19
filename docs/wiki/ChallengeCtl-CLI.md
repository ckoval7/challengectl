# ChallengeCtl Command-Line Interface

ChallengeCtl provides several command-line utilities for managing the system and running challenges. This guide covers the standalone challenge runner, user management, and API key generation tools.

## Table of Contents

- [User Management](#user-management)
- [Standalone Challenge Runner](#standalone-challenge-runner)
- [API Key Generation](#api-key-generation)

## User Management

The `manage-users.py` script provides command-line user management for ChallengeCtl server administrators. Use this tool to create users, manage permissions, and perform administrative tasks without using the web interface.

### Overview

The user management CLI supports:

- Creating temporary and permanent users
- Managing user permissions
- Enabling/disabling users
- Resetting passwords and TOTP secrets
- Listing users and their permissions

### Basic Usage

```bash
python3 manage-users.py [OPTIONS] <command> [arguments]
```

### Global Options

| Option | Description |
|--------|-------------|
| `--db PATH` | Path to database file (default: challengectl.db) |
| `--config PATH` | Path to server config file (default: server-config.yml) |

### Commands

#### create

Create a new user account.

**Syntax:**
```bash
python3 manage-users.py create <username> [OPTIONS]
```

**Options:**
- `--password PASSWORD` - Set password (will prompt if not provided)
- `--temporary` - Create temporary user (must complete setup within 24 hours)
- `--grant PERMISSION` - Grant permission(s) (can be used multiple times)

**Examples:**

Create a permanent user with TOTP (interactive):
```bash
python3 manage-users.py create alice
```

Create a temporary user with a password:
```bash
python3 manage-users.py create bob --temporary --password tempPassword123
```

Create a user with permissions:
```bash
python3 manage-users.py create charlie --temporary --password temp456 --grant create_users
```

**Temporary vs Permanent Users:**

- **Permanent users**: Created with full TOTP setup immediately, ready to use
- **Temporary users**: Created with temporary password, must complete setup on first login
  - Must change password
  - Must set up TOTP 2FA
  - Must complete setup within 24 hours or account is disabled
  - Ideal for onboarding new administrators

#### list

List all user accounts.

**Syntax:**
```bash
python3 manage-users.py list
```

**Example output:**
```
Users:
Username: admin
  Enabled: True
  Password change required: False
  Temporary: False
  Created: 2024-01-15 10:00:00
  Last login: 2024-01-15 14:30:00

Username: operator
  Enabled: True
  Password change required: False
  Temporary: True
  Created: 2024-01-15 11:00:00
  Last login: None
```

#### disable / enable

Disable or enable a user account.

**Syntax:**
```bash
python3 manage-users.py disable <username>
python3 manage-users.py enable <username>
```

**Examples:**
```bash
python3 manage-users.py disable alice
python3 manage-users.py enable alice
```

#### change-password

Change a user's password.

**Syntax:**
```bash
python3 manage-users.py change-password <username> [--password PASSWORD]
```

**Example:**
```bash
python3 manage-users.py change-password alice
```

Password will be prompted securely if not provided.

#### reset-totp

Reset a user's TOTP secret (generates new QR code).

**Syntax:**
```bash
python3 manage-users.py reset-totp <username>
```

**Example:**
```bash
python3 manage-users.py reset-totp alice
```

Displays new TOTP secret and ASCII QR code for scanning.

#### grant-permission

Grant a permission to a user.

**Syntax:**
```bash
python3 manage-users.py grant-permission <username> <permission>
```

**Valid permissions:**
- `create_users` - Allows user to create other users and manage permissions

**Example:**
```bash
python3 manage-users.py grant-permission alice create_users
```

#### revoke-permission

Revoke a permission from a user.

**Syntax:**
```bash
python3 manage-users.py revoke-permission <username> <permission>
```

**Example:**
```bash
python3 manage-users.py revoke-permission alice create_users
```

#### list-permissions

List all permissions for a specific user.

**Syntax:**
```bash
python3 manage-users.py list-permissions <username>
```

**Example output:**
```
Permissions for user 'alice':
  • create_users
```

### Common Workflows

#### Initial Server Setup

Create the first admin user with full permissions:

```bash
# During initial setup, this creates a permanent user with TOTP
python3 manage-users.py create admin --password securePassword123
# Follow the prompts to scan the QR code with your authenticator app
```

The first user automatically receives `create_users` permission.

#### Onboarding a New Administrator

Create a temporary user for a new admin:

```bash
# Create temporary user with user creation permissions
python3 manage-users.py create newadmin --temporary \
  --password temp789xyz --grant create_users

# Share the username and temporary password with the new admin
# They must login and complete setup within 24 hours
```

The new admin will:
1. Login with temporary credentials
2. Be prompted to change password
3. Set up TOTP 2FA with QR code
4. Gain full access after completing setup

#### Rotating TOTP for Security

If a user's authenticator app is compromised or lost:

```bash
# Reset TOTP secret
python3 manage-users.py reset-totp alice

# User must scan new QR code with authenticator app
```

#### Granting Limited Permissions

Create a user who can view but not create users:

```bash
# Create user without create_users permission
python3 manage-users.py create viewer --temporary --password viewOnly456
```

Later, grant permission if needed:

```bash
python3 manage-users.py grant-permission viewer create_users
```

### Security Notes

- **Temporary users auto-disable**: Temporary users not completing setup within 24 hours are automatically disabled by a background task
- **TOTP is mandatory**: All users must have TOTP configured (no exceptions)
- **Password requirements**: Minimum 8 characters
- **Permission system**: Designed to be extensible - additional permissions can be added in the future
- **Audit trail**: All permission grants are logged with the granting administrator's username

---

## Standalone Challenge Runner

The standalone challenge runner (`challengectl.py`) allows you to run SDR challenges directly on a local machine without using the distributed server/runner architecture. This is useful for testing challenges, running small-scale CTF events, or single-device deployments.

### Overview

The standalone runner:

- Loads challenges from a YAML configuration file
- Manages multiple SDR devices
- Transmits challenges in random order with configurable delays
- Supports all modulation types (CW, ASK, NBFM, SSB, FHSS, POCSAG, LRS, FreeDV, Paint)
- Provides testing mode for validating challenge configurations

### Basic Usage

```bash
python3 challengectl.py <config_file> [OPTIONS]
```

### Command-Line Options

| Option | Description |
|--------|-------------|
| `configfile` | Path to YAML configuration file (required) |
| `-v, --verbose` | Enable verbose output for detailed execution information |
| `-t, --test` | Run each challenge once for testing purposes |
| `-d, --dump-config` | Display parsed devices and challenges without running anything |
| `--log-level LEVEL` | Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |

### Configuration File Format

Create a YAML configuration file with your devices and challenges:

```yaml
conference:
  name: "RFCTF 2024"

devices:
  - name: 0
    model: hackrf
    frequency_ranges:
      - "144000000-148000000"
      - "420000000-450000000"

  - name: 1
    model: limesdr
    frequency_ranges:
      - "902000000-928000000"

challenges:
  - name: CW_FLAG_1
    frequency: 146520000
    modulation: cw
    flag: challenges/morse.txt
    speed: 20
    min_delay: 120
    max_delay: 180
    enabled: true

  - name: NBFM_FLAG_2
    frequency: 146550000
    modulation: nbfm
    flag: challenges/voice.wav
    wav_samplerate: 48000
    min_delay: 60
    max_delay: 90
    enabled: true

  - name: FHSS_FLAG_3
    frequency: 433000000
    modulation: fhss
    flag: challenges/data.bin
    channel_spacing: 10000
    hop_rate: 10
    hop_time: 60
    seed: RFHS
    min_delay: 90
    max_delay: 120
    enabled: true
```

### Examples

#### Running Challenges

Start the challenge runner with default settings:

```bash
python3 challengectl.py config.yml
```

Run with verbose output:

```bash
python3 challengectl.py config.yml --verbose
```

#### Testing Configuration

Test each challenge once to verify configuration:

```bash
python3 challengectl.py config.yml --test
```

Display configuration without running:

```bash
python3 challengectl.py config.yml --dump-config
```

#### Debug Mode

Run with debug logging for troubleshooting:

```bash
python3 challengectl.py config.yml --log-level DEBUG
```

### Device Configuration

Each device in the configuration file requires:

- **name**: Device identifier (typically 0, 1, 2, etc.)
- **model**: Device type (`hackrf`, `limesdr`, `usrp`, `bladerf`)
- **frequency_ranges**: List of supported frequency ranges in Hz

Optional parameters:

- **antenna**: Antenna port selection (device-specific)
- **bias_t**: Enable bias-tee power (true/false)

Example device configurations:

```yaml
# HackRF with specific frequency ranges
devices:
  - name: 0
    model: hackrf
    frequency_ranges:
      - "144000000-148000000"

# LimeSDR with multiple ranges and antenna selection
  - name: 1
    model: limesdr
    antenna: BAND2
    frequency_ranges:
      - "420000000-450000000"
      - "902000000-928000000"

# BladeRF with bias-tee enabled
  - name: 2
    model: bladerf
    bias_t: true
    frequency_ranges:
      - "2400000000-2500000000"
```

### Challenge Configuration

Each challenge requires the following parameters:

- **name**: Unique challenge identifier
- **frequency**: Transmission frequency in Hz
- **modulation**: Modulation type (see supported types below)
- **flag**: Path to challenge file
- **min_delay**: Minimum seconds between transmissions
- **max_delay**: Maximum seconds between transmissions
- **enabled**: Whether the challenge is active (true/false)

Modulation-specific parameters:

| Modulation | Additional Parameters |
|------------|----------------------|
| `cw` | `speed` - Words per minute (default: 20) |
| `nbfm` | `wav_samplerate` - Sample rate of WAV file |
| `ssb` | `mode` - SSB mode (usb/lsb), `wav_samplerate` |
| `fhss` | `channel_spacing`, `hop_rate`, `hop_time`, `seed` |
| `pocsag` | `capcode` - POCSAG capcode |
| `lrs` | No additional parameters |
| `freedv` | `mode` - FreeDV mode (1600, 700, etc.) |
| `ask` | No additional parameters |
| `paint` | No additional parameters (uses image files) |

### Logs

The standalone runner creates a log file named `challengectl.log` in the current directory. This file contains:

- Startup and shutdown events
- Challenge execution details
- Device assignments
- Errors and warnings

Monitor the log in real-time:

```bash
tail -f challengectl.log
```

### Limitations

The standalone runner has some limitations compared to the distributed server/runner architecture:

- No web interface for monitoring
- No automatic failover or redundancy
- Limited to devices on a single machine
- No centralized logging or statistics
- Manual restart required on failure

For production deployments or multi-device setups, consider using the [server/runner architecture](Architecture).

## API Key Generation

The `generate-api-key.py` script creates cryptographically secure API keys for runner authentication.

### Basic Usage

Generate a single 32-character API key:

```bash
python3 generate-api-key.py
```

Example output:

```
ck_a3f8b9c2d1e4f5a6b7c8d9e0f1a2
```

### Command-Line Options

| Option | Description |
|--------|-------------|
| `-l, --length LENGTH` | Length of each API key (default: 32, minimum: 16) |
| `-c, --count COUNT` | Number of API keys to generate (default: 1) |

### Examples

#### Generate Multiple Keys

Generate 5 API keys for multiple runners:

```bash
python3 generate-api-key.py --count 5
```

Output:

```
Generated 5 API keys (length: 32):

Key 1: ck_a3f8b9c2d1e4f5a6b7c8d9e0f1a2
Key 2: ck_b4g9c0d2e5f6a7b8c9d0e1f2a3b4
Key 3: ck_c5h0d1e3f7a8b9c0d1e2f3a4b5c6
Key 4: ck_d6i1e2f4a9b0c1d2e3f4a5b6c7d8
Key 5: ck_e7j2f3a5b1c2d3e4f5a6b7c8d9e0
```

#### Generate Longer Keys

Generate a 64-character API key for enhanced security:

```bash
python3 generate-api-key.py --length 64
```

#### Batch Generation

Generate 3 48-character keys:

```bash
python3 generate-api-key.py --length 48 --count 3
```

### Security Considerations

- API keys are generated using Python's `secrets` module, which provides cryptographically strong randomness
- Keys include alphanumeric characters plus hyphens and underscores
- Minimum key length is 16 characters (enforced by the script)
- For production use, 32-character keys provide adequate security
- Longer keys (48 or 64 characters) provide additional security margin

### Using API Keys with Runner Enrollment

Use the secure enrollment process through the Web UI:

1. **Log in to the Web UI** at `http://your-server:8443`

2. **Go to Runners page** and click "Add Runner"

3. **Generate enrollment credentials**: The system will generate both an enrollment token and API key automatically

4. **Copy the credentials** to your runner configuration (they're only shown once)

See the [Runner Setup Guide](Runner-Setup#enroll-your-runner-recommended) for complete enrollment instructions.

### Key Format

Generated API keys follow the format:

```
ck_<random_characters>
```

The `ck_` prefix identifies the key as a ChallengeCtl API key. The random portion uses URL-safe characters (letters, numbers, hyphens, underscores).

### Best Practices

- Generate a unique API key for each runner
- Store keys securely (use environment variables or secure configuration management)
- Rotate keys periodically (e.g., every 6-12 months)
- Revoke keys for decommissioned runners
- Use longer keys (48 or 64 characters) for high-security environments
- Never commit API keys to version control

## Next Steps

Now that you're familiar with the command-line utilities, you can:

- [Configure the server](Server-Setup) for distributed challenge management
- [Set up runners](Runner-Setup) to connect to your server
- [Use the Web Interface](Web-Interface-Guide) to manage users and monitor the system
- [Review the Configuration Reference](Configuration-Reference) for all available options
- [Understand the system architecture](Architecture) to learn how components interact
