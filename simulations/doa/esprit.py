"""ESPRIT for uniform linear arrays (course chapter 16)."""

import numpy as np

from dsp.covariance_matrix import hermitian
from simulations.doa.music import phase_to_angle


def esprit(R, num_sources, d_over_lambda=0.5, tls=True):
    """LS- or TLS-ESPRIT. Returns sorted angles in radians.

    Uses the shift invariance between the first and last ``N - 1`` elements, so it needs a
    calibrated ULA but neither a scan grid nor a peak search.
    """
    n = R.shape[0]
    if num_sources == 0:
        return np.empty(0)
    if not 0 < num_sources < n:
        raise ValueError(f"num_sources must be in [0, {n - 1}], got {num_sources}")
    _, vectors = np.linalg.eigh(hermitian(R))
    Us = vectors[:, -num_sources:]
    upper, lower = Us[:-1], Us[1:]
    if tls:
        # full_matrices=True is required when 2L > N - 1: the null space is then part of V
        # (the course listing omits it and fails, see docs/theory/course_errata.md).
        _, _, Vh = np.linalg.svd(np.hstack((upper, lower)), full_matrices=True)
        V = Vh.conj().T
        V12, V22 = V[:num_sources, num_sources:], V[num_sources:, num_sources:]
        Psi = -np.linalg.solve(V22.T, V12.T).T
    else:
        Psi = np.linalg.lstsq(upper, lower, rcond=None)[0]
    return np.sort(phase_to_angle(np.linalg.eigvals(Psi), d_over_lambda))
