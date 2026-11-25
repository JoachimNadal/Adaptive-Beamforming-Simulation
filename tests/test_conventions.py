"""One phase convention, shared by signals, weights and estimators (audit D1, D2, D5-D8)."""

import numpy as np
import pytest

from dsp.adaptive_weights import das_weights
from dsp.covariance_matrix import compute_covariance_matrix
from dsp.signal_metrics import output_sinr, scene_covariance, to_db
from dsp.steering import steering_derivative, to_radians, ula_steering_vector
from examples.common import WAVELENGTH
from simulations.antenna_array.circular_array import CircularArray
from simulations.antenna_array.linear_array import LinearArray
from simulations.beamforming.mvdr import MVDRBeamformer
from simulations.doa.capon import bartlett_spectrum
from simulations.doa.esprit import esprit
from simulations.doa.music import root_music
from simulations.scenarios.multi_source import simulate_multi_source_snapshot
from simulations.scenarios.single_source import simulate_single_source_snapshot
from simulations.scenarios.snapshot_generator import generate_snapshot_matrix
from simulations.scenarios.spatiotemporal_signal import simulate_spatiotemporal_sources


def test_published_steering_vector(ula4):
    a = ula4.compute_steering_vector(30, WAVELENGTH, "deg")
    np.testing.assert_allclose(a, [1, -1j, -1, 1j], atol=1e-12)
    np.testing.assert_allclose(a, ula_steering_vector(np.radians(30), 4), atol=1e-12)


def _generators(array, angle):
    """One noise-free source at ``angle`` from every generator of the project."""
    t = np.linspace(0, 1, 64)
    common = dict(antenna_array=array, wavelength=WAVELENGTH, noise_power=0.0)
    two = dict(
        desired_angle=angle, interference_angle=0, desired_amplitude=1, interference_amplitude=0
    )
    yield simulate_single_source_snapshot(angle=angle, **common)[:, None]
    yield simulate_multi_source_snapshot(**two, **common)[:, None]
    yield generate_snapshot_matrix(num_snapshots=16, rng=0, **two, **common)
    yield simulate_spatiotemporal_sources(
        time_vector=t, desired_frequency=3, interference_frequency=7, **two, **common
    )


@pytest.mark.parametrize("angle", [-50.0, 20.0, 35.0])
def test_every_generator_agrees_with_every_estimator(ula8, angle):
    grid = np.arange(-90, 90.5, 0.5)
    A = ula8.compute_steering_matrix(grid, WAVELENGTH, "deg")
    for X in _generators(ula8, angle):
        R = compute_covariance_matrix(X)
        assert grid[np.argmax(bartlett_spectrum(R, A))] == angle
        R = R + 1e-6 * np.eye(8)
        assert np.degrees(root_music(R, 1)[0]) == pytest.approx(angle, abs=1e-3)
        assert np.degrees(esprit(R, 1)[0]) == pytest.approx(angle, abs=1e-3)


def test_mvdr_output_sinr_on_the_simulated_signal(ula4):
    """The check missing from the original MVDR test: it measured -28 dB on this scene."""
    X = simulate_spatiotemporal_sources(
        antenna_array=ula4,
        wavelength=WAVELENGTH,
        time_vector=np.linspace(0, 1, 5000),
        desired_angle=20,
        interference_angle=-40,
        desired_frequency=5,
        interference_frequency=12,
        desired_amplitude=1.0,
        interference_amplitude=0.8,
        noise_power=0.04,
        rng=1,
    )
    w = MVDRBeamformer(ula4).compute_weights(compute_covariance_matrix(X), 20, WAVELENGTH)
    A = ula4.compute_steering_matrix([20, -40], WAVELENGTH, "deg")
    sinr = to_db(output_sinr(w, A[:, 0], 1.0, scene_covariance(A[:, 1:], [0.64], 0.04)))
    assert sinr == pytest.approx(20.0, abs=0.5)


def test_unknown_units_are_rejected(ula4):
    with pytest.raises(ValueError, match="unite"):
        ula4.compute_steering_vector(1.0, WAVELENGTH, "degrees")
    assert to_radians(180, "deg") == pytest.approx(np.pi)


@pytest.mark.parametrize("unite, angle", [("deg", 20.0), ("rad", np.radians(20.0))])
def test_pattern_peak_does_not_depend_on_unit(ula4, unite, angle):
    angles, gain = MVDRBeamformer(ula4).compute_beam_pattern(
        np.eye(4), angle, WAVELENGTH, unite=unite
    )
    assert angles[np.argmax(gain)] == pytest.approx(20.0)


def test_circular_array_covers_full_azimuth():
    array = CircularArray.from_spacing(8, WAVELENGTH / 2)
    chord = np.linalg.norm(array.positions_xy[1] - array.positions_xy[0])
    assert chord == pytest.approx(WAVELENGTH / 2)
    grid = np.arange(-180, 180, 1.0)
    A = array.compute_steering_matrix(grid, WAVELENGTH, "deg")
    for angle in (-150.0, -10.0, 95.0):
        w = das_weights(array.compute_steering_vector(angle, WAVELENGTH, "deg"))
        assert grid[np.argmax(np.abs(w.conj() @ A))] == angle


@pytest.mark.parametrize("array", [LinearArray(5, 6.0), CircularArray(5, 6.0)])
def test_steering_derivative_matches_finite_difference(array):
    theta, h = 0.4, 1e-6
    numeric = (
        array.compute_steering_vector(theta + h, WAVELENGTH)
        - array.compute_steering_vector(theta - h, WAVELENGTH)
    ) / (2 * h)
    np.testing.assert_allclose(
        array.compute_steering_derivative(theta, WAVELENGTH), numeric, atol=1e-7
    )
    assert steering_derivative(np.arange(3), 0.1, 1.0).shape == (3, 1)


def test_invalid_geometry_is_rejected():
    with pytest.raises(ValueError):
        LinearArray(0, 1.0)
    with pytest.raises(ValueError):
        CircularArray(2, 1.0)
    with pytest.raises(ValueError):
        LinearArray(2, 1.0).compute_steering_vector(0.0, -1.0)
