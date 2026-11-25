import numpy as np
import pytest

from dsp import calibration, fft, filters
from dsp import signal_metrics as sm
from dsp.covariance_matrix import (
    RecursiveCovariance,
    compute_covariance_matrix,
    diagonal_loading,
    forward_backward,
    loading_level,
    spatial_smoothing,
)
from dsp.steering import ula_steering_vector
from examples.common import WAVELENGTH
from simulations.channels.awgn import complex_noise
from simulations.channels.interference_models import qpsk
from simulations.scenarios.array_snapshots import random_channel_gains, simulate_array_snapshots


def test_covariance_matches_definition():
    X = complex_noise((3, 50), 1.0, rng=0)
    R = sum(np.outer(x, x.conj()) for x in X.T) / 50
    np.testing.assert_allclose(compute_covariance_matrix(X), R, atol=1e-14)
    for bad in (np.zeros(3), np.zeros((3, 0))):
        with pytest.raises(ValueError):
            compute_covariance_matrix(bad)


def test_loading():
    R = np.diag([1.0, 3.0]).astype(complex)
    assert loading_level(R, 0.1) == pytest.approx(0.2)
    np.testing.assert_allclose(np.diag(diagonal_loading(R, 0.5)).real, [1.5, 3.5])
    with pytest.raises(ValueError):
        diagonal_loading(R, -1)


def test_forward_backward_leaves_ideal_ula_covariance_unchanged():
    a = ula_steering_vector(0.3, 6)
    R = np.outer(a, a.conj()) + 0.1 * np.eye(6)
    np.testing.assert_allclose(forward_backward(R), R, atol=1e-12)


def test_spatial_smoothing_bounds():
    for size in (1, 5):
        with pytest.raises(ValueError):
            spatial_smoothing(np.eye(4), size)
    np.testing.assert_allclose(spatial_smoothing(np.eye(4), 3), np.eye(3))


def test_recursive_covariance():
    rec = RecursiveCovariance(2, beta=0.5)
    with pytest.raises(RuntimeError):
        _ = rec.value
    X1, X2 = complex_noise((2, 8), 1.0, 0), complex_noise((2, 8), 1.0, 1)
    R1, R2 = compute_covariance_matrix(X1), compute_covariance_matrix(X2)
    np.testing.assert_allclose(rec.update(X1), R1)
    np.testing.assert_allclose(rec.update(X2), (0.25 * R1 + 0.5 * R2) / 0.75)
    with pytest.raises(ValueError):
        rec.update(np.ones((3, 4)))
    with pytest.raises(ValueError):
        RecursiveCovariance(2, beta=1.0)


def test_psd_matches_scipy_and_parseval():
    signal = pytest.importorskip("scipy.signal")
    x = complex_noise(8192, 2.0, 0) + np.exp(2j * np.pi * 0.2 * np.arange(8192))
    f, psd = fft.power_spectral_density(x, 1000.0, 256)
    assert f[np.argmax(psd)] == pytest.approx(200, abs=4)
    assert psd.sum() * 1000 / 256 == pytest.approx(sm.signal_power(x), rel=0.02)
    _, reference = signal.welch(x, 1000.0, "hann", 256, 128, return_onesided=False, detrend=False)
    np.testing.assert_allclose(psd, np.fft.fftshift(reference), rtol=1e-9)


def test_fft_input_validation():
    with pytest.raises(ValueError):
        fft.stft(np.ones(10), 256)
    with pytest.raises(ValueError):
        fft.get_window("kaiser", 8)
    with pytest.raises(ValueError):
        fft.frame_signal(np.ones(10), 4, 0)
    assert fft.stft(np.ones((4, 1024)), 256).shape == (4, 7, 256)


def test_fir_lowpass_response():
    taps = filters.fir_lowpass(101, 0.1)
    np.testing.assert_allclose(taps, taps[::-1])  # linear phase
    H = np.abs(np.fft.fft(taps, 4096))
    f = np.arange(4096) / 4096
    assert 20 * np.log10(H[(f > 0.14) & (f < 0.5)].max()) < -50
    assert abs(20 * np.log10(H[f < 0.06])).max() < 0.05
    for args in ((100, 0.1), (101, 0.6)):
        with pytest.raises(ValueError):
            filters.fir_lowpass(*args)


