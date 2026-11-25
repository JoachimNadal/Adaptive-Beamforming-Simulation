import numpy as np
import pytest

from ai.datasets.generator import CLASSES, generate_dataset, make_example, waveform
from ai.interference.realtime_classifier import (
    UNKNOWN,
    RealtimeClassifier,
    baseline_classifier,
)
from ai.preprocessing.iq_to_fft import iq_to_log_spectrum
from ai.preprocessing.normalization import standardize, unit_power
from ai.preprocessing.spectrograms import classifier_input, spectrogram_db
from ai.training import metrics
from ai.training.baseline import FEATURES, LinearDiscriminant, extract_features
from dsp.signal_metrics import signal_power
from simulations.channels.awgn import make_rng


def test_dataset_is_balanced_reproducible_and_calibrated():
    data = generate_dataset(20, rng=0)
    assert len(data) == 20 * len(CLASSES)
    np.testing.assert_array_equal(np.bincount(data.labels), 20)
    np.testing.assert_array_equal(data.iq, generate_dataset(20, rng=0).iq)
    assert np.all(np.isnan(data.snr_db) == (data.labels == CLASSES.index("noise")))
    power = np.mean([signal_power(make_example("cw", 1024, 10.0, s)) for s in range(50)])
    assert power == pytest.approx(11.0, rel=0.02)  # 10 dB over unit noise
    with pytest.raises(ValueError):
        waveform("ofdm", 64, make_rng(0))


def test_features_do_not_depend_on_level_or_phase():
    x = make_example("chirp", 1024, 10.0, 0)
    scaled = 1e3 * np.exp(1j) * x
    np.testing.assert_allclose(classifier_input(x), classifier_input(scaled), atol=1e-2)
    np.testing.assert_allclose(iq_to_log_spectrum(x), iq_to_log_spectrum(scaled), atol=1e-3)
    np.testing.assert_allclose(extract_features(x), extract_features(scaled), atol=1e-4)


def test_spectrogram_shape_and_content():
    n = np.arange(1024)
    s = spectrogram_db(np.exp(2j * np.pi * 8 / 64 * n))
    assert s.shape == (61, 64)
    assert np.all(np.argmax(s, axis=1) == 32 + 8)
    z = classifier_input(np.ones((3, 1024), dtype=complex))
    assert z.shape == (3, 61, 64) and z.dtype == np.float32
    assert not np.any(np.isnan(z))


def test_normalization_handles_silence():
    assert np.all(unit_power(np.zeros((2, 8))) == 0)
    assert np.all(standardize(np.ones((1, 4, 4))) == 0)
    assert signal_power(unit_power(np.arange(8) + 1j)) == pytest.approx(1)


def test_metrics_on_known_confusion():
    labels, predictions = [0, 0, 1, 1, 1, 2], [0, 1, 1, 1, 0, 2]
    m = metrics.confusion_matrix(labels, predictions, 4)
    assert m.tolist() == [[1, 1, 0, 0], [1, 2, 0, 0], [0, 0, 1, 0], [0, 0, 0, 0]]
    precision, recall, f1 = metrics.precision_recall_f1(m)
    np.testing.assert_allclose(precision, [0.5, 2 / 3, 1, 0])
    np.testing.assert_allclose(recall, [0.5, 2 / 3, 1, 0])
    np.testing.assert_allclose(f1, [0.5, 2 / 3, 1, 0], atol=1e-9)
    assert metrics.accuracy(labels, predictions) == pytest.approx(4 / 6)
    snr = np.array([0, 1, 2, 3, 4, np.nan])
    by_snr = metrics.accuracy_by_snr(labels, predictions, snr, [0, 2, 5, 9])
    np.testing.assert_allclose(by_snr, [0.5, 2 / 3, np.nan])


def test_baseline_is_far_above_chance():
    train, test = generate_dataset(200, rng=1), generate_dataset(60, rng=3)
    features = extract_features(train.iq)
    assert features.shape == (len(train), len(FEATURES))
    model = LinearDiscriminant().fit(features, train.labels)
    assert metrics.accuracy(test.labels, model.predict(extract_features(test.iq))) > 0.85


def fake(probabilities):
    return lambda iq: np.tile(probabilities, (len(iq), 1))


def test_realtime_classifier_windows_and_smoothing():
    p = np.eye(len(CLASSES))
    outputs = iter([p[1], p[1], p[2], p[2], p[2]])
    rt = RealtimeClassifier(lambda iq: next(outputs)[None], 64, 32, smoothing=3, threshold=0.6)
    assert rt.push(np.ones(63)) == []
    labels = [d.label for chunk in (1, 32, 32, 32, 32) for d in rt.push(np.ones(chunk))]
    assert labels == ["cw", "cw", "cw", "chirp", "chirp"]


def test_realtime_classifier_reports_unknown_and_resets():
    rt = RealtimeClassifier(fake(np.full(len(CLASSES), 1 / len(CLASSES))), 64, 64)
    assert rt.push(np.ones(64))[0].label == UNKNOWN
    rt.push(np.ones(10))
    rt.reset()
    assert rt.push(np.ones(63)) == []


@pytest.mark.parametrize("kwargs", [{"hop": 0}, {"hop": 2000}, {"threshold": 2}, {"smoothing": 0}])
def test_realtime_classifier_validation(kwargs):
    with pytest.raises(ValueError):
        RealtimeClassifier(fake([1.0]), **kwargs)


def test_realtime_classifier_rejects_nan():
    with pytest.raises(ValueError):
        RealtimeClassifier(fake([1.0])).push([np.nan])


def test_baseline_classifier_recognises_easy_signals():
    classify = baseline_classifier(per_class=150)
    for name in ("noise", "cw", "pulsed"):
        probabilities = classify(make_example(name, 1024, 15.0, 5)[None])
        assert CLASSES[int(np.argmax(probabilities))] == name
        assert probabilities.sum() == pytest.approx(1)


@pytest.mark.torch
def test_cnn_trains_saves_and_predicts(tmp_path):
    """Smoke test of the whole chain; accuracy is measured by ai.training.evaluate."""
    torch = pytest.importorskip("torch")
    from ai.interference.realtime_classifier import cnn_classifier
    from ai.training.evaluate import evaluate, load_model
    from ai.training.model import count_parameters
    from ai.training.train import train

    model, history = train(per_class=40, epochs=2, batch_size=32, log=lambda _: None)
    assert history[-1]["loss"] < history[0]["loss"]
    assert count_parameters(model) < 30_000
    torch.save(model.state_dict(), tmp_path / "m.pt")
    report = evaluate(load_model(tmp_path / "m.pt"), per_class=10)
    assert 0 <= report["cnn"]["accuracy"] <= 1
    assert np.sum(report["cnn"]["confusion"]) == 60
    p = cnn_classifier(tmp_path / "m.pt")(make_example("cw", 1024, 10, 0)[None])
    assert p.shape == (1, len(CLASSES)) and p.sum() == pytest.approx(1)
