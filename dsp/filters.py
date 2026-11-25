"""Channel-coherent FIR filtering.

All functions act along the last axis with the same coefficients for every channel.
This matters here: any difference between channels would be a phase error that the
beamformer interprets as a direction.
"""

import numpy as np

from dsp.fft import get_window


def fir_lowpass(num_taps, cutoff, sample_rate=1.0, window="hamming"):
    """Linear-phase windowed-sinc low-pass with unit DC gain."""
    if num_taps < 3 or num_taps % 2 == 0:
        raise ValueError("num_taps must be odd and >= 3 (integer group delay)")
    if not 0 < cutoff < sample_rate / 2:
        raise ValueError("cutoff must lie in (0, sample_rate / 2)")
    n = np.arange(num_taps) - (num_taps - 1) / 2
    fc = cutoff / sample_rate
    taps = 2 * fc * np.sinc(2 * fc * n) * get_window(window, num_taps, periodic=False)
    return taps / taps.sum()


def fir_filter(x, taps, compensate_delay=False):
    """Causal FIR; ``compensate_delay`` removes the linear-phase group delay instead."""
    x = np.asarray(x)
    y = np.apply_along_axis(np.convolve, -1, x, taps)
    start = (len(taps) - 1) // 2 if compensate_delay else 0
    return y[..., start : start + x.shape[-1]]


def decimate(x, factor, num_taps=None):
    """Anti-alias filter (cutoff at 0.8 of the new Nyquist) and keep 1 of ``factor``."""
    if factor < 1:
        raise ValueError("factor must be >= 1")
    if factor == 1:
        return np.asarray(x)
    num_taps = num_taps or 16 * factor + 1
    return fir_filter(x, fir_lowpass(num_taps, 0.4 / factor), True)[..., ::factor]


def frequency_shift(x, frequency, sample_rate=1.0):
    """Multiply by ``exp(j 2 pi frequency t)``."""
    n = np.arange(np.asarray(x).shape[-1])
    return x * np.exp(2j * np.pi * frequency / sample_rate * n)


def remove_dc(x):
    """Subtract the mean of each channel (direct-conversion receivers have a DC spur)."""
    return x - np.mean(x, axis=-1, keepdims=True)
