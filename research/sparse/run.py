"""Experiments of the sparse array study.

    python -m research.sparse.run            # all
    python -m research.sparse.run stress     # selected

Success of a DOA trial: every estimate within 3 degrees of its source.
"""

import sys
import time

import numpy as np

from dsp.adaptive_weights import mvdr_weights
from dsp.covariance_matrix import compute_covariance_matrix
from dsp.signal_metrics import (
    half_power_beamwidth,
    optimal_sinr,
    output_sinr,
    peak_sidelobe_db,
    scene_covariance,
    to_db,
)
from research.covariance.estimators import noise_power
from research.harness import progress, proportion_interval, save_results
from research.sparse import arrays as sp
from simulations.channels.awgn import complex_noise, make_rng
from simulations.doa.music import music_spectrum
from simulations.doa.peaks import find_spectrum_peaks

FIVE = np.array([-50.0, -25.0, 0.0, 25.0, 50.0])
TOLERANCE = 3.0


def simulate(positions, angles_deg, powers, snapshots, rng, correlation=0.0, phase=0.0,
             position_error=0.0, coupling=0.0):  # fmt: skip
    """Snapshots of a sparse array with optional imperfections.

    ``correlation`` links the first two sources; ``phase`` is the RMS channel error in degrees;
    ``position_error`` the RMS element displacement in wavelengths; ``coupling`` the coupling
    coefficient between elements half a wavelength apart, decaying with the distance.
    """
    positions = np.asarray(positions, float)
    n, count = len(positions), len(angles_deg)
    true = positions + 2 * position_error * rng.standard_normal(n)
    A = sp.steering(true, np.radians(angles_deg))
    if coupling:
        distance = np.abs(np.subtract.outer(positions, positions))
        C = np.where(distance > 0, coupling / np.maximum(distance, 1), 1.0) * np.exp(
            -1j * np.pi * np.maximum(distance - 1, 0)
        )
        A = C @ A
    if phase:
        A = np.exp(1j * np.radians(phase) * rng.standard_normal(n))[:, None] * A
    s = complex_noise((count, snapshots), 1.0, rng)
    if correlation:
        s[1] = correlation * s[0] + np.sqrt(1 - correlation**2) * s[1]
    X = A @ (np.sqrt(powers)[:, None] * s)
    return X + complex_noise((n, snapshots), 1.0, rng)


def trial_success(positions, angles, powers, snapshots, trials, seed, **options):
    """Success rate with interval, and RMSE of the successful trials."""
    errors, successes, weakest = [], 0, 0
    weak = int(np.argmin(powers))
    for t in range(trials):
        rng = make_rng([seed, t])
        X = simulate(positions, angles, np.asarray(powers, float), snapshots, rng, **options)
        estimate = sp.coarray_music(compute_covariance_matrix(X), positions, len(angles))
        error = estimate - np.sort(angles)
        ok = bool(np.max(np.abs(error)) < TOLERANCE)
        successes += ok
        weakest += bool(np.abs(error[weak]) < TOLERANCE)
        if ok:
            errors.append(error)
    return {
        "success": successes / trials,
        "interval": proportion_interval(successes, trials),
        "weakest_found": weakest / trials,
        "rmse_deg": float(np.sqrt(np.mean(np.square(errors)))) if errors else float("nan"),
    }


# ------------------------------------------------------------------------- experiments


def geometry():
    """Coarray, beam and ambiguity figures of each geometry."""
    result = {}
    angles = np.arange(-90, 90.02, 0.02)
    u = np.linspace(0, 2, 4001)
    for name, positions in sp.GEOMETRIES.items():
        array = sp.make_array(positions)
        pattern = np.abs(sp.steering(positions, np.radians(angles)).mean(axis=0)) ** 2
        gain = sp.ambiguity(positions, u)
        main = int(np.argmax(np.diff(gain) > 0))  # first minimum
        # with half-wavelength units u = 2 is the trivial wrap from -90 to +90 degrees
        last = len(u) - 1 - main
        spacing = np.diff(np.sort(positions))
        result[name] = {
            "positions": positions,
            "elements": len(positions),
            "aperture": int(max(positions)),
            "coarray_weights": sp.coarray(positions),
            "contiguous_lags": sp.contiguous(positions),
            "identifiable_sources": sp.contiguous(positions),
            "beamwidth_deg": half_power_beamwidth(angles, pattern),
            "sidelobe_db": peak_sidelobe_db(pattern),
            "worst_ambiguity": float(gain[main:last].max()),
            "worst_ambiguity_at_sine": float(u[main + int(np.argmax(gain[main:last]))]),
            "unit_spacing_pairs": int(np.sum(spacing == 1)),
            "grating_lobe": bool(np.any(gain[main:last] > 0.999)),
            "num_elements_check": array.num_elements,
        }
    return result