def test_filtering_preserves_interchannel_phase():
    a = ula_steering_vector(0.5, 4)
    x = np.outer(a, np.exp(2j * np.pi * 0.02 * np.arange(400)))
    y = filters.fir_filter(x, filters.fir_lowpass(31, 0.2))[:, 60:]
    np.testing.assert_allclose(y / y[0], np.broadcast_to(a[:, None], y.shape), atol=1e-12)


def test_decimation_rejects_aliases():
    n = np.arange(4096)
    keep, alias = np.exp(2j * np.pi * 0.02 * n), np.exp(2j * np.pi * 0.27 * n)
    assert sm.signal_power(filters.decimate(keep, 4)[50:-50]) == pytest.approx(1, abs=0.01)
    assert sm.signal_power(filters.decimate(alias, 4)[50:-50]) < 1e-4
    assert filters.decimate(keep, 1).size == 4096
    with pytest.raises(ValueError):
        filters.decimate(keep, 0)


def test_frequency_shift_and_dc_removal():
    x = filters.frequency_shift(np.ones(64), 8, 64)
    assert np.argmax(np.abs(np.fft.fft(x))) == 8
    assert np.abs(filters.remove_dc(np.ones((2, 8)) * [[1], [2j]])).max() < 1e-15


def test_metrics_on_known_patterns(ula8):
    a = ula8.compute_steering_vector(0, WAVELENGTH)
    angles = np.arange(-90, 90.05, 0.05)
    A = ula8.compute_steering_matrix(angles, WAVELENGTH, "deg")
    gain = np.abs(sm.beam_response(a / 8, A)) ** 2
    # textbook values for a uniform 8-element half-wavelength array
    assert sm.half_power_beamwidth(angles, gain) == pytest.approx(12.8, abs=0.1)
    assert sm.peak_sidelobe_db(gain) == pytest.approx(-12.8, abs=0.1)
    assert sm.white_noise_gain(a / 8, a) == pytest.approx(8)
    assert np.isnan(sm.half_power_beamwidth(angles, np.ones_like(angles)))
    assert np.isnan(sm.peak_sidelobe_db(np.array([0.1, 1.0, 0.1])))


def test_sinr_bound(ula8):
    A = ula8.compute_steering_matrix([0, 23], WAVELENGTH, "deg")
    R = sm.scene_covariance(A[:, 1:], [100.0], 1.0)
    best = sm.optimal_sinr(A[:, 0], 1.0, R)
    w = np.linalg.solve(R, A[:, 0])
    assert sm.output_sinr(w, A[:, 0], 1.0, R) == pytest.approx(best)
    assert sm.output_sinr(A[:, 0], A[:, 0], 1.0, R) < best < 8.0


def test_evm_and_angle_rmse():
    ref = qpsk(1000, 1, rng=0)
    assert sm.error_vector_magnitude(ref * 3 * np.exp(1j), ref) == pytest.approx(0, abs=1e-12)
    assert sm.angle_rmse([10, -5], [-5, 11]) == pytest.approx(np.sqrt(0.5))
    with pytest.raises(ValueError):
        sm.angle_rmse([1], [1, 2])


def test_calibration_recovers_channel_errors(ula8):
    g = random_channel_gains(8, rng=3)
    scene = simulate_array_snapshots(
        ula8, WAVELENGTH, [12.0], [100.0], 1000, 1.0, rng=0, channel_gains=g
    )
    a = ula8.compute_steering_vector(12.0, WAVELENGTH, "deg")
    estimate = calibration.estimate_calibration(scene.X, a)
    gain_db, phase_deg = calibration.calibration_residual(estimate, g)
    assert gain_db < 0.05 and phase_deg < 0.5
    raw_gain, raw_phase = calibration.calibration_residual(np.ones(8), g)
    assert raw_gain > 0.5 and raw_phase > 10
    corrected = calibration.apply_calibration(scene.X, estimate)
    # The correction only matters if it makes the physics right again.
    R = compute_covariance_matrix(corrected)
    u = np.linalg.eigh(R)[1][:, -1]
    assert abs(np.vdot(u, a)) ** 2 / 8 > 0.9999


def test_calibration_rejects_dead_channels():
    with pytest.raises(ValueError):
        calibration.apply_calibration(np.ones((2, 4)), [1, 0])
    X = np.vstack((np.zeros(50), complex_noise((1, 50), 1.0, 0)))
    with pytest.raises(ValueError):
        calibration.estimate_calibration(X, np.ones(2))
