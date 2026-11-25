"""Sparse geometries, difference coarrays, coarray DOA and the matching Cramer-Rao bound.

Positions are integers in units of half a wavelength.
"""

import numpy as np

from dsp.covariance_matrix import hermitian
from examples.common import WAVELENGTH
from simulations.antenna_array.base import AntennaArray
from simulations.doa.music import root_music

GEOMETRIES = {
    "ULA-4": (0, 1, 2, 3),
    "nested-4": (0, 1, 2, 5),
    "MRA-4": (0, 1, 4, 6),
    "coprime-4": (0, 2, 3, 4),
    "ULA-8": tuple(range(8)),
    "nested-8": (0, 1, 2, 3, 4, 9, 14, 19),
    "MRA-8": (0, 1, 4, 10, 16, 18, 21, 23),
    "ULA-7 (aperture of MRA-4)": tuple(range(7)),
}


def make_array(positions):
    x = np.asarray(positions, float) * WAVELENGTH / 2
    return AntennaArray(np.column_stack((x, np.zeros(len(x)))))


def steering(positions, thetas_rad):
    return np.exp(-1j * np.pi * np.outer(positions, np.sin(np.atleast_1d(thetas_rad))))


def coarray(positions):
    """Weight function: how many element pairs are ``lag`` apart, for lag = 0 .. aperture."""
    d = np.subtract.outer(positions, positions)
    return np.array([np.sum(d == lag) for lag in range(int(np.max(d)) + 1)])


def contiguous(positions):
    """Largest M such that all lags 0 .. M exist: M sources at most are identifiable."""
    weights = coarray(positions)
    holes = np.flatnonzero(weights == 0)
    return int(holes[0] - 1) if holes.size else len(weights) - 1


def virtual_covariance(R, positions):
    """Toeplitz matrix of the virtual uniform array built from averaged lags."""
    positions = np.asarray(positions)
    d = np.subtract.outer(positions, positions)
    m = contiguous(positions)
    lags = np.array([np.mean(R[d == lag]) for lag in range(m + 1)])
    index = np.subtract.outer(np.arange(m + 1), np.arange(m + 1))
    return hermitian(np.where(index >= 0, lags[np.abs(index)], lags[np.abs(index)].conj()))


def coarray_music(R, positions, num_sources):
    """Root-MUSIC on the virtual array; angles in degrees, sorted."""
    return np.degrees(root_music(virtual_covariance(R, positions), num_sources))


def ambiguity(positions, u):
    """|a(0)^H a(u)| / N against the difference of sines ``u``: the beam pattern of the array."""
    return np.abs(np.exp(-1j * np.pi * np.outer(u, positions)).mean(axis=1))


def crb(positions, thetas_rad, powers, noise, snapshots):
    """Cramer-Rao bound of the angles for uncorrelated sources (rad^2, diagonal).

    Gaussian model with unknown angles, powers and noise. The Fisher information is
    ``K vec(dR_i)^H (R^-T kron R^-1) vec(dR_j)``, valid with more sources than antennas as long
    as it is invertible, which the structure of the coarray decides.
    """
    positions = np.asarray(positions, float)
    thetas = np.asarray(thetas_rad, float)
    A = steering(positions, thetas)
    D = -1j * np.pi * positions[:, None] * np.cos(thetas) * A
    R = (A * powers) @ A.conj().T + noise * np.eye(len(positions))
    Ri = np.linalg.inv(R)
    derivatives = []
    for i, p in enumerate(powers):
        block = p * np.outer(D[:, i], A[:, i].conj())
        derivatives.append(block + block.conj().T)
    derivatives += [np.outer(A[:, i], A[:, i].conj()) for i in range(len(powers))]
    derivatives.append(np.eye(len(positions)))
    products = [Ri @ d for d in derivatives]
    fisher = snapshots * np.array([[np.trace(a @ b).real for b in products] for a in products])
    scale = 1 / np.sqrt(np.diag(fisher))
    normalised = fisher * np.outer(scale, scale)
    if np.linalg.cond(normalised) > 1e10:
        return np.full(len(thetas), np.nan)
    return np.diag(np.linalg.inv(normalised) * np.outer(scale, scale))[: len(thetas)]
