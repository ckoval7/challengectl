#!/usr/bin/env python3
"""
Challenge Duration Calculator

Automatically calculates the expected duration of challenge transmissions based on
modulation type and parameters (audio file length, CW speed, etc.).
"""

import os
import logging
import wave
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def get_wav_duration(file_path: str) -> Optional[float]:
    """Get duration of a WAV file in seconds.

    Args:
        file_path: Path to WAV file

    Returns:
        Duration in seconds, or None if unable to read
    """
    try:
        with wave.open(file_path, 'rb') as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            duration = frames / float(rate)
            return duration
    except Exception as e:
        logger.warning(f"Could not read WAV file duration from {file_path}: {e}")
        return None


def calculate_cw_duration(message: str, wpm: int) -> float:
    """Calculate duration of CW (morse code) transmission.

    Args:
        message: Message to transmit
        wpm: Words per minute (PARIS standard)

    Returns:
        Duration in seconds
    """
    # CW timing: PARIS standard = 50 dot-units per word
    # At 1 WPM, one word takes 60 seconds / 1 = 60 seconds
    # One dot-unit = 60 / 50 = 1.2 seconds at 1 WPM
    # At N WPM, one dot-unit = 1.2 / N seconds

    # Approximate characters in message (each char is roughly 10 dot-units on average)
    # More accurate would be to look up morse code for each character
    # PARIS has 50 dot-units total for 5 characters = 10 dot-units per character average

    dot_unit_duration = 1.2 / wpm  # seconds per dot
    estimated_units = len(message) * 10  # Rough estimate: 10 units per character

    # Add spacing between characters (3 units) and words (7 units)
    # Rough approximation: add 30% for spacing
    duration = estimated_units * dot_unit_duration * 1.3

    return duration


def calculate_paint_duration(file_path: str, image_width: int = 113, line_time_ms: int = 25) -> Optional[float]:
    """Calculate duration of spectrum paint transmission.

    Args:
        file_path: Path to paint binary file
        image_width: Width of image in pixels (default: 113)
        line_time_ms: Time per line in milliseconds (default: 25ms)

    Returns:
        Duration in seconds, or None if unable to calculate
    """
    try:
        file_size = os.path.getsize(file_path)

        # Each pixel is 1 byte (grayscale)
        # Number of lines = file_size / image_width
        num_lines = file_size / image_width

        # Total time = num_lines * line_time_ms / 1000
        duration = (num_lines * line_time_ms) / 1000.0

        return duration
    except Exception as e:
        logger.warning(f"Could not calculate paint duration from {file_path}: {e}")
        return None


def calculate_fhss_duration(hop_time: float, num_hops: int = None) -> float:
    """Calculate duration of FHSS transmission.

    Args:
        hop_time: Time per hop in seconds
        num_hops: Number of hops (if known), otherwise estimate based on audio

    Returns:
        Duration in seconds
    """
    if num_hops:
        return hop_time * num_hops

    # If we don't know number of hops, return a conservative estimate
    # Typically FHSS challenges hop for 30-60 seconds
    return 30.0  # Default estimate


def calculate_pager_duration(message: str, baud_rate: int = 512) -> float:
    """Calculate duration of pager transmission (POCSAG/LRS).

    Args:
        message: Message to transmit
        baud_rate: Baud rate (default: 512 for POCSAG)

    Returns:
        Duration in seconds
    """
    # POCSAG/LRS overhead is significant
    # Rough estimate: ~10 bits per character + overhead
    # Add preamble and postamble

    bits_per_char = 10
    total_bits = len(message) * bits_per_char + 1000  # Add overhead
    duration = total_bits / baud_rate

    # Add minimum transmission time for preamble/sync
    duration += 2.0

    return duration


