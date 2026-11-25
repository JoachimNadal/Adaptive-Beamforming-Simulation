"""Derive receiver requirements from simulation.

    python scripts/hardware_error_budget.py

Writes ``docs/hardware/error_budget_results.md``. Reference scene: N elements at half
wavelength, target at broadside (SNR 0 dB), one interferer at -25 degrees. Everything is
simulated; no hardware is involved.
"""

from pathlib import Path

import numpy as np

from dsp.adaptive_weights import mvdr_weights, null_steering_weights
from dsp.calibration import calibration_residual, estimate_calibration
from dsp.covariance_matrix import compute_covariance_matrix
from dsp.signal_metrics import null_depth_db, optimal_sinr, output_sinr, scene_covariance, to_db
from examples.common import WAVELENGTH, reference_array
from simulations.channels.awgn import make_rng
from simulations.scenarios.array_snapshots import random_channel_gains, simulate_array_snapshots

TARGET, JAMMER = 0.0, -25.0
TRIALS = 400
OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "hardware" / "error_budget_results.md"


def table(title, header, rows, note=""):
    lines = [f"\n## {title}\n"]
    if note:
        lines.append(note + "\n")
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "---:|" * len(header))
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


def steering(array):
    return array.compute_steering_matrix([TARGET, JAMMER], WAVELENGTH, "deg")


def phase_rows():
    """Deterministic null and adaptive MVDR against residual channel phase errors."""
    rng = make_rng(0)
    rows = []
    for phase in (0.1, 0.5, 1, 2, 5, 10, 20):
        row = [phase]
        for n in (4, 8):
            A = steering(reference_array(n))
            w_null = null_steering_weights(A, [1, 0])
            depths, losses = [], []
            for _ in range(TRIALS):
                g = np.exp(1j * np.radians(phase) * rng.standard_normal(n))
                real = g[:, None] * A
                depths.append(null_depth_db(w_null, real[:, 0], real[:, 1]))
                R_in = scene_covariance(real[:, 1:], [1000.0], 1.0)
                R = R_in + np.outer(real[:, 0], real[:, 0].conj())
                w = mvdr_weights(R, A[:, 0], 1e-2 * np.trace(R).real / n)
                best = optimal_sinr(real[:, 0], 1.0, R_in)
                losses.append(to_db(best) - to_db(output_sinr(w, real[:, 0], 1.0, R_in)))
            row += [f"{np.median(depths):.1f}", f"{np.quantile(depths, 0.9):.1f}"]
            row += [f"{np.median(losses):.2f}", f"{np.quantile(losses, 0.9):.2f}"]
        rows.append(row)
    return rows


def gain_rows():
    rng = make_rng(1)
    rows = []
    for gain in (0.05, 0.1, 0.2, 0.5, 1.0, 2.0):
        row = [gain]
        for n in (4, 8):
            A = steering(reference_array(n))
            w = null_steering_weights(A, [1, 0])
            depths = []
            for _ in range(TRIALS):
                real = (10 ** (gain * rng.standard_normal(n) / 20))[:, None] * A
                depths.append(null_depth_db(w, real[:, 0], real[:, 1]))
            row += [f"{np.median(depths):.1f}", f"{np.quantile(depths, 0.9):.1f}"]
        rows.append(row)
    return rows


def quantize(x, bits, full_scale):
    step = 2 * full_scale / 2**bits

    def rail(v):
        return np.clip(np.round(v / step) * step, -full_scale, full_scale - step)

    return rail(x.real) + 1j * rail(x.imag)


def adc_loss(inr_db, bits, headroom_db, trials=40):
    """Mean SINR loss (dB) of MVDR behind an ideal quantiser that clips at full scale."""
    array, n, K = reference_array(4), 4, 2048
    A = steering(array)
    power = 10 ** (inr_db / 10)
    full_scale = 10 ** (headroom_db / 20) * np.sqrt((power + 2) / 2)
    R_in = scene_covariance(A[:, 1:], [power], 1.0)
    best = optimal_sinr(A[:, 0], 1.0, R_in)
    losses = []
    for seed in range(trials):
        clean = simulate_array_snapshots(
            array, WAVELENGTH, [TARGET, JAMMER], [1.0, power], K, rng=seed
        ).X
        error = quantize(clean, bits, full_scale) - clean
        R = compute_covariance_matrix(clean + error)
        w = mvdr_weights(R, A[:, 0], 1e-3 * np.trace(R).real / n)
        noise = np.mean(np.abs(w.conj() @ error) ** 2)
        degraded = 1 / (1 / output_sinr(w, A[:, 0], 1.0, R_in) + noise)
        losses.append(to_db(best) - to_db(degraded))
    return np.mean(losses)


