#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from multiprocessing import Process, Queue
import logging
import string
import argparse
from time import sleep
from random import randint, choice, shuffle
import random
import sqlite3
import csv
import yaml
import numpy as np
import subprocess
from datetime import datetime

from challenges import (ask, cw, nbfm, spectrum_paint, pocsagtx_osmocom, lrs_pager, lrs_tx,
                        freedv_tx, ssb_tx, fhss_tx)

# Log file configuration - actual setup happens in main() after parsing args
LOG_FILE = 'challengectl.log'

# def build_database(flagfile, devicefile):
#     """Create sqlite database based on flags file and devices file.
#        Database file name will be based on
#        conference name extracted from first line of flags file."""
#     flag_input = read_flags(flagfile)
#     # Skip first line of flag_input where conference information is stored
#     # Add remaining lines to flag_line array
#     flag_line = np.asarray(flag_input[1:])

#     devices = read_devices(devicefile)

#     # Read name of conference from first line of flag file
#     conference = flag_input[0][0]
#     # Create sqlite database for conference and connect to the database
#     conn = sqlite3.connect(conference + ".db")
#     c = conn.cursor()
#     # Create database schema
#     c.execute('''CREATE TABLE flags(chal_id integer primary key,chal_name,flag,module,modopt1,modopt2,
#     minwait integer,maxwait integer,freq1,freq2,freq3)''')
#     c.execute(
#         "CREATE TABLE flag_status(chal_id integer primary key,enabled,lastrun integer,ready)")
#     c.execute("CREATE TABLE devices(dev_id integer primary key,dev_string,dev_busy)")
#     # Insert flags from flag_line array into database
#     c.executemany(
#         "INSERT INTO flags VALUES (?,?,?,?,?,?,?,?,?,?,?)", flag_line)
#     # Add flag status row for each flag, setting each flag to enabled, lastrun blank, ready
#     c.executemany("INSERT INTO flag_status VALUES (?,1,'',1)",
#                   flag_line[:, :1])
#     # Insert devices from devices array into database, set each device to not busy
#     c.executemany("INSERT INTO devices VALUES (?,?,0)", devices)
#     conn.commit()
#     conn.close()


class Radio:
    """TODO: Doc string here"""

    def __init__(self, properties: dict) -> None:
        pass

    def check_freqrange(self, frequency) -> bool:
        pass

    def set_device_string(self, model, name, bias_t) -> str:
        pass


class Challenge:
    '''
    Contains properies and functions related to individual challenges
    '''
    def __init__(self, properties: dict) -> None:
        self.properties = properties
        self.name:str = properties.get('name')
        if properties.get('enabled') is not None:
            self.enabled:bool = properties.get('enabled')
        else:
            True

    def check_modulation(self, requested_modulation: str) -> bool:
        '''
        Checks if the modulation type is valid. Disables challenge if it's not.
        '''
        # Load modulation parameters to get valid types
        params_def = load_modulation_parameters()
        if not params_def:
            logging.error("Cannot validate modulation type: modulation_parameters.yml not loaded")
            self.enabled = False
            return False

        # Get valid modulation types (exclude 'all' which is for global parameters)
        valid_modulation_types = [k for k in params_def.keys() if k != 'all']

        if requested_modulation in valid_modulation_types:
            passed = True
            logging.info("Modulation check for %s passed.", self.name)
        else:
            logging.error("Unknown modulation type %s in %s", requested_modulation, self.name)
            self.enabled = False
            passed = False
        return passed

    def check_parameters(self) -> bool:
        '''
        Checks for mandatory parameters based on modulation type
        Validates optional parameters
        Returns True if all mandatory parameters present, False otherwise
        '''
        # Load modulation parameter definitions
        params_def = load_modulation_parameters()
        if not params_def:
            logging.error("Cannot validate parameters: modulation_parameters.yml not loaded")
            return False

        modulation = self.properties.get('modulation')
        if not modulation:
            logging.error(f"Challenge '{self.name}' missing 'modulation' parameter")
            self.enabled = False
            return False

        # Get parameter requirements for this modulation type
        mod_params = params_def.get(modulation, {})
        global_params = params_def.get('all', {})

        # Combine mandatory parameters (global + modulation-specific)
        mandatory = set(global_params.get('mandatory', [])) | set(mod_params.get('mandatory', []))
        optional = set(global_params.get('optional', [])) | set(mod_params.get('optional', []))

        # Check all mandatory parameters are present
        missing_params = []
        for param in mandatory:
            if param not in self.properties or self.properties[param] is None:
                missing_params.append(param)

        if missing_params:
            logging.error(f"Challenge '{self.name}' missing mandatory parameters: {', '.join(missing_params)}")
            self.enabled = False
            return False

        # Validate flag file exists if it's a file path
        flag = self.properties.get('flag')
        if flag and isinstance(flag, str):
            # Only check if it looks like a file path (contains / or ends with common extensions)
            if '/' in flag or flag.endswith(('.wav', '.bin', '.txt')):
                if not os.path.exists(flag):
                    logging.error(f"Challenge '{self.name}': Flag file not found: {flag}")
                    self.enabled = False
                    return False

        # Log info about optional parameters
        present_optional = [p for p in optional if p in self.properties and self.properties[p] is not None]
        if present_optional:
            logging.debug(f"Challenge '{self.name}' has optional parameters: {', '.join(present_optional)}")

        logging.info(f"Challenge '{self.name}' parameter validation passed")
        return True


