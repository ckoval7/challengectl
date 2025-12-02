#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: CW Transmit
# Author: corey
# Copyright: RFHS
# Description: Transmit Morse Code for CW Challenge
# GNU Radio version: 3.10.1.1

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




class cw_tx(gr.top_block):

    def __init__(self, antenna='', bbgain=20, deviceargs="file=/dev/null,freq=100e6,label='Complex Sampled (IQ) File',rate=1e6,throttle=false", flag='RFHS', freq=146550000, ifgain=20, rfgain=32, samp_rate=2400000, speed=15):
        gr.top_block.__init__(self, "CW Transmit", catch_exceptions=True)

        ##################################################
        # Parameters
        ##################################################
        self.antenna = antenna
        self.bbgain = bbgain
        self.deviceargs = deviceargs
        self.flag = flag
        self.freq = freq
        self.ifgain = ifgain
        self.rfgain = rfgain
        self.samp_rate = samp_rate
        self.speed = speed

        ##################################################
        # Variables
        ##################################################
        self.cw_samp_rate = cw_samp_rate = int(samp_rate/100)

        ##################################################
        # Blocks
        ##################################################
        self.rfhs_cw_source_0 = rfhs.cw_source(flag, 15, cw_samp_rate)
        self.rational_resampler_xxx_0 = filter.rational_resampler_fcc(
                interpolation=samp_rate,
                decimation=cw_samp_rate,
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
        self.blocks_moving_average_xx_0 = blocks.moving_average_ff(int(1.2/speed*cw_samp_rate/2), 1/(1.2/speed*cw_samp_rate/2), 4000, 1)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.blocks_moving_average_xx_0, 0), (self.rational_resampler_xxx_0, 0))
        self.connect((self.rational_resampler_xxx_0, 0), (self.osmosdr_sink_0, 0))
        self.connect((self.rfhs_cw_source_0, 0), (self.blocks_moving_average_xx_0, 0))


    def get_antenna(self):
        return self.antenna

    def set_antenna(self, antenna):
        self.antenna = antenna
        self.osmosdr_sink_0.set_antenna(self.antenna, 0)

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

    def get_rfgain(self):
        return self.rfgain

    def set_rfgain(self, rfgain):
        self.rfgain = rfgain
        self.osmosdr_sink_0.set_gain(self.rfgain, 0)

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.set_cw_samp_rate(int(self.samp_rate/100))
        self.osmosdr_sink_0.set_sample_rate(self.samp_rate)

    def get_speed(self):
        return self.speed

    def set_speed(self, speed):
        self.speed = speed
        self.blocks_moving_average_xx_0.set_length_and_scale(int(1.2/self.speed*self.cw_samp_rate/2), 1/(1.2/self.speed*self.cw_samp_rate/2))

    def get_cw_samp_rate(self):
        return self.cw_samp_rate

    def set_cw_samp_rate(self, cw_samp_rate):
        self.cw_samp_rate = cw_samp_rate
        self.blocks_moving_average_xx_0.set_length_and_scale(int(1.2/self.speed*self.cw_samp_rate/2), 1/(1.2/self.speed*self.cw_samp_rate/2))



def argument_parser():
    description = 'Transmit Morse Code for CW Challenge'
    parser = ArgumentParser(description=description)
    parser.add_argument(
        "-a", "--antenna", dest="antenna", type=str, default='',
        help="Set Antenna [default=%(default)r]")
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
        "-g", "--rfgain", dest="rfgain", type=eng_float, default=eng_notation.num_to_str(float(32)),
        help="Set RF Gain [default=%(default)r]")
    parser.add_argument(
        "-s", "--samp-rate", dest="samp_rate", type=intx, default=2400000,
        help="Set Sample Rate [default=%(default)r]")
    parser.add_argument(
        "-w", "--speed", dest="speed", type=intx, default=15,
        help="Set Speed WPM [default=%(default)r]")
    return parser


def main(top_block_cls=cw_tx, options=None):
    if options is None:
        options = argument_parser().parse_args()
    tb = top_block_cls(antenna=options.antenna, bbgain=options.bbgain, deviceargs=options.deviceargs, flag=options.flag, freq=options.freq, ifgain=options.ifgain, rfgain=options.rfgain, samp_rate=options.samp_rate, speed=options.speed)

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
