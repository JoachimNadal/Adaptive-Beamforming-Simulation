"""Beamformers checked against theory, not against their own output."""

import numpy as np
import pytest

from dsp.adaptive_weights import (
    IllConditionedError,
    das_weights,
    lcmv_weights,
    mvdr_weights,
    null_steering_weights,
    rls_update,
)
from dsp.covariance_matrix import compute_covariance_matrix
from dsp.signal_metrics import (
    null_depth_db,
    optimal_sinr,
    output_sinr,
    scene_covariance,
    to_db,
    white_noise_gain,
)
from examples.common import WAVELENGTH
from simulations.beamforming.delay_and_sum import DelayAndSumBeamformer
from simulations.beamforming.lcmv import LCMVBeamformer
from simulations.beamforming.lms import LMSBeamformer, NLMSBeamformer
from simulations.beamforming.mvdr import MVDRBeamformer
from simulations.beamforming.null_steering import NullSteeringBeamformer
from simulations.beamforming.rls import RLSBeamformer
from simulations.channels.interference_models import qpsk
from simulations.scenarios.array_snapshots import simulate_array_snapshots


def test_mvdr_equals_theoretical_optimum(ula8):
    A = ula8.compute_steering_matrix([0, -25, 40], WAVELENGTH, "deg")
    R = scene_covariance(A, [1, 3162, 3162], 1.0)
    R_in = scene_covariance(A[:, 1:], [3162, 3162], 1.0)
    w = mvdr_weights(R, A[:, 0])
    assert output_sinr(w, A[:, 0], 1, R_in) == pytest.approx(optimal_sinr(A[:, 0], 1, R_in))
    assert np.vdot(w, A[:, 0]) == pytest.approx(1)  # distortionless


def test_course_reference_scene_is_bounded(ula8):
    """Course 24.8 prints 18-22 dB; no weights can exceed N * SNR = 9.03 dB (erratum E2)."""
    A = ula8.compute_steering_matrix([0, -25, 40], WAVELENGTH, "deg")
    R_in = scene_covariance(A[:, 1:], [10**3.5] * 2, 1.0)
    assert to_db(optimal_sinr(A[:, 0], 1.0, R_in)) == pytest.approx(8.79, abs=0.01)


def test_mvdr_limits(ula8):
    a = ula8.compute_steering_vector(10, WAVELENGTH, "deg")
    b = ula8.compute_steering_vector(-30, WAVELENGTH, "deg")
    R = scene_covariance(b[:, None], [100.0], 1.0)
    np.testing.assert_allclose(mvdr_weights(np.eye(8), a), das_weights(a), atol=1e-12)
    np.testing.assert_allclose(mvdr_weights(R, a, loading=1e9), das_weights(a), atol=1e-6)


def test_mvdr_refuses_rank_deficient_covariance(ula4):
    """Audit D9: K < N used to return meaningless weights."""
    X = simulate_array_snapshots(ula4, WAVELENGTH, [0], [1.0], 2, rng=0).X
    R = compute_covariance_matrix(X)
    with pytest.raises(IllConditionedError):
        MVDRBeamformer(ula4).compute_weights(R, 0, WAVELENGTH)
    w = MVDRBeamformer(ula4, relative_loading=0.1).compute_weights(R, 0, WAVELENGTH)
    assert np.vdot(w, w).real <= 1.0
    with pytest.raises(ValueError):
        mvdr_weights(R, np.ones(4), loading=-1)
    with pytest.raises(ValueError):
        mvdr_weights(np.full((4, 4), np.nan), np.ones(4))


def test_smi_loss_follows_reed_mallett_brennan(ula8):
    """Mean SINR loss with signal-free snapshots is (K - N + 2) / (K + 1)."""
    A = ula8.compute_steering_matrix([0, -25], WAVELENGTH, "deg")
    R_in = scene_covariance(A[:, 1:], [1000.0], 1.0)
    best = optimal_sinr(A[:, 0], 1.0, R_in)
    K = 16
    ratios = []
    for seed in range(1500):
        X = simulate_array_snapshots(ula8, WAVELENGTH, [-25], [1000.0], K, rng=seed).X
        w = mvdr_weights(compute_covariance_matrix(X), A[:, 0])
        ratios.append(output_sinr(w, A[:, 0], 1.0, R_in) / best)
    assert np.mean(ratios) == pytest.approx((K - 8 + 2) / (K + 1), abs=0.01)