def stress():
    """Five sources on four elements under more demanding conditions."""
    mra = sp.GEOMETRIES["MRA-4"]
    ten_db = np.full(5, 10.0)
    result = {}
    for k in (50, 100, 200, 500, 1000, 2000, 4000, 10000):
        result[f"snapshots={k}"] = trial_success(mra, FIVE, ten_db, k, 300, 1)
    for snr in (-10, -5, 0, 5, 10, 20, 30, 40):
        p = np.full(5, 10 ** (snr / 10))
        entry = trial_success(mra, FIVE, p, 1000, 300, 2)
        entry["crb_deg"] = float(
            np.degrees(np.sqrt(np.mean(sp.crb(mra, np.radians(FIVE), p, 1.0, 1000))))
        )
        result[f"snr={snr}"] = entry
    for rho in (0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9):
        result[f"correlation={rho}"] = trial_success(
            mra, FIVE, ten_db, 4000, 300, 3, correlation=rho
        )
    for phase in (0, 1, 2, 5, 10, 20):
        result[f"phase={phase}"] = trial_success(mra, FIVE, ten_db, 4000, 300, 4, phase=phase)
    for displacement in (0, 0.002, 0.005, 0.01, 0.02, 0.05):
        result[f"position={displacement}"] = trial_success(
            mra, FIVE, ten_db, 4000, 300, 5, position_error=displacement
        )
    for c in (0, 0.05, 0.1, 0.2, 0.3):
        result[f"coupling={c}"] = trial_success(mra, FIVE, ten_db, 4000, 100, 6, coupling=c)
    for spread in (0, 3, 6, 10, 15, 20):
        powers = np.array([10.0, 10.0, 10 ** (1 - spread / 10), 10.0, 10.0])
        result[f"spread={spread}"] = trial_success(mra, FIVE, powers, 1000, 300, 7)
    for spacing in (25, 20, 15, 12, 10, 8, 6):
        angles = spacing * np.arange(-2, 3)
        result[f"spacing={spacing}"] = trial_success(mra, angles, ten_db, 4000, 300, 8)
    for count in (1, 2, 3, 4, 5, 6):
        angles = np.linspace(-50, 50, count) if count > 1 else np.array([10.0])
        result[f"sources={count}"] = trial_success(mra, angles, np.full(count, 10.0), 1000, 300, 9)
    for t in (0, 1):  # random directions, at least 12 degrees apart
        result[f"random K={(1000, 4000)[t]}"] = random_directions(mra, (1000, 4000)[t])
    return result


def random_directions(positions, snapshots, trials=400):
    successes = 0
    for t in range(trials):
        rng = make_rng([10, snapshots, t])
        while True:
            angles = np.sort(rng.uniform(-60, 60, 5))
            if np.min(np.diff(angles)) > 12:
                break
        X = simulate(positions, angles, np.full(5, 10.0), snapshots, rng)
        estimate = sp.coarray_music(compute_covariance_matrix(X), positions, 5)
        successes += bool(np.max(np.abs(estimate - angles)) < TOLERANCE)
    return {"success": successes / trials, "interval": proportion_interval(successes, trials)}


def combined_scene(rng, count, separation, n_db=10.0):
    while True:
        angles = np.sort(rng.uniform(-60, 60, count))
        if np.min(np.diff(angles)) >= separation:
            break
    powers = 10 ** ((n_db - rng.uniform(0, 10, count)) / 10)
    return angles, powers


def combined():
    """All imperfections at once, five and two sources (H4.7, H4.8)."""
    levels = {
        "mild": {"separation": 18.0, "phase": 2.0, "coupling": 0.05},
        "severe": {"separation": 14.0, "phase": 5.0, "coupling": 0.1},
    }
    result = {}
    for level, v in levels.items():
        options = {
            "phase": v["phase"],
            "coupling": v["coupling"],
            "position_error": 0.01,
            "correlation": 0.2,
        }
        for count, names in ((5, ("MRA-4", "nested-4")), (2, ("MRA-4", "nested-4", "ULA-4"))):
            for name in names:
                positions = sp.GEOMETRIES[name]
                if sp.contiguous(positions) < count:
                    continue
                errors, successes, trials = [], 0, 400
                for t in range(trials):
                    rng = make_rng([14, count, t])
                    angles, powers = combined_scene(rng, count, v["separation"])
                    X = simulate(positions, angles, powers, 500, rng, **options)
                    R = compute_covariance_matrix(X)
                    error = sp.coarray_music(R, positions, count) - angles
                    ok = bool(np.max(np.abs(error)) < TOLERANCE)
                    successes += ok
                    errors.append(error)
                result[f"{level} sources={count} {name}"] = {
                    "success": successes / trials,
                    "interval": proportion_interval(successes, trials),
                    "median_error_deg": float(np.median(np.abs(errors))),
                    "rmse_deg": float(np.sqrt(np.mean(np.square(errors)))),
                }
    return result


