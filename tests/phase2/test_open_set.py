import numpy as np
import pytest

from ai.datasets.generator import generate_dataset
from dsp.signal_metrics import signal_power
from research.open_set import detectors as det
from research.open_set import recordings
from research.open_set import waveforms as wf


@pytest.mark.parametrize("family", wf.FAMILIES)
def test_unseen_families_have_unit_power_and_vary(family):
    x = wf.FAMILIES[family](1024, np.random.default_rng(0))
    y = wf.FAMILIES[family](1024, np.random.default_rng(1))
    assert x.shape == (1024,) and signal_power(x) == pytest.approx(1, rel=0.02)
    assert not np.allclose(x, y)


@pytest.mark.parametrize("name", wf.IMPAIRMENTS)
def test_impairments_are_moderate_and_keep_shape(name):
    data = generate_dataset(3, rng=0)
    out = wf.impair(name, data.iq, rng=1)
    assert out.shape == data.iq.shape and out.dtype == np.complex64
    assert np.all(np.isfinite(out)) and not np.allclose(out, data.iq)
    change = signal_power(out) / signal_power(data.iq)
    assert 0.3 < change < 3


def test_extended_features_do_not_depend_on_level():
    iq = generate_dataset(4, rng=0).iq
    a, b = det.extended_features(iq), det.extended_features(1e3 * iq)
    assert np.all(np.isfinite(a))
    np.testing.assert_allclose(a, b, atol=2e-2)


def test_distance_detectors_flag_far_points():
    rng = np.random.default_rng(0)
    centres = rng.normal(0, 5, (3, 4))
    labels = rng.integers(0, 3, 600)
    x = centres[labels] + rng.standard_normal((600, 4))
    far = centres[0] + 40
    for detector in (det.ClassMahalanobis(), det.NearestNeighbours()):
        detector.fit(x, labels)
        inside = detector.score(centres[labels[:50]] + rng.standard_normal((50, 4)))
        assert detector.score(far[None])[0] > inside.max()


def test_spectrogram_residual_is_zero_inside_the_subspace():
    rng = np.random.default_rng(0)
    basis = rng.standard_normal((5, 60))
    data = (rng.standard_normal((200, 5)) @ basis).reshape(200, 6, 10).astype(np.float32)
    residual = det.SpectrogramResidual(components=8).fit(data)
    assert residual.score(data).max() < 1e-2
    assert residual.score(data + rng.standard_normal(data.shape).astype(np.float32)).min() > 5


def test_confidence_scores():
    logits = np.array([[10.0, 0, 0], [1, 1, 1]])
    assert det.softmax_score(logits)[0] < 1e-3 < det.softmax_score(logits)[1]
    assert det.energy_score(logits)[0] < det.energy_score(logits)[1]


def test_fusion_is_a_rank():
    reference = [np.arange(100.0), np.arange(100.0)]
    out = det.rank_fusion(reference, [np.array([-1.0, 1e9]), np.array([-1.0, 1e9])])
    np.testing.assert_allclose(out, [0, 1])


def test_recording_split_separates_bursts_from_noise():
    rng = np.random.default_rng(0)
    iq = 0.05 * (rng.standard_normal(40 * 1024) + 1j * rng.standard_normal(40 * 1024))
    iq[10 * 1024 : 14 * 1024] += 1.0 * np.exp(2j * np.pi * 0.1 * np.arange(4 * 1024))
    signal, noise = recordings.split(iq)
    assert len(signal) == 4 and len(noise) >= 30
    kurtosis, flatness = recordings.noise_statistics(noise)
    assert kurtosis == pytest.approx(2, abs=0.1) and flatness > -0.6


def test_git_hash_and_safe_names():
    assert recordings.git_blob_hash(b"") == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
    path = recordings.local_path("s", {"path": "../../etc/passwd"})
    assert path.parent == recordings.STORE / "s"
