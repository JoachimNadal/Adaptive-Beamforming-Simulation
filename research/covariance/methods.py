"""Beamformers under comparison: every method maps snapshots to weights.

The look direction is broadside. ``Context`` holds what a real receiver would know: the
nominal manifold and the target direction, never the true scene.
"""

from dataclasses import replace

import numpy as np

from dsp.adaptive_weights import das_weights, lcmv_weights, mvdr_weights
from dsp.covariance_matrix import compute_covariance_matrix, loading_level
from embedded.common.config import PipelineConfig
from embedded.common.iq_frame import IQFrame
from embedded.common.pipeline import BeamformingPipeline
from examples.common import WAVELENGTH, reference_array
from research.covariance import estimators as est
from simulations.beamforming.lcmv import LCMVBeamformer
from simulations.doa.order_estimation import estimate_order_mdl

SECTOR_DEG = 10.0


class Context:
    def __init__(self, n):
        self.n = n
        self.array = reference_array(n)
        self.a = self.array.compute_steering_vector(0, WAVELENGTH, "deg")
        grid = np.arange(-90, 90.5, 1.0)
        self.G = self.array.compute_steering_matrix(
            grid[np.abs(grid) > SECTOR_DEG], WAVELENGTH, "deg"
        )
        lcmv = LCMVBeamformer(self.array, derivative_constraint=True)
        self.C, self.f = lcmv.constraints(0, [], WAVELENGTH, "deg")
        self.config = replace(PipelineConfig(), num_elements=n, covariance_beta=0.0)


def _sample(X, c):
    return mvdr_weights(compute_covariance_matrix(X), c.a)


def _relative(X, c):
    S = compute_covariance_matrix(X)
    return mvdr_weights(S, c.a, loading_level(S, 1e-2))


def noise_loaded_weights(X, c, factor=10.0, derivative=False):
    """MVDR (or LCMV with derivative constraint) with loading ``factor x`` estimated noise."""
    R = est.noise_loaded(compute_covariance_matrix(X), X.shape[1], factor)
    return lcmv_weights(R, c.C, c.f) if derivative else mvdr_weights(R, c.a)


def _noise(X, c):
    return noise_loaded_weights(X, c)


def _noise_derivative(X, c):
    return noise_loaded_weights(X, c, derivative=True)


def _relative_derivative(X, c):
    S = compute_covariance_matrix(X)
    return lcmv_weights(S, c.C, c.f, loading_level(S, 1e-2))


def _toeplitz(X, c):
    R = est.toeplitz_forward_backward(X)
    floor = est.noise_power(compute_covariance_matrix(X), X.shape[1])
    # averaging can make the matrix indefinite: restore a margin above the noise floor
    deficit = max(0.0, floor - np.linalg.eigvalsh(R)[0])
    return mvdr_weights(R + (deficit + 10 * floor) * np.eye(c.n), c.a)


def _clipped(X, c):
    return mvdr_weights(est.clipped(compute_covariance_matrix(X), X.shape[1]), c.a)


def _sign(X, c):
    R = est.sign_covariance(X)
    return mvdr_weights(R, c.a, loading_level(R, 1e-2))


def _reconstruction(X, c):
    S = compute_covariance_matrix(X)
    S = S + loading_level(S, 1e-9) * np.eye(c.n)
    R = est.reconstruction(S, c.G)
    return mvdr_weights(R, c.a, loading_level(R, 1e-9))


def _eigenspace(X, c):
    """Projection of the steering vector on the signal subspace (MDL order)."""
    S = compute_covariance_matrix(X)
    order = min(max(estimate_order_mdl(S, X.shape[1]), 1), c.n - 1)
    values, vectors = np.linalg.eigh(S)
    Us, ls = vectors[:, -order:], values[-order:]
    w = (Us / ls) @ (Us.conj().T @ c.a)
    return w / np.vdot(w, c.a).conj()


