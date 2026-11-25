"""Regenerate every figure of the documentation, with fixed seeds.

    python scripts/generate_figures.py            # all
    python scripts/generate_figures.py smi music  # names containing these words

Output goes to assets/images. The course (Appendix C.1) refers to this script.
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from dsp.adaptive_weights import das_weights, lcmv_weights, mvdr_weights
from dsp.covariance_matrix import compute_covariance_matrix, spatial_smoothing
from dsp.signal_metrics import (
    optimal_sinr,
    output_sinr,
    scene_covariance,
    to_db,
    white_noise_gain,
)
from examples.common import WAVELENGTH, reference_array
from simulations.antenna_array.circular_array import CircularArray
from simulations.beamforming.delay_and_sum import DelayAndSumBeamformer
from simulations.beamforming.lcmv import LCMVBeamformer
from simulations.beamforming.lms import LMSBeamformer, NLMSBeamformer
from simulations.beamforming.rls import RLSBeamformer
from simulations.channels.awgn import complex_noise
from simulations.channels.interference_models import qpsk
from simulations.channels.multipath import Path as RayPath
from simulations.channels.multipath import multipath_snapshots
from simulations.doa.capon import bartlett_spectrum, capon_spectrum
from simulations.doa.crb import crb_stochastic
from simulations.doa.esprit import esprit
from simulations.doa.music import music_spectrum, root_music
from simulations.doa.order_estimation import estimate_order_aic, estimate_order_mdl
from simulations.plot_style import MUTED, REFERENCE, SERIES, TEXT, mark_angles, styled
from simulations.scenarios.adaptive_tracking import run_tracking
from simulations.scenarios.array_snapshots import simulate_array_snapshots

OUTPUT = Path(__file__).resolve().parents[1] / "assets" / "images"
ANGLES = np.arange(-90, 90.1, 0.1)
FIGURES = {}


def figure(path):
    """Register a function returning a Matplotlib figure under an output path."""

    def register(function):
        FIGURES[path] = function
        return function

    return register


def steering(array, angles):
    return array.compute_steering_matrix(angles, WAVELENGTH, "deg")


def pattern_axes(title, floor=-60, size=(6.4, 3.6)):
    fig, ax = plt.subplots(figsize=size)
    ax.set(xlabel="Angle (degrees)", ylabel="Gain (dB)", title=title)
    ax.set_xlim(-90, 90)
    ax.set_ylim(floor, 6)
    ax.set_xticks(range(-90, 91, 30))
    return fig, ax


def plot_pattern(ax, w, array, label, **style):
    ax.plot(ANGLES, to_db(np.abs(w.conj() @ steering(array, ANGLES)) ** 2), label=label, **style)


# ------------------------------------------------------------------------------ basics


@figure("../diagrams/array_convention.png")
def array_convention():
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    theta = np.radians(30)
    x = np.arange(4) * 1.0
    to_source = np.array([-np.sin(theta), np.cos(theta)])
    for m, position in enumerate(x):
        start = np.array([position, 0.0])
        ax.annotate(
            "", start, start + 2.3 * to_source, arrowprops={"arrowstyle": "->", "color": SERIES[0]}
        )
        ax.plot(*start, "o", color=TEXT, markersize=8)
        ax.text(position, -0.28, f"$A_{m}$", ha="center", color=TEXT)
    # wavefront through A0
    along = np.array([np.cos(theta), np.sin(theta)])
    front = np.array([-0.6 * along, 3.2 * along])
    ax.plot(*front.T, color=SERIES[1], linestyle="--", label="wavefront reaching $A_0$")
    foot = along * np.dot([3, 0], along)
    ax.plot([3, foot[0]], [0, foot[1]], color=SERIES[2], linewidth=2.5)
    ax.text(3.15, 0.75, r"$3\,d\,\sin\theta$", color=TEXT, ha="left")
    ax.plot([0, 0], [0, 2.4], color=REFERENCE, linestyle=":")
    arc = np.linspace(0, theta, 30)
    ax.plot(-1.5 * np.sin(arc), 1.5 * np.cos(arc), color=MUTED, linewidth=1)
    ax.text(-0.36, 1.62, r"$\theta > 0$", color=TEXT, ha="center")
    ax.text(0.06, 2.42, "broadside", color=MUTED, fontsize=8)
    ax.text(
        0.0, -0.85, r"$a_m(\theta) = e^{-j\,m\,k\,d\,\sin\theta}$: element $m$ lags behind $A_0$",
        color=TEXT,
    )  # fmt: skip
    ax.set_aspect("equal")
    ax.set_xlim(-1.6, 4.4)
    ax.set_ylim(-1.1, 2.8)
    ax.axis("off")
    ax.legend(loc="upper right")
    return fig


@figure("steering_vectors/steering_phases_simulation.png")
def steering_phases():
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    for color, angle in zip(SERIES, (0, 15, 30), strict=False):
        phases = np.degrees(np.angle(steering(reference_array(), angle)[:, 0]))
        phases = np.unwrap(phases, period=360)
        ax.plot(range(4), phases, "o-", color=color, label=f"{angle} degrees", markersize=7)
    ax.set(
        xlabel="Antenna index", ylabel="Phase (degrees, unwrapped)", title="Steering vector phases"
    )
    ax.set_xticks(range(4))
    ax.legend()
    return fig


@figure("beamforming/delay_and_sum_beam_pattern_target_angle_30_degrees.png")
def das_cartesian():
    fig, ax = pattern_axes("Delay-and-sum steered to 30 degrees", -40)
    for n in (4, 8, 16):
        array = reference_array(n)
        plot_pattern(ax, das_weights(steering(array, 30)[:, 0]), array, f"{n} elements")
    mark_angles(ax, 30)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.34), ncol=3)
    return fig


@figure("beamforming/delay_and_sum_polar_beam_pattern.png")
def das_polar():
    fig, ax = plt.subplots(figsize=(5.4, 3.6), subplot_kw={"projection": "polar"})
    das = DelayAndSumBeamformer(reference_array())
    das.plot_polar_beam_pattern(30, WAVELENGTH, ax=ax)
    ax.set_title("Delay-and-sum, 4 elements, steered to 30 degrees")
    return fig


@figure("beamforming/uniform_circular_array.png")
def circular():
    fig, ax = plt.subplots(figsize=(4.8, 4.8), subplot_kw={"projection": "polar"})
    array = CircularArray.from_spacing(8, WAVELENGTH / 2)
    grid = np.arange(-180, 180.5, 0.5)
    for angle in (-120, 0, 75):
        w = das_weights(steering(array, angle)[:, 0])
        gain = to_db(np.abs(w.conj() @ steering(array, grid)) ** 2)
        ax.plot(np.radians(grid), np.maximum(gain, -30), label=f"{angle} degrees")
    ax.set_theta_zero_location("N")
    ax.set_ylim(-30, 3)
    ax.set_yticks([-20, -10, 0])
    ax.set_title("8-element circular array (dB)")
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.16), ncol=3)
    return fig


# -------------------------------------------------------------------- adaptive weights


@figure("beamforming/beamformer_comparison.png")
def comparison():
    """The scene of course section 24.8 (N = 8, SNR 0 dB, two jammers at 35 dB INR)."""
    array, truth = reference_array(8), [0, -25, 40]
    A = steering(array, truth)
    R_in = scene_covariance(A[:, 1:], [10**3.5] * 2, 1.0)
    X = simulate_array_snapshots(array, WAVELENGTH, truth, [1, 10**3.5, 10**3.5], 128, rng=1).X
    R = compute_covariance_matrix(X)
    loading = 1e-3 * np.trace(R).real / 8
    weights = {
        "delay-and-sum": das_weights(A[:, 0]),
        "MVDR, loaded": mvdr_weights(R, A[:, 0], loading),
        "LCMV, explicit nulls": lcmv_weights(R, A, [1, 0, 0], loading),
    }
    fig, ax = pattern_axes("Two 35 dB interferers, 8 elements, 128 snapshots", -70)
    for name, w in weights.items():
        sinr = to_db(output_sinr(w, A[:, 0], 1.0, R_in))
        plot_pattern(ax, w, array, f"{name}: SINR {sinr:.1f} dB")
    mark_angles(ax, truth)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.42))
    return fig


@figure("mvdr/smi_convergence.png")
def smi_convergence():
    array, n = reference_array(8), 8
    A = steering(array, [0, -25])
    R_in = scene_covariance(A[:, 1:], [1000.0], 1.0)
    best = optimal_sinr(A[:, 0], 1.0, R_in)
    K = np.array([8, 10, 12, 16, 24, 32, 48, 64, 128])
    loss: dict[str, list] = {"target absent": [], "target present": [], "present, loaded": []}
    for k in K:
        results: dict[str, list] = {name: [] for name in loss}
        for seed in range(300):
            absent = simulate_array_snapshots(array, WAVELENGTH, [-25], [1000.0], k, rng=seed).X
            present = simulate_array_snapshots(
                array, WAVELENGTH, [0, -25], [1.0, 1000.0], k, rng=seed
            ).X
            Ra, Rp = compute_covariance_matrix(absent), compute_covariance_matrix(present)
            for name, R, load in (
                ("target absent", Ra, 0.0),
                ("target present", Rp, 0.0),
                ("present, loaded", Rp, 10.0),
            ):
                w = mvdr_weights(R, A[:, 0], load)
                results[name].append(output_sinr(w, A[:, 0], 1.0, R_in) / best)
        for name in loss:
            loss[name].append(to_db(np.mean(results[name])))
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    theory = to_db((K[K >= n] - n + 2) / (K[K >= n] + 1))
    ax.plot(K, theory, color=REFERENCE, linestyle="--", label="Reed-Mallett-Brennan")
    for name, values in loss.items():
        ax.plot(K, values, "o-", markersize=5, label=name)
    ax.set_xscale("log", base=2)
    ax.set_xticks(K[[0, 3, 5, 7, 8]], K[[0, 3, 5, 7, 8]])
    ax.set(xlabel="Snapshots", ylabel="SINR loss (dB)", title="Sample MVDR, 8 elements")
    ax.legend(loc="lower right")
    return fig


@figure("mvdr/diagonal_loading.png")
def diagonal_loading():
    array = reference_array(8)
    A = steering(array, [0, -25, 40])
    levels = np.logspace(-6, 1, 60)
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(6.4, 5), sharex=True)
    for label, error in (("exact direction", 0.0), ("0.5 degree error", 0.5)):
        true = steering(array, error)[:, 0]
        R_in = scene_covariance(A[:, 1:], [1000.0] * 2, 1.0)
        R = R_in + 10 * np.outer(true, true.conj())
        sinr, wng = [], []
        for level in levels:
            w = mvdr_weights(R, A[:, 0], level * np.trace(R).real / 8)
            sinr.append(to_db(output_sinr(w, true, 10.0, R_in)))
            wng.append(to_db(white_noise_gain(w, A[:, 0])))
        top.plot(levels, sinr, label=label)
        bottom.plot(levels, wng, label=label)
    bottom.set_xscale("log")
    top.set(ylabel="Output SINR (dB)", title="Diagonal loading: protection against pointing error")
    bottom.set(xlabel="Loading relative to tr(R)/N", ylabel="White noise gain (dB)")
    top.legend(loc="lower left")
    return fig


@figure("mvdr/pointing_error.png")
def pointing_error():
    array = reference_array(8)
    A = steering(array, [0, -25, 40])
    R_in = scene_covariance(A[:, 1:], [1000.0] * 2, 1.0)
    errors = np.linspace(-4, 4, 161)
    curves: dict[str, list] = {"MVDR": [], "MVDR, loaded 1e-2": [], "LCMV, derivative": []}
    best = []
    robust = LCMVBeamformer(array, derivative_constraint=True)
    for error in errors:
        true = steering(array, error)[:, 0]
        R = R_in + 10 * np.outer(true, true.conj())
        best.append(to_db(optimal_sinr(true, 10.0, R_in)))
        for name, w in (
            ("MVDR", mvdr_weights(R, A[:, 0])),
            ("MVDR, loaded 1e-2", mvdr_weights(R, A[:, 0], 1e-2 * np.trace(R).real / 8)),
            ("LCMV, derivative", robust.compute_weights(R, 0, WAVELENGTH)),
        ):
            curves[name].append(to_db(output_sinr(w, true, 10.0, R_in)))
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ax.plot(errors, best, color=REFERENCE, linestyle="--", label="optimum")
    for name, values in curves.items():
        ax.plot(errors, values, label=name)
    ax.set(
        xlabel="Pointing error (degrees)",
        ylabel="Output SINR (dB)",
        title="Self-cancellation of a 10 dB target",
    )
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.4), ncol=2)
    return fig


@figure("beamforming/adaptive_learning_curves.png")
def learning_curves():
    """The interferer level jumps by 20 dB: a fixed LMS step leaves its stability region."""
    array, runs, num, jump = reference_array(), 40, 800, 400
    level = np.where(np.arange(num) < jump, 1.0, 10.0)
    curves = {"LMS": np.zeros(num), "NLMS": np.zeros(num), "RLS": np.zeros(num)}
    for seed in range(runs):
        pilot, jam = qpsk(num, 1, rng=seed), qpsk(num, 3, 0.11, rng=1000 + seed)
        scene = simulate_array_snapshots(
            array,
            WAVELENGTH,
            [10, -35],
            [1.0, 10.0],
            num,
            0.1,
            seed,
            waveforms=np.stack((pilot, level * jam)),
        )
        for name, beamformer in (
            ("LMS", LMSBeamformer(array, 0.5 / (4 * 11.1))),
            ("NLMS", NLMSBeamformer(array, 0.5)),
            ("RLS", RLSBeamformer(array, 0.98, 1e-2)),
        ):
            with np.errstate(over="ignore", invalid="ignore"):
                curves[name] += beamformer.train(scene.X, pilot)[1] / runs
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    for name, values in curves.items():
        smooth = np.convolve(np.nan_to_num(values, nan=1e9, posinf=1e9), np.ones(10) / 10, "valid")
        ax.plot(np.arange(9, num), to_db(smooth), label=name)  # causal average
    ax.axvline(jump, color=REFERENCE, linestyle=(0, (2, 2)), linewidth=1)
    ax.text(jump + 8, 12, "interferer +20 dB", color=MUTED, fontsize=8)
    ax.set_ylim(-20, 15)
    ax.set(xlabel="Snapshot", ylabel="Squared error (dB)", title="Supervised adaptation")
    ax.legend(loc="upper left")
    return fig


@figure("realtime/interferer_tracking.png")
def tracking():
    result = run_tracking(reference_array(), rng=0)
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    ax.plot(
        result.interferer_angle_deg,
        result.optimum_db,
        color=REFERENCE,
        linestyle="--",
        label="optimum",
    )
    for name in ("recursive", "SMI", "RLS", "frozen", "DAS"):
        ax.plot(result.interferer_angle_deg, result.sinr_db[name], label=name)
    ax.set(
        xlabel="Interferer angle (degrees), sweeping left to right",
        ylabel="Output SINR (dB)",
        title="Moving 30 dB interferer, 4 elements, 32-snapshot blocks",
    )
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.42), ncol=3)
    return fig


# --------------------------------------------------------------------------------- DOA


@figure("music/spectra_comparison.png")
def spectra():
    array, truth = reference_array(8), [-10, 0, 35]
    X = simulate_array_snapshots(array, WAVELENGTH, truth, [10.0] * 3, 200, rng=2026).X
    R, A = compute_covariance_matrix(X), steering(array, ANGLES)
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    for name, s in (
        ("Bartlett", bartlett_spectrum(R, A)),
        ("Capon", capon_spectrum(R, A)),
        ("MUSIC", music_spectrum(R, A, 3)),
    ):
        ax.plot(ANGLES, to_db(s / s.max()), label=name)
    mark_angles(ax, truth, "true directions")
    ax.set(
        xlabel="Angle (degrees)",
        ylabel="Normalized spectrum (dB)",
        title="Three sources, two within a beamwidth (8 elements)",
    )
    ax.set_xlim(-90, 90)
    ax.set_xticks(range(-90, 91, 30))
    ax.legend()
    return fig


@figure("music/rmse_vs_snr.png")
def rmse():
    array, truth, K = reference_array(8), np.array([-25.0, 0.0, 40.0]), 200
    A = steering(array, truth)
    D = np.column_stack([array.compute_steering_derivative(t, WAVELENGTH, "deg") for t in truth])
    snrs = np.arange(-10, 21, 2.5)
    curves: dict[str, list] = {"root-MUSIC": [], "TLS-ESPRIT": []}
    bound = []
    for snr in snrs:
        p = 10 ** (snr / 10)
        crb = crb_stochastic(A, D, p * np.eye(3), 1.0, K)
        bound.append(np.degrees(np.sqrt(np.trace(crb) / 3)))
        errors: dict[str, list] = {name: [] for name in curves}
        for seed in range(200):
            X = simulate_array_snapshots(array, WAVELENGTH, truth, [p] * 3, K, rng=seed).X
            R = compute_covariance_matrix(X)
            errors["root-MUSIC"].append(np.degrees(root_music(R, 3)) - truth)
            errors["TLS-ESPRIT"].append(np.degrees(esprit(R, 3)) - truth)
        for name in curves:
            curves[name].append(np.sqrt(np.mean(np.square(errors[name]))))
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    ax.semilogy(snrs, bound, color=REFERENCE, linestyle="--", label="Cramér-Rao bound")
    for name, values in curves.items():
        ax.semilogy(snrs, values, "o-", markersize=5, label=name)
    ax.set(
        xlabel="SNR per antenna (dB)",
        ylabel="RMSE (degrees)",
        title="Three sources, 8 elements, 200 snapshots, 200 trials",
    )
    ax.legend()
    return fig


@figure("doa/source_counting.png")
def counting():
    array = reference_array(8)
    snrs = np.arange(-20, 3, 2.0)
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    for name, estimator in (("MDL", estimate_order_mdl), ("AIC", estimate_order_aic)):
        hit = []
        for snr in snrs:
            p = 10 ** (snr / 10)
            hit.append(
                np.mean(
                    [
                        estimator(
                            compute_covariance_matrix(
                                simulate_array_snapshots(
                                    array, WAVELENGTH, [-20, 25], [p, p], 200, rng=seed
                                ).X
                            ),
                            200,
                        )
                        == 2
                        for seed in range(200)
                    ]
                )
            )
        ax.plot(snrs, hit, "o-", markersize=5, label=name)
    ax.set(
        xlabel="SNR per antenna (dB)",
        ylabel="Probability of counting 2",
        title="Counting two sources (8 elements, 200 snapshots)",
    )
    ax.set_ylim(-0.03, 1.05)
    ax.legend()
    return fig


@figure("doa/coherent_multipath.png")
def coherent():
    array, truth = reference_array(8), [-20, 25]
    rays = [RayPath(truth[0]), RayPath(truth[1], 0.0, 0.8j)]
    X = multipath_snapshots(array, WAVELENGTH, qpsk(500, 4, rng=0), rays)
    R = compute_covariance_matrix(X + complex_noise(X.shape, 0.03, 1))
    sub = reference_array(6)
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    for name, s in (
        ("MUSIC", music_spectrum(R, steering(array, ANGLES), 2)),
        (
            "MUSIC, spatial smoothing (6)",
            music_spectrum(spatial_smoothing(R, 6), steering(sub, ANGLES), 2),
        ),
    ):
        ax.plot(ANGLES, to_db(s / s.max()), label=name)
    mark_angles(ax, truth, "true directions")
    ax.set(
        xlabel="Angle (degrees)",
        ylabel="Normalized spectrum (dB)",
        title="Two coherent paths of one signal",
    )
    ax.set_xlim(-90, 90)
    ax.set_xticks(range(-90, 91, 30))
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.38), ncol=3)
    return fig


# -------------------------------------------------------------------------------- main


def main(words):
    for path, build in FIGURES.items():
        if words and not any(word in path for word in words):
            continue
        with styled():
            fig = build()
            target = OUTPUT / path
            target.parent.mkdir(parents=True, exist_ok=True)
            # no timestamp or version in the file: identical runs give identical bytes
            fig.savefig(target, metadata={"Software": None})
            plt.close(fig)
        print(target.relative_to(OUTPUT.parents[1]))
    if not words or "dashboard" in words:
        from dashboard.app import main as dashboard

        dashboard(["--snapshot", str(OUTPUT / "realtime" / "dashboard.png")])


if __name__ == "__main__":
    main(sys.argv[1:])
