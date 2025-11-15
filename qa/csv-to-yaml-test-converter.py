#!/usr/bin/env python3
"""
Convert legacy CSV flag files to YAML format for testing
This is used by the test suite to validate the new YAML-based code
"""

import sys
import csv
import yaml


def parse_csv_flags(flagfile):
    """Parse CSV flag file into conference info and challenges list."""
    with open(flagfile, 'r') as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        raise ValueError("Empty CSV file")

    # First line: conference,starttime,endtime
    conference_row = rows[0]
    conference_name = conference_row[0]
    start_time = conference_row[1] if len(conference_row) > 1 else ""
    end_time = conference_row[2] if len(conference_row) > 2 else ""

    # Remaining lines are challenges
    challenges = []
    for row in rows[1:]:
        if not row or not row[0]:  # Skip empty rows
            continue

        # CSV format: chal_id,chal_name,flag,module,modopt1,modopt2,minwait,maxwait,freq1,freq2,freq3
        chal_id = row[0]
        chal_name = row[1] if len(row) > 1 else f"Challenge_{chal_id}"
        flag = row[2] if len(row) > 2 else ""
        modulation = row[3] if len(row) > 3 else ""
        modopt1 = row[4] if len(row) > 4 else ""
        modopt2 = row[5] if len(row) > 5 else ""
        minwait = int(row[6]) if len(row) > 6 and row[6] else 60
        maxwait = int(row[7]) if len(row) > 7 and row[7] else 90
        freq1 = row[8] if len(row) > 8 else ""

        # Build challenge dict based on modulation type
        challenge = {
            'name': chal_name,
            'modulation': modulation,
            'flag': flag,
            'min_delay': minwait,
            'max_delay': maxwait,
            'enabled': True
        }

        # Parse frequency - could be numeric or named range
        if freq1:
            try:
                # Try to parse as integer (in kHz from CSV), convert to Hz for YAML
                freq_khz = int(freq1)
                challenge['frequency'] = freq_khz * 1000
            except ValueError:
                # It's a named range like "ham_900"
                challenge['frequency'] = freq1.lower()

        # Add modulation-specific parameters
        if modulation == 'cw':
            if modopt1:
                challenge['speed'] = int(modopt1)
        elif modulation == 'nbfm':
            if modopt1:
                challenge['wav_samplerate'] = int(modopt1)
        elif modulation == 'ssb':
            # modopt1 could be mode (lsb/usb) or wav_samplerate
            if modopt1:
                if modopt1.lower() in ['lsb', 'usb']:
                    challenge['mode'] = modopt1.lower()
                else:
                    challenge['wav_samplerate'] = int(modopt1)
        elif modulation == 'pocsag':
            if modopt1:
                challenge['capcode'] = int(modopt1)
        elif modulation == 'fhss':
            # For FHSS, would need more complex parsing
            # For now, add basic structure
            if modopt1:
                challenge['seed'] = modopt1
            challenge['hop_rate'] = 10  # default
            challenge['hop_time'] = 60  # default
            challenge['channel_spacing'] = 10000  # default
        elif modulation == 'freedv':
            if modopt1:
                if modopt1.lower() in ['lsb', 'usb']:
                    challenge['mode'] = modopt1.lower()
                else:
                    challenge['wav_samplerate'] = int(modopt1)

        challenges.append(challenge)

    return conference_name, start_time, end_time, challenges


def parse_csv_devices(devicefile):
    """Parse CSV device file into devices list."""
    devices = []

    # Define a test-device model for CI testing
    models = [{
        'model': 'test-device',
        'rf_gain': 0,
        'bias_t': False
    }]

    with open(devicefile, 'r') as f:
        reader = csv.reader(f)
        for idx, row in enumerate(reader):
            if not row or len(row) < 2:
                continue

            # For test devices, just use index as name
            device = {
                'name': str(idx),
                'model': 'test-device'
            }
            devices.append(device)

    return devices, models


def convert_csv_to_yaml(flagfile, devicefile, output_file=None):
    """Convert CSV flag and device files to YAML config."""

    # Parse CSV files
    conference_name, start_time, end_time, challenges = parse_csv_flags(flagfile)
    devices, models = parse_csv_devices(devicefile)

    # Build YAML structure
    config = {
        'mode': 'controller',
        'conference': {
            'name': conference_name,
            'start': start_time,
            'stop': end_time
        },
        'radios': {
            'autodetect': False,
            'models': models,
            'devices': devices
        },
        'challenges': [
            {'default_min_delay': 60, 'default_max_delay': 90}
        ] + challenges
    }

    # Output YAML
    yaml_output = yaml.dump(config, default_flow_style=False, sort_keys=False)

    if output_file:
        with open(output_file, 'w') as f:
            f.write(yaml_output)
        return output_file
    else:
        return yaml_output


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <flagfile.csv> <devicefile.csv> [output.yml]")
        sys.exit(1)

    flagfile = sys.argv[1]
    devicefile = sys.argv[2]
    output_file = sys.argv[3] if len(sys.argv) > 3 else None

    result = convert_csv_to_yaml(flagfile, devicefile, output_file)

    if not output_file:
        print(result)
    else:
        print(f"Converted to {output_file}")
