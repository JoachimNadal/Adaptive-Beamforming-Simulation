"""Beamscan DOA spectra: Bartlett (conventional) and Capon (minimum variance)."""

import numpy as np

from dsp.adaptive_weights import _checked
from dsp.covariance_matrix import hermitian, loading_level


def bartlett_spectrum(R, A):
    """Conventional spatial spectrum ``a^H R a / N^2``, an unbiased power at the peak.

    ``A`` holds the steering vectors of the scan grid as columns.
    """
    n = A.shape[0]
    return np.einsum("ij,ij->j", A.conj(), R @ A).real / n**2


def capon_spectrum(R, A, relative_loading=0.0):
    """Capon spectrum ``1 / (a^H R^-1 a)``: output power of an MVDR beam per direction."""
    Rl = hermitian(R + loading_level(R, relative_loading) * np.eye(R.shape[0]))
    RiA = np.linalg.solve(_checked(Rl, "covariance"), A)
    return 1.0 / np.einsum("ij,ij->j", A.conj(), RiA).real
