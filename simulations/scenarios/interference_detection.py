"""Detection of spatially structured interference from array snapshots.

The statistic is the sphericity of the covariance eigenvalues: with spatially white noise
they are equal up to estimation error, while any source raises one of them. It needs no
noise-level calibration, so a common gain change does not cause false alarms. Uncalibrated
*per-channel* gains do, because they make the noise unequal between antennas.
"""

from dataclasses import dataclass

import numpy as np

from dsp.covariance_matrix import compute_covariance_matrix
from simulations.channels.awgn import complex_noise, make_rng
from simulations.doa.music import music_spectrum
from simulations.doa.order_estimation import estimate_order_mdl
from simulations.doa.peaks import find_spectrum_peaks


def eigenvalue_ratio(R):
    """Largest eigenvalue over the mean of the others (about 1 in white noise)."""
    eigenvalues = np.linalg.eigvalsh(R)
    return float(eigenvalues[-1] / max(np.mean(eigenvalues[:-1]), np.finfo(float).tiny))


def calibrate_threshold(num_antennas, num_snapshots, false_alarm_rate=1e-2, trials=4000, rng=None):
    """Monte-Carlo threshold of :func:`eigenvalue_ratio` for a false-alarm rate."""
    if trials * false_alarm_rate < 10:
        raise ValueError("too few trials to estimate this false-alarm rate")
    rng = make_rng(rng)
    ratios = [
        eigenvalue_ratio(
            compute_covariance_matrix(complex_noise((num_antennas, num_snapshots), 1.0, rng))
        )
        for _ in range(trials)
    ]
    return float(np.quantile(ratios, 1 - false_alarm_rate))


@dataclass(frozen=True)
class Detection:
    detected: bool
    statistic: float
    num_sources: int
    angles_deg: np.ndarray


class InterferenceDetector:
    """Detects sources, counts them (MDL) and locates them (MUSIC)."""

    def __init__(self, antenna_array, wavelength, num_snapshots, false_alarm_rate=1e-2, rng=None):
        self.angles_deg = np.arange(-90, 90.25, 0.25)
        self.A = antenna_array.compute_steering_matrix(self.angles_deg, wavelength, "deg")
        self.num_snapshots = num_snapshots
        self.threshold = calibrate_threshold(
            antenna_array.num_elements, num_snapshots, false_alarm_rate, rng=rng
        )

    def detect(self, X):
        if X.shape[1] != self.num_snapshots:
            raise ValueError(f"threshold calibrated for {self.num_snapshots} snapshots")
        R = compute_covariance_matrix(X)
        statistic = eigenvalue_ratio(R)
        if statistic <= self.threshold:
            return Detection(False, statistic, 0, np.empty(0))
        order = max(1, estimate_order_mdl(R, self.num_snapshots))
        spectrum = music_spectrum(R, self.A, order)
        return Detection(
            True, statistic, order, find_spectrum_peaks(self.angles_deg, spectrum, order)
        )
