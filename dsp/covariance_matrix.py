"""Spatial covariance estimation and conditioning (course chapter 9)."""

import numpy as np


def hermitian(R):
    """Return the Hermitian part of a square matrix."""
    return 0.5 * (R + R.conj().T)


def compute_covariance_matrix(X):
    """Sample covariance ``X X^H / K`` of a ``(num_antennas, num_snapshots)`` matrix."""
    X = np.asarray(X)
    if X.ndim != 2:
        raise ValueError("X must have shape (num_antennas, num_snapshots)")
    num_snapshots = X.shape[1]
    if num_snapshots == 0:
        raise ValueError("X contains no snapshot")
    return hermitian((X @ X.conj().T) / num_snapshots)


def diagonal_loading(R, alpha):
    """Return ``R + alpha I``."""
    if alpha < 0:
        raise ValueError("alpha must be non-negative")
    return hermitian(R + alpha * np.eye(R.shape[0]))


def loading_level(R, relative):
    """Absolute loading for a level given relative to the mean eigenvalue ``tr(R)/N``."""
    return relative * np.trace(R).real / R.shape[0]


def forward_backward(R):
    """Forward-backward average; valid for centro-symmetric arrays such as a ULA."""
    return hermitian(0.5 * (R + R[::-1, ::-1].conj()))


def spatial_smoothing(R, subarray_size, use_forward_backward=True):
    """Average the covariances of overlapping ULA subarrays.

    Restores the rank lost with coherent sources, at the cost of aperture: the result is
    a ``subarray_size`` square matrix. ``N - subarray_size + 1`` subarrays decorrelate as
    many coherent sources, and forward-backward averaging up to twice as many.
    """
    n = R.shape[0]
    if not 1 < subarray_size <= n:
        raise ValueError("subarray_size must be in [2, N]")
    starts = range(n - subarray_size + 1)
    Rs = np.mean([R[i : i + subarray_size, i : i + subarray_size] for i in starts], axis=0)
    return forward_backward(Rs) if use_forward_backward else hermitian(Rs)


class RecursiveCovariance:
    """Exponentially weighted covariance ``R <- beta R + (1 - beta) R_block``.

    The estimate is bias-corrected, so the first update equals the first block covariance.
    """

    def __init__(self, num_antennas, beta=0.9):
        if not 0 <= beta < 1:
            raise ValueError("beta must be in [0, 1)")
        self.num_antennas = num_antennas
        self.beta = beta
        self.reset()

    def reset(self):
        self._sum = np.zeros((self.num_antennas, self.num_antennas), dtype=complex)
        self._weight = 0.0

    def update(self, X):
        R = compute_covariance_matrix(X)
        if R.shape[0] != self.num_antennas:
            raise ValueError(f"expected {self.num_antennas} antennas, got {R.shape[0]}")
        self._sum = self.beta * self._sum + (1 - self.beta) * R
        self._weight = self.beta * self._weight + (1 - self.beta)
        return self.value

    @property
    def value(self):
        if self._weight == 0:
            raise RuntimeError("no data: call update() first")
        return hermitian(self._sum / self._weight)