def test_lcmv_generalises_mvdr_and_null_steering(ula8):
    A = ula8.compute_steering_matrix([0, -25, 40], WAVELENGTH, "deg")
    R = scene_covariance(A, [1, 100, 100], 1.0)
    np.testing.assert_allclose(lcmv_weights(R, A[:, :1], [1]), mvdr_weights(R, A[:, 0]))
    f = [1, 0, 0]
    np.testing.assert_allclose(
        lcmv_weights(np.eye(8), A, f), null_steering_weights(A, f), atol=1e-12
    )
    w = LCMVBeamformer(ula8).compute_weights(R, 0, WAVELENGTH, [-25, 40])
    np.testing.assert_allclose(A.conj().T @ w, f, atol=1e-10)
    angles, gain = LCMVBeamformer(ula8).compute_beam_pattern(R, 0, WAVELENGTH, [-25, 40])
    assert gain[angles == -25][0] < 1e-18


def test_centred_derivative_constraint_costs_no_array_gain(ula8):
    """Erratum E7: referenced to element 0 the same constraint loses 5.2 dB."""
    beamformer = LCMVBeamformer(ula8, derivative_constraint=True)
    a = ula8.compute_steering_vector(0, WAVELENGTH, "deg")
    w = beamformer.compute_weights(np.eye(8), 0, WAVELENGTH)
    assert white_noise_gain(w, a) == pytest.approx(8.0)
    d = ula8.compute_steering_derivative(0, WAVELENGTH)
    edge = lcmv_weights(np.eye(8), np.column_stack((a, d)), [1, 0])
    assert to_db(white_noise_gain(edge, a)) == pytest.approx(3.80, abs=0.01)


def test_derivative_constraint_protects_against_pointing_error(ula8):
    """A 1 degree error on a strong target costs MVDR almost 20 dB (self-cancellation)."""
    true = ula8.compute_steering_matrix([1.0, -25, 40], WAVELENGTH, "deg")
    R = scene_covariance(true, [10, 1000, 1000], 1.0)
    R_in = scene_covariance(true[:, 1:], [1000, 1000], 1.0)
    best = to_db(optimal_sinr(true[:, 0], 10, R_in))

    def loss(weights):
        return best - to_db(output_sinr(weights, true[:, 0], 10, R_in))

    assert loss(MVDRBeamformer(ula8).compute_weights(R, 0, WAVELENGTH)) > 15
    robust = LCMVBeamformer(ula8, derivative_constraint=True)
    assert loss(robust.compute_weights(R, 0, WAVELENGTH)) < 1.5


def test_lcmv_validation(ula4):
    C = ula4.compute_steering_matrix(np.linspace(-60, 60, 5), WAVELENGTH, "deg")
    for solver in (lambda: lcmv_weights(np.eye(4), C, np.ones(5)),
                   lambda: null_steering_weights(C, np.ones(5)),
                   lambda: lcmv_weights(np.eye(4), C[:, :1], [1], loading=-1)):  # fmt: skip
        with pytest.raises(ValueError):
            solver()


def test_null_steering_multiple_and_coincident(ula8):
    beamformer = NullSteeringBeamformer(ula8)
    w = beamformer.compute_weights(20, [-40, -10, 60], WAVELENGTH)
    A = ula8.compute_steering_matrix([20, -40, -10, 60], WAVELENGTH, "deg")
    np.testing.assert_allclose(np.abs(w.conj() @ A), [1, 0, 0, 0], atol=1e-12)
    assert null_depth_db(w, A[:, 0], A[:, 1]) < -200
    with pytest.raises(IllConditionedError):  # audit D10
        beamformer.compute_weights(20, 20, WAVELENGTH)
    angles, gain = beamformer.compute_beam_pattern(20, -40, WAVELENGTH)
    assert gain[angles == 20][0] == pytest.approx(1)


def _supervised_scene(array, num=4000, interferer_power=100.0, seed=0):
    pilot = qpsk(num, 1, rng=seed)
    jam = qpsk(num, 3, 0.11, rng=seed + 1)
    scene = simulate_array_snapshots(
        array, WAVELENGTH, [10, -35], [1.0, interferer_power], num, 0.1, seed,
        waveforms=np.stack((pilot, jam)),
    )  # fmt: skip
    return scene, pilot