def disable_bladerf_biastee(device):
    """
    Turn off BladeRF bias-tee after transmission completes.

    Args:
        device: Device string (e.g., "bladerf=serial,biastee=1")
    """
    if device and device.find("bladerf") != -1 and device.find("biastee=1") != -1:
        bladeserial = parse_bladerf_ser(device)
        serialarg = '*:serial={}'.format(bladeserial)
        logging.debug(f"Disabling BladeRF bias-tee for serial {bladeserial}")
        subprocess.run(['bladeRF-cli', '-d', serialarg, 'set', 'biastee', 'tx', 'off'])


def cleanup_after_transmission(device_id, device_q, flag_q, flag_args):
    """
    Cleanup after transmission: return device to pool, random sleep, return flag to queue.

    Args:
        device_id: Device ID to return to the queue
        device_q: Device queue
        flag_q: Flag queue
        flag_args: Challenge arguments (contains timing and queue control)
    """
    # Return device to pool
    logging.debug(f"Returning device {device_id} to pool")
    device_q.put(device_id)

    # Random sleep between transmissions (if not disabled)
    norandsleep = flag_args[8]
    if norandsleep == False:
        mintime = flag_args[4]
        maxtime = flag_args[5]
        sleep_time = randint(mintime, maxtime)
        logging.debug(f"Sleeping for {sleep_time} seconds between transmissions")
        sleep(sleep_time)

    # Return flag to queue for retransmission (if enabled)
    replaceinqueue = flag_args[7]
    if replaceinqueue != False:
        logging.debug(f"Returning challenge {flag_args[0]} to queue for retransmission")
        flag_q.put(flag_args[0])


def get_antenna_and_print(device_id):
    """
    Get antenna for device and print it if configured.

    Args:
        device_id: Device ID

    Returns:
        str: Antenna string (or empty string if not configured)
    """
    global verbose
    antenna = get_device_antenna(device_id)
    if antenna:
        logging.debug(f"Device {device_id} using antenna: {antenna}")
        if verbose:
            print(f"Using antenna: {antenna}")
    else:
        logging.debug(f"Device {device_id} has no antenna configured")
    return antenna


