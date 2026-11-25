import numpy as np
import pytest

from dsp.covariance_matrix import compute_covariance_matrix, spatial_smoothing
from dsp.signal_metrics import scene_covariance
from examples.common import WAVELENGTH
from simulations.antenna_array.circular_array import CircularArray
from simulations.antenna_array.linear_array import LinearArray
from simulations.channels.awgn import complex_noise
from simulations.channels.interference_models import qpsk
from simulations.channels.multipath import Path, multipath_snapshots
from simulations.doa.capon import bartlett_spectrum, capon_spectrum
from simulations.doa.crb import crb_stochastic
from simulations.doa.esprit import esprit
from simulations.doa.music import music_spectrum, noise_subspace, root_music
from simulations.doa.order_estimation import estimate_order_aic, estimate_order_mdl
from simulations.doa.peaks import find_spectrum_peaks
from simulations.scenarios.adaptive_tracking import TrackingConfig, run_tracking
from simulations.scenarios.array_snapshots import simulate_array_snapshots
from simulations.scenarios.interference_detection import (
    InterferenceDetector,
    calibrate_threshold,
)

GRID = np.arange(-90, 90.25, 0.25)


@pytest.mark.parametrize("n, num_sources", [(4, 1), (4, 2), (4, 3), (6, 3), (8, 3), (8, 5)])
def test_grid_free_estimators_are_exact_without_noise(n, num_sources):
    """Includes the sizes for which the course TLS listing crashes (erratum E1)."""
    array = LinearArray(n, WAVELENGTH / 2)
    angles = np.linspace(-40, 35, num_sources) if num_sources > 1 else np.array([17.0])
    A = array.compute_steering_matrix(angles, WAVELENGTH, "deg")
    R = scene_covariance(A, np.linspace(1, 2, num_sources), 0.01)
    np.testing.assert_allclose(np.degrees(esprit(R, num_sources)), angles, atol=1e-6)
    np.testing.assert_allclose(np.degrees(esprit(R, num_sources, tls=False)), angles, atol=1e-6)
    np.testing.assert_allclose(np.degrees(root_music(R, num_sources)), angles, atol=1e-4)


@pytest.mark.parametrize(
    "array", [LinearArray(8, 6.25), CircularArray.from_spacing(8, 6.25)], ids=["ULA", "UCA"]
)
def test_spectra_locate_sources(array):
    angles = [-25.0, 0.0, 40.0]
    scene = simulate_array_snapshots(array, WAVELENGTH, angles, [10.0] * 3, 500, rng=3)
    R = compute_covariance_matrix(scene.X)
    A = array.compute_steering_matrix(GRID, WAVELENGTH, "deg")
    for spectrum in (music_spectrum(R, A, 3), capon_spectrum(R, A)):
        np.testing.assert_allclose(find_spectrum_peaks(GRID, spectrum, 3), angles, atol=0.6)


def test_spectra_measure_power(ula8):
    """Bartlett and Capon are calibrated power estimates for a single source."""
    a = ula8.compute_steering_matrix([12.0], WAVELENGTH, "deg")
    R = scene_covariance(a, [5.0], 0.1)
    assert bartlett_spectrum(R, a)[0] == pytest.approx(5.0 + 0.1 / 8)
    assert capon_spectrum(R, a)[0] == pytest.approx(5.0 + 0.1 / 8)


def test_resolution_ranking(ula8):
    """Two sources 8 degrees apart (beamwidth 12.8): MUSIC resolves, Bartlett does not."""
    scene = simulate_array_snapshots(ula8, WAVELENGTH, [-4, 4], [30.0, 30.0], 500, rng=0)
    R = compute_covariance_matrix(scene.X)
    A = ula8.compute_steering_matrix(GRID, WAVELENGTH, "deg")

    def peaks_inside(spectrum):
        return sum(abs(p) < 8 for p in find_spectrum_peaks(GRID, spectrum, 8))

    assert peaks_inside(bartlett_spectrum(R, A)) == 1
    assert peaks_inside(music_spectrum(R, A, 2)) == 2


@pytest.mark.parametrize("snr_db", [0, 10, 20])
def test_root_music_is_statistically_efficient(ula8, snr_db):
    """Monte-Carlo RMSE against the Cramer-Rao bound; ESPRIT is known to be above it."""
    angles, K, power = np.array([-25.0, 0.0, 40.0]), 200, 10 ** (snr_db / 10)
    A = ula8.compute_steering_matrix(angles, WAVELENGTH, "deg")
    D = np.column_stack([ula8.compute_steering_derivative(t, WAVELENGTH, "deg") for t in angles])
    bound = np.degrees(np.sqrt(np.diag(crb_stochastic(A, D, power * np.eye(3), 1.0, K))))
    errors: dict[str, list] = {"root": [], "esprit": []}
    for seed in range(200):
        scene = simulate_array_snapshots(ula8, WAVELENGTH, angles, [power] * 3, K, rng=seed)
        R = compute_covariance_matrix(scene.X)
        errors["root"].append(np.degrees(root_music(R, 3)) - angles)
        errors["esprit"].append(np.degrees(esprit(R, 3)) - angles)
    rmse = {k: np.sqrt(np.mean(np.square(v), axis=0)) for k, v in errors.items()}
    assert np.all(rmse["root"] > 0.85 * bound)  # 200 trials: 5 % standard error
    assert np.all(rmse["root"] < 1.25 * bound)
    assert np.all(rmse["esprit"] < 1.8 * bound)


