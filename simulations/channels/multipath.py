"""Specular multipath: delayed copies of one signal arriving from several directions.

Copies of the same waveform are *coherent*. If their delay spread is short compared with
the inverse bandwidth, the source covariance stays rank 1 and MVDR/MUSIC fail unless
spatial smoothing is used.
"""

from dataclasses import dataclass

import numpy as np

from dsp.steering import to_radians


@dataclass(frozen=True)
class Path:
    """One arrival: direction in degrees, delay in samples, complex amplitude."""

    angle_deg: float
    delay_samples: float = 0.0
    gain: complex = 1.0


def fractional_delay(x, delay_samples):
    """Circularly delay a signal by a possibly fractional number of samples (FFT method)."""
    f = np.fft.fftfreq(len(x))
    return np.fft.ifft(np.fft.fft(x) * np.exp(-2j * np.pi * f * delay_samples))


def multipath_snapshots(antenna_array, wavelength, signal, paths):
    """Noise-free snapshots ``(N, len(signal))`` of ``signal`` received over ``paths``."""
    if not paths:
        raise ValueError("at least one path is required")
    X = np.zeros((antenna_array.num_elements, len(signal)), dtype=complex)
    for path in paths:
        a = antenna_array.compute_steering_vector(to_radians(path.angle_deg, "deg"), wavelength)
        X += np.outer(a, path.gain * fractional_delay(signal, path.delay_samples))
    return X