class transmitter:
    '''TODO: Doc string here'''
    # flag_args:chal_id,flag,modopt1,modopt2,minwait,maxwait,freq1

    def fire_ask(self, device_id, flag_q, device_q, *flag_args):
        global verbose
        if verbose:
            print("\nTransmitting ASK\n")
        flag_args = flag_args[0]
        device = fetch_device(device_id)
        flag = flag_args[1]
        freq = int(flag_args[6]) * 1000
        antenna = get_antenna_and_print(device_id)

        logging.info(f"Starting ASK transmission: device={device_id}, freq={freq}Hz")
        logging.debug(f"ASK flag data: {flag[:20]}..." if len(flag) > 20 else f"ASK flag data: {flag}")

        ask.main(flag.encode("utf-8").hex(), freq, device, antenna)
        sleep(3)
        logging.info("ASK transmission complete")
        disable_bladerf_biastee(device)
        cleanup_after_transmission(device_id, device_q, flag_q, flag_args)

    def fire_cw(self, device_id, flag_q, device_q, *flag_args):
        global verbose
        if verbose:
            print("\nTransmitting CW\n")
        flag_args = flag_args[0]
        device = fetch_device(device_id)
        if verbose:
            print(device)
        flag = flag_args[1]
        speed = int(flag_args[2])
        freq = int(flag_args[6]) * 1000
        antenna = get_antenna_and_print(device_id)

        logging.info(f"Starting CW transmission: device={device_id}, freq={freq}Hz, speed={speed}WPM")
        logging.debug(f"CW flag text: {flag[:30]}..." if len(flag) > 30 else f"CW flag text: {flag}")

        p = Process(target=cw.main, args=(flag, speed, freq, device, antenna))
        p.start()
        p.join()
        sleep(3)

        if(p.exitcode != 0):
            logging.error(f"CW transmission process exited with code {p.exitcode}")
        else:
            logging.info("CW transmission complete")

        disable_bladerf_biastee(device)
        cleanup_after_transmission(device_id, device_q, flag_q, flag_args)
        if(p.exitcode != 0):
            sys.exit(p.exitcode)

    def fire_ssb(self, device_id, flag_q, device_q, *flag_args):
        """
        Call the ssb_tx flow graph to transmit Lower Sideband (LSB)
        or Upper Sideband (USB) modulated signals.
        """
        global verbose
        flag_args = flag_args[0]
        device = fetch_device(device_id)
        wav_src = str(flag_args[1])
        if not os.path.isfile(wav_src):
            logging.error(f"SSB: WAV file not found: {wav_src}")
            print("Unable to find wav file {}".format(wav_src))
            exit(1)

        # modopt1 might be 'mode' (lsb/usb) or wav_samplerate, check which
        mode_or_rate = str(flag_args[2]) if flag_args[2] else ''
        if mode_or_rate.lower() in ['lsb', 'usb']:
            mode = mode_or_rate.lower()
            wav_rate = int(flag_args[3]) if flag_args[3] else 48000
        else:
            mode = 'usb'  # default to USB
            wav_rate = int(mode_or_rate) if mode_or_rate else 48000

        if verbose:
            print(f"\nTransmitting SSB ({mode.upper()})\n")

        freq = int(flag_args[6]) * 1000
        antenna = get_antenna_and_print(device_id)

        logging.info(f"Starting SSB transmission: device={device_id}, mode={mode.upper()}, freq={freq}Hz, wav_rate={wav_rate}")
        logging.debug(f"SSB WAV source: {wav_src}")

        # Configure options for ssb_tx flowgraph
        ssb_opts = ssb_tx.argument_parser().parse_args('')
        ssb_opts.dev = device
        ssb_opts.freq = freq
        ssb_opts.wav_file = wav_src
        ssb_opts.wav_samp_rate = wav_rate
        ssb_opts.mode = mode
        ssb_opts.antenna = antenna

        # Call ssb_tx main with options
        ssb_tx.main(options=ssb_opts)

        sleep(3)
        logging.info("SSB transmission complete")
        disable_bladerf_biastee(device)
        cleanup_after_transmission(device_id, device_q, flag_q, flag_args)

    def fire_nbfm(self, device_id, flag_q, device_q, *flag_args):
        """
        Calls the nbfm flow graph to transmit Narrow Band FM modulated signals
        """
        global verbose
        if verbose:
            print("\nTransmitting NBFM\n")
        flag_args = flag_args[0]
        device = fetch_device(device_id)
        wav_src = str(flag_args[1])
        if not os.path.isfile(wav_src):
            logging.error(f"NBFM: WAV file not found: {wav_src}")
            print("Unable to find wav file {}".format(wav_src))
            exit(1)
        wav_rate = int(flag_args[2])
        freq = int(flag_args[6]) * 1000
        antenna = get_antenna_and_print(device_id)

        logging.info(f"Starting NBFM transmission: device={device_id}, freq={freq}Hz, wav_rate={wav_rate}")
        logging.debug(f"NBFM WAV source: {wav_src}")

        # Configure options for nbfm_tx flowgraph
        nbfm_opts = nbfm.argument_parser().parse_args('')
        nbfm_opts.dev = device
        nbfm_opts.freq = freq
        nbfm_opts.wav_file = wav_src
        nbfm_opts.wav_samp_rate = wav_rate
        nbfm_opts.antenna = antenna

        # Call nbfm_tx main with options
        nbfm.main(options=nbfm_opts)

        sleep(3)
        logging.info("NBFM transmission complete")
        disable_bladerf_biastee(device)
        cleanup_after_transmission(device_id, device_q, flag_q, flag_args)

    def fire_pocsag(self, device_id, flag_q, device_q, *flag_args):
        global verbose
        if verbose:
            print("\nTransmitting POCSAG\n")
        flag_args = flag_args[0]
        device = fetch_device(device_id)
        flag = flag_args[1]
        modopt1 = flag_args[2]
        freq = int(flag_args[6]) * 1000
        antenna = get_antenna_and_print(device_id)

        logging.info(f"Starting POCSAG transmission: device={device_id}, freq={freq}Hz, capcode={modopt1}")
        logging.debug(f"POCSAG message: {flag[:30]}..." if len(flag) > 30 else f"POCSAG message: {flag}")

        # Configure options specific to pocsagtx_osmocom script
        pocsagopts = pocsagtx_osmocom.argument_parser().parse_args('')
        pocsagopts.deviceargs = device
        pocsagopts.samp_rate = 2400000
        pocsagopts.pagerfreq = freq
        pocsagopts.capcode = int(modopt1)
        pocsagopts.message = flag
        pocsagopts.antenna = antenna

        # Call main in pocsagtx_osmocom, passing in pocsagopts options array
        pocsagtx_osmocom.main(options=pocsagopts)

        if verbose:
            print("Finished TX POCSAG, sleeping for 3sec before returning device")
        sleep(3)
        logging.info("POCSAG transmission complete")
        disable_bladerf_biastee(device)
        cleanup_after_transmission(device_id, device_q, flag_q, flag_args)

    def fire_lrs(self, device_id, flag_q, device_q, *flag_args):
        global verbose
        if verbose:
            print("\nTransmitting LRS\n")
        flag_args = flag_args[0]
        device = fetch_device(device_id)
        flag = flag_args[1]
        freq = int(flag_args[6]) * 1000
        antenna = get_antenna_and_print(device_id)

        logging.info(f"Starting LRS transmission: device={device_id}, freq={freq}Hz")
        logging.debug(f"LRS pager arguments: {flag}")

        # Configure options specific to lrs_pager script
        lrspageropts = lrs_pager.argument_parser().parse_args(flag.split())
        # Generate random filename in /tmp/ for pager bin file
        randomstring = ''.join(random.choices(
            string.ascii_uppercase + string.digits, k=6))
        outfile = f"/tmp/lrs_{randomstring}.bin"
        lrspageropts.outputfile = outfile
        logging.debug(f"Generating LRS binary file: {outfile}")
        lrs_pager.main(options=lrspageropts)

        # Configure options specific to lrs_tx script
        lrsopts = lrs_tx.argument_parser().parse_args('')
        lrsopts.deviceargs = device
        lrsopts.freq = freq
        lrsopts.binfile = outfile
        lrsopts.antenna = antenna

        # Call main in lrs_tx, passing in lrsopts options array
        lrs_tx.main(options=lrsopts)
        sleep(3)
        logging.info("LRS transmission complete")
        disable_bladerf_biastee(device)

        # Delete pager bin file from /tmp/
        os.remove(outfile)
        logging.debug(f"Removed temporary file: {outfile}")
        if verbose:
            print("Removed outfile")
        cleanup_after_transmission(device_id, device_q, flag_q, flag_args)
        if verbose:
            print("Returned flag to pool")

    def fire_fhss(self, device_id, flag_q, device_q, *flag_args):
        """
        Call the fhss_tx flow graph to transmit Frequency Hopping Spread Spectrum signals
        """
        global verbose
        if verbose:
            print("\nTransmitting FHSS\n")
        flag_args = flag_args[0]
        device = fetch_device(device_id)

        # Extract parameters from flag_args
        wav_src = str(flag_args[1])
        if not os.path.isfile(wav_src):
            logging.error(f"FHSS: WAV file not found: {wav_src}")
            print("Unable to find wav file {}".format(wav_src))
            exit(1)

        # modopt1 contains FHSS-specific parameters as a dict
        fhss_params = flag_args[2] if isinstance(flag_args[2], dict) else {}
        channel_spacing = fhss_params.get('channel_spacing', 10000)  # Hz
        hop_rate = fhss_params.get('hop_rate', 10)  # hops per second
        hop_time = fhss_params.get('hop_time', 60)  # seconds
        seed = fhss_params.get('seed', 'RFHS')  # RNG seed

        # modopt2 contains wav_samplerate
        wav_rate = int(flag_args[3]) if flag_args[3] else 48000

        freq = int(flag_args[6]) * 1000
        antenna = get_antenna_and_print(device_id)

        logging.info(f"Starting FHSS transmission: device={device_id}, freq={freq}Hz, hop_rate={hop_rate}Hz")
        logging.debug(f"FHSS parameters: channel_spacing={channel_spacing}, hop_time={hop_time}, seed={seed}, wav_rate={wav_rate}")
        logging.debug(f"FHSS WAV source: {wav_src}")

        # Configure options for fhss_tx flowgraph
        fhss_opts = fhss_tx.argument_parser().parse_args('')
        fhss_opts.dev = device
        fhss_opts.freq = freq
        fhss_opts.file = wav_src
        fhss_opts.wav_rate = wav_rate
        fhss_opts.channel_spacing = int(channel_spacing)
        fhss_opts.hop_rate = int(hop_rate)
        fhss_opts.hop_time = float(hop_time)
        fhss_opts.seed = str(seed)
        fhss_opts.antenna = antenna

        # Call fhss_tx main with options
        fhss_tx.main(options=fhss_opts)

        sleep(3)
        logging.info("FHSS transmission complete")
        disable_bladerf_biastee(device)
        cleanup_after_transmission(device_id, device_q, flag_q, flag_args)