def test_adaptive_filters_approach_the_optimum_sinr(ula4):
    scene, pilot = _supervised_scene(ula4)
    R_in = scene.R_interference_noise
    best = to_db(optimal_sinr(scene.A[:, 0], 1.0, R_in))
    mu = 0.3 / np.trace(scene.R).real
    for beamformer, tolerance in (
        (LMSBeamformer(ula4, mu), 3.0),
        (NLMSBeamformer(ula4, 0.05), 3.0),
        (RLSBeamformer(ula4, 0.999, 1e-2), 0.1),
    ):
        w, _ = beamformer.train(scene.X, pilot)
        assert best - to_db(output_sinr(w, scene.A[:, 0], 1.0, R_in)) < tolerance
        assert beamformer.plot_learning_curve(np.ones(3)) is not None


def test_lms_diverges_beyond_its_stability_bound(ula4):
    scene, pilot = _supervised_scene(ula4, 800)
    largest = np.linalg.eigvalsh(scene.R)[-1]
    with np.errstate(all="ignore"):
        _, unstable = LMSBeamformer(ula4, 4 / largest).train(scene.X, pilot)
        _, stable = LMSBeamformer(ula4, 0.1 / largest).train(scene.X, pilot)
    assert not np.max(unstable) < 1e6
    assert stable[-100:].mean() < 1


def test_nlms_is_insensitive_to_input_level(ula4):
    scene, pilot = _supervised_scene(ula4, 500)
    _, e1 = NLMSBeamformer(ula4, 0.5).train(scene.X, pilot)
    _, e2 = NLMSBeamformer(ula4, 0.5).train(1000 * scene.X, pilot)
    np.testing.assert_allclose(e1, e2, rtol=1e-6)


def test_rls_matches_batch_least_squares(ula4):
    scene, pilot = _supervised_scene(ula4, 200)
    lam, delta = 0.97, 0.5
    w, _ = RLSBeamformer(ula4, lam, delta).train(scene.X, pilot)
    weights = lam ** np.arange(199, -1, -1)
    R = (scene.X * weights) @ scene.X.conj().T + delta * lam**200 * np.eye(4)
    r = (scene.X * weights) @ pilot.conj()
    np.testing.assert_allclose(w, np.linalg.solve(R, r), rtol=1e-8)


@pytest.mark.parametrize("jammer_amplitude", [0.0, 100.0])
def test_rls_stays_stable_in_single_precision(ula4, jammer_amplitude):
    """Audit D11: P must remain Hermitian positive definite, as on an embedded target."""
    rng = np.random.default_rng(1)
    a = ula4.compute_steering_vector(30, WAVELENGTH, "deg")
    w, P = np.zeros(4, np.complex64), 100 * np.eye(4, dtype=np.complex64)
    for _ in range(5000):
        s, n = rng.standard_normal(2), 0.1 * rng.standard_normal((4, 2))
        x = (jammer_amplitude * a * complex(*s) + n @ [1, 1j]).astype(np.complex64)
        error = np.complex64(rng.standard_normal() - np.vdot(w, x))
        w, P = rls_update(w, P, x, error, 0.9)
    assert P.dtype == w.dtype == np.complex64
    assert np.all(np.linalg.eigvalsh(P) > 0)
    assert np.all(np.isfinite(w))


@pytest.mark.parametrize("kwargs", [{"lambda_factor": 0.0}, {"lambda_factor": 1.1}, {"delta": 0.0}])
def test_rls_parameter_validation(ula4, kwargs):
    with pytest.raises(ValueError):
        RLSBeamformer(ula4, **kwargs)


def test_plots_return_axes(ula4):
    das = DelayAndSumBeamformer(ula4)
    angles, gain = das.compute_beam_pattern(30, WAVELENGTH)
    for decibels in (False, True):
        assert das.plot_beam_pattern(angles, gain, decibels=decibels).lines
    assert das.plot_polar_beam_pattern(30, WAVELENGTH).lines
    assert ula4.plot_array() is not None
    assert ula4.plot_steering_phases(30, WAVELENGTH, "deg") is not None
