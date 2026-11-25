"""Phase 2 feasibility probes: small simulations used to rank research directions.

    python research/feasibility_probes.py            # A to D
    python research/feasibility_probes.py novelty    # E, needs PyTorch and results/ai/model.pt

They use the Phase 1 code without modifying it. Simulation only; a probe is not a study.
"""

import sys

import numpy as np

from dsp.adaptive_weights import lcmv_weights, mvdr_weights, null_steering_weights
from dsp.covariance_matrix import compute_covariance_matrix, loading_level
from dsp.signal_metrics import (
    half_power_beamwidth,
    null_depth_db,
    optimal_sinr,
    output_sinr,
    peak_sidelobe_db,
    scene_covariance,
    to_db,
)
from examples.common import WAVELENGTH, reference_array
from simulations.antenna_array.base import AntennaArray
from simulations.beamforming.lcmv import LCMVBeamformer
from simulations.doa.music import root_music
from simulations.scenarios.array_snapshots import simulate_array_snapshots


def reconstructed_covariance(R, array, sector_deg=10):
    """Interference-plus-noise covariance from the Capon spectrum off the target sector."""
    grid = np.arange(-90, 90.5, 1.0)
    G = array.compute_steering_matrix(grid[np.abs(grid) > sector_deg], WAVELENGTH, "deg")
    capon = 1 / np.einsum("ij,ij->j", G.conj(), np.linalg.solve(R, G)).real
    return (G * capon) @ G.conj().T


def probe_loading(trials=150):
    print("A. SINR loss (dB) of loading strategies, K=256, target in the data")
    for n in (4, 8):
        array = reference_array(n)
        a = array.compute_steering_vector(0, WAVELENGTH, "deg")
        C, f = LCMVBeamformer(array, derivative_constraint=True).constraints(0, [], WAVELENGTH)
        for error, snr in ((0, 1.0), (2, 10.0)):
            for inr in (20, 40, 60):
                power = 10 ** (inr / 10)
                true = array.compute_steering_matrix([error, -25], WAVELENGTH, "deg")
                R_in = scene_covariance(true[:, 1:], [power], 1.0)
                best = optimal_sinr(true[:, 0], snr, R_in)
                ratios: dict[str, list[float]] = {}
                for seed in range(trials):
                    X = simulate_array_snapshots(
                        array, WAVELENGTH, [error, -25], [snr, power], 256, rng=seed
                    ).X
                    R = compute_covariance_matrix(X)
                    noise = np.mean(np.linalg.eigvalsh(R)[: n - 2])
                    relative = loading_level(R, 1e-2)
                    Rr = reconstructed_covariance(R, array)
                    for name, w in (
                        ("MVDR 1e-2", mvdr_weights(R, a, relative)),
                        ("MVDR 10 noise", mvdr_weights(R, a, 10 * noise)),
                        ("LCMV 1e-2", lcmv_weights(R, C, f, relative)),
                        ("LCMV 10 noise", lcmv_weights(R, C, f, 10 * noise)),
                        ("reconstruction", mvdr_weights(Rr, a, 1e-9 * np.trace(Rr).real)),
                    ):
                        sinr = output_sinr(w, true[:, 0], snr, R_in)
                        ratios.setdefault(name, []).append(sinr / best)
                text = ", ".join(f"{k} {-to_db(np.mean(v)):.2f}" for k, v in ratios.items())
                print(f"   N={n} error={error} deg SNR={to_db(snr):.0f} INR={inr}: {text}")


def probe_fixed_point(trials=300):
    print("B. median null depth (dB) with quantised weights, interferer in -60 to -20 deg")
    rng = np.random.default_rng(0)
    for bits in (6, 8, 10, 12, 14, 16):
        row = []
        for n in (4, 8):
            depths = []
            for _ in range(trials):
                C = reference_array(n).compute_steering_matrix(
                    [0, rng.uniform(-60, -20)], WAVELENGTH, "deg"
                )
                w = null_steering_weights(C, [1, 0])
                scale = np.abs(np.concatenate((w.real, w.imag))).max()
                step = scale * 2.0 ** (1 - bits)
                wq = step * (np.round(w.real / step) + 1j * np.round(w.imag / step))
                depths.append(null_depth_db(wq, C[:, 0], C[:, 1]))
            row.append(f"N={n} {np.median(depths):.1f}")
        print(f"   {bits} bits: {', '.join(row)}")


