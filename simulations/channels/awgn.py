"""Circular complex Gaussian noise.

Every generator of the project draws its noise here so that "noise power" means the same
thing everywhere: ``E|n|^2``, split equally between the real and imaginary parts.
"""

import numpy as np

from dsp.signal_metrics import from_db, signal_power


def make_rng(rng=None):
    """Accept ``None``, an integer seed or a ``numpy.random.Generator``."""
    return np.random.default_rng(rng)


def complex_noise(shape, power, rng=None):
    """Circular complex Gaussian samples with ``E|n|^2 = power``."""
    if power < 0:
        raise ValueError("power must be non-negative")
    rng = make_rng(rng)
    return np.sqrt(power / 2) * (rng.standard_normal(shape) + 1j * rng.standard_normal(shape))


def awgn(x, snr_db, rng=None):
    """Add white noise at ``snr_db`` relative to the measured power of ``x``."""
    x = np.asarray(x)
    return x + complex_noise(x.shape, signal_power(x) / from_db(snr_db), rng)