def comparison():
    """Few sources: sparse arrays against uniform arrays, same number of elements."""
    result = {}
    for name in ("ULA-4", "nested-4", "MRA-4", "ULA-8", "nested-8", "MRA-8"):
        positions = sp.GEOMETRIES[name]
        for separation in (2, 4, 6, 8, 12, 16):
            angles = np.array([-separation / 2, separation / 2])
            errors = {"coarray": [], "direct": []}
            found = {"coarray": 0, "direct": 0}
            trials = 200
            grid = np.arange(-90, 90.1, 0.1)
            G = sp.steering(positions, np.radians(grid))
            for t in range(trials):
                rng = make_rng([11, separation, t])
                X = simulate(positions, angles, np.full(2, 10.0), 500, rng)
                R = compute_covariance_matrix(X)
                estimates = {
                    "coarray": sp.coarray_music(R, positions, 2),
                    "direct": find_spectrum_peaks(grid, music_spectrum(R, G, 2), 2),
                }
                for key, value in estimates.items():
                    if len(value) == 2 and np.max(np.abs(value - angles)) < separation / 2:
                        found[key] += 1
                        errors[key].append(value - angles)
            bound = sp.crb(positions, np.radians(angles), np.full(2, 10.0), 1.0, 500)
            result[f"{name} separation={separation}"] = {
                key: {
                    "resolved": found[key] / trials,
                    "rmse_deg": float(np.sqrt(np.mean(np.square(errors[key]))))
                    if errors[key]
                    else float("nan"),
                }
                for key in found
            } | {"crb_deg": float(np.degrees(np.sqrt(np.mean(bound))))}
    return result


def ambiguity():
    """False peaks: one source, two-source confusion, and random scans for the sparse arrays."""
    result = {}
    grid = np.arange(-90, 90.05, 0.05)
    for name in ("ULA-4", "nested-4", "MRA-4", "nested-8", "MRA-8"):
        positions = sp.GEOMETRIES[name]
        G = sp.steering(positions, np.radians(grid))
        outliers = {}
        for snr in (-10, -5, 0):
            wrong = 0
            for t in range(500):
                rng = make_rng([12, snr + 100, t])
                angle = rng.uniform(-60, 60)
                X = simulate(positions, [angle], np.array([10 ** (snr / 10)]), 20, rng)
                R = compute_covariance_matrix(X)
                power = np.einsum("ij,ij->j", G.conj(), R @ G).real
                wrong += abs(grid[np.argmax(power)] - angle) > 10
            outliers[f"snr={snr}"] = wrong / 500
        result[name] = outliers
    return result


def beamforming():
    """MVDR SINR against the interferer angle: INR 30 dB, 0 dB target, exact R and K = 256."""
    result = {}
    angles = np.concatenate((np.arange(3, 30, 1.0), np.arange(30, 76, 3.0)))
    for name in ("ULA-4", "nested-4", "MRA-4", "ULA-8", "MRA-8"):
        positions = sp.GEOMETRIES[name]
        n = len(positions)
        a = np.ones(n, complex)
        optimum, sample, das = [], [], []
        for angle in angles:
            b = sp.steering(positions, np.radians(angle))[:, 0]
            R_in = scene_covariance(b[:, None], [1000.0], 1.0)
            optimum.append(to_db(optimal_sinr(a, 1.0, R_in)))
            das.append(to_db(output_sinr(a / n, a, 1.0, R_in)))
            ratios = []
            for t in range(40):
                rng = make_rng([13, int(angle), t])
                X = simulate(positions, [0.0, angle], np.array([1.0, 1000.0]), 256, rng)
                S = compute_covariance_matrix(X)
                w = mvdr_weights(S, a, 10 * noise_power(S, 256))
                ratios.append(output_sinr(w, a, 1.0, R_in))
            sample.append(to_db(np.mean(ratios)))
        result[name] = {
            "angles": angles, "optimum_db": optimum, "sample_db": sample, "das_db": das,
        }  # fmt: skip
    return result


EXPERIMENTS = (geometry, stress, combined, comparison, ambiguity, beamforming)


def main(names):
    for experiment in EXPERIMENTS:
        if names and experiment.__name__ not in names:
            continue
        start = time.perf_counter()
        save_results("sparse", experiment.__name__, experiment())
        progress(f"{experiment.__name__}: {time.perf_counter() - start:.0f} s")


if __name__ == "__main__":
    main(sys.argv[1:])
