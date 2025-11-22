#!/usr/bin/env python3
"""
Waterfall Image Generator

Generates waterfall (spectrogram) images from FFT data captured by the spectrum listener.
Uses matplotlib for high-quality PNG output with proper axis labels and colormaps.
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server use
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import logging

logger = logging.getLogger(__name__)


def generate_waterfall(fft_data: np.ndarray, frequency: int, sample_rate: int,
                      fft_size: int, frame_rate: int, output_path: str,
                      reference_level_dbm: float = -10.0):
    """Generate waterfall PNG image from FFT data.

    Args:
        fft_data: 2D numpy array of FFT power data [time, frequency]
        frequency: Center frequency in Hz
        sample_rate: Sample rate in Hz
        fft_size: FFT size used for capture
        frame_rate: Frame rate (fps) used for capture
        output_path: Path to save PNG image
        reference_level_dbm: Reference level in dBm for full scale (default: -10 dBm)
                            This converts linear power to absolute dBm values.
                            Typical values: -10 dBm for RTL-SDR, 0 dBm for HackRF
    """
    logger.info(f"Generating waterfall: {fft_data.shape[0]} frames x {fft_data.shape[1]} bins")

    # Find the maximum power value across all data (for normalization)
    max_power = np.max(fft_data)
    if max_power <= 0:
        max_power = 1.0  # Avoid division by zero for empty/zero data

    # Convert power to dBFS (dB relative to full scale)
    # Normalize to max value, so maximum signal is at 0 dBFS
    fft_data_dbfs = 10 * np.log10(fft_data / max_power + 1e-10)

    # Convert dBFS to dBm using reference level
    # 0 dBFS corresponds to reference_level_dbm
    fft_data_db = fft_data_dbfs + reference_level_dbm

    # Auto-scale: use 5th and 95th percentile for dynamic range
    vmin = np.percentile(fft_data_db, 5)
    vmax = np.percentile(fft_data_db, 95)

    logger.debug(f"Power range: {vmin:.1f} to {vmax:.1f} dBm (reference: {reference_level_dbm:.1f} dBm at 0 dBFS)")

    # Create custom colormap (blue -> green -> yellow -> red)
    colors = ['#000033', '#000066', '#0000CC', '#00CC00', '#CCCC00', '#CC6600', '#CC0000']
    n_bins = 256
    cmap = LinearSegmentedColormap.from_list('spectrum', colors, N=n_bins)

    # Calculate time and frequency axes
    duration = fft_data.shape[0] / frame_rate
    time_axis = np.linspace(0, duration, fft_data.shape[0])

    freq_min = frequency - sample_rate / 2
    freq_max = frequency + sample_rate / 2
    freq_axis = np.linspace(freq_min, freq_max, fft_size)

    # Create figure with appropriate size
    # Height scales with number of time frames to maintain aspect ratio
    width_inches = 12
    height_inches = max(6, min(48, fft_data.shape[0] / 50))  # Scale height, cap at 48"

    fig, ax = plt.subplots(figsize=(width_inches, height_inches), dpi=100)

    # Plot waterfall
    im = ax.imshow(
        fft_data_db,
        aspect='auto',
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        extent=[freq_min / 1e6, freq_max / 1e6, duration, 0],  # [left, right, bottom, top]
        interpolation='nearest'
    )

    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, label='Power (dBm)')

    # Set labels
    ax.set_xlabel('Frequency (MHz)')
    ax.set_ylabel('Time (seconds)')
    ax.set_title(f'Spectrum Waterfall - {frequency / 1e6:.3f} MHz')

    # Add grid
    ax.grid(True, alpha=0.3, linestyle='--')

    # Format frequency axis to show MHz with 3 decimal places
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.3f}'))

    # Tight layout to prevent label cutoff
    plt.tight_layout()

    # Save to file
    plt.savefig(output_path, format='png', dpi=100, bbox_inches='tight')
    plt.close(fig)

    logger.info(f"Waterfall image saved: {output_path}")


def generate_waterfall_with_markers(fft_data: np.ndarray, frequency: int, sample_rate: int,
                                   fft_size: int, frame_rate: int, output_path: str,
                                   markers: list = None, reference_level_dbm: float = -10.0):
    """Generate waterfall with optional time/frequency markers.

    This is an enhanced version that can mark specific events or signals.

    Args:
        fft_data: 2D numpy array of FFT power data [time, frequency]
        frequency: Center frequency in Hz
        sample_rate: Sample rate in Hz
        fft_size: FFT size used for capture
        frame_rate: Frame rate (fps) used for capture
        output_path: Path to save PNG image
        markers: List of marker dicts with keys: time, freq, label, color
        reference_level_dbm: Reference level in dBm for full scale (default: -10 dBm)
    """
    # Generate base waterfall
    generate_waterfall(fft_data, frequency, sample_rate, fft_size, frame_rate, output_path,
                      reference_level_dbm=reference_level_dbm)

    # If markers provided, add them
    if markers:
        # Re-open figure to add markers
        fig = plt.figure(figsize=(12, max(6, fft_data.shape[0] / 50)), dpi=100)
        ax = fig.gca()

        # Re-plot waterfall (could be optimized by saving/loading)
        # Apply same power conversion as main function
        max_power = np.max(fft_data)
        if max_power <= 0:
            max_power = 1.0
        fft_data_dbfs = 10 * np.log10(fft_data / max_power + 1e-10)
        fft_data_db = fft_data_dbfs + reference_level_dbm
        vmin = np.percentile(fft_data_db, 5)
        vmax = np.percentile(fft_data_db, 95)

        duration = fft_data.shape[0] / frame_rate
        freq_min = frequency - sample_rate / 2
        freq_max = frequency + sample_rate / 2

        colors = ['#000033', '#000066', '#0000CC', '#00CC00', '#CCCC00', '#CC6600', '#CC0000']
        cmap = LinearSegmentedColormap.from_list('spectrum', colors, N=256)

        im = ax.imshow(
            fft_data_db,
            aspect='auto',
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            extent=[freq_min / 1e6, freq_max / 1e6, duration, 0],
            interpolation='nearest'
        )

        # Add markers
        for marker in markers:
            t = marker.get('time', 0)
            f = marker.get('freq', frequency) / 1e6  # Convert to MHz
            label = marker.get('label', '')
            color = marker.get('color', 'white')

            ax.plot(f, t, 'o', color=color, markersize=8)
            if label:
                ax.annotate(label, (f, t), color=color, fontsize=10,
                           xytext=(10, -10), textcoords='offset points',
                           bbox=dict(boxstyle='round,pad=0.5', fc='black', alpha=0.7))

        plt.colorbar(im, ax=ax, label='Power (dBm)')
        ax.set_xlabel('Frequency (MHz)')
        ax.set_ylabel('Time (seconds)')
        ax.set_title(f'Spectrum Waterfall - {frequency / 1e6:.3f} MHz')
        ax.grid(True, alpha=0.3, linestyle='--')

        plt.tight_layout()
        plt.savefig(output_path, format='png', dpi=100, bbox_inches='tight')
        plt.close(fig)

        logger.info(f"Waterfall with markers saved: {output_path}")


# Example usage for testing
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # Generate test data
    duration = 30  # seconds
    frame_rate = 20  # fps
    fft_size = 1024

    num_frames = duration * frame_rate

    # Simulated FFT data (noise + signal)
    fft_data = np.random.randn(num_frames, fft_size) ** 2

    # Add a signal that sweeps across frequency
    for i in range(num_frames):
        t = i / frame_rate
        signal_pos = int(fft_size * (0.3 + 0.4 * (t / duration)))
        signal_width = 10
        fft_data[i, signal_pos-signal_width:signal_pos+signal_width] += 10.0

    # Generate waterfall
    generate_waterfall(
        fft_data=fft_data,
        frequency=146000000,  # 146 MHz
        sample_rate=2000000,  # 2 MHz
        fft_size=fft_size,
        frame_rate=frame_rate,
        output_path='test_waterfall.png'
    )

    print("Test waterfall generated: test_waterfall.png")
