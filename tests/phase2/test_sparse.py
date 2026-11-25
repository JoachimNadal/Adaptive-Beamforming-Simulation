import numpy as np
import pytest

from dsp.signal_metrics import scene_covariance
from examples.common import WAVELENGTH
from research.sparse import arrays as sp
from research.sparse.run import simulate, trial_success
from simulations.doa.crb import crb_stochastic


def test_known_coarrays():
    assert sp.coarray((0, 1, 4, 6)).tolist() == [4, 1, 1, 1, 1, 1, 1]  # perfect ruler
    assert sp.contiguous((0, 1, 4, 6)) == 6
    assert sp.contiguous((0, 1, 2, 5)) == 5
    assert sp.contiguous((0, 2, 5)) == 0  # lag 1 missing
    assert sp.contiguous(sp.GEOMETRIES["nested-8"]) == 19
    assert sp.contiguous(sp.GEOMETRIES["MRA-8"]) == 23


def test_steering_matches_the_array_class():
    positions = (0, 1, 4, 6)
    a = sp.make_array(positions).compute_steering_vector(0.3, WAVELENGTH)
    np.testing.assert_allclose(sp.steering(positions, 0.3)[:, 0], a, atol=1e-12)


@pytest.mark.parametrize("positions", [(0, 1, 4, 6), (0, 1, 2, 5), tuple(range(5))])
def test_virtual_covariance_is_exact_for_uncorrelated_sources(positions):
    thetas, powers = np.radians([-30, 10, 45]), np.array([1.0, 2.0, 0.5])
    R = scene_covariance(sp.steering(positions, thetas), powers, 0.3)
    m = sp.contiguous(positions)
    expected = scene_covariance(sp.steering(np.arange(m + 1), thetas), powers, 0.3)
    np.testing.assert_allclose(sp.virtual_covariance(R, positions), expected, atol=1e-12)


def test_more_sources_than_elements_with_the_exact_covariance():
    thetas = np.radians([-50, -25, 0, 25, 50])
    R = scene_covariance(sp.steering((0, 1, 4, 6), thetas), np.full(5, 10.0), 1.0)
    np.testing.assert_allclose(sp.coarray_music(R, (0, 1, 4, 6), 5), np.degrees(thetas), atol=1e-3)


def test_crb_agrees_with_the_classical_bound_for_few_sources():
    """With L < N the uncorrelated-source bound cannot exceed the one of study 1."""
    positions, thetas = tuple(range(8)), np.radians([-20, 15])
    A = sp.steering(positions, thetas)
    D = -1j * np.pi * np.arange(8)[:, None] * np.cos(thetas) * A
    classical = np.diag(crb_stochastic(A, D, 5 * np.eye(2), 1.0, 100))
    ours = sp.crb(positions, thetas, np.full(2, 5.0), 1.0, 100)
    assert np.all(ours <= classical * 1.0001)
    np.testing.assert_allclose(ours, classical, rtol=0.05)


def test_crb_exists_beyond_the_number_of_elements_only_for_sparse_arrays():
    thetas = np.radians([-50, -25, 0, 25, 50])
    assert np.all(np.isfinite(sp.crb((0, 1, 4, 6), thetas, np.full(5, 10.0), 1.0, 100)))
    assert np.all(np.isnan(sp.crb((0, 1, 2, 3), thetas, np.full(5, 10.0), 1.0, 100)))


def test_imperfections_change_the_data():
    base = simulate((0, 1, 4, 6), [0, 20], np.ones(2), 50, np.random.default_rng(0))
    for option in ({"phase": 5}, {"position_error": 0.01}, {"coupling": 0.1}):
        other = simulate((0, 1, 4, 6), [0, 20], np.ones(2), 50, np.random.default_rng(0), **option)
        assert other.shape == base.shape and not np.allclose(other, base)


def test_trial_success_reports_the_probe_result():
    result = trial_success((0, 1, 4, 6), np.array([-50.0, -25, 0, 25, 50]), np.full(5, 10.0),
                           4000, 20, 0)  # fmt: skip
    assert result["success"] == 1.0 and result["rmse_deg"] < 0.3
