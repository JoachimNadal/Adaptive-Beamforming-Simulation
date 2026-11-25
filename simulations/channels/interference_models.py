"""Baseband waveforms used to test receivers against interference.

These are numerical models for receive-side simulation only. All have unit mean power, so
callers set the level explicitly. Frequencies are normalised to the sample rate.
"""

import numpy as np

from dsp.filters import fir_filter, fir_lowpass
from simulations.channels.awgn import complex_noise, make_rng


def unit_power(x):
    """Scale to unit mean power."""
    return x / np.sqrt(np.mean(np.abs(x) ** 2))


def cw_tone(num_samples, frequency=0.0, rng=None):
    """Continuous wave with random initial phase."""
    phase = 2 * np.pi * make_rng(rng).random()
    return np.exp(1j * (2 * np.pi * frequency * np.arange(num_samples) + phase))


def linear_chirp(num_samples, start_frequency=-0.3, stop_frequency=0.3, period=None, rng=None):
    """Repeating linear frequency sweep of ``period`` samples, with continuous phase."""
    period = period or num_samples
    u = (np.arange(num_samples) % period) / period
    frequency = start_frequency + (stop_frequency - start_frequency) * u
    phase = 2 * np.pi * (np.cumsum(frequency) + make_rng(rng).random())
    return np.exp(1j * phase)


def qpsk(num_samples, samples_per_symbol=8, frequency=0.0, rng=None):
    """Rectangular-pulse QPSK at a carrier offset."""
    rng = make_rng(rng)
    symbols = np.exp(1j * (np.pi / 4 + np.pi / 2 * rng.integers(0, 4, num_samples)))
    baseband = np.repeat(symbols[: -(-num_samples // samples_per_symbol)], samples_per_symbol)
    n = np.arange(num_samples)
    return baseband[:num_samples] * np.exp(2j * np.pi * frequency * n)


def band_limited_noise(num_samples, bandwidth=0.25, frequency=0.0, rng=None, num_taps=65):
    """Gaussian noise occupying ``bandwidth`` (two-sided, normalised) around ``frequency``."""
    if not 0 < bandwidth < 1:
        raise ValueError("bandwidth must be in (0, 1)")
    noise = complex_noise(num_samples + num_taps, 1.0, rng)
    shaped = fir_filter(noise, fir_lowpass(num_taps, bandwidth / 2))[num_taps:]
    return unit_power(shaped * np.exp(2j * np.pi * frequency * np.arange(num_samples)))


def pulsed(num_samples, pulse_length=32, period=128, frequency=0.0, rng=None):
    """Periodic on/off tone with a random start offset; unit *mean* power."""
    if not 0 < pulse_length <= period:
        raise ValueError("need 0 < pulse_length <= period")
    rng = make_rng(rng)
    gate = (np.arange(num_samples) + rng.integers(0, period)) % period < pulse_length
    x = gate * cw_tone(num_samples, frequency, rng)
    return unit_power(x) if gate.any() else x
