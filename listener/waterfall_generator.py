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
COLORMAP = ['#000033', '#000066', '#0000CC', '#00CC00', '#CCCC00', '#CC6600', '#CC0000']

MAX_PERCENTILE = 98
MIN_PERCENTILE = 50


def generate_waterfall(fft_data: np.ndarray, frequency: int, sample_rate: int,
                      fft_size: int, frame_rate: int, output_path: str,
                      reference_level_dbm: float = -10.0,
                      vmin_dbm: float = None,
                      vmax_dbm: float = None):
    """Generate waterfall PNG image from FFT data with dual-bandwidth view.

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
        vmin_dbm: Minimum power level for waterfall scale (dBm). If None, auto-scale.
        vmax_dbm: Maximum power level for waterfall scale (dBm). If None, auto-scale.
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

    # Use manual scale if provided, otherwise auto-scale
    if vmin_dbm is not None and vmax_dbm is not None:
        vmin = vmin_dbm
        vmax = vmax_dbm
        logger.info(f"Using manual waterfall scale: {vmin:.1f} to {vmax:.1f} dBm")
    else:
        # Auto-scale: use 5th and 95th percentile for dynamic range
        vmin = np.percentile(fft_data_db, MIN_PERCENTILE)
        vmax = np.percentile(fft_data_db, MAX_PERCENTILE)
        logger.debug(f"Auto-scaling waterfall: {vmin:.1f} to {vmax:.1f} dBm (reference: {reference_level_dbm:.1f} dBm at 0 dBFS)")

    # Create custom colormap (blue -> green -> yellow -> red)
    colors = COLORMAP
    n_bins = 256
    cmap = LinearSegmentedColormap.from_list('spectrum', colors, N=n_bins)

    # Calculate time and frequency axes for full bandwidth
    duration = fft_data.shape[0] / frame_rate
    time_axis = np.linspace(0, duration, fft_data.shape[0])

    freq_min = frequency - sample_rate / 2
    freq_max = frequency + sample_rate / 2
    freq_axis = np.linspace(freq_min, freq_max, fft_size)

    # Extract center 200 kHz for decimated waterfall
    zoom_bandwidth = 200e3  # 200 kHz
    bins_per_hz = fft_size / sample_rate
    zoom_bins = int(zoom_bandwidth * bins_per_hz)
    center_bin = fft_size // 2
    zoom_start = center_bin - zoom_bins // 2
    zoom_end = center_bin + zoom_bins // 2

    # Extract center portion of spectrum
    fft_data_zoom_db = fft_data_db[:, zoom_start:zoom_end]

    zoom_freq_min = frequency - zoom_bandwidth / 2
    zoom_freq_max = frequency + zoom_bandwidth / 2

    logger.info(f"Zoom waterfall: {zoom_bins} bins covering {zoom_bandwidth/1e3:.1f} kHz")

    # Create figure with two subplots side-by-side (full bandwidth on left, zoom on right)
    # Height scales with number of time frames to maintain aspect ratio
    base_height = max(6, min(48, fft_data.shape[0] / 50))  # Scale height, cap at 48"
    width_inches = 16  # Wider to accommodate side-by-side layout

    # Allocate 60% width to full bandwidth, 40% to zoom
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(width_inches, base_height),
                                     gridspec_kw={'width_ratios': [3, 2]})

    # Plot full bandwidth waterfall
    im1 = ax1.imshow(
        fft_data_db,
        aspect='auto',
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        extent=[freq_min / 1e6, freq_max / 1e6, duration, 0],  # [left, right, bottom, top]
        interpolation='nearest'
    )

    # Set labels for full bandwidth
    ax1.set_xlabel('Frequency (MHz)')
    ax1.set_ylabel('Time (seconds)')
    ax1.set_title(f'Full Spectrum - {frequency / 1e6:.3f} MHz (BW: {sample_rate/1e6:.2f} MHz)')
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.3f}'))

    # Plot zoomed (200 kHz) waterfall
    im2 = ax2.imshow(
        fft_data_zoom_db,
        aspect='auto',
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        extent=[zoom_freq_min / 1e6, zoom_freq_max / 1e6, duration, 0],
        interpolation='nearest'
    )

    # Set labels for zoomed waterfall
    ax2.set_xlabel('Frequency (MHz)')
    ax2.set_ylabel('Time (seconds)')
    ax2.set_title(f'Zoomed View - {frequency / 1e6:.3f} MHz (BW: {zoom_bandwidth/1e3:.0f} kHz)')
    ax2.grid(True, alpha=0.3, linestyle='--')
    ax2.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.3f}'))

    # Add single colorbar on the right side of the figure
    fig.subplots_adjust(right=0.93)
    cbar_ax = fig.add_axes([0.94, 0.15, 0.01, 0.7])
    cbar = fig.colorbar(im1, cax=cbar_ax, label='Power (dBm)')

    # Tight layout to prevent label cutoff (but preserve colorbar space)
    plt.tight_layout(rect=[0, 0, 0.93, 1])

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
        vmin = np.percentile(fft_data_db, MIN_PERCENTILE)
        vmax = np.percentile(fft_data_db, MAX_PERCENTILE)

        duration = fft_data.shape[0] / frame_rate
        freq_min = frequency - sample_rate / 2
        freq_max = frequency + sample_rate / 2

        colors = COLORMAP
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
