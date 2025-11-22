#!/usr/bin/env python3
"""
GNU Radio Spectrum Listener Flowgraph

Captures RF signals using osmocom source and generates FFT data for waterfall generation.
This is a Python-based GNU Radio flowgraph that doesn't require the GUI.
"""

import numpy as np
import time
import logging
from typing import List, Optional

# Try to import GNU Radio components
HAS_GNURADIO = False
HAS_OSMOSDR = False
window = None

try:
    from gnuradio import gr, blocks, fft as gr_fft
    HAS_GNURADIO = True

    # Import window functions (location varies by GNU Radio version)
    try:
        from gnuradio.fft import window as fft_window
        window = fft_window
    except (ImportError, AttributeError):
        try:
            from gnuradio import window
        except ImportError:
            # Fallback to numpy/scipy windows
            import numpy as np
            class WindowFallback:
                @staticmethod
                def blackmanharris(n):
                    return np.blackman(n).tolist()
            window = WindowFallback

    # Import osmosdr (optional, might not be available in all installs)
    try:
        from osmosdr import source as osmo_source
        HAS_OSMOSDR = True
    except ImportError:
        logging.warning("gr-osmosdr not available - hardware recording disabled, simulation mode only")

except ImportError as e:
    logging.warning(f"GNU Radio not available - using simulated data for testing: {e}")

logger = logging.getLogger(__name__)


