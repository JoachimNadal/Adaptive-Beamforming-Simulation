"""Streaming interference classification over a sliding window.

Any callable mapping a ``(1, window)`` IQ array to class probabilities can be plugged in, so
this module does not require PyTorch; :func:`cnn_classifier` builds one from a checkpoint.
"""

from collections import deque
from dataclasses import dataclass

import numpy as np

from ai.datasets.generator import CLASSES, generate_dataset
from ai.training.baseline import LinearDiscriminant, extract_features

UNKNOWN = "unknown"


@dataclass(frozen=True)
class Decision:
    label: str  # a class name or "unknown"
    confidence: float  # smoothed probability of the best class
    probabilities: np.ndarray


class RealtimeClassifier:
    """Buffers IQ, classifies every ``hop`` samples and averages the last ``smoothing`` results.

    The label is ``unknown`` while the best smoothed probability is below ``threshold``.
    A confidence threshold is a weak novelty detector: see ai/README.md for measurements.
    """

    def __init__(self, classify, window=1024, hop=512, smoothing=4, threshold=0.6):
        if not 0 < hop <= window:
            raise ValueError("need 0 < hop <= window")
        if not 0 <= threshold <= 1 or smoothing < 1:
            raise ValueError("threshold must be in [0, 1] and smoothing >= 1")
        self.classify = classify
        self.window, self.hop, self.threshold = window, hop, threshold
        self._history: deque = deque(maxlen=smoothing)
        self._buffer = np.empty(0, dtype=np.complex64)

    def push(self, iq):
        """Add samples; returns one :class:`Decision` per completed window."""
        iq = np.asarray(iq, dtype=np.complex64).ravel()
        if not np.all(np.isfinite(iq)):
            raise ValueError("IQ contains NaN or infinity")
        self._buffer = np.concatenate((self._buffer, iq))
        decisions = []
        while len(self._buffer) >= self.window:
            self._history.append(self.classify(self._buffer[None, : self.window])[0])
            self._buffer = self._buffer[self.hop :]
            probabilities = np.mean(self._history, axis=0)
            best = int(np.argmax(probabilities))
            confidence = float(probabilities[best])
            label = CLASSES[best] if confidence >= self.threshold else UNKNOWN
            decisions.append(Decision(label, confidence, probabilities))
        return decisions

    def reset(self):
        """Forget buffered samples and past decisions (after a gain or frequency change)."""
        self._history.clear()
        self._buffer = self._buffer[:0]


def baseline_classifier(per_class=300, seed=1):
    """Classification callable from the hand-crafted baseline; trains in a few seconds."""
    data = generate_dataset(per_class, rng=seed)
    model = LinearDiscriminant().fit(extract_features(data.iq), data.labels)

    def classify(iq):
        score = -0.5 * model.distances(extract_features(iq))
        likelihood = np.exp(score - score.max(axis=1, keepdims=True))
        return likelihood / likelihood.sum(axis=1, keepdims=True)

    return classify


def cnn_classifier(path, num_threads=1):
    """Classification callable from a checkpoint written by ``ai.training.train``.

    One thread is the fastest choice for this model size (3 ms against 16 ms with 8 threads
    on an i7-9700K).
    """
    import torch

    from ai.preprocessing.spectrograms import classifier_input
    from ai.training.evaluate import load_model, softmax
    from ai.training.model import predict_logits

    torch.set_num_threads(num_threads)
    model = load_model(path)
    return lambda iq: softmax(predict_logits(model, classifier_input(iq)))
