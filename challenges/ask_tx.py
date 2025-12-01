#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: ASK Transmit
# Author: corey
# Copyright: RFHS
# Description: Transmit ASK CTF Challenge
# GNU Radio version: 3.10.9.2

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
from gnuradio import rfhs
import osmosdr
import time




class ask_tx(gr.top_block):

    def __init__(self, antenna='', baud_rate=2400, bbgain=20, deviceargs="file=/dev/null,freq=100e6,label='Complex Sampled (IQ) File',rate=1e6,throttle=false", flag='RFHS', freq=146550000, ifgain=20, repeat=10, rfgain=32, samp_rate=2400000):
        gr.top_block.__init__(self, "ASK Transmit", catch_exceptions=True)

        ##################################################
        # Parameters
        ##################################################
        self.antenna = antenna
        self.baud_rate = baud_rate
        self.bbgain = bbgain
        self.deviceargs = deviceargs
        self.flag = flag
        self.freq = freq
        self.ifgain = ifgain
        self.repeat = repeat
        self.rfgain = rfgain
        self.samp_rate = samp_rate

        ##################################################
        # Blocks
        ##################################################

        self.rfhs_ask_source_0 = rfhs.ask_source(flag, samp_rate, baud_rate)
        self.rational_resampler_xxx_0 = filter.rational_resampler_fcc(
                interpolation=1,
                decimation=1,
                taps=[],
                fractional_bw=0)
        self.osmosdr_sink_0 = osmosdr.sink(
            args="numchan=" + str(1) + " " + deviceargs
        )
        self.osmosdr_sink_0.set_sample_rate(samp_rate)
        self.osmosdr_sink_0.set_center_freq(freq, 0)
        self.osmosdr_sink_0.set_freq_corr(0, 0)
        self.osmosdr_sink_0.set_gain(rfgain, 0)
        self.osmosdr_sink_0.set_if_gain(ifgain, 0)
        self.osmosdr_sink_0.set_bb_gain(bbgain, 0)
        self.osmosdr_sink_0.set_antenna(antenna, 0)
        self.osmosdr_sink_0.set_bandwidth(0, 0)
        self.low_pass_filter_0 = filter.fir_filter_ccf(
            1,
            firdes.low_pass(
                1,
                samp_rate,
                3000,
                300,
                window.WIN_HAMMING,
                6.76))
        self.blocks_moving_average_xx_0 = blocks.moving_average_cc((int(samp_rate/baud_rate)), 0.9/(samp_rate/baud_rate), 4000, 1)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.blocks_moving_average_xx_0, 0), (self.low_pass_filter_0, 0))
        self.connect((self.low_pass_filter_0, 0), (self.osmosdr_sink_0, 0))
        self.connect((self.rational_resampler_xxx_0, 0), (self.blocks_moving_average_xx_0, 0))
        self.connect((self.rfhs_ask_source_0, 0), (self.rational_resampler_xxx_0, 0))


    def get_antenna(self):
        return self.antenna

    def set_antenna(self, antenna):
        self.antenna = antenna
        self.osmosdr_sink_0.set_antenna(self.antenna, 0)

    def get_baud_rate(self):
        return self.baud_rate

    def set_baud_rate(self, baud_rate):
        self.baud_rate = baud_rate
        self.blocks_moving_average_xx_0.set_length_and_scale((int(self.samp_rate/self.baud_rate)), 0.9/(self.samp_rate/self.baud_rate))

    def get_bbgain(self):
        return self.bbgain

    def set_bbgain(self, bbgain):
        self.bbgain = bbgain
        self.osmosdr_sink_0.set_bb_gain(self.bbgain, 0)

    def get_deviceargs(self):
        return self.deviceargs

    def set_deviceargs(self, deviceargs):
        self.deviceargs = deviceargs

    def get_flag(self):
        return self.flag

    def set_flag(self, flag):
        self.flag = flag

    def get_freq(self):
        return self.freq

    def set_freq(self, freq):
        self.freq = freq
        self.osmosdr_sink_0.set_center_freq(self.freq, 0)

    def get_ifgain(self):
        return self.ifgain

    def set_ifgain(self, ifgain):
        self.ifgain = ifgain
        self.osmosdr_sink_0.set_if_gain(self.ifgain, 0)

    def get_repeat(self):
        return self.repeat

    def set_repeat(self, repeat):
        self.repeat = repeat

    def get_rfgain(self):
        return self.rfgain

    def set_rfgain(self, rfgain):
        self.rfgain = rfgain
        self.osmosdr_sink_0.set_gain(self.rfgain, 0)

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.blocks_moving_average_xx_0.set_length_and_scale((int(self.samp_rate/self.baud_rate)), 0.9/(self.samp_rate/self.baud_rate))
        self.low_pass_filter_0.set_taps(firdes.low_pass(1, self.samp_rate, 3000, 300, window.WIN_HAMMING, 6.76))
        self.osmosdr_sink_0.set_sample_rate(self.samp_rate)



def argument_parser():
    description = 'Transmit ASK CTF Challenge'
    parser = ArgumentParser(description=description)
    parser.add_argument(
        "-a", "--antenna", dest="antenna", type=str, default='',
        help="Set Antenna [default=%(default)r]")
    parser.add_argument(
        "--baud-rate", dest="baud_rate", type=intx, default=2400,
        help="Set Baud Rate [default=%(default)r]")
    parser.add_argument(
        "-b", "--bbgain", dest="bbgain", type=eng_float, default=eng_notation.num_to_str(float(20)),
        help="Set Base Band Gain [default=%(default)r]")
    parser.add_argument(
        "-d", "--deviceargs", dest="deviceargs", type=str, default="file=/dev/null,freq=100e6,label='Complex Sampled (IQ) File',rate=1e6,throttle=false",
        help="Set Device String [default=%(default)r]")
    parser.add_argument(
        "-m", "--flag", dest="flag", type=str, default='RFHS',
        help="Set Flag [default=%(default)r]")
    parser.add_argument(
        "-f", "--freq", dest="freq", type=intx, default=146550000,
        help="Set Center Frequency [default=%(default)r]")
    parser.add_argument(
        "-i", "--ifgain", dest="ifgain", type=eng_float, default=eng_notation.num_to_str(float(20)),
        help="Set IF Gain [default=%(default)r]")
    parser.add_argument(
        "-r", "--repeat", dest="repeat", type=intx, default=10,
        help="Set Repeat [default=%(default)r]")
    parser.add_argument(
        "-g", "--rfgain", dest="rfgain", type=eng_float, default=eng_notation.num_to_str(float(32)),
        help="Set RF Gain [default=%(default)r]")
    parser.add_argument(
        "-s", "--samp-rate", dest="samp_rate", type=intx, default=2400000,
        help="Set Sample Rate [default=%(default)r]")
    return parser


def main(top_block_cls=ask_tx, options=None):
    if options is None:
        options = argument_parser().parse_args()
    tb = top_block_cls(antenna=options.antenna, baud_rate=options.baud_rate, bbgain=options.bbgain, deviceargs=options.deviceargs, flag=options.flag, freq=options.freq, ifgain=options.ifgain, repeat=options.repeat, rfgain=options.rfgain, samp_rate=options.samp_rate)

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