class SpectrumListener:
    """GNU Radio flowgraph for capturing RF spectrum and generating FFT data."""

    def __init__(self, frequency: int, sample_rate: int = 2000000,
                 fft_size: int = 1024, gain: float = 40.0, device_id: str = "",
                 simulate: bool = False):
        """Initialize spectrum listener.

        Args:
            frequency: Center frequency in Hz
            sample_rate: Sample rate in Hz (default 2 MHz)
            fft_size: FFT size for spectrum analysis (default 1024)
            gain: RF gain in dB (default 40)
            device_id: Device identifier string (e.g., "rtlsdr=0", "hackrf=0")
            simulate: Force simulation mode (generate test data without SDR hardware)
        """
        self.frequency = frequency
        self.sample_rate = sample_rate
        self.fft_size = fft_size
        self.gain = gain
        self.device_id = device_id
        self.simulate = simulate

        # FFT data storage
        self.fft_frames = []
        self.recording = False

        if HAS_GNURADIO and HAS_OSMOSDR and not simulate:
            self.tb = gr.top_block()
            self._build_flowgraph()
        else:
            self.tb = None
            if simulate:
                logger.info("Simulation mode: Using simulated spectrum data")
            elif not HAS_GNURADIO:
                logger.warning("GNU Radio not available - using simulation mode")
            elif not HAS_OSMOSDR:
                logger.warning("gr-osmosdr not available - using simulation mode")

    def _build_flowgraph(self):
        """Build GNU Radio flowgraph for spectrum capture."""
        # Osmocom source (supports RTL-SDR, HackRF, etc.)
        # Use device_id to select specific device
        self.source = osmo_source(args=self.device_id)
        self.source.set_sample_rate(self.sample_rate)
        self.source.set_center_freq(self.frequency, 0)
        self.source.set_freq_corr(0, 0)
        self.source.set_gain(self.gain, 0)
        self.source.set_if_gain(20, 0)
        self.source.set_bb_gain(20, 0)
        self.source.set_antenna('', 0)
        self.source.set_bandwidth(0, 0)

        # Stream to Vector for FFT processing
        self.s2v = blocks.stream_to_vector(gr.sizeof_gr_complex, self.fft_size)

        # FFT block (GNU Radio 3.9+ uses fft.fft_vcc, older uses blocks.fft_vcc)
        window_fn = window.blackmanharris(self.fft_size) if window else []
        try:
            # Try GNU Radio 3.9+ API
            self.fft = gr_fft.fft_vcc(self.fft_size, True, window_fn, True)
        except (AttributeError, NameError):
            # Fallback for GNU Radio 3.8
            self.fft = blocks.fft_vcc(self.fft_size, True, window_fn, True)

        # Complex to Mag^2 (power) - try multiple APIs
        try:
            # GNU Radio 3.10+ API
            self.c2mag = blocks.complex_to_mag_squared(self.fft_size)
        except (AttributeError, TypeError):
            # Fallback: use complex_to_mag and multiply
            self.c2mag = blocks.complex_to_mag(self.fft_size)

        # Vector sink to collect FFT frames
        self.sink = blocks.vector_sink_f(self.fft_size)

        # Connect flowgraph
        self.tb.connect(self.source, self.s2v)
        self.tb.connect(self.s2v, self.fft)
        self.tb.connect(self.fft, self.c2mag)
        self.tb.connect(self.c2mag, self.sink)

    def record(self, duration: float, frame_rate: int = 20) -> np.ndarray:
        """Capture RF spectrum for specified duration.

        Args:
            duration: Recording duration in seconds
            frame_rate: FFT frames per second (default 20 fps)

        Returns:
            2D numpy array of FFT data [time, frequency]
        """
        if not HAS_GNURADIO or not HAS_OSMOSDR or self.simulate or not self.tb:
            # Return simulated data for testing
            if self.simulate:
                logger.info("Using simulated spectrum data (simulation mode enabled)")
            else:
                logger.warning("Using simulated spectrum data (GNU Radio/osmosdr not available)")
            return self._generate_simulated_spectrum(duration, frame_rate)

        self.fft_frames = []
        self.recording = True

        try:
            # Calculate number of frames to capture
            num_frames = int(duration * frame_rate)
            samples_per_frame = int(self.sample_rate / frame_rate)

            logger.info(f"Capturing {num_frames} frames at {frame_rate} fps")

            # Start flowgraph
            self.tb.start()

            start_time = time.time()

            # Collect FFT frames
            while len(self.fft_frames) < num_frames and self.recording:
                # Get data from sink
                data = self.sink.data()

                if len(data) >= self.fft_size:
                    # Extract one frame
                    frame = np.array(data[:self.fft_size])

                    # Apply FFT shift (move DC to center)
                    frame_shifted = np.fft.fftshift(frame)

                    self.fft_frames.append(frame_shifted)

                    # Clear consumed data
                    self.sink.reset()

                    # Wait for next frame
                    elapsed = time.time() - start_time
                    expected_frames = int(elapsed * frame_rate)
                    if len(self.fft_frames) < expected_frames:
                        time.sleep(1.0 / frame_rate)

                time.sleep(0.001)  # Small sleep to prevent busy waiting

            # Stop flowgraph
            self.tb.stop()
            self.tb.wait()

            # Convert to 2D array
            fft_data = np.array(self.fft_frames)

            logger.info(f"Captured {fft_data.shape[0]} frames, shape: {fft_data.shape}")

            return fft_data

        except Exception as e:
            logger.error(f"Error during recording: {e}", exc_info=True)
            if self.tb:
                self.tb.stop()
                self.tb.wait()
            raise

        finally:
            self.recording = False

    def _generate_simulated_spectrum(self, duration: float, frame_rate: int) -> np.ndarray:
        """Generate simulated spectrum data for testing when GNU Radio is unavailable.

        Args:
            duration: Duration in seconds
            frame_rate: Frames per second

        Returns:
            2D numpy array of simulated FFT data
        """
        num_frames = int(duration * frame_rate)

        # Create simulated spectrum with noise floor and some signals
        frames = []

        for i in range(num_frames):
            # Base noise floor
            noise = np.random.randn(self.fft_size) * 0.1

            # Add simulated signals at various positions
            t = i / frame_rate

            # Signal 1: Carrier at 1/4 position
            signal_pos1 = self.fft_size // 4
            signal_width1 = 5
            signal_strength1 = 1.0 if (t % 2.0) < 1.5 else 0.0  # Pulsed signal
            noise[signal_pos1-signal_width1:signal_pos1+signal_width1] += signal_strength1

            # Signal 2: Wideband at center
            signal_pos2 = self.fft_size // 2
            signal_width2 = 20
            signal_strength2 = 0.5 + 0.3 * np.sin(2 * np.pi * t * 0.5)  # Varying signal
            noise[signal_pos2-signal_width2:signal_pos2+signal_width2] += signal_strength2

            # Signal 3: Narrow signal at 3/4 position
            signal_pos3 = 3 * self.fft_size // 4
            signal_width3 = 3
            signal_strength3 = 0.8
            noise[signal_pos3-signal_width3:signal_pos3+signal_width3] += signal_strength3

            # Convert to power (square)
            power = noise ** 2

            frames.append(power)

        return np.array(frames)

    def stop(self):
        """Stop recording early."""
        self.recording = False
        if self.tb:
            self.tb.stop()
