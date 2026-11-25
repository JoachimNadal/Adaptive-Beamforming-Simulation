"""Beamformer weights: closed-form solutions and recursive updates."""

import numpy as np

from dsp.covariance_matrix import hermitian

#: Systems worse conditioned than this are refused rather than silently solved.
MAX_CONDITION = 1e12


class IllConditionedError(np.linalg.LinAlgError):
    """The linear system has no numerically meaningful solution."""


def _checked(matrix, what):
    if not np.all(np.isfinite(matrix)):
        raise ValueError(f"{what} contains NaN or infinity")
    cond = np.linalg.cond(matrix)
    if not cond <= MAX_CONDITION:
        raise IllConditionedError(f"{what} is ill-conditioned (cond = {cond:.1e})")
    return matrix


def _check_constraints(C):
    if C.shape[1] > C.shape[0]:
        raise ValueError(f"{C.shape[1]} constraints exceed {C.shape[0]} antennas")


# --------------------------------------------------------------------- closed form


def das_weights(a):
    """Delay-and-sum weights with unit response toward steering vector ``a``."""
    return a / np.vdot(a, a).real


def mvdr_weights(R, a, loading=0.0):
    """MVDR/Capon weights ``(R + loading I)^-1 a / (a^H (R + loading I)^-1 a)``."""
    if loading < 0:
        raise ValueError("loading must be non-negative")
    Rl = _checked(hermitian(R + loading * np.eye(R.shape[0])), "covariance")
    u = np.linalg.solve(Rl, a)
    return u / np.vdot(a, u).real


def lcmv_weights(R, C, f, loading=0.0):
    """LCMV weights: minimise ``w^H R w`` subject to ``C^H w = f``.

    The response toward column ``c_i`` is ``w^H c_i = conj(f_i)``.
    """
    if loading < 0:
        raise ValueError("loading must be non-negative")
    _check_constraints(C)
    f = np.asarray(f, dtype=complex)
    Rl = _checked(hermitian(R + loading * np.eye(R.shape[0])), "covariance")
    RiC = np.linalg.solve(Rl, C)
    G = _checked(hermitian(C.conj().T @ RiC), "constraint matrix")
    return RiC @ np.linalg.solve(G, f)


def null_steering_weights(C, f, regularization=0.0):
    """Minimum-norm weights satisfying ``C^H w = f`` (exactly if regularization is 0)."""
    _check_constraints(C)
    f = np.asarray(f, dtype=complex)
    G = hermitian(C.conj().T @ C + regularization * np.eye(C.shape[1]))
    return C @ np.linalg.solve(_checked(G, "constraint matrix"), f)


# ----------------------------------------------------------------------- recursive


def lms_update(weights, input_vector, error, mu):
    """
    Perform one LMS weight update.

    Parameters
    ----------
    weights : np.ndarray
        Current complex weight vector.

    input_vector : np.ndarray
        Current received signal vector.

    error : complex
        Error between desired signal and beamformer output.

    mu : float
        LMS learning rate. Stable in the mean for ``0 < mu < 2 / lambda_max(R)``.

    Returns
    -------
    np.ndarray
        Updated weight vector.
    """

    return weights + mu * input_vector * np.conjugate(error)


def nlms_update(weights, input_vector, error, mu, eps=1e-9):
    """One NLMS update; stable for ``0 < mu < 2`` whatever the input power."""
    power = np.vdot(input_vector, input_vector).real
    return weights + (mu / (eps + power)) * input_vector * np.conjugate(error)


def rls_update(weights, P, input_vector, error, forgetting):
    """One RLS update of ``(weights, P)`` for the a-priori error ``error``.

    ``P`` must be re-symmetrised: with this ``u u^H`` form the anti-Hermitian round-off grows
    as ``1 / forgetting^n`` and the recursion diverges, even in white noise.

    RLS has no protection against loss of excitation: without input, ``P`` grows as
    ``1 / forgetting^n`` until it overflows. Freeze the recursion when the input vanishes.
    """
    u = P @ input_vector
    gain = u / (forgetting + np.vdot(input_vector, u).real)
    weights = weights + gain * np.conjugate(error)
    P = hermitian((P - np.outer(gain, u.conj())) / forgetting)
    return weights, P
