"""Flat fading coefficients with unit mean power."""

import numpy as np

from simulations.channels.awgn import complex_noise, make_rng


def rayleigh_coefficients(shape, rng=None):
    """Independent Rayleigh coefficients (no line of sight)."""
    return complex_noise(shape, 1.0, rng)


def rician_coefficients(shape, k_factor, rng=None, los_phase=0.0):
    """Independent Rician coefficients; ``k_factor`` is the linear LOS/scatter power ratio."""
    if k_factor < 0:
        raise ValueError("k_factor must be non-negative")
    los = np.sqrt(k_factor / (k_factor + 1)) * np.exp(1j * los_phase)
    return los + np.sqrt(1 / (k_factor + 1)) * rayleigh_coefficients(shape, rng)


def doppler_fading(num_samples, normalized_doppler, rng=None, num_paths=64):
    """Time-correlated Rayleigh fading with the Clarke isotropic-scattering model.

    Sum of ``num_paths`` plane waves with uniformly distributed arrival angles, giving the
    autocorrelation ``J0(2 pi f_D tau)``. ``normalized_doppler`` is ``f_D / sample_rate``.
    """
    rng = make_rng(rng)
    n = np.arange(num_samples)
    # stratified angles: faster convergence to J0 than independent ones
    angles = 2 * np.pi * (np.arange(num_paths) + rng.random(num_paths)) / num_paths
    phases = 2 * np.pi * rng.random(num_paths)
    doppler = 2 * np.pi * normalized_doppler * np.cos(angles)
    return np.exp(1j * (np.outer(doppler, n) + phases[:, None])).sum(axis=0) / np.sqrt(num_paths)


def apply_flat_fading(x, coefficients):
    """Multiply a signal by fading coefficients broadcast along its last axis."""
    return np.asarray(x) * coefficients
