#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: NBFM Transmitter
# Author: Corey Koval
# Description: NBFM Transmitter with adjustable audio levels
# GNU Radio version: 3.10.1.1

from gnuradio import analog
from gnuradio import blocks
from gnuradio import filter
from gnuradio.filter import firdes
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
import osmosdr




class nbfm(gr.top_block):

    def __init__(self, audio_gain=0.6, bb_gain=20, dev='bladerf=0', file='./test.wav', freq=int(449e6), if_gain=20, ppm=0, rf_gain=20, rf_samp_rate=2000000, wav_rate=48000):
        gr.top_block.__init__(self, "NBFM Transmitter", catch_exceptions=True)

        ##################################################
        # Parameters
        ##################################################
        self.audio_gain = audio_gain
        self.bb_gain = bb_gain
        self.dev = dev
        self.file = file
        self.freq = freq
        self.if_gain = if_gain
        self.ppm = ppm
        self.rf_gain = rf_gain
        self.rf_samp_rate = rf_samp_rate
        self.wav_rate = wav_rate

        ##################################################
        # Variables
        ##################################################
        self.audio_rate = audio_rate = 48000
        self.variable_low_pass_filter_taps_0 = variable_low_pass_filter_taps_0 = firdes.low_pass(audio_gain, wav_rate, 3000,300, window.WIN_HAMMING, 6.76)
        self.if_rate = if_rate = audio_rate*4

        ##################################################
        # Blocks
        ##################################################
        self.rational_resampler_xxx_1 = filter.rational_resampler_fff(
                interpolation=audio_rate,
                decimation=wav_rate,
                taps=variable_low_pass_filter_taps_0,
                fractional_bw=0)
        self.rational_resampler_xxx_0 = filter.rational_resampler_ccc(
            interpolation=samp_rate,
            decimation=int(240e3),
            taps=[],
            fractional_bw=0.0,
        )
        self.osmosdr_sink_0 = osmosdr.sink(args="numchan=" + str(1) + " " + str(dev))
        self.osmosdr_sink_0.set_sample_rate(samp_rate)
        self.osmosdr_sink_0.set_center_freq(freq, 0)
        self.osmosdr_sink_0.set_freq_corr(25, 0)
        self.osmosdr_sink_0.set_gain(rf_gain, 0)
        self.osmosdr_sink_0.set_if_gain(if_gain, 0)
        self.osmosdr_sink_0.set_bb_gain(bb_gain, 0)
        self.osmosdr_sink_0.set_antenna(ant, 0)
        self.osmosdr_sink_0.set_bandwidth(0, 0)

        self.blocks_wavfile_source_0 = blocks.wavfile_source(wav_file, False)
        self.blocks_multiply_const_vxx_0 = blocks.multiply_const_vff((0.7, ))
        self.analog_nbfm_tx_0 = analog.nbfm_tx(
        	audio_rate=audio_rate,
        	quad_rate=if_rate,
        	tau=75e-6,
        	max_dev=5e3,
        	fh=-1.0,
                )


        ##################################################
        # Connections
        ##################################################
        self.connect((self.analog_nbfm_tx_0, 0), (self.rational_resampler_xxx_0, 0))
        self.connect((self.blocks_multiply_const_vxx_0, 0), (self.rational_resampler_xxx_1, 0))
        self.connect((self.blocks_wavfile_source_0, 0), (self.blocks_multiply_const_vxx_0, 0))
        self.connect((self.rational_resampler_xxx_0, 0), (self.osmosdr_sink_0, 0))
        self.connect((self.rational_resampler_xxx_1, 0), (self.analog_nbfm_tx_0, 0))


    def get_audio_gain(self):
        return self.audio_gain

    def set_audio_gain(self, audio_gain):
        self.audio_gain = audio_gain
        self.set_variable_low_pass_filter_taps_0(firdes.low_pass(self.audio_gain, self.wav_rate, 3000, 300, window.WIN_HAMMING, 6.76))

    def get_bb_gain(self):
        return self.bb_gain

    def set_bb_gain(self, bb_gain):
        self.bb_gain = bb_gain

    def get_dev(self):
        return self.dev

    def set_dev(self, dev):
        self.dev = dev

    def get_file(self):
        return self.file

    def set_file(self, file):
        self.file = file

    def get_freq(self):
        return self.freq

    def set_freq(self, freq):
        self.freq = freq

    def get_if_gain(self):
        return self.if_gain

    def set_if_gain(self, if_gain):
        self.if_gain = if_gain

    def get_ppm(self):
        return self.ppm

    def set_ppm(self, ppm):
        self.ppm = ppm

    def get_rf_gain(self):
        return self.rf_gain

    def set_rf_gain(self, rf_gain):
        self.rf_gain = rf_gain

    def get_rf_samp_rate(self):
        return self.rf_samp_rate

    def set_rf_samp_rate(self, rf_samp_rate):
        self.rf_samp_rate = rf_samp_rate

    def get_wav_rate(self):
        return self.wav_rate

    def set_wav_rate(self, wav_rate):
        self.wav_rate = wav_rate
        self.set_variable_low_pass_filter_taps_0(firdes.low_pass(self.audio_gain, self.wav_rate, 3000, 300, window.WIN_HAMMING, 6.76))

    def get_audio_rate(self):
        return self.audio_rate

    def set_audio_rate(self, audio_rate):
        self.audio_rate = audio_rate
        self.set_if_rate(self.audio_rate*4)

    def get_variable_low_pass_filter_taps_0(self):
        return self.variable_low_pass_filter_taps_0

    def set_variable_low_pass_filter_taps_0(self, variable_low_pass_filter_taps_0):
        self.variable_low_pass_filter_taps_0 = variable_low_pass_filter_taps_0
        self.rational_resampler_xxx_1.set_taps(self.variable_low_pass_filter_taps_0)

    def get_if_rate(self):
        return self.if_rate

    def set_if_rate(self, if_rate):
        self.if_rate = if_rate


def main(wav_src, wav_rate, frequency, device, antenna, top_block_cls=nbfm, options=None):

    global wav_file
    global wav_samp_rate
    global freq
    global dev
    global ant
    global samp_rate

    wav_file = wav_src
    wav_samp_rate = wav_rate
    freq = frequency
    dev = device
    ant = str(antenna)
    samp_rate = 2000000

    tb = top_block_cls()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()

    tb.wait()


if __name__ == '__main__':
    main()