def calculate_challenge_duration(config: Dict, files_dir: str = "files",
                                include_pre_paint: bool = False,
                                pre_paint_duration: float = 0.0) -> float:
    """Calculate expected duration of a challenge transmission.

    Args:
        config: Challenge configuration dictionary
        files_dir: Directory where challenge files are stored
        include_pre_paint: Whether to include pre-challenge paint duration
        pre_paint_duration: Duration of pre-challenge paint (if known)

    Returns:
        Duration in seconds
    """
    modulation = config.get('modulation', '').lower()
    duration = 0.0

    # Check for explicitly configured duration first
    if 'duration' in config and config['duration'] is not None:
        duration = float(config['duration'])
        logger.debug(f"Using explicit duration: {duration}s")

        # Still add pre-paint if requested
        if include_pre_paint and pre_paint_duration > 0:
            duration += pre_paint_duration
            logger.debug(f"Added pre-paint duration: {pre_paint_duration}s, total: {duration}s")

        return duration

    # Calculate based on modulation type
    if modulation in ['nbfm', 'ssb', 'freedv']:
        # Audio-based modulations
        flag = config.get('flag', '')
        flag_file_hash = config.get('flag_file_hash')

        # Check for flag_file_hash first (from uploaded files)
        if flag_file_hash:
            file_path = os.path.join(files_dir, flag_file_hash)
        # Check if flag is a sha256: reference
        elif flag.startswith('sha256:'):
            # It's a hash reference - construct file path
            file_hash = flag[7:]
            file_path = os.path.join(files_dir, file_hash)
        else:
            # It's a relative path
            file_path = flag if os.path.isabs(flag) else os.path.join(files_dir, '..', flag)

        if os.path.exists(file_path):
            wav_duration = get_wav_duration(file_path)
            if wav_duration:
                duration = wav_duration
                logger.debug(f"Calculated audio duration: {duration}s from {file_path}")
            else:
                duration = 30.0  # Default fallback
                logger.warning(f"Could not calculate audio duration, using default: {duration}s")
        else:
            duration = 30.0  # Default if file not found
            logger.warning(f"Audio file not found at {file_path}, using default: {duration}s")

    elif modulation == 'cw':
        # CW morse code
        message = config.get('flag', '')
        wpm = config.get('speed', 35)
        duration = calculate_cw_duration(message, wpm)
        logger.debug(f"Calculated CW duration: {duration}s (message: {len(message)} chars, {wpm} WPM)")

    elif modulation == 'paint':
        # Spectrum paint
        flag = config.get('flag', '')
        flag_file_hash = config.get('flag_file_hash')

        # Check for flag_file_hash first (from uploaded files)
        if flag_file_hash:
            file_path = os.path.join(files_dir, flag_file_hash)
        # Check if flag is a sha256: reference
        elif flag.startswith('sha256:'):
            file_hash = flag[7:]
            file_path = os.path.join(files_dir, file_hash)
        else:
            file_path = flag if os.path.isabs(flag) else os.path.join(files_dir, '..', flag)

        if os.path.exists(file_path):
            paint_duration = calculate_paint_duration(file_path)
            if paint_duration:
                duration = paint_duration
                logger.debug(f"Calculated paint duration: {duration}s from {file_path}")
            else:
                duration = 30.0
                logger.warning(f"Could not calculate paint duration, using default: {duration}s")
        else:
            duration = 30.0
            logger.warning(f"Paint file not found at {file_path}, using default: {duration}s")

    elif modulation == 'fhss':
        # FHSS - hop-based duration
        hop_time = config.get('hop_time', 0.1)
        # Try to estimate from audio if available
        flag = config.get('flag', '')
        flag_file_hash = config.get('flag_file_hash')

        if flag_file_hash or flag:
            # Check for flag_file_hash first (from uploaded files)
            if flag_file_hash:
                file_path = os.path.join(files_dir, flag_file_hash)
            # Check if flag is a sha256: reference
            elif flag.startswith('sha256:'):
                file_hash = flag[7:]
                file_path = os.path.join(files_dir, file_hash)
            else:
                file_path = flag if os.path.isabs(flag) else os.path.join(files_dir, '..', flag)

            if os.path.exists(file_path):
                wav_duration = get_wav_duration(file_path)
                if wav_duration:
                    # Audio duration determines number of hops
                    num_hops = int(wav_duration / hop_time)
                    duration = calculate_fhss_duration(hop_time, num_hops)
                    logger.debug(f"Calculated FHSS duration: {duration}s ({num_hops} hops)")
                else:
                    duration = calculate_fhss_duration(hop_time)
                    logger.debug(f"FHSS duration estimate: {duration}s")
            else:
                duration = calculate_fhss_duration(hop_time)
                logger.debug(f"FHSS duration estimate: {duration}s")
        else:
            duration = calculate_fhss_duration(hop_time)
            logger.debug(f"FHSS duration estimate: {duration}s")

    elif modulation in ['pocsag', 'lrs']:
        # Pager transmissions
        message = config.get('flag', '')
        duration = calculate_pager_duration(message)
        logger.debug(f"Calculated pager duration: {duration}s (message: {len(message)} chars)")

    elif modulation == 'ask':
        # ASK - similar to CW
        message = config.get('flag', '')
        # ASK is typically faster than CW
        duration = len(message) * 0.1  # Rough estimate: 100ms per bit
        logger.debug(f"Calculated ASK duration: {duration}s")

    else:
        # Unknown modulation - use safe default
        duration = 30.0
        logger.warning(f"Unknown modulation type '{modulation}', using default: {duration}s")

    # Add pre-challenge paint duration if requested
    if include_pre_paint and pre_paint_duration > 0:
        duration += pre_paint_duration
        logger.debug(f"Added pre-paint duration: {pre_paint_duration}s, total: {duration}s")

    # Ensure minimum duration
    if duration < 1.0:
        logger.warning(f"Calculated duration {duration}s is too short, using minimum 1.0s")
        duration = 1.0

    return duration


# Pre-challenge paint duration constants
# Based on spectrum_paint.py parameters: paint.paint_bc(113, 25, ...)
# Default paint file is 'challenges/rfhs.bin'
PRE_PAINT_IMAGE_WIDTH = 113
PRE_PAINT_LINE_TIME_MS = 25
PRE_PAINT_FILE = 'challenges/rfhs.bin'


def get_pre_paint_duration(files_dir: str = "files") -> float:
    """Get the duration of the pre-challenge spectrum paint.

    Args:
        files_dir: Base directory for files

    Returns:
        Duration in seconds
    """
    # Calculate paint duration from default file
    paint_file_path = os.path.join(files_dir, '..', PRE_PAINT_FILE)

    if os.path.exists(paint_file_path):
        duration = calculate_paint_duration(paint_file_path, PRE_PAINT_IMAGE_WIDTH, PRE_PAINT_LINE_TIME_MS)
        if duration:
            logger.debug(f"Pre-challenge paint duration: {duration}s")
            return duration

    # Fallback estimate if we can't calculate from file
    # Typical paint files are ~5-10 seconds
    default_duration = 7.0
    logger.debug(f"Could not calculate pre-paint duration, using estimate: {default_duration}s")
    return default_duration
