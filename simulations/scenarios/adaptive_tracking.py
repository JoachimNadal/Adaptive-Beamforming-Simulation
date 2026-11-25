"""Adaptation to a moving interferer.

Compares weights that are frozen, recomputed from independent blocks (SMI), recomputed from
an exponentially weighted covariance, or updated at every sample with RLS. Scoring uses
the true instantaneous scene, never the algorithm's own estimate.
"""

from dataclasses import dataclass, field

import numpy as np

from dsp.adaptive_weights import das_weights, mvdr_weights, rls_update
from dsp.covariance_matrix import RecursiveCovariance, compute_covariance_matrix, loading_level
from dsp.signal_metrics import optimal_sinr, output_sinr, scene_covariance, to_db
from simulations.channels.awgn import complex_noise, make_rng


@dataclass(frozen=True)
class TrackingConfig:
    wavelength: float = 12.5
    target_angle_deg: float = 10.0
    interferer_start_deg: float = -60.0
    interferer_stop_deg: float = -20.0
    target_power: float = 1.0
    interferer_power: float = 1000.0
    noise_power: float = 1.0
    num_blocks: int = 100
    block_size: int = 32
    relative_loading: float = 1e-3
    covariance_beta: float = 0.5
    rls_forgetting: float = 0.98


@dataclass
class TrackingResult:
    interferer_angle_deg: np.ndarray
    sinr_db: dict = field(default_factory=dict)
    optimum_db: np.ndarray = field(default_factory=lambda: np.empty(0))


def run_tracking(antenna_array, config=None, rng=None):
    """Return the SINR of every strategy at the **end** of each block.

    Block strategies are scored causally: weights computed from block ``b`` are applied to
    block ``b + 1``, as in a real pipeline. RLS is given a perfect pilot as reference.
    """
    config = config or TrackingConfig()
    rng = make_rng(rng)
    n = antenna_array.num_elements
    total = config.num_blocks * config.block_size
    angles = np.linspace(config.interferer_start_deg, config.interferer_stop_deg, total)
    a_target = antenna_array.compute_steering_vector(
        config.target_angle_deg, config.wavelength, "deg"
    )
    A_int = antenna_array.compute_steering_matrix(angles, config.wavelength, "deg")
    pilot = np.exp(0.5j * np.pi * rng.integers(0, 4, total))
    jammer = complex_noise(total, config.interferer_power, rng)
    X = np.outer(a_target, np.sqrt(config.target_power) * pilot) + A_int * jammer
    X = X + complex_noise((n, total), config.noise_power, rng)

    weights = {name: das_weights(a_target) for name in ("DAS", "frozen", "SMI", "recursive")}
    weights["RLS"] = das_weights(a_target)
    P = np.eye(n, dtype=complex)
    recursive = RecursiveCovariance(n, config.covariance_beta)
    sinr: dict[str, list[float]] = {name: [] for name in weights}
    optimum = []

    for b in range(config.num_blocks):
        block = slice(b * config.block_size, (b + 1) * config.block_size)
        Xb = X[:, block]
        for i in range(config.block_size):
            x = Xb[:, i]
            error = pilot[block][i] - np.vdot(weights["RLS"], x)
            weights["RLS"], P = rls_update(weights["RLS"], P, x, error, config.rls_forgetting)

        R_in = scene_covariance(
            A_int[:, block.stop - 1 : block.stop], [config.interferer_power], config.noise_power
        )
        for name, w in weights.items():
            sinr[name].append(to_db(output_sinr(w, a_target, config.target_power, R_in)))
        optimum.append(to_db(optimal_sinr(a_target, config.target_power, R_in)))

        R_block = compute_covariance_matrix(Xb)
        R_rec = recursive.update(Xb)
        loading = config.relative_loading
        if b == 0:
            weights["frozen"] = mvdr_weights(R_block, a_target, loading_level(R_block, loading))
        weights["SMI"] = mvdr_weights(R_block, a_target, loading_level(R_block, loading))
        weights["recursive"] = mvdr_weights(R_rec, a_target, loading_level(R_rec, loading))

    return TrackingResult(
        interferer_angle_deg=angles[config.block_size - 1 :: config.block_size],
        sinr_db={name: np.array(values) for name, values in sinr.items()},
        optimum_db=np.array(optimum),
    )