def adc_rows():
    return [
        [bits] + [f"{adc_loss(inr, bits, 15):.2f}" for inr in (20, 40, 60)]
        for bits in (4, 6, 8, 10, 12, 14)
    ]


def headroom_rows():
    return [
        [headroom] + [f"{adc_loss(inr, 14, headroom):.2f}" for inr in (20, 40, 60)]
        for headroom in (9, 12, 15, 18)
    ]


def bandwidth_rows():
    """Residual interferer power after one narrowband null, averaged over a flat band."""
    rows = []
    for fraction in (1e-4, 1e-3, 5e-3, 1e-2, 2e-2, 5e-2, 1e-1):
        row = [f"{100 * fraction:g} %", f"{2.4e3 * fraction:g}"]
        for n in (4, 8):
            w = null_steering_weights(steering(reference_array(n)), [1, 0])
            offsets = np.linspace(-fraction / 2, fraction / 2, 201)
            path = np.arange(n) * 0.5 * np.sin(np.radians(JAMMER))
            responses = np.exp(-2j * np.pi * np.outer(path, 1 + offsets))
            row.append(f"{to_db(np.mean(np.abs(w.conj() @ responses) ** 2)):.1f}")
        rows.append(row)
    return rows


def calibration_rows():
    array = reference_array(8)
    rows = []
    for snr_db in (0, 10, 20, 30):
        row = [snr_db]
        for K in (64, 256, 1024):
            residuals = []
            for seed in range(100):
                g = random_channel_gains(8, 1.0, 40.0, rng=seed)
                X = simulate_array_snapshots(
                    array, WAVELENGTH, [0], [10 ** (snr_db / 10)], K, rng=seed, channel_gains=g
                ).X
                residuals.append(calibration_residual(estimate_calibration(X, np.ones(8)), g)[1])
            row.append(f"{np.mean(residuals):.2f}")
        rows.append(row)
    return rows


def timing_rows():
    """Skew and length equivalent to a phase error at 2.4 GHz (wavelength 125 mm in air)."""
    return [
        [
            phase,
            f"{phase / 360 / 2.4e9 * 1e12:.2f}",
            f"{phase / 360 * 125:.2f}",
            f"{phase / 360 * 125 / np.sqrt(3.0):.2f}",
            f"{phase / 360 / 1e6 * 1e9:.1f}",
        ]
        for phase in (0.5, 1, 2, 5)
    ]


def main():
    sections = [
        "# Error budget results\n\n"
        "Generated by `python scripts/hardware_error_budget.py`. **Simulation only.**",
        table(
            "Residual channel phase error",
            ["RMS (deg)"]
            + [f"N={n}: {c}" for n in (4, 8) for c in ("null", "null p90", "loss", "loss p90")],
            phase_rows(),
            "`null`: depth in dB of a deterministic null (median and 90th percentile). `loss`:\n"
            "SINR in dB lost by MVDR (loading 1e-2) against the optimum, INR 30 dB, SNR 0 dB, "
            "target in the data.",
        ),
        table(
            "Residual channel gain error (deterministic null, dB)",
            ["RMS (dB)", "N=4: null", "N=4: null p90", "N=8: null", "N=8: null p90"],
            gain_rows(),
        ),
        table(
            "ADC resolution (SINR loss in dB, N=4, MVDR)",
            ["bits", "INR 20 dB", "INR 40 dB", "INR 60 dB"],
            adc_rows(),
            "Ideal quantiser, full scale 15 dB above the RMS level of each I and Q rail, "
            "loading 1e-3.",
        ),
        table(
            "Headroom (SINR loss in dB, N=4, MVDR, 14 bits)",
            ["full scale above RMS (dB)", "INR 20 dB", "INR 40 dB", "INR 60 dB"],
            headroom_rows(),
            "Gaussian interferer: at 12 dB about 2e-4 of the samples clip, which is enough to "
            "matter.",
        ),
        table(
            "Signal bandwidth (residual interferer power in dB after a narrowband null)",
            ["fractional", "MHz at 2.4 GHz", "N=4", "N=8"],
            bandwidth_rows(),
        ),
        table(
            "Calibration from one known source (residual phase, deg RMS, N=8)",
            ["source SNR (dB)", "K=64", "K=256", "K=1024"],
            calibration_rows(),
            "Starting point: 40 deg RMS phase and 1 dB RMS gain errors.",
        ),
        table(
            "Equivalent timing and length errors",
            [
                "phase (deg)",
                "RF skew at 2.4 GHz (ps)",
                "length in air (mm)",
                "length at eps_eff = 3 (mm)",
                "sampling skew at 1 MHz IF (ns)",
            ],
            timing_rows(),
        ),
    ]
    text = "\n".join(sections) + "\n"
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(text, encoding="utf-8", newline="\n")
    print(text)


if __name__ == "__main__":
    main()