def probe_sparse(trials=50):
    print("C. 4-element minimum redundancy array (0, 1, 4, 6), five sources, K=4000, 10 dB")
    index = np.array([0, 1, 4, 6])
    array = AntennaArray(np.column_stack((index * WAVELENGTH / 2, np.zeros(4))))
    truth = np.array([-50.0, -25.0, 0.0, 25.0, 50.0])
    resolved, errors = 0, []
    for seed in range(trials):
        X = simulate_array_snapshots(array, WAVELENGTH, truth, [10.0] * 5, 4000, rng=seed).X
        R = compute_covariance_matrix(X)
        # lag k of the virtual array: average of R over element pairs that are k apart
        difference = np.subtract.outer(index, index)
        lags = np.array([np.mean(R[difference == k]) for k in range(index[-1] + 1)])
        virtual = np.subtract.outer(np.arange(len(lags)), np.arange(len(lags)))
        T = np.where(virtual >= 0, lags[np.abs(virtual)], lags[np.abs(virtual)].conj())
        estimate = np.degrees(root_music(T, 5))
        if np.max(np.abs(estimate - truth)) < 3:
            resolved += 1
            errors.append(estimate - truth)
    angles = np.arange(-90, 90.05, 0.05)
    gain = np.abs(array.compute_steering_matrix(angles, WAVELENGTH, "deg").mean(axis=0)) ** 2
    print(f"   resolved {resolved}/{trials}, RMSE {np.sqrt(np.mean(np.square(errors))):.2f} deg")
    print(
        f"   beamwidth {half_power_beamwidth(angles, gain):.1f} deg, "
        f"sidelobe {peak_sidelobe_db(gain):.1f} dB (uniform array: 26.3 deg, -11.3 dB)"
    )


def probe_wideband():
    print("D. optimum SINR (dB), target broadside, 30 dB interferers over a 10 % band")
    offsets = np.linspace(-0.05, 0.05, 64)
    for n, interferers in ((4, (-50,)), (4, (-50, 40)), (8, (-50,)), (8, (-50, 40, 70))):
        path = np.arange(n) * 0.5
        row = []
        for subbands in (1, 4, 16, 64):
            values = []
            for band in np.array_split(offsets, subbands):
                R = np.eye(n, dtype=complex)
                for offset in band:
                    for angle in interferers:
                        delay = path * (1 + offset) * np.sin(np.radians(angle))
                        v = np.exp(-2j * np.pi * delay)
                        R += 1000 / len(band) * np.outer(v, v.conj())
                values.append(to_db(optimal_sinr(np.ones(n, dtype=complex), 1.0, R)))
            row.append(f"{subbands} subbands {np.mean(values):.2f}")
        print(f"   N={n}, interferers {interferers}: {', '.join(row)}")


def probe_novelty(checkpoint="results/ai/model.pt"):
    import torch

    from ai.datasets.generator import CLASSES, generate_dataset
    from ai.preprocessing.spectrograms import classifier_input
    from ai.training.evaluate import load_model, unseen_waveforms

    model = load_model(checkpoint)

    def embed(iq):
        z = torch.from_numpy(classifier_input(iq))
        with torch.no_grad():
            parts = [model.features(b[:, None]).mean(dim=(2, 3)) for b in z.split(256)]
        return torch.cat(parts).numpy()

    train, test = generate_dataset(500, rng=1), generate_dataset(200, rng=3)
    E = embed(train.iq)
    means = np.stack([E[train.labels == c].mean(axis=0) for c in range(len(CLASSES))])
    centred = E - means[train.labels]
    precision = np.linalg.inv(centred.T @ centred / len(E) + 1e-4 * np.eye(E.shape[1]))

    def distance(iq):
        d = embed(iq)[:, None] - means
        return np.min(np.einsum("nki,ij,nkj->nk", d, precision, d), axis=1)

    known, unseen = distance(test.iq), distance(unseen_waveforms(400, rng=9))
    threshold = np.quantile(known, 0.95)
    auc = np.mean(unseen[:, None] > known[None])
    print("E. Mahalanobis distance in the CNN embedding")
    print(f"   unseen rejected {np.mean(unseen > threshold):.3f} for 5 % known, AUC {auc:.3f}")


if __name__ == "__main__":
    if "novelty" in sys.argv[1:]:
        probe_novelty()
    else:
        for probe in (probe_loading, probe_fixed_point, probe_sparse, probe_wideband):
            probe()
