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


def _noise(X, c):
    S = compute_covariance_matrix(X)
    return mvdr_weights(est.noise_loaded(S, X.shape[1]), c.a)


def _noise_derivative(X, c):
    S = compute_covariance_matrix(X)
    return lcmv_weights(est.noise_loaded(S, X.shape[1]), c.C, c.f)


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


METHODS = {
    "delay-and-sum": lambda X, c: das_weights(c.a),
    "sample": _sample,
    "relative 1e-2": _relative,
    "relative 1e-2 + derivative": _relative_derivative,
    "Phase 1 pipeline": _pipeline,
    "noise x10": _noise,
    "noise x10 + derivative": _noise_derivative,
    "Ledoit-Wolf": lambda X, c: mvdr_weights(est.ledoit_wolf(X), c.a),
    "OAS": lambda X, c: mvdr_weights(est.oas(X), c.a),
    "Toeplitz-FB": _toeplitz,
    "clipped": _clipped,
    "sign": _sign,
    "Tyler": lambda X, c: mvdr_weights(est.regularized_tyler(X), c.a),
    "eigenspace": _eigenspace,
    "reconstruction": _reconstruction,
}
