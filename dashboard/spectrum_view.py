"""Power spectrum panel."""

import numpy as np

from dsp.fft import power_spectral_density
from dsp.signal_metrics import to_db
from simulations.plot_style import SERIES


class SpectrumPanel:
    """PSD of one antenna against the beamformer output.

    With unit-gain weights the difference is what the beamformer removed.
    """

    def __init__(self, ax, sample_rate_hz, nfft=64):
        self.ax, self.sample_rate_hz, self.nfft = ax, sample_rate_hz, nfft
        (self.antenna,) = ax.plot([], [], color=SERIES[0], label="antenna 0")
        (self.output,) = ax.plot([], [], color=SERIES[1], label="beamformer output")
        ax.set(xlabel="Frequency (kHz)", ylabel="PSD (dB/Hz)", title="Spectrum")
        ax.legend(loc="upper right")

    def update(self, antenna, output):
        levels = []
        for line, x in ((self.antenna, antenna), (self.output, output)):
            f, psd = power_spectral_density(x, self.sample_rate_hz, self.nfft)
            line.set_data(f / 1e3, to_db(np.maximum(psd, 1e-30)))
            levels.append(line.get_ydata())
        self.ax.set_xlim(f[0] / 1e3, f[-1] / 1e3)
        self.ax.set_ylim(np.min(levels) - 3, np.max(levels) + 8)
