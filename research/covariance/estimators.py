"""Covariance estimators for adaptive beamforming.

All take snapshots ``X`` of shape ``(N, K)`` and return an ``N x N`` Hermitian matrix.
Definitions, derivations and references are in ``REPORT.md``.
"""

import numpy as np

from dsp.covariance_matrix import compute_covariance_matrix, forward_backward, hermitian
from simulations.doa.order_estimation import estimate_order_mdl


def _shrink(S, rho):
    n = S.shape[0]
    mu = np.trace(S).real / n
    return hermitian((1 - rho) * S + rho * mu * np.eye(n))


def ledoit_wolf_intensity(X):
    """Distribution-free shrinkage intensity (Ledoit and Wolf, 2004), complex data."""
    n, k = X.shape
    S = compute_covariance_matrix(X)
    mu = np.trace(S).real / n
    distance = np.linalg.norm(S - mu * np.eye(n)) ** 2
    if distance == 0:
        return 1.0
    # sum_k ||x x^H - S||^2 = sum ||x||^4 - k ||S||^2
    fourth = np.sum(np.sum(np.abs(X) ** 2, axis=0) ** 2)
    variance = (fourth - k * np.linalg.norm(S) ** 2) / k**2
    return float(np.clip(variance / distance, 0, 1))


def oas_intensity(S, num_snapshots):
    """Oracle approximating shrinkage, re-derived for complex Gaussian data.

    The published formula (Chen, Wiesel, Eldar, Hero, 2010) is for real data, where
    ``E tr(S^2) = (1 + 1/K) tr(R^2) + tr(R)^2 / K``. For circular complex data the factor of
    ``tr(R^2)`` is 1, which changes the coefficients (derivation in the report).
    """
    n, k = S.shape[0], num_snapshots
    t2 = np.linalg.norm(S) ** 2
    t1 = np.trace(S).real ** 2
    denominator = (k - 1 / n) * (t2 - t1 / n)
    if denominator <= 0:
        return 1.0
    return float(min((t1 - t2 / n) / denominator, 1.0))


def ledoit_wolf(X):
    return _shrink(compute_covariance_matrix(X), ledoit_wolf_intensity(X))


def oas(X):
    S = compute_covariance_matrix(X)
    return _shrink(S, oas_intensity(S, X.shape[1]))


def noise_power(S, num_snapshots):
    """Mean of the eigenvalues that MDL attributes to noise."""
    order = min(estimate_order_mdl(S, num_snapshots), S.shape[0] - 1)
    return float(np.mean(np.linalg.eigvalsh(S)[: S.shape[0] - order]))


def noise_loaded(S, num_snapshots, factor=10.0):
    """Loading proportional to the estimated noise instead of the total power."""
    return hermitian(S + factor * noise_power(S, num_snapshots) * np.eye(S.shape[0]))


def toeplitz(S):
    """Average along diagonals: the structure of uncorrelated sources on an ideal ULA."""
    n = S.shape[0]
    lags = np.array([np.mean(np.diagonal(S, -k)) for k in range(n)])
    index = np.subtract.outer(np.arange(n), np.arange(n))
    return hermitian(np.where(index >= 0, lags[np.abs(index)], lags[np.abs(index)].conj()))


def toeplitz_forward_backward(X):
    return toeplitz(forward_backward(compute_covariance_matrix(X)))


def clipped(S, num_snapshots):
    """Eigenvalues raised to the noise floor (fast maximum likelihood with estimated noise)."""
    values, vectors = np.linalg.eigh(hermitian(S))
    values = np.maximum(values, noise_power(S, num_snapshots))
    return hermitian((vectors * values) @ vectors.conj().T)


def sign_covariance(X):
    """Covariance of unit-norm snapshots, rescaled to the sample trace."""
    norms = np.maximum(np.linalg.norm(X, axis=0), np.finfo(float).tiny)
    R = compute_covariance_matrix(X / norms)
    return R * (np.mean(norms**2) / np.trace(R).real)


def regularized_tyler(X, rho=1e-2, iterations=50, tolerance=1e-6):
    """Regularised Tyler M-estimator, rescaled to the sample trace.

    Fixed point of ``(1 - rho) (N / K) sum x x^H / (x^H R^-1 x) + rho I`` with ``tr R = N``.
    Scale-free: each snapshot only contributes its direction.
    """
    n, k = X.shape
    R = np.eye(n, dtype=complex)
    for _ in range(iterations):
        quadratic = np.einsum("ik,ik->k", X.conj(), np.linalg.solve(R, X)).real
        weights = 1 / np.maximum(quadratic, np.finfo(float).tiny)
        update = (1 - rho) * (n / k) * (X * weights) @ X.conj().T + rho * np.eye(n)
        update = hermitian(update * (n / np.trace(update).real))
        done = np.linalg.norm(update - R) < tolerance * np.linalg.norm(R)
        R = update
        if done:
            break
    return R * (np.mean(np.sum(np.abs(X) ** 2, axis=0)) / n)


def reconstruction(S, steering_off_sector):
    """Interference-plus-noise covariance from the Capon spectrum (Gu and Leshem, 2012).

    ``steering_off_sector`` holds the steering vectors outside the target sector. The target
    itself is therefore absent from the result, which prevents self-cancellation.
    """
    G = steering_off_sector
    capon = 1 / np.einsum("ij,ij->j", G.conj(), np.linalg.solve(S, G)).real
    return hermitian((G * capon) @ G.conj().T)
