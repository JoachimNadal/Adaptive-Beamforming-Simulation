import numpy as np
import pytest

from dsp.covariance_matrix import compute_covariance_matrix, spatial_smoothing
from dsp.signal_metrics import signal_power
from examples.common import WAVELENGTH
from simulations.beamforming.mvdr import MVDRBeamformer
from simulations.channels import awgn, fading, interference_models, multipath
from simulations.scenarios.multi_source import simulate_multi_source_snapshot
from simulations.scenarios.snapshot_generator import generate_snapshot_matrix
from simulations.scenarios.timeseries_snapshot_generator import (
    generate_snapshots_from_timeseries,
)


def test_noise_power_is_the_requested_one():
    """Audit D4: it used to be twice the requested value."""
    n = awgn.complex_noise(200_000, 0.02, rng=0)
    assert signal_power(n) == pytest.approx(0.02, rel=0.02)
    assert np.var(n.real) == pytest.approx(np.var(n.imag), rel=0.02)
    assert abs(np.mean(n**2)) < 2e-4  # circularity
    with pytest.raises(ValueError):
        awgn.complex_noise(1, -1.0)


def test_awgn_snr():
    x = np.exp(2j * np.pi * 0.1 * np.arange(100_000))
    noise = awgn.awgn(x, 7.0, rng=0) - x
    assert 10 * np.log10(1 / signal_power(noise)) == pytest.approx(7.0, abs=0.1)


def test_generators_are_reproducible(ula4):
    scene = dict(
        antenna_array=ula4,
        wavelength=WAVELENGTH,
        desired_angle=1,
        interference_angle=2,
        desired_amplitude=1,
        interference_amplitude=1,
        noise_power=1,
    )
    for generator, extra in (
        (simulate_multi_source_snapshot, {}),
        (generate_snapshot_matrix, {"num_snapshots": 4}),
    ):
        first, second = (generator(**scene, **extra, rng=5) for _ in range(2))
        np.testing.assert_array_equal(first, second)


@pytest.mark.parametrize("coherent, rank", [(False, 2), (True, 1)])
def test_source_coherence(ula4, coherent, rank):
    """Audit D3: sources must be uncorrelated unless coherence is asked for."""
    X = generate_snapshot_matrix(
        ula4, WAVELENGTH, 20, -25, 1.0, 0.8, 0.0, 400, rng=0, coherent=coherent
    )
    assert np.linalg.matrix_rank(compute_covariance_matrix(X), tol=1e-6) == rank


def test_mvdr_rejects_the_interferer_with_default_sources(ula4):
    """The original generator made MVDR amplify the interferer by 2.9 dB."""
    X = generate_snapshot_matrix(ula4, WAVELENGTH, 20, -25, 1.0, 0.7, 0.04, 2000, rng=0)
    R = compute_covariance_matrix(X)
    w = MVDRBeamformer(ula4).compute_weights(R, 20, WAVELENGTH)
    a = ula4.compute_steering_vector(-25, WAVELENGTH, "deg")
    assert abs(np.vdot(w, a)) ** 2 < 1e-2


def test_fading_power_and_limits():
    h = fading.rician_coefficients(100_000, 3.0, rng=0)
    assert signal_power(h) == pytest.approx(1, rel=0.02)
    np.testing.assert_allclose(np.abs(fading.rician_coefficients(100, 1e12, rng=0)), 1, atol=1e-4)
    with pytest.raises(ValueError):
        fading.rician_coefficients(1, -1.0)
    np.testing.assert_allclose(fading.apply_flat_fading(np.ones(3), 2j), [2j] * 3)


def test_doppler_fading_has_clarke_autocorrelation():
    special = pytest.importorskip("scipy.special")
    fd, lags = 0.01, np.array([0, 10, 20, 38])
    rho = np.zeros(len(lags), dtype=complex)
    for seed in range(300):
        h = fading.doppler_fading(600, fd, rng=seed)
        rho += [np.mean(h[: 600 - k].conj() * h[k:]) for k in lags]
    np.testing.assert_allclose((rho / 300).real, special.j0(2 * np.pi * fd * lags), atol=0.08)


@pytest.mark.parametrize(
    "name, kwargs",
    [
        ("cw_tone", {"frequency": 0.1}),
        ("linear_chirp", {"period": 100}),
        ("qpsk", {"frequency": 0.05}),
        ("band_limited_noise", {"bandwidth": 0.3}),
        ("pulsed", {"pulse_length": 16, "period": 64}),
    ],
)
def test_interference_waveforms_have_unit_power(name, kwargs):
    x = getattr(interference_models, name)(4096, rng=0, **kwargs)
    assert x.shape == (4096,)
    assert signal_power(x) == pytest.approx(1.0, rel=1e-6)


def test_interference_parameters_are_checked():
    with pytest.raises(ValueError):
        interference_models.band_limited_noise(64, bandwidth=1.5)
    with pytest.raises(ValueError):
        interference_models.pulsed(64, pulse_length=200, period=128)


def test_band_limited_noise_occupies_its_band():
    x = interference_models.band_limited_noise(1 << 15, 0.2, 0.1, rng=0)
    p = np.abs(np.fft.fft(x)) ** 2
    inside = np.abs(np.fft.fftfreq(x.size) - 0.1) < 0.11
    assert p[inside].sum() / p.sum() > 0.97


def test_fractional_delay():
    x = np.exp(2j * np.pi * 5 / 64 * np.arange(64))
    np.testing.assert_allclose(multipath.fractional_delay(x, 1), np.roll(x, 1), atol=1e-12)
    expected = x * np.exp(-2j * np.pi * 5 / 64 * 2.5)
    np.testing.assert_allclose(multipath.fractional_delay(x, 2.5), expected, atol=1e-12)


def test_spatial_smoothing_restores_rank_lost_by_multipath(ula8):
    s = interference_models.qpsk(512, rng=0)
    paths = [multipath.Path(-20.0), multipath.Path(25.0, 0.0, 0.9 * np.exp(1j))]
    R = compute_covariance_matrix(multipath.multipath_snapshots(ula8, WAVELENGTH, s, paths))
    assert np.linalg.matrix_rank(R, tol=1e-6) == 1
    assert np.linalg.matrix_rank(spatial_smoothing(R, 6), tol=1e-6) == 2
    with pytest.raises(ValueError):
        multipath.multipath_snapshots(ula8, WAVELENGTH, s, [])


def test_timeseries_subsampling():
    X = np.arange(20).reshape(2, 10)
    assert generate_snapshots_from_timeseries(X, 3).shape == (2, 4)
    with pytest.raises(ValueError):
        generate_snapshots_from_timeseries(X[0])
    with pytest.raises(ValueError):
        generate_snapshots_from_timeseries(X, 0)
