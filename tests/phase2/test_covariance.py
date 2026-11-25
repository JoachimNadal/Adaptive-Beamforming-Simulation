"""Estimators checked against their definitions and known limits."""

import numpy as np
import pytest

from dsp.covariance_matrix import compute_covariance_matrix
from dsp.signal_metrics import scene_covariance
from examples.common import WAVELENGTH, reference_array
from research.covariance import estimators as est
from research.covariance.methods import METHODS, Context
from research.covariance.run import evaluate, simulate
from simulations.channels.awgn import complex_noise, make_rng


def draw(R, k, seed):
    return np.linalg.cholesky(R) @ complex_noise((R.shape[0], k), 1.0, seed)


@pytest.fixture
def R():
    A = reference_array(6).compute_steering_matrix([0, 30], WAVELENGTH, "deg")
    return scene_covariance(A, [2.0, 20.0], 1.0)


def test_complex_wishart_moment_behind_oas(R):
    """E tr(S^2) = tr(R^2) + tr(R)^2 / K for circular complex data (real data differ)."""
    k = 5
    values = [np.linalg.norm(compute_covariance_matrix(draw(R, k, s))) ** 2 for s in range(20000)]
    expected = np.linalg.norm(R) ** 2 + np.trace(R).real ** 2 / k
    assert np.mean(values) == pytest.approx(expected, rel=0.02)


def oracle_intensity(R, k):
    """Minimiser of E||(1-r) S + r tr(S)/N I - R||^2 from the complex Wishart moments."""
    n, t1, t2 = R.shape[0], np.trace(R).real ** 2, np.linalg.norm(R) ** 2
    return (t1 - t2 / n) / ((k - 1 / n) * t2 + (1 - k / n) * t1)


def test_oracle_formula_minimises_the_monte_carlo_error(R):
    k, rhos = 8, np.linspace(0, 1, 41)
    errors = np.zeros(len(rhos))
    for seed in range(3000):
        S = compute_covariance_matrix(draw(R, k, seed))
        errors += [np.linalg.norm(est._shrink(S, r) - R) ** 2 for r in rhos]
    assert rhos[np.argmin(errors)] == pytest.approx(oracle_intensity(R, k), abs=0.03)


@pytest.mark.parametrize("k", [4, 8, 24])
def test_data_driven_shrinkage_is_close_to_the_oracle(R, k):
    X = [draw(R, k, seed) for seed in range(400)]
    errors = {
        "sample": np.mean([np.linalg.norm(compute_covariance_matrix(x) - R) ** 2 for x in X]),
        "oas": np.mean([np.linalg.norm(est.oas(x) - R) ** 2 for x in X]),
        "lw": np.mean([np.linalg.norm(est.ledoit_wolf(x) - R) ** 2 for x in X]),
        "oracle": np.mean(
            [
                np.linalg.norm(
                    est._shrink(compute_covariance_matrix(x), oracle_intensity(R, k)) - R
                )
                ** 2
                for x in X
            ]
        ),
    }
    assert errors["oracle"] <= min(errors["oas"], errors["lw"]) * 1.02
    assert errors["oas"] < errors["sample"] and errors["lw"] < errors["sample"]


def test_shrinkage_limits():
    X = complex_noise((4, 50_000), 1.0, 0)
    assert est.ledoit_wolf_intensity(X) > 0.5  # already proportional to identity
    assert est.ledoit_wolf_intensity(np.eye(1)) == 1.0
    assert est.oas_intensity(np.eye(4, dtype=complex), 10) == 1.0


def test_noise_power_is_consistent(R):
    S = compute_covariance_matrix(draw(R, 4000, 0))
    assert est.noise_power(S, 4000) == pytest.approx(1.0, rel=0.05)


def test_toeplitz_is_exact_for_uncorrelated_sources(R):
    np.testing.assert_allclose(est.toeplitz(R), R, atol=1e-10)


def test_clipping_only_raises_small_eigenvalues(R):
    S = compute_covariance_matrix(draw(R, 12, 1))
    before, after = np.linalg.eigvalsh(S), np.linalg.eigvalsh(est.clipped(S, 12))
    assert np.all(after >= before - 1e-9)
    assert after[-1] == pytest.approx(before[-1])


def test_tyler_ignores_snapshot_scale(R):
    X = draw(R, 400, 0)
    scale = 10 ** make_rng(1).uniform(-3, 3, 400)
    a, b = est.regularized_tyler(X), est.regularized_tyler(X * scale)
    np.testing.assert_allclose(a / np.trace(a), b / np.trace(b), atol=1e-4)
    # and it is proportional to R for Gaussian data
    shape = est.regularized_tyler(draw(R, 20_000, 2), rho=1e-6)
    np.testing.assert_allclose(shape / np.trace(shape), R / np.trace(R), atol=0.01)


def test_reconstruction_removes_the_target_but_keeps_the_interferer():
    c = Context(8)
    A = c.array.compute_steering_matrix([0, -25], WAVELENGTH, "deg")
    R = scene_covariance(A, [100.0, 100.0], 1.0)
    Rr = est.reconstruction(R, c.G)
    target, interferer = (np.vdot(a, Rr @ a).real for a in A.T)
    assert interferer > 20 * target


def test_every_method_returns_unit_gain_or_fails_loudly():
    c = Context(4)
    X, _, _ = simulate(c, make_rng(0), 64, 0, [(-25, 30)], {})
    for name, method in METHODS.items():
        w = method(X, c)
        assert np.vdot(w, c.a) == pytest.approx(1, abs=1e-6), name


@pytest.mark.parametrize("kind", ["gaussian", "student", "impulsive"])
def test_noise_models_have_unit_power(kind):
    c = Context(4)
    X, _, _ = simulate(c, make_rng(0), 400_000, -100, [(-25, -100)], {"noise": kind})
    assert np.mean(np.abs(X) ** 2) == pytest.approx(1.0, rel=0.05)


def test_evaluate_is_paired_and_bounded():
    result = evaluate(4, 32, 0, [(-25, 20)], trials=5, methods=["sample", "noise x10"])
    again = evaluate(4, 32, 0, [(-25, 20)], trials=5, methods=["sample", "noise x10"])
    assert result == again
    assert all(r["loss_db"] >= -1e-9 for r in result.values())