def select_freq(band, config=None):
    """Read from config or frequencies text file, select row that starts with band argument.
    Returns tuple with randomly selected frequency (in kHz), the minimum frequency for that band (in kHz),
    and the maximum frequency for that band (in kHz).

    Args:
        band: Named frequency range (e.g., "ham_144")
        config: Optional config dict. If provided, reads from config['frequency_ranges'].
                If not provided, falls back to frequencies.txt for backward compatibility.

    Returns:
        Tuple of (random_freq_khz, min_freq_khz, max_freq_khz)
    """
    # Try to read from config first
    if config and 'frequency_ranges' in config:
        for freq_range in config['frequency_ranges']:
            if freq_range.get('name') == band:
                min_hz = freq_range['min_hz']
                max_hz = freq_range['max_hz']
                # Select random frequency in Hz
                freq_hz = randint(min_hz, max_hz)
                # Convert to kHz for return value (legacy compatibility)
                freq_khz = freq_hz // 1000
                min_khz = min_hz // 1000
                max_khz = max_hz // 1000
                return (freq_khz, min_khz, max_khz)

    # Fallback to frequencies.txt for backward compatibility
    try:
        with open("frequencies.txt", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if row[0] == band:
                    freq = randint(int(row[1]), int(row[2]))
                    return ((freq, row[1], row[2]))
    except FileNotFoundError:
        logging.warning(f"frequencies.txt not found and frequency range '{band}' not in config")
        pass

    return None


# def select_dvbt(channel):
#     """TODO: Deprecate me"""
#     with open("dvbt_channels.txt") as f:
#         reader = csv.reader(f)
#         for row in reader:
#             if row[0] == channel:
#                 return (int(row[1]))


# def read_flags(flags_file):
#     """Read lines from flags_file and return a list of lists for each row in the flags_file.
#     The first item in the list contains conference information, and the remaining items in the
#     list contain information about each flag."""

#     flag_input = []
#     with open(flags_file) as f:
#         reader = csv.reader(f)
#         for row in reader:
#             flag_input.append(row)
#     return flag_input


# def read_devices(devices_file):
#     """Read lines from devices file, and return a list of lists for each row in the devices file."""
#     devices_input = []
#     with open(devices_file) as f:
#         reader = csv.reader(f, quotechar='"')
#         for row in reader:
#             devices_input.append(row)
#     return devices_input


# Global device registry for YAML-based configuration
device_registry = {}

# Global modulation parameters loaded from modulation_parameters.yml
modulation_params = None


def load_modulation_parameters():
    """Load modulation parameter definitions from YAML file."""
    global modulation_params
    if modulation_params is None:
        try:
            with open('modulation_parameters.yml', 'r', encoding='utf-8') as f:
                modulation_params = yaml.safe_load(f)
                logging.info("Loaded modulation parameter definitions")
        except FileNotFoundError:
            logging.error("modulation_parameters.yml not found")
            modulation_params = {}
        except yaml.YAMLError as e:
            logging.error(f"Error parsing modulation_parameters.yml: {e}")
            modulation_params = {}
    return modulation_params


def fetch_device(dev_id):
    """Get device string for a given device id from global registry."""
    global device_registry
    if dev_id in device_registry:
        device_string = device_registry[dev_id]['device_string']
        logging.debug(f"Fetched device {dev_id}: {device_string}")
        return device_string
    else:
        logging.error(f"Device ID {dev_id} not found in registry")
        return None


def get_device_antenna(dev_id):
    """Get the preferred antenna for a device from the registry."""
    global device_registry
    if dev_id in device_registry:
        # Check device-specific antenna setting first
        antenna = device_registry[dev_id]['config'].get('antenna', '')
        # If not set at device level, check model defaults
        if not antenna:
            antenna = device_registry[dev_id]['model_defaults'].get('antenna', '')
        logging.debug(f"Retrieved antenna for device {dev_id}: {antenna if antenna else '(none)'}")
        return antenna if antenna else ""
    logging.warning(f"Device {dev_id} not found in registry when retrieving antenna")
    return ""


# def fetch_device_old(dev_id):
#     """Query database for device string for a given device id and return the device string."""
#     global conference
#     conn = sqlite3.connect(conference + ".db")
#     c = conn.cursor()
#     c.execute("SELECT dev_string FROM devices WHERE dev_id=?", (dev_id,))
#     device = c.fetchone()
#     conn.close()
#     return device[0]


# Parse bladerf serial number from device string
def parse_bladerf_ser(device):
    bladerfdevind = device.find("bladerf=")
    serialstart = bladerfdevind + 8
    serialend = serialstart + 32
    bladeserial = device[serialstart:serialend]
    return bladeserial

def argument_parser():
    parser = argparse.ArgumentParser(
        description="A script to run SDR challenges on multiple SDR devices.")
    # parser.add_argument('flagfile', help="Flags file")
    # parser.add_argument('devicefile', help="Devices file")
    parser.add_argument('configfile', help="YAML Configuration File", default='config.yml')
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-t", "--test", help="Run each challenge once to test flags.", action="store_true")
    parser.add_argument("-d", "--dump-config", help="Display parsed devices and challenges without running anything.", action="store_true", dest="dump_config")
    parser.add_argument("--log-level",
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        default='INFO',
                        help="Set logging level (default: INFO)")
    return parser


def check_radios_config(radio_config):
    # check uniqueness of names
    # check freq limits
    # check sanity of gain values
    # check sanity of frequencies

    pass


def check_challenges(challenge_config):
    # check uniqeness of names
    # check modulation type
    # check options against modulator
    # check sanity of frequencies and other things that involve numbers
    pass


def build_device_string(device_config: dict, model_defaults: dict) -> str:
    '''
    Build gr-osmosdr device string from device configuration and model defaults
    '''
    model = device_config.get('model')
    name = device_config.get('name')

    # Start with model=name or model=serial
    device_string = f"{model}={name}"

    # Add bias_t if specified (check device config first, then model defaults)
    bias_t = device_config.get('bias_t')
    if bias_t is None and model_defaults:
        bias_t = model_defaults.get('bias_t')
    if bias_t:
        device_string += ",biastee=1"
        logging.debug(f"Built device string with bias-tee: {device_string}")
    else:
        logging.debug(f"Built device string: {device_string}")

    return device_string


def parse_radios_from_yaml(config: dict) -> list:
    '''
    Parse radios configuration from YAML and return list of device info tuples
    Returns: List of (device_id, device_string, device_config) tuples
    '''
    radios_config = config.get('radios', {})
    devices = radios_config.get('devices', [])
    models_config = radios_config.get('models', [])

    # Build model defaults dictionary
    model_defaults = {}
    for model_conf in models_config:
        model_name = model_conf.get('model')
        if model_name:
            model_defaults[model_name] = model_conf

    # Build device list
    device_list = []
    for idx, device_conf in enumerate(devices):
        model = device_conf.get('model')
        model_def = model_defaults.get(model, {})
        device_string = build_device_string(device_conf, model_def)
        device_list.append((idx, device_string, device_conf, model_def))
        logging.info(f"Configured device {idx}: {device_string}")

    if not device_list:
        logging.warning("No devices configured in YAML")

    return device_list


def parse_challenges_from_yaml(config: dict) -> list:
    '''
    Parse challenges configuration from YAML and return list of enabled, validated challenges
    Returns: List of challenge dictionaries that passed validation
    '''
    challenges_raw = config.get('challenges', [])

    # Extract default delays if present
    default_min_delay = None
    default_max_delay = None
    challenges = []

    for item in challenges_raw:
        if isinstance(item, dict):
            # Check if this is the defaults dict
            if 'default_min_delay' in item or 'default_max_delay' in item:
                default_min_delay = item.get('default_min_delay', 60)
                default_max_delay = item.get('default_max_delay', 90)
                continue

            # Apply defaults if not specified in challenge
            if default_min_delay is not None and 'min_delay' not in item:
                item['min_delay'] = default_min_delay
            if default_max_delay is not None and 'max_delay' not in item:
                item['max_delay'] = default_max_delay

            # Check if challenge is explicitly disabled
            if not item.get('enabled', True):
                logging.info(f"Skipping disabled challenge: {item.get('name')}")
                continue

            # Create Challenge object and validate
            challenge = Challenge(item)

            # Check modulation type
            modulation = item.get('modulation')
            if modulation and challenge.check_modulation(modulation):
                # Validate parameters
                if challenge.check_parameters():
                    # Only add if still enabled after validation
                    if challenge.enabled:
                        challenges.append(item)
                        logging.info(f"Loaded and validated challenge: {item.get('name')}")
                    else:
                        logging.warning(f"Challenge '{item.get('name')}' failed validation and was disabled")
                else:
                    logging.warning(f"Challenge '{item.get('name')}' failed parameter validation")
            else:
                logging.warning(f"Challenge '{item.get('name')}' has invalid modulation type or failed modulation check")

    if not challenges:
        logging.warning("No enabled challenges found in YAML")

    return challenges


def parse_yaml(configfile) -> dict:
    '''
    Parse config.yml, check for mandatory fields
    '''
    parse_err = Exception('Cannot parse config file. Check log for more details')
    with open(configfile, 'r', encoding='utf-8') as conf_file:
        config = yaml.safe_load(conf_file)

    if config.get('radios') is not None:
        # Validate radios configuration
        logging.info("Found radios configuration")
    else:
        logging.critical("Section 'radios' is missing from configuration")
        raise parse_err

    if config.get('challenges') is not None:
        # Validate challenges configuration
        logging.info("Found challenges configuration")
    else:
        logging.critical("Section 'challenges' is missing from configuration")
        raise parse_err

    return config


def dump_config(device_list, challenges_list, config):
    """
    Display parsed devices and challenges without running anything
    """
    print("\n" + "="*80)
    print("CONFIGURATION DUMP")
    print("="*80)

    # Display conference info
    conference_config = config.get('conference', {})
    print(f"\nConference: {conference_config.get('name', 'N/A')}")
    print(f"Start: {conference_config.get('start', 'N/A')}")
    print(f"Stop: {conference_config.get('stop', 'N/A')}")

    # Display devices
    print("\n" + "-"*80)
    print(f"DEVICES ({len(device_list)} configured)")
    print("-"*80)

    for dev_id, dev_string, dev_config, model_defaults in device_list:
        print(f"\nDevice {dev_id}:")
        print(f"  Model: {dev_config.get('model', 'N/A')}")
        print(f"  Name/Serial: {dev_config.get('name', 'N/A')}")
        print(f"  Device String: {dev_string}")
        antenna = dev_config.get('antenna', model_defaults.get('antenna', ''))
        if antenna:
            print(f"  Antenna: {antenna}")
        bias_t = dev_config.get('bias_t', model_defaults.get('bias_t'))
        if bias_t:
            print(f"  Bias-T: {bias_t}")

    # Display challenges
    print("\n" + "-"*80)
    print(f"CHALLENGES ({len(challenges_list)} enabled)")
    print("-"*80)

    for idx, challenge in enumerate(challenges_list):
        print(f"\n[{idx+1}] {challenge.get('name', 'N/A')}")
        print(f"    Modulation: {challenge.get('modulation', 'N/A')}")
        print(f"    Flag: {challenge.get('flag', 'N/A')}")
        print(f"    Frequency: {challenge.get('frequency', 'N/A')} Hz")
        print(f"    Delays: {challenge.get('min_delay', 'N/A')}s - {challenge.get('max_delay', 'N/A')}s")

        # Display modulation-specific parameters
        mod_params = {}
        for key in ['speed', 'capcode', 'mode', 'wav_samplerate', 'seed', 'hop_rate', 'hop_time', 'channel_spacing', 'text']:
            if key in challenge and challenge[key] is not None:
                mod_params[key] = challenge[key]

        if mod_params:
            print(f"    Parameters: {', '.join([f'{k}={v}' for k, v in mod_params.items()])}")

    print("\n" + "="*80)
    print(f"Total: {len(device_list)} devices, {len(challenges_list)} challenges")
    print("="*80 + "\n")


def main(options=None):
    if options is None:
        options = argument_parser().parse_args()

    args = options
    test = args.test
    global conference, device_registry, verbose
    verbose = args.verbose

    # Configure logging with user-specified or default log level
    # Rotate existing log file with timestamp before starting new log
    if os.path.exists(LOG_FILE):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        archived_log = f'challengectl.{timestamp}.log'
        os.rename(LOG_FILE, archived_log)

    # Convert log level string to logging constant
    log_level = getattr(logging, args.log_level)

    logging.basicConfig(filename=LOG_FILE,
                        filemode='w',
                        level=log_level,
                        format='%(asctime)s challengectl[%(process)d]: %(levelname)s: %(message)s',
                        datefmt='%Y-%m-%dT%H:%M:%S')

    logging.info(f"Logging initialized at {args.log_level} level")

    # Create thread safe FIFO queues for devices and flags
    device_Q = Queue()
    flag_Q = Queue()

    # Parse YAML configuration file
    config = parse_yaml(args.configfile)

    # Extract conference name from config
    conference = config['conference']['name']
    logging.info(f"Conference: {conference}")

    # Parse radios from YAML and populate device registry and queue
    device_list = parse_radios_from_yaml(config)
    if not device_list:
        logging.error("No devices configured. Exiting.")
        print("Error: No devices configured in YAML file.")
        return 1

    # Populate device registry and queue
    for dev_id, dev_string, dev_config, model_defaults in device_list:
        device_registry[dev_id] = {
            'device_string': dev_string,
            'config': dev_config,
            'model_defaults': model_defaults
        }
        device_Q.put(dev_id)
        logging.info(f"Device {dev_id} added to queue: {dev_string}")

    # Parse challenges from YAML
    challenges_list = parse_challenges_from_yaml(config)
    if not challenges_list:
        logging.error("No enabled challenges found. Exiting.")
        print("Error: No enabled challenges found in YAML file.")
        return 1

    # If dump_config flag is set, display configuration and exit
    if args.dump_config:
        dump_config(device_list, challenges_list, config)
        return 0

    # Randomize order of challenges except when testing flags
    if test != True:
        shuffle(challenges_list)

    logging.info(f"Loaded {len(challenges_list)} challenges")
    print(f"Loaded {len(challenges_list)} challenges")

    challenges_transmitted = 0

    # Put challenges into thread safe flag_Q
    logging.debug(f"Queueing {len(challenges_list)} challenges")
    for challenge in challenges_list:
        flag_Q.put(challenge)

    dev_available = device_Q.get()
    logging.debug(f"Got first available device: {dev_available}")
    t = transmitter()

    jobs = []

    try:
        while dev_available is not None:
            # Get next challenge from queue
            challenge = flag_Q.get()

            # Extract challenge parameters from YAML structure
            cc_name = challenge.get('name', 'Unknown')
            cc_module = challenge.get('modulation')
            cc_flag = challenge.get('flag')
            cc_minwait = challenge.get('min_delay', 60)
            cc_maxwait = challenge.get('max_delay', 90)
            cc_freq1 = challenge.get('frequency')

            # Extract modulation-specific options
            if cc_module == 'fhss':
                # For FHSS, pack multiple parameters into modopt1 as a dict
                cc_modopt1 = {
                    'channel_spacing': challenge.get('channel_spacing', 10000),
                    'hop_rate': challenge.get('hop_rate', 10),
                    'hop_time': challenge.get('hop_time', 60),
                    'seed': challenge.get('seed', 'RFHS')
                }
                cc_modopt2 = challenge.get('wav_samplerate', 48000)
            else:
                cc_modopt1 = challenge.get('speed') or challenge.get('capcode') or challenge.get('mode') or challenge.get('wav_samplerate', '')
                cc_modopt2 = challenge.get('wav_samplerate', '')

            # Determine frequency (could be numeric, named range, or array of named ranges)
            frequency_ranges = challenge.get('frequency_ranges')

            if frequency_ranges:
                # New format: array of named frequency ranges
                # Select a random range from the array
                selected_range_name = choice(frequency_ranges)
                freq_range = select_freq(selected_range_name, config)
                if freq_range:
                    txfreq_khz = freq_range[0]
                    txfreq = txfreq_khz * 1000
                    freq_or_range = str(freq_range[1]) + "-" + str(freq_range[2])
                else:
                    logging.error(f"Could not find frequency range: {selected_range_name}")
                    raise ValueError(f"Unknown frequency range: {selected_range_name}")
            else:
                # Legacy format: single frequency or band name
                try:
                    # Frequency in Hz from YAML
                    txfreq = int(cc_freq1)
                    # Convert to kHz for display/legacy compatibility
                    txfreq_khz = txfreq // 1000
                    freq_or_range = str(txfreq_khz)
                except (ValueError, TypeError):
                    # Named frequency range (e.g., "ham_144")
                    freq_range = select_freq(cc_freq1, config)
                    if freq_range:
                        txfreq_khz = freq_range[0]
                        txfreq = txfreq_khz * 1000
                        freq_or_range = str(freq_range[1]) + "-" + str(freq_range[2])
                    else:
                        logging.error(f"Could not find frequency range: {cc_freq1}")
                        raise ValueError(f"Unknown frequency range: {cc_freq1}")

            # Paint waterfall every time during the CTF, or only once when testing
            if(test != True or challenges_transmitted == 0):
                if verbose:
                    print(f"\nPainting Waterfall on {txfreq_khz} kHz\n")
                logging.info(f"Painting waterfall on {txfreq_khz} kHz using device {dev_available}")
                device = fetch_device(dev_available)
                antenna = get_device_antenna(dev_available)
                if antenna and verbose:
                    print(f"Using antenna: {antenna}")

                p = Process(target=spectrum_paint.main, args=(txfreq, device, antenna))
                p.start()
                p.join()
                logging.debug("Waterfall painting complete")
                # Turn off biastee if the device is a bladerf with the biastee enabled
                if device and device.find("bladerf") != -1 and device.find("biastee=1") != -1:
                    bladeserial = parse_bladerf_ser(device)
                    serialarg = '*:serial={}'.format(bladeserial)
                    subprocess.run(['bladeRF-cli', '-d', serialarg, 'set', 'biastee', 'tx', 'off'])

            print(f"\nStarting {cc_name} on {txfreq_khz} kHz ({cc_module})")
            logging.info(f"Starting challenge '{cc_name}' ({cc_module}) on {txfreq_khz} kHz with device {dev_available}")

            # Create list of challenge module arguments
            # Format: [chal_id, flag, modopt1, modopt2, minwait, maxwait, freq_khz, replaceinqueue, norandsleep]
            replaceinqueue = True
            norandsleep = False
            if(test):
                replaceinqueue = False
                norandsleep = True

            # Use challenge dict as ID for now (will be replaced with proper ID system later)
            cc_id = challenges_transmitted
            challengeargs = [cc_id, cc_flag, cc_modopt1, cc_modopt2, cc_minwait, cc_maxwait, txfreq_khz, replaceinqueue, norandsleep]

            # Call appropriate fire_ method for modulation type
            if hasattr(t, "fire_" + cc_module):
                p = Process(target=getattr(t, "fire_" + cc_module), args=(dev_available, flag_Q, device_Q, challengeargs))
                p.start()
                if(test == True):
                    jobs.append(p)
                challenges_transmitted += 1
            else:
                logging.error(f"Unknown modulation type '{cc_module}' for challenge '{cc_name}'")
                print(f"Error: Unknown modulation type '{cc_module}' for challenge '{cc_name}'. Skipping.")
                # Put device back in queue since we didn't use it
                device_Q.put(dev_available)
            # #we need a way to know if p.start errored or not
            # os.system("echo " + freq_or_range + " > /run/shm/wctf_status/" + current_chal[8] + "_sdr")
            # os.system('''timeout 15 ssh -F /root/wctf/liludallasmultipass/ssh/config -oStrictHostKeyChecking=no -oConnectTimeout=10 -oPasswordAuthentication=no -n scoreboard echo ''' + freq_or_range + " > /run/shm/wctf_status/" + current_chal[8] + "_sdr")
            dev_available = device_Q.get()
            sleep(1)
            if(test == True and flag_Q.empty()):
                returnvalue = 0
                print("Testing complete")
                while(len(jobs)>0):
                    proc = jobs[0]
                    exitcode = proc.exitcode
                    jobs.remove(proc)
                    if(exitcode == None):
                        jobs.append(proc)
                        continue
                    if(exitcode != 0):
                        print("Failed")
                        returnvalue = 1
                        exit(returnvalue)
                    #print("exitcode: {}".format(proc.exitcode))
                    proc.join()
                exit(returnvalue)
    except KeyboardInterrupt:
        print("Trying to Exit!")
        try:
            p.terminate()
            p.join()
        except UnboundLocalError:
            pass
        finally:
            exit()


if __name__ == '__main__':
    main()
