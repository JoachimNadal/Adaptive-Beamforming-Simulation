"""Per-channel gain/phase calibration (course chapter 22).

Model: ``x_measured = diag(g) x_ideal``, with ``g[0] = 1`` by convention since a common
complex factor is unobservable and irrelevant to beamforming.
"""

import numpy as np

from dsp.covariance_matrix import compute_covariance_matrix


def estimate_calibration(X, a_reference):
    """Channel gains from one dominant source of known direction.

    Uses the principal eigenvector of the covariance (course 22.2.3), so the reference may
    carry any modulation. The snapshot-mean method of course listing 22.1 only works for
    an unmodulated source at exactly 0 Hz.
    """
    _, vectors = np.linalg.eigh(compute_covariance_matrix(X))
    g = vectors[:, -1] / a_reference
    if abs(g[0]) < 1e-9 * np.max(np.abs(g)):
        raise ValueError("reference channel 0 carries no signal")
    return g / g[0]


def apply_calibration(X, g):
    """Correct measured snapshots: ``diag(1/g) X``."""
    g = np.asarray(g)
    if np.any(np.abs(g) < 1e-9):
        raise ValueError("calibration contains a dead channel (zero gain)")
    return X / g[:, None]


def calibration_residual(g_estimated, g_true):
    """RMS residual ``(gain error in dB, phase error in degrees)`` after correction."""
    r = np.asarray(g_true) / np.asarray(g_estimated)
    r = r * np.exp(-1j * np.angle(np.mean(r))) / np.mean(np.abs(r))
    gain_db = 20 * np.log10(np.abs(r))
    phase_deg = np.degrees(np.angle(r))
    return float(np.sqrt(np.mean(gain_db**2))), float(np.sqrt(np.mean(phase_deg**2)))
