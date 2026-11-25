"""MUSIC and root-MUSIC (course chapter 15)."""

import numpy as np

from dsp.covariance_matrix import hermitian


def noise_subspace(R, num_sources):
    """Eigenvectors of the ``N - num_sources`` smallest eigenvalues."""
    n = R.shape[0]
    if not 0 <= num_sources < n:
        raise ValueError(f"num_sources must be in [0, {n - 1}], got {num_sources}")
    _, vectors = np.linalg.eigh(hermitian(R))
    return vectors[:, : n - num_sources]


def music_spectrum(R, A, num_sources):
    """MUSIC pseudo-spectrum ``N / |U_n^H a|^2`` on the scan grid ``A``.

    It is not a power spectrum: peak heights say nothing about source levels.
    """
    Un = noise_subspace(R, num_sources)
    projection = np.sum(np.abs(Un.conj().T @ A) ** 2, axis=0)
    return A.shape[0] / np.maximum(projection, np.finfo(float).eps)


def root_music(R, num_sources, d_over_lambda=0.5):
    """Grid-free MUSIC for a ULA. Returns sorted angles in radians.

    Finds the roots of ``a(1/z)^T U_n U_n^H a(z)`` nearest the unit circle, with
    ``z = exp(-j k d sin(theta))``.
    """
    n = R.shape[0]
    if num_sources == 0:
        return np.empty(0)
    Un = noise_subspace(R, num_sources)
    C = Un @ Un.conj().T
    # highest power of z first
    coefficients = [np.trace(C, offset=lag) for lag in range(n - 1, -n, -1)]
    roots = np.roots(coefficients)
    # roots come in conjugate-reciprocal pairs: keep one per pair, the inner one
    inner = roots[np.argsort(np.abs(roots))][: n - 1]
    selected = inner[np.argsort(1 - np.abs(inner))][:num_sources]
    return np.sort(phase_to_angle(selected, d_over_lambda))


def phase_to_angle(z, d_over_lambda):
    """Angles from ``z = exp(-j 2 pi (d / lambda) sin(theta))``."""
    sine = -np.angle(z) / (2 * np.pi * d_over_lambda)
    return np.arcsin(np.clip(sine, -1.0, 1.0))