def _pipeline(X, c):
    """The frozen Phase 1 pipeline on one block, explicit nulls included."""
    pipeline = BeamformingPipeline(replace(c.config, block_size=max(X.shape[1], c.n)), np.ones(c.n))
    return pipeline.process(IQFrame(X, 0, 0, 1e6, c.config.carrier_hz)).weights


def _interference_subspace(S, snapshots, a):
    """Signal eigenvectors, minus the one that is mostly the target.

    An eigenvector is attributed to the target if more than half of its energy lies along the
    nominal steering vector.
    """
    n = S.shape[0]
    order = min(estimate_order_mdl(S, snapshots), n - 1)
    _, vectors = np.linalg.eigh(S)
    Q = vectors[:, n - order :]
    along = np.abs(Q.conj().T @ a) ** 2 / np.vdot(a, a).real
    return Q[:, along < 0.5]


def _eigencanceler(X, c):
    """Minimum-norm weights orthogonal to the measured interference subspace."""
    Q = _interference_subspace(compute_covariance_matrix(X), X.shape[1], c.a)
    w = c.a - Q @ (Q.conj().T @ c.a)
    return w / np.vdot(w, c.a).conj()


def _hybrid(X, c):
    """Eigenspace projection; eigencanceler when no noise subspace is left for it."""
    order = estimate_order_mdl(compute_covariance_matrix(X), X.shape[1])
    return _eigenspace(X, c) if order <= c.n - 2 else _eigencanceler(X, c)


def _reduced_rank_gsc(X, c):
    """Sidelobe canceller restricted to the principal components of the blocked data."""
    S = compute_covariance_matrix(X)
    # orthonormal basis of the space orthogonal to the target
    B = np.linalg.svd(c.a[:, None], full_matrices=True)[0][:, 1:]
    quiescent = c.a / c.n
    Sb = B.conj().T @ S @ B
    order = min(estimate_order_mdl(Sb, X.shape[1]), c.n - 2) if c.n > 2 else 1
    if order == 0:
        return quiescent
    values, vectors = np.linalg.eigh(Sb)
    U, power = vectors[:, -order:], values[-order:]
    adaptive = (U / power) @ (U.conj().T @ (B.conj().T @ (S @ quiescent)))
    return quiescent - B @ adaptive


class _NoiseLoadedPipeline(BeamformingPipeline):
    """Phase 1 pipeline with loading proportional to the noise (baseline file untouched)."""

    def _solve_lcmv(self, R, interferers, loading, result):
        snapshots = result.output.size * self._covariance.effective_blocks
        return super()._solve_lcmv(R, interferers, 10 * est.noise_power(R, snapshots), result)


def _pipeline_noise(X, c):
    pipeline = _NoiseLoadedPipeline(
        replace(c.config, block_size=max(X.shape[1], c.n)), np.ones(c.n)
    )
    return pipeline.process(IQFrame(X, 0, 0, 1e6, c.config.carrier_hz)).weights


METHODS = {
    "delay-and-sum": lambda X, c: das_weights(c.a),
    "sample": _sample,
    "relative 1e-2": _relative,
    "relative 1e-2 + derivative": _relative_derivative,
    "Phase 1 pipeline": _pipeline,
    "pipeline, noise loading": _pipeline_noise,
    "noise x10": _noise,
    "noise x10 + derivative": _noise_derivative,
    "Ledoit-Wolf": lambda X, c: mvdr_weights(est.ledoit_wolf(X), c.a),
    "OAS": lambda X, c: mvdr_weights(est.oas(X), c.a),
    "Toeplitz-FB": _toeplitz,
    "clipped": _clipped,
    "sign": _sign,
    "Tyler": lambda X, c: mvdr_weights(est.regularized_tyler(X), c.a),
    "eigenspace": _eigenspace,
    "eigencanceler": _eigencanceler,
    "hybrid": _hybrid,
    "reduced-rank GSC": _reduced_rank_gsc,
    "reconstruction": _reconstruction,
}
