"""Time-frequency features."""

import numpy as np

from ai.preprocessing.normalization import standardize, unit_power
from dsp.fft import stft
from dsp.signal_metrics import to_db

NFFT, HOP = 64, 16


def spectrogram_db(iq, nfft=NFFT, hop=HOP):
    """Log-power spectrogram ``(..., frames, nfft)`` of unit-power IQ."""
    power = np.abs(stft(unit_power(np.asarray(iq)), nfft, hop)) ** 2
    return to_db(power + 1e-6)  # the floor bounds the log of empty bins


def classifier_input(iq):
    """Standardised spectrogram, the exact input of the CNN (training and inference)."""
    return standardize(spectrogram_db(iq)).astype(np.float32)
