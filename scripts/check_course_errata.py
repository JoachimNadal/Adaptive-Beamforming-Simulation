"""Reproduce each item of docs/theory/course_errata.md.

Functions named ``course_*`` copy the printed listings on purpose, defects included.

    python scripts/check_course_errata.py
"""

import numpy as np

from dsp.adaptive_weights import lcmv_weights
from dsp.calibration import calibration_residual, estimate_calibration
from dsp.covariance_matrix import compute_covariance_matrix
from dsp.signal_metrics import optimal_sinr, scene_covariance, to_db, white_noise_gain
from examples.common import WAVELENGTH, reference_array
from simulations.channels.awgn import complex_noise
from simulations.doa.order_estimation import estimate_order_mdl
from simulations.scenarios.array_snapshots import random_channel_gains, simulate_array_snapshots

TRUTH, POWERS, K = [0.0, -25.0, 40.0], [1.0, 10**3.5, 10**3.5], 128


def course_tls_esprit(R, L):
    """Listing C.1, ``esprit(..., tls=True)``."""
    _, vectors = np.linalg.eigh(R)
    Us = vectors[:, -L:]
    _, _, Vh = np.linalg.svd(np.hstack([Us[:-1], Us[1:]]), full_matrices=False)
    V = Vh.conj().T
    Psi = -np.linalg.solve(V[L:, L:].T, V[:L, L:].T).T
    return np.sort(np.arcsin(-np.angle(np.linalg.eigvals(Psi)) / np.pi))


def course_order(R, N):
    """Listing 24.1, source counting on the loaded covariance."""
    R = R + 1e-2 * np.trace(R).real / N * np.eye(N)
    eigenvalues = np.linalg.eigvalsh(R)
    L = int(np.sum(eigenvalues > 2 * np.mean(eigenvalues[: N // 2])))
    return max(1, min(L, N - 1, 5))


def course_peaks(angles_deg, spectrum, count, target_deg=0.0):
    """Listing 24.1, "strongest peaks": actually the largest grid samples."""
    chosen = []
    for i in np.argsort(spectrum)[::-1]:
        if abs(angles_deg[i] - target_deg) > 2:
            chosen.append(angles_deg[i])
        if len(chosen) == count:
            break
    return np.array(chosen)


def e1():
    for n, L in ((4, 2), (6, 3), (8, 4), (8, 3)):
        A = reference_array(n).compute_steering_matrix(np.linspace(-40, 35, L), WAVELENGTH, "deg")
        try:
            course_tls_esprit(scene_covariance(A, np.ones(L), 0.01), L)
            outcome = "works"
        except np.linalg.LinAlgError as error:
            outcome = f"fails ({error})"
        print(f"E1  TLS-ESPRIT listing, N={n} L={L}: {outcome}")


def e2():
    A = reference_array(8).compute_steering_matrix(TRUTH, WAVELENGTH, "deg")
    R_in = scene_covariance(A[:, 1:], POWERS[1:], 1.0)
    best = to_db(optimal_sinr(A[:, 0], 1.0, R_in))
    print(f"E2  optimum SINR {best:.2f} dB, bound N*SNR {to_db(8.0):.2f} dB (table: 18 to 22 dB)")


def e3():
    array, course, mdl = reference_array(8), [], []
    for seed in range(200):
        X = simulate_array_snapshots(array, WAVELENGTH, TRUTH, POWERS, K, rng=seed).X
        R = compute_covariance_matrix(X)
        course.append(course_order(R, 8))
        mdl.append(estimate_order_mdl(R, K))
    for name, orders in (("listing 24.1", course), ("MDL, unloaded", mdl)):
        values, counts = np.unique(orders, return_counts=True)
        found = dict(zip(values.tolist(), counts.tolist(), strict=True))
        print(f"E3  {name}: estimated orders {found} (true: 3)")


def e4():
    angles = np.linspace(-90, 90, 721)
    strong = 1 / ((angles - 40.1) ** 2 + 0.5)
    weak = 0.02 / ((angles + 25) ** 2 + 0.5)
    print(
        f"E4  peaks at 40.1 and -25, listing 24.1 returns {course_peaks(angles, strong + weak, 2)}"
    )


def e5():
    g = random_channel_gains(8, 1.0, 40.0, rng=0)
    array = reference_array(8)
    a = array.compute_steering_vector(10, WAVELENGTH, "deg")
    for name, waveform in (
        ("constant source", np.ones((1, 1024))),
        ("modulated source", complex_noise((1, 1024), 1.0, 1)),
    ):
        X = simulate_array_snapshots(
            array, WAVELENGTH, [10], [100.0], 1024, rng=0, waveforms=waveform, channel_gains=g
        ).X
        mean = X.mean(axis=1) / a
        listing = calibration_residual(mean / mean[0], g)[1]
        eigen = calibration_residual(estimate_calibration(X, a), g)[1]
        print(f"E5  {name}: listing 22.1 {listing:.2f} deg RMS, eigenvector {eigen:.2f} deg RMS")


def e7():
    array = reference_array(8)
    a = array.compute_steering_vector(0, WAVELENGTH)
    d = array.compute_steering_derivative(0, WAVELENGTH)
    for name, column in (("element 0", d), ("array centre", d - a * np.vdot(a, d) / 8)):
        w = lcmv_weights(np.eye(8), np.column_stack((a, column)), [1, 0])
        print(f"E7  derivative referenced to {name}: WNG {to_db(white_noise_gain(w, a)):.2f} dB")


if __name__ == "__main__":
    for check in (e1, e2, e3, e4, e5, e7):
        check()
