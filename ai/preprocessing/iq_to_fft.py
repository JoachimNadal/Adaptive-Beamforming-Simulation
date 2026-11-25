"""One-dimensional spectral features."""

import numpy as np

from ai.preprocessing.normalization import unit_power
from dsp.fft import power_spectral_density
from dsp.signal_metrics import to_db


def iq_to_log_spectrum(iq, nfft=256):
    """Level-independent Welch spectrum in dB, ``(..., nfft)``, centred in frequency."""
    _, psd = power_spectral_density(unit_power(np.asarray(iq)), 1.0, nfft)
    return to_db(psd)
