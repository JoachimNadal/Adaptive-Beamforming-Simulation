"""Cramer-Rao bound: the yardstick for the DOA estimators (course chapter 17)."""

import numpy as np

from dsp.covariance_matrix import hermitian


def crb_stochastic(A, D, source_covariance, noise_power, num_snapshots):
    """Stochastic CRB covariance of the angles, in rad^2.

    ``A`` are the steering vectors and ``D`` their derivatives per radian, both ``(N, L)``.
    Take the square root of the diagonal for standard deviations.
    """
    n, num_sources = A.shape
    if num_sources >= n:
        raise ValueError("needs fewer sources than antennas")
    R = hermitian(A @ source_covariance @ A.conj().T + noise_power * np.eye(n))
    projector = np.eye(n) - A @ np.linalg.solve(A.conj().T @ A, A.conj().T)
    M = D.conj().T @ projector @ D
    H = source_covariance @ A.conj().T @ np.linalg.solve(R, A @ source_covariance)
    fisher = 2 * num_snapshots / noise_power * np.real(M * H.T)
    return np.linalg.inv(fisher)