def test_crb_matches_single_source_closed_form(ula8):
    """Stochastic CRB of one source on a ULA: 6 (1 + 1/(N s)) / (s K N (N^2-1) (pi cos)^2)."""
    theta, snr, K = np.radians(20.0), 5.0, 100
    A = ula8.compute_steering_matrix(theta, WAVELENGTH)
    D = ula8.compute_steering_derivative(theta, WAVELENGTH)[:, None]
    expected = 6 * (1 + 1 / (8 * snr)) / (snr * K * 8 * 63 * (np.pi * np.cos(theta)) ** 2)
    assert crb_stochastic(A, D, np.array([[snr]]), 1.0, K)[0, 0] == pytest.approx(expected)
    with pytest.raises(ValueError):
        crb_stochastic(np.ones((2, 2)), np.ones((2, 2)), np.eye(2), 1.0, 1)


@pytest.mark.parametrize("true_order", [0, 1, 2, 3])
def test_mdl_counts_sources(ula8, true_order):
    angles = [-25.0, 0.0, 40.0][:true_order] or [0.0]
    powers = [3.0] * true_order or [0.0]
    hits = sum(
        estimate_order_mdl(
            compute_covariance_matrix(
                simulate_array_snapshots(ula8, WAVELENGTH, angles, powers, 300, rng=s).X
            ),
            300,
        )
        == true_order
        for s in range(50)
    )
    assert hits >= 48


def test_aic_is_at_least_as_sensitive_as_mdl(ula8):
    R = compute_covariance_matrix(complex_noise((8, 100), 1.0, 0))
    assert estimate_order_aic(R, 100) >= estimate_order_mdl(R, 100)


def test_diagonal_loading_breaks_order_estimation(ula8):
    """Erratum E3: the course pipeline counts sources on the loaded covariance."""
    scene = simulate_array_snapshots(
        ula8, WAVELENGTH, [0, -25, 40], [1, 10**3.5, 10**3.5], 128, rng=0
    )
    R = compute_covariance_matrix(scene.X)
    loaded = R + 1e-2 * np.trace(R).real / 8 * np.eye(8)
    assert estimate_order_mdl(R, 128) == 3
    assert estimate_order_mdl(loaded, 128) < 3


def test_music_needs_smoothing_for_coherent_paths(ula8):
    s = qpsk(1000, 4, rng=0)
    X = multipath_snapshots(ula8, WAVELENGTH, s, [Path(-20.0), Path(25.0, 0.0, 0.8j)])
    X = X + complex_noise(X.shape, 0.01, 1)
    R = compute_covariance_matrix(X)
    smoothed = spatial_smoothing(R, 6)
    np.testing.assert_allclose(np.degrees(root_music(smoothed, 2)), [-20, 25], atol=0.3)
    assert np.max(np.abs(np.degrees(root_music(R, 2)) - [-20, 25])) > 2


def test_peaks_are_local_maxima():
    """Erratum E4: the two largest samples here belong to the same peak."""
    x = np.arange(0, 100.0)
    spectrum = 10 * np.exp(-(((x - 30.3) / 8) ** 2)) + 2 * np.exp(-(((x - 70) / 4) ** 2)) + 1e-3
    np.testing.assert_allclose(find_spectrum_peaks(x, spectrum, 2), [30.3, 70], atol=0.01)
    assert find_spectrum_peaks(x, spectrum, 5).size == 2
    assert find_spectrum_peaks(x, spectrum, 2, min_separation=60).size == 1


def test_source_count_validation():
    for count in (-1, 4):
        with pytest.raises(ValueError):
            noise_subspace(np.eye(4), count)
    with pytest.raises(ValueError):
        esprit(np.eye(4), 4)
    assert esprit(np.eye(4), 0).size == root_music(np.eye(4), 0).size == 0


def test_interference_detector_operating_point(ula4):
    detector = InterferenceDetector(ula4, WAVELENGTH, 128, false_alarm_rate=1e-2, rng=0)
    false_alarms = np.mean(
        [detector.detect(complex_noise((4, 128), 1.0, 10_000 + i)).detected for i in range(2000)]
    )
    assert 0.002 < false_alarms < 0.02
    # a pure gain change must not trigger it
    assert not detector.detect(1000 * complex_noise((4, 128), 1.0, 3)).detected
    result = detector.detect(simulate_array_snapshots(ula4, WAVELENGTH, [20], [1.0], 128, rng=1).X)
    assert result.detected and result.num_sources == 1
    assert result.angles_deg[0] == pytest.approx(20, abs=2)
    with pytest.raises(ValueError):
        detector.detect(np.ones((4, 10)))
    with pytest.raises(ValueError):
        calibrate_threshold(4, 16, 1e-3, trials=100)


def test_tracking_a_moving_interferer(ula4):
    result = run_tracking(ula4, TrackingConfig(num_blocks=60), rng=0)
    mean = {k: v[10:].mean() for k, v in result.sinr_db.items()}
    best = result.optimum_db[10:].mean()
    assert all(value < best + 1e-9 for value in mean.values())
    for adaptive in ("SMI", "recursive", "RLS"):
        assert mean[adaptive] > mean["DAS"] + 10
        assert mean[adaptive] > mean["frozen"] + 10
    assert len(result.interferer_angle_deg) == 60
