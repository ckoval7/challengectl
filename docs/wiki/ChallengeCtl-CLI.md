# ChallengeCtl Command-Line Interface

ChallengeCtl provides several command-line utilities for managing the system and running challenges. This guide covers the standalone challenge runner and API key generation tools.

## Table of Contents

- [Standalone Challenge Runner](#standalone-challenge-runner)
- [API Key Generation](#api-key-generation)

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

### Adding Keys to Server Configuration

After generating an API key, add it to your server configuration file:

1. **Generate the key**:
```bash
python3 generate-api-key.py
```

2. **Edit `server-config.yml`**:
```yaml
server:
  api_keys:
    runner-1: "ck_abc123def456..."  # Your generated key
    runner-2: "ck_def456ghi789..."  # Another generated key
```

3. **Restart the server** to apply changes:
```bash
sudo systemctl restart challengectl
# Or if running manually:
# Press Ctrl+C and restart: python -m challengectl.server.server
```

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
