# Challenge Development Guide

This guide covers how to add new challenge types and modulations to ChallengeCtl. Adding a new challenge involves creating a GNU Radio flowgraph, implementing the fire function in the runner, and integrating it with the challenge distribution system.

## Table of Contents

- [Overview](#overview)
- [Creating a GNU Radio Flowgraph](#creating-a-gnu-radio-flowgraph)
- [Implementing the Fire Function](#implementing-the-fire-function)
- [Integrating with the Runner](#integrating-with-the-runner)
- [Configuration](#configuration)
- [Testing](#testing)
- [Best Practices](#best-practices)
- [Examples](#examples)

## Overview

ChallengeCtl supports multiple modulation types, each implemented as a separate GNU Radio flowgraph. When adding a new challenge type, you will:

1. **Design the flowgraph** in GNU Radio Companion (GRC)
2. **Use parameters** instead of variables for runtime configuration
3. **Configure the osmocom sink** for SDR output
4. **Generate Python code** from the flowgraph
5. **Create a fire function** that wraps the flowgraph
6. **Integrate with the runner** to enable challenge execution
7. **Update configuration schemas** to support the new modulation type

## Creating a GNU Radio Flowgraph

### Step 1: Open GNU Radio Companion

Launch GNU Radio Companion to create your flowgraph:

```bash
gnuradio-companion
```

### Step 2: Use Parameters Instead of Variables

**Critical**: ChallengeCtl passes runtime values to flowgraphs. You must use **Parameters** blocks, not **Variables** blocks, for any values that need to be controlled by challengectl.

**Variables**: Computed once when the flowgraph starts (static)
**Parameters**: Can be passed in when the flowgraph is instantiated (dynamic)

#### Adding Parameters

1. From the block list, add **Parameter** blocks (not Variable blocks)
2. Configure each parameter with:
   - **ID**: The parameter name (e.g., `tx_freq`, `sample_rate`, `gain`)
   - **Type**: Data type (int, float, string, etc.)
   - **Default Value**: Fallback value for testing

**Example parameters for a typical challenge**:

```
Parameter: tx_freq
  Type: int
  Default: 146550000

Parameter: sample_rate
  Type: int
  Default: 2000000

Parameter: rf_gain
  Type: int
  Default: 14

Parameter: if_gain
  Type: int
  Default: 32

Parameter: audio_file
  Type: string
  Default: "/tmp/test.wav"

Parameter: device_string
  Type: string
  Default: "hackrf=0"
```

#### Common Parameters

Most challenges should accept these standard parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `tx_freq` | int | Transmission frequency in Hz |
| `sample_rate` | int | RF sample rate (typically 2000000) |
| `rf_gain` | int | RF gain setting for the SDR |
| `if_gain` | int | IF gain setting (HackRF only) |
| `device_string` | string | Osmocom device identifier |
| `audio_file` or `flag_file` | string | Path to the challenge file |

### Step 3: Configure the Osmocom Sink

Every challenge flowgraph must output to an **osmocom Sink** block to transmit via SDR hardware.

#### Adding the Osmocom Sink

1. Add **osmocom Sink** block from the block list
2. Configure the block:

**Device Arguments**:
```python
device_string
```
Use the `device_string` parameter to allow runtime device selection.

**Sample Rate**:
```python
sample_rate
```
Use the `sample_rate` parameter.

**Center Frequency**:
```python
tx_freq
```
Use the `tx_freq` parameter for runtime frequency control.

**RF Gain**:
```python
rf_gain
```
Use the `rf_gain` parameter.

**IF Gain** (HackRF only):
```python
if_gain
```
Use the `if_gain` parameter.

**Antenna**:
```python
antenna if antenna else ""
```
Optional antenna selection parameter.

**Bandwidth**:
```python
0
```
Zero typically means automatic bandwidth selection.

#### Sample Osmocom Sink Configuration

```
Block: osmocom Sink
  Device Arguments: device_string
  Sample Rate (sps): sample_rate
  Ch0: Frequency (Hz): tx_freq
  Ch0: RF Gain (dB): rf_gain
  Ch0: IF Gain (dB): if_gain
  Ch0: Bandwidth (Hz): 0
```

### Step 4: Build Your Signal Processing Chain

Design the signal processing blocks between your source and the osmocom sink. This varies by modulation type.

#### Example: NBFM Transmitter Chain

```
[WAV File Source] → [Rational Resampler] → [NBFM Transmitter] → [Rational Resampler] → [osmocom Sink]
```

#### Example: CW Transmitter Chain

```
[Vector Source] → [Repeat] → [Multiply Const] → [Frequency Modulator] → [Rational Resampler] → [osmocom Sink]
```

### Step 5: Set Flowgraph Options

Configure the flowgraph properties (double-click the canvas):

**ID**: Use a descriptive name (e.g., `nbfm_tx`, `cw_tx`, `fhss_tx`)

**Title**: Human-readable title

**Generate Options**: `No GUI` (required for headless operation)

**Run**: `True` (so the flowgraph runs when instantiated)

**Realtime Scheduling**: `Off` (unless specifically needed)

### Step 6: Generate Python Code

1. Click the **Generate** button (gear icon) or press F5
2. GNU Radio generates a `.py` file in your working directory
3. Review the generated code to understand the class structure

The generated file will contain a class with a constructor that accepts your parameters:

```python
class nbfm_tx(gr.top_block):
    def __init__(self, tx_freq=146550000, sample_rate=2000000,
                 rf_gain=14, if_gain=32, audio_file="/tmp/test.wav",
                 device_string="hackrf=0"):
        # Flowgraph implementation
```

### Step 7: Save the Flowgraph

Save your `.grc` file in the `challenges/` directory of the repository for future reference and maintenance.

```bash
challenges/
  ├── nbfm_tx.grc
  ├── cw_tx.grc
  ├── ssb_tx.grc
  └── your_new_modulation.grc
```

## Implementing the Fire Function

The fire function is a Python wrapper that instantiates your flowgraph, runs it, and handles errors. It serves as the interface between the runner and GNU Radio.

### Location

Create or modify files in the `challenges/` directory:

```bash
challenges/
  ├── __init__.py
  ├── nbfm.py
  ├── cw.py
  └── your_modulation.py
```

### Basic Fire Function Structure

```python
#!/usr/bin/env python3
"""
Your modulation challenge implementation.
"""

from gnuradio import gr
import logging
import time
from typing import Optional

# Import your generated flowgraph class
from challenges.your_modulation_flowgraph import your_modulation_tx

logger = logging.getLogger(__name__)


def main(frequency: int,
         device_string: str,
         flag_file: str,
         antenna: Optional[str] = None,
         rf_gain: int = 14,
         if_gain: int = 32,
         sample_rate: int = 2000000,
         **kwargs):
    """
    Fire a your_modulation challenge.

    Args:
        frequency: Transmission frequency in Hz
        device_string: Osmocom device string
        flag_file: Path to the challenge file
        antenna: Optional antenna selection
        rf_gain: RF gain in dB
        if_gain: IF gain in dB (HackRF only)
        sample_rate: RF sample rate in Hz
        **kwargs: Additional modulation-specific parameters

    Returns:
        int: 0 on success, non-zero on error
    """
    try:
        logger.info(f"Starting your_modulation transmission on {frequency} Hz")

        # Instantiate the flowgraph with parameters
        tb = your_modulation_tx(
            tx_freq=frequency,
            sample_rate=sample_rate,
            rf_gain=rf_gain,
            if_gain=if_gain,
            device_string=device_string,
            flag_file=flag_file,
            antenna=antenna if antenna else ""
            # Add modulation-specific parameters here
        )

        # Start the flowgraph
        tb.start()

        # Wait for transmission to complete
        # Option 1: Wait for flowgraph to finish (if using Head block or finite source)
        tb.wait()

        # Option 2: Run for a specific duration (if using infinite source)
        # duration = kwargs.get('duration', 30)  # seconds
        # time.sleep(duration)
        # tb.stop()
        # tb.wait()

        logger.info("Transmission completed successfully")
        return 0

    except Exception as e:
        logger.error(f"Error during transmission: {e}", exc_info=True)
        return 1

    finally:
        # Cleanup
        try:
            tb.stop()
            tb.wait()
        except Exception:
            pass


if __name__ == '__main__':
    # Test the challenge locally
    import argparse

    parser = argparse.ArgumentParser(description='Your Modulation Challenge')
    parser.add_argument('-f', '--frequency', type=int, default=146550000,
                        help='Transmission frequency in Hz')
    parser.add_argument('-d', '--device', type=str, default='hackrf=0',
                        help='Device string')
    parser.add_argument('-i', '--input', type=str, required=True,
                        help='Path to challenge file')
    parser.add_argument('-g', '--rf-gain', type=int, default=14,
                        help='RF gain in dB')
    parser.add_argument('--if-gain', type=int, default=32,
                        help='IF gain in dB')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    exit(main(
        frequency=args.frequency,
        device_string=args.device,
        flag_file=args.input,
        rf_gain=args.rf_gain,
        if_gain=args.if_gain
    ))
```

### Fire Function Best Practices

1. **Accept standard parameters**: All fire functions should accept `frequency`, `device_string`, and `flag_file` at minimum
2. **Use logging**: Log start, completion, and errors using Python's logging module
3. **Handle exceptions**: Wrap flowgraph execution in try/except blocks
4. **Return status codes**: Return 0 on success, non-zero on error
5. **Clean up resources**: Always stop and wait for the flowgraph in a finally block
6. **Support testing**: Include a `__main__` block for standalone testing

### Handling Different Source Types

#### File-Based Sources (WAV, Binary)

```python
# File will be read by flowgraph
tb = your_tx(
    flag_file=flag_file,
    # ...
)
tb.start()
tb.wait()  # Waits until file is fully transmitted
```

#### Text-Based Sources (CW, Text Messages)

```python
# Convert text to appropriate format
message = kwargs.get('message', 'DEFAULT MESSAGE')

tb = your_tx(
    message=message,
    # ...
)
tb.start()
tb.wait()
```

#### Duration-Based Transmission

```python
# Run for specified duration
duration = kwargs.get('duration', 30)

tb = your_tx(
    # parameters
)
tb.start()
time.sleep(duration)
tb.stop()
tb.wait()
```

## Integrating with the Runner

### Step 1: Register the Fire Function

Import your fire function in the runner's challenge module.

Edit `runner/runner.py` (or the appropriate runner file):

```python
from challenges import (
    ask,
    cw,
    nbfm,
    ssb_tx,
    fhss_tx,
    pocsagtx_osmocom,
    lrs_pager,
    lrs_tx,
    freedv_tx,
    spectrum_paint,
    your_modulation  # Add your module
)
```

### Step 2: Add Modulation Mapping

Add your modulation type to the runner's modulation dispatcher:

```python
MODULATION_MAP = {
    'cw': cw.main,
    'ask': ask.main,
    'nbfm': nbfm.main,
    'ssb': ssb_tx.main,
    'fhss': fhss_tx.main,
    'pocsag': pocsagtx_osmocom.main,
    'lrs': lrs_tx.main,
    'freedv': freedv_tx.main,
    'paint': spectrum_paint.main,
    'your_modulation': your_modulation.main,  # Add your mapping
}
```

### Step 3: Create Challenge Execution Logic

The runner will call your fire function with appropriate parameters:

```python
def execute_challenge(challenge, device_string, antenna):
    """Execute a challenge transmission."""
    modulation = challenge['modulation']

    if modulation not in MODULATION_MAP:
        logger.error(f"Unknown modulation type: {modulation}")
        return False

    fire_function = MODULATION_MAP[modulation]

    # Build parameters dict
    params = {
        'frequency': challenge['frequency'],
        'device_string': device_string,
        'flag_file': challenge['flag_file'],
        'antenna': antenna,
        'rf_gain': challenge.get('rf_gain', 14),
        'if_gain': challenge.get('if_gain', 32),
    }

    # Add modulation-specific parameters
    if modulation == 'your_modulation':
        params['custom_param'] = challenge.get('custom_param', default_value)

    # Execute
    try:
        result = fire_function(**params)
        return result == 0
    except Exception as e:
        logger.error(f"Challenge execution failed: {e}")
        return False
```

## Configuration

### Add to Modulation Parameters

Update `modulation_parameters.yml` to define required and optional parameters for your new modulation:

```yaml
your_modulation:
  mandatory:
    - frequency
    - flag
    - modulation
    - min_delay
    - max_delay
  optional:
    - custom_param
    - another_param
```

### Example Challenge Configuration

Add example challenges to the server configuration:

```yaml
challenges:
  - name: YOUR_MOD_FLAG_1
    frequency: 146550000
    modulation: your_modulation
    flag: challenges/your_file.bin
    min_delay: 60
    max_delay: 90
    enabled: true
    # Modulation-specific parameters
    custom_param: 42
    another_param: "value"
```

## Testing

### Step 1: Test the Flowgraph Directly

Test your flowgraph in GNU Radio Companion first:

1. Set parameter default values to real test values
2. Click **Execute** (play button) or press F6
3. Verify transmission with an SDR receiver
4. Check for errors in the console output

### Step 2: Test the Fire Function Standalone

Test your fire function directly:

```bash
cd challenges/
python3 your_modulation.py \
    --frequency 146550000 \
    --device "hackrf=0" \
    --input /path/to/test/file.bin \
    --rf-gain 14
```

Monitor with an SDR receiver to verify the signal.

### Step 3: Test with Standalone ChallengeCtl

Create a test configuration file:

```yaml
conference:
  name: "Test"

devices:
  - name: 0
    model: hackrf
    frequency_limits:
      - "144000000-148000000"

challenges:
  - name: TEST_YOUR_MOD
    frequency: 146550000
    modulation: your_modulation
    flag: challenges/test.bin
    min_delay: 60
    max_delay: 90
    enabled: true
    custom_param: 42
```

Run standalone challengectl:

```bash
python3 challengectl.py test-config.yml --test
```

### Step 4: Test with Runner and Server

1. Deploy your changes to a test server
2. Configure a test challenge in `server-config.yml`
3. Start a runner and monitor logs
4. Verify the challenge is received, executed, and completed successfully

### Validation Checklist

- [ ] Flowgraph uses parameters, not variables
- [ ] Osmocom sink is properly configured
- [ ] Fire function accepts standard parameters
- [ ] Fire function logs appropriately
- [ ] Standalone test transmits successfully
- [ ] Signal can be received and decoded
- [ ] Runner integrates without errors
- [ ] Challenge appears in server configuration
- [ ] Challenge executes and completes successfully
- [ ] Error handling works correctly

## Best Practices

### Flowgraph Design

1. **Keep it simple**: Minimize complexity where possible
2. **Use standard blocks**: Prefer built-in GNU Radio blocks over custom code
3. **Handle errors gracefully**: Add error handling for file operations
4. **Test thoroughly**: Verify with real SDR hardware
5. **Document parameters**: Comment your flowgraph clearly

### Fire Function Design

1. **Consistent interface**: Match the pattern of existing fire functions
2. **Comprehensive logging**: Log all important events and errors
3. **Resource cleanup**: Always clean up in finally blocks
4. **Flexible parameters**: Support optional parameters with sensible defaults
5. **Return status codes**: 0 for success, non-zero for failure

### Performance

1. **Optimize sample rates**: Use appropriate sample rates for your modulation
2. **Minimize CPU usage**: Avoid unnecessary processing blocks
3. **Test on target hardware**: Verify performance on actual runner devices
4. **Monitor memory**: Check for memory leaks in long-running tests

### Security

1. **Validate inputs**: Check file paths and parameters
2. **Sanitize filenames**: Prevent path traversal attacks
3. **Limit file sizes**: Don't load excessively large files into memory
4. **Error messages**: Don't expose sensitive paths or information

## Examples

### Example 1: Simple Text-Based Modulation

```python
#!/usr/bin/env python3
"""Simple text-based modulation example."""

from gnuradio import gr
from challenges.text_mod_flowgraph import text_mod_tx
import logging

logger = logging.getLogger(__name__)

def main(frequency, device_string, flag_file, antenna=None,
         rf_gain=14, if_gain=32, **kwargs):
    try:
        # Read text from file
        with open(flag_file, 'r') as f:
            message = f.read().strip()

        logger.info(f"Transmitting message on {frequency} Hz")

        tb = text_mod_tx(
            tx_freq=frequency,
            device_string=device_string,
            message=message,
            rf_gain=rf_gain,
            if_gain=if_gain
        )

        tb.start()
        tb.wait()

        logger.info("Transmission complete")
        return 0

    except Exception as e:
        logger.error(f"Transmission failed: {e}")
        return 1
```

### Example 2: Binary File Transmission

```python
#!/usr/bin/env python3
"""Binary file transmission example."""

from gnuradio import gr
from challenges.binary_mod_flowgraph import binary_mod_tx
import logging
import os

logger = logging.getLogger(__name__)

def main(frequency, device_string, flag_file, antenna=None,
         rf_gain=14, if_gain=32, sample_rate=2000000, **kwargs):
    try:
        # Validate file exists
        if not os.path.exists(flag_file):
            logger.error(f"File not found: {flag_file}")
            return 1

        logger.info(f"Transmitting {flag_file} on {frequency} Hz")

        tb = binary_mod_tx(
            tx_freq=frequency,
            sample_rate=sample_rate,
            device_string=device_string,
            flag_file=flag_file,
            rf_gain=rf_gain,
            if_gain=if_gain,
            antenna=antenna if antenna else ""
        )

        tb.start()
        tb.wait()

        logger.info("Transmission complete")
        return 0

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1

    finally:
        try:
            tb.stop()
            tb.wait()
        except Exception:
            pass
```

### Example 3: Duration-Based Transmission

```python
#!/usr/bin/env python3
"""Duration-based transmission example."""

from gnuradio import gr
from challenges.duration_mod_flowgraph import duration_mod_tx
import logging
import time

logger = logging.getLogger(__name__)

def main(frequency, device_string, flag_file, antenna=None,
         rf_gain=14, if_gain=32, **kwargs):
    try:
        duration = kwargs.get('duration', 30)  # Default 30 seconds

        logger.info(f"Transmitting for {duration} seconds on {frequency} Hz")

        tb = duration_mod_tx(
            tx_freq=frequency,
            device_string=device_string,
            flag_file=flag_file,
            rf_gain=rf_gain,
            if_gain=if_gain
        )

        tb.start()
        time.sleep(duration)
        tb.stop()
        tb.wait()

        logger.info("Transmission complete")
        return 0

    except Exception as e:
        logger.error(f"Error: {e}")
        return 1

    finally:
        try:
            tb.stop()
            tb.wait()
        except Exception:
            pass
```

## Next Steps

After successfully implementing and testing your new challenge type:

1. **Document the modulation**: Add details to the [Configuration Reference](Configuration-Reference#modulation-specific-parameters)
2. **Update examples**: Add example configurations to `server-config.example.yml`
3. **Add to troubleshooting**: Document common issues in the [Troubleshooting Guide](Troubleshooting)
4. **Submit a pull request**: Contribute your new challenge type back to the project
5. **Share with the community**: Write about your challenge type and how to decode it

## Further Reading

- [GNU Radio Tutorials](https://wiki.gnuradio.org/index.php/Tutorials)
- [Osmocom Source/Sink Documentation](https://osmocom.org/projects/gr-osmosdr/wiki)
- [ChallengeCtl Architecture](Architecture) - Understanding how challenges flow through the system
- [Configuration Reference](Configuration-Reference) - All configuration options
- [Runner Setup](Runner-Setup) - Setting up test runners
