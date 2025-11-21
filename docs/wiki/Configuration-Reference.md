# Configuration Reference

This comprehensive reference documents all configuration options for the ChallengeCtl server and runner. Both components use YAML configuration files that define system behavior, challenge parameters, and device settings.

## Table of Contents

- [Server Configuration](#server-configuration)
- [Runner Configuration](#runner-configuration)
- [Challenge Configuration](#challenge-configuration)
- [Modulation-Specific Parameters](#modulation-specific-parameters)
- [Environment Variables](#environment-variables)

## Server Configuration

The server configuration file (default: `server-config.yml`) defines server behavior, API keys, and challenge definitions.

### Server Section

Configures the Flask web server and API settings.

```yaml
server:
  bind: "0.0.0.0"
  port: 8443
  cors_origins:
    - "https://challengectl.example.com"
  api_keys:
    runner-1: "api-key-here"
  files_dir: "files"
  heartbeat_timeout: 90
  assignment_timeout: 300
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `bind` | string | `"0.0.0.0"` | IP address to bind the server to. Use `"0.0.0.0"` for all interfaces or `"127.0.0.1"` for localhost only. |
| `port` | integer | `8443` | TCP port for the HTTP server. |
| `cors_origins` | array | `[]` | List of allowed CORS origins for web UI access. Never use wildcards with credentials. |
| `files_dir` | string | `"files"` | Directory where challenge files are stored. Relative to server working directory. |
| `heartbeat_timeout` | integer | `90` | Seconds before marking a runner offline due to missed heartbeats. Should be 3x heartbeat interval. |
| `assignment_timeout` | integer | `300` | Seconds before requeuing a challenge that remains assigned. Prevents stuck assignments. |

#### CORS Origins

The `cors_origins` setting is security-critical. It controls which web origins can make authenticated requests to the API.

**Development**:
```yaml
cors_origins:
  - "http://localhost:5173"  # Vite dev server
  - "http://localhost:8443"  # Direct server access
```

**Production**:
```yaml
cors_origins:
  - "https://challengectl.example.com"
  - "https://www.challengectl.example.com"
```

**Important**: Never use wildcards (`*`) with credentials. This is a major security vulnerability.

#### API Keys

API keys are **not** stored in this configuration file. Use the secure enrollment process via the Web UI instead. See [Runner Setup Guide](Runner-Setup#enroll-your-runner) for instructions.

The enrollment process provides:
- API keys stored bcrypt-hashed in the database (one-way hashing like passwords)
- One-time credential display during generation
- Multi-factor host validation to prevent credential reuse on multiple machines
  - Captures MAC address, machine ID, IP address, and hostname
  - Enforces validation immediately (no grace period)
  - Requires at least ONE identifier to match for authentication
- Enrollment token expiration for time-limited registration
- Each runner has a unique, cryptographically random 32-character key
- Re-enrollment process for legitimate host migration

### Frequency Ranges Section

Defines named frequency ranges for random frequency selection in challenges. This is optional but recommended for dynamic frequency allocation.

```yaml
frequency_ranges:
  - name: "ham_144"
    display_name: "2 Meter Ham Band"
    description: "2m Amateur Radio Band (144-148 MHz)"
    min_hz: 144000000
    max_hz: 148000000

  - name: "ham_440"
    display_name: "70 Centimeter Ham Band"
    description: "70cm Amateur Radio Band (420-450 MHz)"
    min_hz: 420000000
    max_hz: 450000000

  - name: "ism_433"
    display_name: "433 MHz ISM Band"
    description: "433 MHz ISM Band (433.05-434.79 MHz)"
    min_hz: 433050000
    max_hz: 434790000
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | yes | Unique identifier for the range. Used in challenge configuration. |
| `display_name` | string | yes | Human-friendly name shown in the UI and public dashboard. |
| `description` | string | yes | Detailed description of the frequency range. |
| `min_hz` | integer | yes | Minimum frequency in Hz. |
| `max_hz` | integer | yes | Maximum frequency in Hz. |

#### Usage

When a challenge references one or more frequency ranges, the system:
1. Randomly selects one of the specified ranges (if multiple are configured)
2. Randomly selects a frequency within that range
3. Assigns the frequency to the runner before transmission

This allows for:
- **Dynamic frequency allocation** - Different frequency on each transmission
- **Band-specific challenges** - Constrain challenges to specific amateur or ISM bands
- **Event flexibility** - Update available ranges without modifying challenges

#### Reloading Configuration

Frequency ranges can be dynamically reloaded without restarting the server:
- Via API: `POST /api/frequency-ranges/reload`
- Via Web UI: Click "Reload" button in the frequency range selector

See [API Reference](API-Reference#frequency-range-management) for endpoint details.

### Conference Section

Defines event metadata and scheduling (optional).

```yaml
conference:
  name: "RFCTF 2025"
  start: "2025-04-05 09:00:00 -5"
  stop: "2025-04-07 18:00:00 -5"
  timezone: "America/New_York"
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | string | `"ChallengeCtl"` | Name of the conference or event. Displayed in the web UI and TOTP provisioning. |
| `start` | string | none | Event start time in format "YYYY-MM-DD HH:MM:SS TZ". |
| `stop` | string | none | Event stop time in format "YYYY-MM-DD HH:MM:SS TZ". |
| `timezone` | string | system | Timezone for event times (e.g., "America/New_York", "UTC"). |

### Challenges Section

Defines all challenges that the system will transmit. See [Challenge Configuration](#challenge-configuration) below for detailed parameters.

## Runner Configuration

The runner configuration file (default: `runner-config.yml`) defines how the runner connects to the server and manages SDR devices.

### Runner Section

Configures the runner's connection and behavior.

```yaml
runner:
  runner_id: "runner-1"
  server_url: "https://192.168.1.100:8443"
  api_key: "ck_abc123def456ghi789"
  ca_cert: ""
  verify_ssl: true
  cache_dir: "cache"
  heartbeat_interval: 30
  poll_interval: 10
  spectrum_paint_before_challenge: true
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `runner_id` | string | required | Unique identifier for this runner. |
| `server_url` | string | required | Full URL to the ChallengeCtl server, including protocol and port. |
| `enrollment_token` | string | optional | One-time enrollment token from Web UI (first-time setup only). Can be left in config after enrollment. |
| `api_key` | string | required | API key for authentication. Obtained from Web UI during enrollment or legacy config. |
| `ca_cert` | string | `""` | Path to CA certificate file for SSL verification. Empty uses system certificates. |
| `verify_ssl` | boolean | `true` | Whether to verify SSL certificates. Set to `false` only for development with self-signed certs. |
| `cache_dir` | string | `"cache"` | Directory for caching downloaded challenge files. Relative to runner working directory. |
| `heartbeat_interval` | integer | `30` | Seconds between heartbeat messages to the server. |
| `poll_interval` | integer | `10` | Seconds between polling for new task assignments. |
| `spectrum_paint_before_challenge` | boolean | `true` | Whether to transmit a spectrum watermark before each challenge. |

#### Server URL

The `server_url` must be a complete URL:

**Development (HTTP)**:
```yaml
server_url: "http://192.168.1.100:8443"
```

**Production (HTTPS)**:
```yaml
server_url: "https://challengectl.example.com"
```

#### SSL Verification

For production deployments, always use SSL verification:

```yaml
verify_ssl: true
ca_cert: "/etc/ssl/certs/ca-bundle.crt"  # Optional: custom CA
```

For development with self-signed certificates:

```yaml
verify_ssl: false  # Development only!
```

**Warning**: Disabling SSL verification in production is a security risk.

#### Heartbeat and Poll Intervals

Tuning these values affects responsiveness and server load:

**Responsive (higher load)**:
```yaml
heartbeat_interval: 20  # 3 heartbeats before timeout
poll_interval: 5        # Check for tasks every 5 seconds
```

**Balanced (recommended)**:
```yaml
heartbeat_interval: 30  # 3 heartbeats before timeout
poll_interval: 10       # Check for tasks every 10 seconds
```

**Conservative (lower load)**:
```yaml
heartbeat_interval: 45  # 2 heartbeats before timeout
poll_interval: 15       # Check for tasks every 15 seconds
```

**Important**: Ensure `heartbeat_interval * 3 <= server.heartbeat_timeout` to avoid premature offline marking.

### Radios Section

Defines SDR device models and individual devices.

```yaml
radios:
  models:
    - model: hackrf
      rf_gain: 14
      if_gain: 32
      bias_t: true
      rf_samplerate: 2000000
      ppm: 0

  devices:
    - name: 0
      model: hackrf
      frequency_limits:
        - "144000000-148000000"
        - "420000000-450000000"
```

#### Model Defaults

Define default parameters for each device model. These can be overridden on individual devices.

**Supported models**:
- `hackrf` - HackRF One
- `limesdr` - LimeSDR USB/Mini
- `bladerf` - Nuand bladeRF
- `usrp` - Ettus USRP (various models)

**HackRF Example**:
```yaml
models:
  - model: hackrf
    rf_gain: 14         # RF gain (0-47 dB)
    if_gain: 32         # IF gain (0-40 dB)
    bias_t: true        # Enable antenna bias-tee
    rf_samplerate: 2000000
    ppm: 0              # Frequency correction
```

**BladeRF Example**:
```yaml
models:
  - model: bladerf
    rf_gain: 43         # TX VGA1 gain
    bias_t: true
    rf_samplerate: 2000000
    ppm: 0
    antenna: TX1        # TX antenna port
```

**USRP Example**:
```yaml
models:
  - model: usrp
    rf_gain: 20
    bias_t: false
    rf_samplerate: 2000000
    ppm: 0
```

#### Device Configuration

Define individual SDR devices available to this runner.

```yaml
devices:
  - name: 0                    # Device identifier (index or serial)
    model: hackrf              # Device model
    rf_gain: 14                # Override model default
    if_gain: 32
    frequency_limits:          # Supported frequency ranges
      - "144000000-148000000"  # 2m ham band (144-148 MHz)
      - "420000000-450000000"  # 70cm ham band (420-450 MHz)
```

#### Device Names

Device names can be:

**Index number** (simplest):
```yaml
- name: 0
  model: hackrf
```

**Serial number** (for specific device):
```yaml
- name: "1234567890abcdef"
  model: bladerf
```

**USRP identifier**:
```yaml
- name: "type=b200"
  model: usrp
```

#### Frequency Limits

Frequency limits define which challenges this device can handle.

```yaml
frequency_limits:
  - "144000000-148000000"   # 144.0 - 148.0 MHz
  - "420000000-450000000"   # 420.0 - 450.0 MHz
  - "902000000-928000000"   # 902.0 - 928.0 MHz
```

**Omitting frequency limits**:
If not specified, the device can handle any frequency within its hardware capabilities.

```yaml
- name: 0
  model: hackrf
  # No frequency_limits = can use full hardware range (1 MHz - 6 GHz)
```

**Important**: Only configure frequencies that are:
- Legal to transmit on in your jurisdiction
- Covered by your license (if required)
- Within your antenna's specifications

## Challenge Configuration

Challenges are defined in the server configuration file. Each challenge specifies transmission parameters and file references.

### Basic Challenge Structure

ChallengeCtl supports three ways to specify frequencies:

```yaml
challenges:
  # Option 1: Single frequency
  - name: NBFM_FIXED
    frequency: 146550000  # Hz (146.550 MHz)
    modulation: nbfm
    flag: challenges/file.wav
    min_delay: 60
    max_delay: 90
    enabled: true

  # Option 2: Named frequency ranges
  - name: NBFM_RANDOM
    frequency_ranges:  # Random frequency from these ranges
      - ham_144
      - ham_220
    modulation: nbfm
    flag: challenges/file.wav
    min_delay: 60
    max_delay: 90
    enabled: true

  # Option 3: Manual frequency range
  - name: CW_CUSTOM_RANGE
    manual_frequency_range:
      min_hz: 146000000  # 146.000 MHz
      max_hz: 146100000  # 146.100 MHz
    modulation: cw
    flag: "CQ CQ CQ DE RFCTF K"
    speed: 35
    min_delay: 60
    max_delay: 90
    enabled: true
```

### Common Parameters

These parameters apply to all challenges regardless of modulation type.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | yes | Unique identifier for the challenge. Alphanumeric and underscores. |
| `frequency` | integer | conditional | Transmission frequency in Hz (e.g., 146550000 for 146.55 MHz). Required if not using `frequency_ranges` or `manual_frequency_range`. |
| `frequency_ranges` | array | conditional | Array of named frequency range identifiers (e.g., `["ham_144", "ham_440"]`). System randomly selects a frequency from these ranges on each transmission. Required if not using `frequency` or `manual_frequency_range`. |
| `manual_frequency_range` | object | conditional | Custom frequency range with `min_hz` and `max_hz` integer fields. System randomly selects a frequency within this range on each transmission. Required if not using `frequency` or `frequency_ranges`. |
| `modulation` | string | yes | Modulation type. See [Modulation-Specific Parameters](#modulation-specific-parameters). |
| `flag` | string | yes | Path to challenge file or inline text content. |
| `min_delay` | integer | yes | Minimum seconds between transmissions of this challenge. |
| `max_delay` | integer | yes | Maximum seconds between transmissions of this challenge. |
| `enabled` | boolean | yes | Whether this challenge is currently active. |

**Frequency Specification:** Each challenge must use exactly one of: `frequency`, `frequency_ranges`, or `manual_frequency_range`.

**Named Frequency Ranges:** The named ranges referenced in `frequency_ranges` must be defined in the `frequency_ranges` section at the top of the configuration file. See [Frequency Ranges Section](#frequency-ranges-section) for details.

**Frequency Selection Logic:**
- `frequency`: Always uses the specified frequency
- `frequency_ranges`: On each transmission, randomly selects one range from the array, then randomly selects a frequency within that range
- `manual_frequency_range`: On each transmission, randomly selects a frequency between `min_hz` and `max_hz`

### Optional Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `public_view` | object | see below | Control visibility on public dashboard. |
| `public_view.show_frequency` | boolean | `true` | Show frequency on public pages. |
| `public_view.show_last_tx_time` | boolean | `false` | Show last transmission time publicly. |
| `public_view.show_active_status` | boolean | `true` | Show whether currently transmitting. |

### Public Visibility Example

```yaml
- name: HIDDEN_CHALLENGE
  frequency: 146550000
  modulation: cw
  flag: "SECRET MESSAGE"
  min_delay: 60
  max_delay: 90
  enabled: true
  public_view:
    show_frequency: false      # Don't show frequency
    show_last_tx_time: false   # Don't show timing
    show_active_status: false  # Don't show status
```

### Challenge File Paths

The `flag` parameter can reference files in several ways:

**Relative path** (relative to server working directory):
```yaml
flag: challenges/voice.wav
```

**Absolute path**:
```yaml
flag: /opt/challengectl/files/voice.wav
```

**Inline text** (for text-based modulations like CW, ASK):
```yaml
flag: "CQ CQ CQ DE RFCTF K"
```

### Default Delays

You can set default delays for all challenges:

```yaml
challenges:
  - default_min_delay: 60
    default_max_delay: 90

  - name: CHALLENGE_1
    # Inherits min_delay: 60, max_delay: 90
    frequency: 146550000
    modulation: nbfm
    flag: file.wav
    enabled: true

  - name: CHALLENGE_2
    # Override defaults
    min_delay: 120
    max_delay: 180
    frequency: 146600000
    modulation: cw
    flag: "HELLO WORLD"
    enabled: true
```

## Modulation-Specific Parameters

Each modulation type requires specific additional parameters beyond the common challenge parameters.

### CW (Morse Code)

Transmits text as Morse code (continuous wave).

```yaml
- name: CW_FLAG_1
  frequency: 146520000
  modulation: cw
  flag: "CQ CQ CQ DE RFCTF K"
  speed: 20
  min_delay: 60
  max_delay: 90
  enabled: true
```

**Additional parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `speed` | integer | `20` | Transmission speed in words per minute (WPM). Typical range: 5-40. |

**Flag format**: Plain text string. Supports letters, numbers, and limited punctuation.

### NBFM (Narrowband FM)

Transmits audio files using narrowband frequency modulation.

```yaml
- name: NBFM_FLAG_1
  frequency: 146550000
  modulation: nbfm
  flag: challenges/voice.wav
  wav_samplerate: 48000
  min_delay: 60
  max_delay: 90
  enabled: true
```

**Additional parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `wav_samplerate` | integer | `48000` | Sample rate of the WAV file in Hz. Common values: 44100, 48000. |

**Flag format**: Path to WAV audio file.

### SSB (Single Sideband)

Transmits audio files using single sideband modulation.

```yaml
- name: SSB_FLAG_1
  frequency: 146600000
  modulation: ssb
  mode: usb
  flag: challenges/voice.wav
  wav_samplerate: 48000
  min_delay: 60
  max_delay: 90
  enabled: true
```

**Additional parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mode` | string | `"usb"` | Sideband mode: `"usb"` (upper sideband) or `"lsb"` (lower sideband). |
| `wav_samplerate` | integer | `48000` | Sample rate of the WAV file in Hz. |

**Flag format**: Path to WAV audio file.

### ASK (Amplitude Shift Keying)

Transmits binary data using amplitude shift keying.

```yaml
- name: ASK_FLAG_1
  frequency: 146700000
  modulation: ask
  flag: "flag{this_is_ask_data}"
  min_delay: 60
  max_delay: 90
  enabled: true
```

**Additional parameters**: None

**Flag format**: Text string (will be encoded to binary).

### POCSAG (Paging)

Transmits paging messages using the POCSAG protocol.

```yaml
- name: POCSAG_FLAG_1
  frequency: 146800000
  modulation: pocsag
  flag: "POCSAG message with flag"
  capcode: 123456
  min_delay: 60
  max_delay: 90
  enabled: true
```

**Additional parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `capcode` | integer | required | POCSAG capcode (address) for the message. Typically 7-digit number. |

**Flag format**: Text string (message content).

### FHSS (Frequency Hopping Spread Spectrum)

Transmits data using frequency hopping.

```yaml
- name: FHSS_FLAG_1
  frequency: 433000000
  modulation: fhss
  flag: challenges/data.wav
  channel_spacing: 10000
  hop_rate: 10
  hop_time: 60
  seed: RFHS
  wav_samplerate: 48000
  min_delay: 120
  max_delay: 180
  enabled: true
```

**Additional parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `channel_spacing` | integer | `10000` | Spacing between hop channels in Hz. |
| `hop_rate` | integer | `10` | Number of hops per second. |
| `hop_time` | integer | `60` | Total transmission time in seconds. |
| `seed` | string | `"RFHS"` | Pseudo-random seed for hop sequence. Same seed = same sequence. |
| `wav_samplerate` | integer | `48000` | Sample rate of the WAV file in Hz. |

**Flag format**: Path to WAV audio file.

### LRS (LoRa)

Transmits using LoRa spread spectrum modulation.

```yaml
- name: LRS_FLAG_1
  frequency: 146900000
  modulation: lrs
  flag: "-s 10 -p 976 -pf 1"
  min_delay: 60
  max_delay: 90
  enabled: true
```

**Additional parameters**: None (parameters embedded in flag string)

**Flag format**: Command-line arguments for LoRa transmitter. Common options:
- `-s` - Spreading factor
- `-p` - Preamble length
- `-pf` - Preamble format

### FreeDV (Digital Voice)

Transmits digital voice using FreeDV.

```yaml
- name: FREEDV_FLAG_1
  frequency: 147100000
  modulation: freedv
  mode: usb
  flag: challenges/voice.wav
  text: "FreeDV text message"
  wav_samplerate: 48000
  min_delay: 60
  max_delay: 90
  enabled: true
```

**Additional parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mode` | string | `"usb"` | FreeDV mode (USB/LSB). |
| `text` | string | optional | Optional text message to transmit alongside voice. |
| `wav_samplerate` | integer | `48000` | Sample rate of the WAV file in Hz. |

**Flag format**: Path to WAV audio file.

### Paint (Spectrum Waterfall)

Transmits images as spectrum waterfall patterns.

```yaml
- name: PAINT_FLAG_1
  frequency: 147000000
  modulation: paint
  flag: challenges/image.bin
  min_delay: 120
  max_delay: 180
  enabled: true
```

**Additional parameters**: None

**Flag format**: Path to binary file or image file (PNG, JPG) for spectrum painting.

## Environment Variables

Both server and runner support environment variables for overriding configuration.

### Server Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `CONFIG_PATH` | Path to server configuration file | `/etc/challengectl/server-config.yml` |
| `DATABASE_PATH` | Path to SQLite database file | `/var/lib/challengectl/challengectl.db` |
| `PORT` | Override server port | `8080` |
| `HOST` | Override bind address | `127.0.0.1` |
| `CHALLENGECTL_CORS_ORIGINS` | Comma-separated CORS origins | `https://example.com,https://www.example.com` |

**Example usage**:
```bash
export CONFIG_PATH=/etc/challengectl/server-config.yml
export DATABASE_PATH=/var/lib/challengectl/challengectl.db
export PORT=8080
python -m server.server
```

### Runner Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `CONFIG_PATH` | Path to runner configuration file | `/etc/challengectl/runner-config.yml` |

**Example usage**:
```bash
export CONFIG_PATH=/etc/challengectl/runner-config.yml
python -m runner.runner
```

## Configuration Best Practices

### Security

1. **Protect configuration files**:
   ```bash
   chmod 600 server-config.yml runner-config.yml
   ```

2. **Use strong API keys**:
   - Minimum 32 characters
   - Cryptographically random
   - Unique per runner

3. **Enable SSL in production**:
   ```yaml
   server_url: "https://challengectl.example.com"
   verify_ssl: true
   ```

4. **Restrict CORS origins**:
   ```yaml
   cors_origins:
     - "https://challengectl.example.com"  # Specific domain only
   ```

### Performance

1. **Tune poll intervals** based on your needs:
   - Lower values = more responsive but higher load
   - Higher values = lower load but less responsive

2. **Set appropriate timeouts**:
   ```yaml
   heartbeat_timeout: 90      # 3x heartbeat_interval
   assignment_timeout: 300    # 5 minutes for transmission + download
   ```

3. **Use frequency limits** to distribute load:
   ```yaml
   # Runner 1 handles 2m band
   frequency_limits:
     - "144000000-148000000"

   # Runner 2 handles 70cm band
   frequency_limits:
     - "420000000-450000000"
   ```

### Reliability

1. **Set realistic delays**:
   ```yaml
   min_delay: 60   # Minimum 1 minute between transmissions
   max_delay: 120  # Maximum 2 minutes
   ```

2. **Use absolute file paths** in production:
   ```yaml
   flag: /opt/challengectl/files/challenge.wav
   ```

3. **Test configurations** before deployment:
   ```bash
   python challengectl.py config.yml --dump-config
   ```

## Next Steps

Now that you understand all configuration options, you can:

- [Set up the server](Server-Setup) with your custom configuration
- [Deploy runners](Runner-Setup) with optimized settings
- [Review the Architecture](Architecture) to understand how configuration affects system behavior
- [Explore the API](API-Reference) for programmatic configuration management
