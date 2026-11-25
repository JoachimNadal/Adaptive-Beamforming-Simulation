"""Out-of-distribution scores: larger means "less like the training data".

Every detector is fitted on training data only, and its threshold is set on separate
in-distribution validation data.
"""

import numpy as np

from ai.preprocessing.iq_to_fft import iq_to_log_spectrum
from ai.preprocessing.normalization import unit_power
from ai.training.baseline import extract_features


def extended_features(iq):
    """The six baseline features plus higher-order and cyclic statistics (scale-free).

    Added: |C20|, |C40|, C42 (constellation shape), spectral entropy and number of occupied
    peaks, largest autocorrelation away from zero lag (repetition), lag-1 phase statistics
    (instantaneous frequency mean spread and kurtosis), crest factor.
    """
    x = np.atleast_2d(unit_power(np.asarray(iq, dtype=np.complex64)))
    n = x.shape[1]
    power = np.abs(x) ** 2
    m20, m40 = np.mean(x**2, axis=1), np.mean(x**4, axis=1)
    m42 = np.mean(power**2, axis=1)
    c40 = np.abs(m40 - 3 * m20**2)
    c42 = m42 - np.abs(m20) ** 2 - 2
    # remove a possible carrier before |C20|: use the strongest bin of the squared signal
    squared = np.abs(np.fft.fft(x**2, axis=1)) / n
    fourth = np.abs(np.fft.fft(x**4, axis=1)) / n
    log_psd = iq_to_log_spectrum(x)
    p = 10 ** (log_psd / 10)
    p = p / p.sum(axis=1, keepdims=True)
    entropy = -np.sum(p * np.log(p + 1e-12), axis=1) / np.log(p.shape[1])
    above = np.mean(log_psd > log_psd.max(axis=1, keepdims=True) - 10, axis=1)
    spectrum = np.abs(np.fft.fft(x, 2 * n, axis=1)) ** 2
    autocorrelation = np.abs(np.fft.ifft(spectrum, axis=1))[:, : n // 2]
    far = autocorrelation[:, 32:].max(axis=1) / autocorrelation[:, 0]
    envelope = power - power.mean(axis=1, keepdims=True)
    cyclic = np.abs(np.fft.rfft(envelope, axis=1))[:, 1:]
    cyclic_peak = cyclic.max(axis=1) / np.sqrt(np.mean(cyclic**2, axis=1))
    step = np.angle(x[:, 1:] * x[:, :-1].conj())
    centred = step - np.angle(np.mean(np.exp(1j * step), axis=1, keepdims=True))
    centred = np.angle(np.exp(1j * centred))
    spread = np.std(centred, axis=1)
    tail = np.mean(centred**4, axis=1) / (np.mean(centred**2, axis=1) ** 2 + 1e-12)
    return np.column_stack(
        (
            extract_features(x),
            np.log(c40 + 1e-2),
            c42,
            squared.max(axis=1),
            fourth.max(axis=1),
            entropy,
            above,
            far,
            np.log(cyclic_peak),
            spread,
            np.log(tail),
            np.log(power.max(axis=1)),
        )
    )


class Standardizer:
    def fit(self, features):
        self.mean, self.std = features.mean(axis=0), features.std(axis=0) + 1e-9
        return self

    def __call__(self, features):
        return (features - self.mean) / self.std


class ClassMahalanobis:
    """Smallest Mahalanobis distance to a class mean, shared covariance."""

    def fit(self, features, labels):
        self.scale = Standardizer().fit(features)
        z = self.scale(features)
        classes = np.unique(labels)
        self.means = np.stack([z[labels == c].mean(axis=0) for c in classes])
        centred = z - self.means[np.searchsorted(classes, labels)]
        covariance = centred.T @ centred / len(z) + 1e-3 * np.eye(z.shape[1])
        self.factor = np.linalg.cholesky(np.linalg.inv(covariance))
        return self

    def score(self, features):
        d = (self.scale(features)[:, None, :] - self.means) @ self.factor
        return np.min(np.sum(d**2, axis=2), axis=1)


class NearestNeighbours:
    """Distance to the k-th nearest training example."""

    def __init__(self, k=10, limit=4000):
        self.k, self.limit = k, limit

    def fit(self, features, labels=None):
        self.scale = Standardizer().fit(features)
        step = max(1, len(features) // self.limit)
        self.bank = self.scale(features)[::step].astype(np.float32)
        return self

    def score(self, features, chunk=256):
        z = self.scale(features).astype(np.float32)
        norms = np.sum(self.bank**2, axis=1)
        out = []
        for i in range(0, len(z), chunk):
            q = z[i : i + chunk]
            d = np.sum(q**2, axis=1)[:, None] + norms - 2 * q @ self.bank.T
            out.append(np.partition(d, self.k - 1, axis=1)[:, self.k - 1])
        return np.sqrt(np.maximum(np.concatenate(out), 0))


class SpectrogramResidual:
    """Energy of the spectrogram outside its principal components (linear autoencoder)."""

    def __init__(self, components=64):
        self.components = components

    def fit(self, spectrograms, labels=None):
        flat = spectrograms.reshape(len(spectrograms), -1)
        self.mean = flat.mean(axis=0)
        # randomised range finder: the full SVD would need several gigabytes
        rng = np.random.default_rng(0)
        centred = flat - self.mean
        sketch = centred.T @ (centred @ rng.standard_normal((flat.shape[1], self.components + 8)))
        self.basis, _ = np.linalg.qr(sketch.astype(np.float32))
        return self

    def score(self, spectrograms):
        z = spectrograms.reshape(len(spectrograms), -1) - self.mean
        projected = z @ self.basis
        return np.sum(z**2, axis=1) - np.sum(projected**2, axis=1)


def softmax_score(logits):
    z = logits - logits.max(axis=1, keepdims=True)
    return 1 - 1 / np.exp(z).sum(axis=1)


def energy_score(logits):
    top = logits.max(axis=1)
    return -(top + np.log(np.exp(logits - top[:, None]).sum(axis=1)))


def rank_fusion(reference_scores, scores):
    """Mean of the empirical CDF positions of several detectors on validation data."""
    ranks = [
        np.searchsorted(np.sort(reference), s) / len(reference)
        for reference, s in zip(reference_scores, scores, strict=True)
    ]
    return np.mean(ranks, axis=0)
