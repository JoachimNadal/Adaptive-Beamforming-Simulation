"""Experiments of the covariance study.

    python -m research.covariance.run                 # all
    python -m research.covariance.run snapshots cost  # selected

Every method sees the same snapshots (paired trials) and is scored on the true scene. Results
go to ``research/covariance/results``.
"""

import sys
import time

import numpy as np

from dsp.signal_metrics import optimal_sinr, output_sinr, scene_covariance
from examples.common import WAVELENGTH
from research.covariance.methods import METHODS, Context
from research.harness import bootstrap_loss, loss_db, progress, save_results
from simulations.channels.awgn import complex_noise, make_rng

INTERFERER = -25.0


def simulate(context, rng, snapshots, snr_db, interferers, options):
    """Return ``(X, a_true, R_in)`` for one random scene.

    ``interferers`` is a list of ``(angle, INR dB)``. Options: ``pointing`` (deg), ``phase``
    (deg RMS channel errors, with 0.1 dB of gain error per degree), ``noise`` in
    ``gaussian | student | impulsive``, ``duty`` of the interferers, ``correlation`` of the
    target with the first interferer.
    """
    n = context.n
    angles = [options.get("pointing", 0.0)] + [angle for angle, _ in interferers]
    A = context.array.compute_steering_matrix(angles, WAVELENGTH, "deg")
    phase = options.get("phase", 0.0)
    if phase:
        gain = 10 ** (0.1 * phase * rng.standard_normal(n) / 20)
        A = (gain * np.exp(1j * np.radians(phase) * rng.standard_normal(n)))[:, None] * A
    snr = 10 ** (snr_db / 10)
    powers = np.array([10 ** (inr / 10) for _, inr in interferers])

    s = complex_noise(snapshots, 1.0, rng)
    J = complex_noise((len(interferers), snapshots), 1.0, rng)
    duty = options.get("duty", 1.0)
    if duty < 1:
        J = J * (rng.random((len(interferers), snapshots)) < duty) / np.sqrt(duty)
    correlation = options.get("correlation", 0.0)
    if correlation:
        J[0] = correlation * s + np.sqrt(1 - correlation**2) * J[0]

    texture = np.ones(snapshots)
    kind = options.get("noise", "gaussian")
    if kind == "student":  # complex t with 3 degrees of freedom, unit variance
        texture = 1 / rng.gamma(1.5, 1 / 1.5, snapshots) / 3
    elif kind == "impulsive":  # 5 % of snapshots 20 dB stronger, unit mean power
        texture = np.where(rng.random(snapshots) < 0.05, 100.0, 1.0) / 5.95
    noise = np.sqrt(texture) * complex_noise((n, snapshots), 1.0, rng)

    X = np.outer(A[:, 0], np.sqrt(snr) * s) + A[:, 1:] @ (np.sqrt(powers)[:, None] * J) + noise
    return X, A[:, 0], scene_covariance(A[:, 1:], powers, 1.0)


def evaluate(n, snapshots, snr_db, interferers, trials=200, methods=None, **options):
    """Loss and 95 % interval of each method, on ``trials`` paired scenes."""
    context = Context(n)
    ratios: dict[str, list[float]] = {name: [] for name in methods or METHODS}
    failures = dict.fromkeys(ratios, 0)
    for seed in range(trials):
        rng = make_rng([seed, n, snapshots])
        X, a, R_in = simulate(context, rng, snapshots, snr_db, interferers, options)
        best = optimal_sinr(a, 1.0, R_in)
        for name in ratios:
            try:
                w = METHODS[name](X, context)
                ratios[name].append(output_sinr(w, a, 1.0, R_in) / best)
            except np.linalg.LinAlgError:
                failures[name] += 1  # counted as no output at all
                ratios[name].append(0.0)
    return {
        name: {
            "loss_db": loss_db(values),
            "interval_db": bootstrap_loss(values),
            "worst_decile_db": float(-10 * np.log10(max(np.quantile(values, 0.1), 1e-30))),
            "failures": failures[name],
        }
        for name, values in ratios.items()
    }


# ------------------------------------------------------------------------- experiments


def snapshots():
    """Loss against K and INR, 0 dB target in the data, no model error."""
    return {
        f"N={n} K={factor}N INR={inr}": evaluate(n, factor * n, 0, [(INTERFERER, inr)])
        for n in (4, 8)
        for factor in (1, 2, 4, 8, 32)
        for inr in (0, 20, 40, 60)
    }


def pointing():
    return {
        f"N={n} SNR={snr} error={error}": evaluate(n, 256, snr, [(INTERFERER, 40)], pointing=error)
        for n in (4, 8)
        for snr in (0, 10, 20)
        for error in (0, 0.5, 1, 2, 3, 4)
    }


def calibration():
    """Channel errors on top of a 2 degree pointing error, 10 dB target."""
    return {
        f"N={n} phase={phase} pointing={error}": evaluate(
            n, 256, 10, [(INTERFERER, 40)], phase=phase, pointing=error
        )
        for n in (4, 8)
        for error in (0, 2)
        for phase in (0, 1, 2, 5, 10, 20)
    }


def noise_models():
    return {
        f"N={n} K={k} {kind} INR={inr}": evaluate(n, k, 0, [(INTERFERER, inr)], noise=kind)
        for n in (4, 8)
        for k in (4 * n, 256)
        for kind in ("gaussian", "student", "impulsive")
        for inr in (10, 30)
    }


def pulsed():
    """Interferer present in a fraction of the snapshots, same mean power."""
    return {
        f"N={n} duty={duty}": evaluate(n, 256, 0, [(INTERFERER, 30)], duty=duty)
        for n in (4, 8)
        for duty in (1.0, 0.3, 0.1, 0.03)
    }


def many():
    """Number of 30 dB interferers, up to the degrees of freedom."""
    angles = (-25, 35, -55, 65, 15, -70, 50)
    return {
        f"N={n} interferers={count}": evaluate(n, 256, 0, [(angle, 30) for angle in angles[:count]])
        for n in (4, 8)
        for count in range(1, n)
    }


def correlation():
    """Coherence between the target and the interferer (multipath-like)."""
    return {
        f"N={n} correlation={rho}": evaluate(n, 256, 0, [(INTERFERER, 10)], correlation=rho)
        for n in (4, 8)
        for rho in (0.0, 0.3, 0.6, 0.9)
    }


def cost(repeats=200):
    """Median time per weight computation, microseconds, on one PC and one run."""
    result = {}
    for n in (4, 8, 16):
        context = Context(n)
        rng = make_rng(0)
        X, _, _ = simulate(context, rng, 256, 0, [(INTERFERER, 30)], {})
        row = {}
        for name, method in METHODS.items():
            durations = []
            for _ in range(repeats):
                start = time.perf_counter()
                method(X, context)
                durations.append(time.perf_counter() - start)
            row[name] = float(np.median(durations[repeats // 10 :]) * 1e6)
        result[f"N={n}"] = row
    return result


EXPERIMENTS = (snapshots, pointing, calibration, noise_models, pulsed, many, correlation, cost)


def main(names):
    for experiment in EXPERIMENTS:
        if names and experiment.__name__ not in names:
            continue
        start = time.perf_counter()
        save_results("covariance", experiment.__name__, experiment())
        progress(f"{experiment.__name__}: {time.perf_counter() - start:.0f} s")


if __name__ == "__main__":
    main(sys.argv[1:])
