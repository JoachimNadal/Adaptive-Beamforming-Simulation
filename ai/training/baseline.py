"""Hand-crafted features with a linear discriminant: the reference a CNN has to beat."""

import numpy as np

from ai.preprocessing.iq_to_fft import iq_to_log_spectrum
from ai.preprocessing.normalization import unit_power
from dsp.signal_metrics import from_db

FEATURES = (
    "spectral flatness",
    "spectral peak",
    "occupied bandwidth",
    "envelope kurtosis",
    "envelope variation",
    "short-time power variation",
)


def extract_features(iq, window=32):
    """Six scale-invariant features per signal, ``(examples, 6)``."""
    x = np.atleast_2d(unit_power(iq))
    log_psd = iq_to_log_spectrum(x)
    psd = from_db(log_psd)
    mean_psd = psd.mean(axis=1)
    envelope = np.abs(x) ** 2
    blocks = envelope[:, : x.shape[1] // window * window].reshape(len(x), -1, window).mean(axis=2)
    return np.column_stack(
        (
            log_psd.mean(axis=1) - 10 * np.log10(mean_psd),
            log_psd.max(axis=1) - 10 * np.log10(mean_psd),
            np.mean(psd > mean_psd[:, None], axis=1),
            np.log(np.mean(envelope**2, axis=1)),
            np.std(np.sqrt(envelope), axis=1),
            np.log(np.std(blocks, axis=1) + 1e-3),
        )
    )


class LinearDiscriminant:
    """Gaussian classes with a shared covariance."""

    def fit(self, features, labels):
        classes = np.unique(labels)
        self.means = np.stack([features[labels == c].mean(axis=0) for c in classes])
        centred = features - self.means[np.searchsorted(classes, labels)]
        covariance = centred.T @ centred / len(features)
        self.precision = np.linalg.inv(covariance + 1e-6 * np.eye(features.shape[1]))
        return self

    def distances(self, features):
        """Squared Mahalanobis distance to each class."""
        d = features[:, None, :] - self.means
        return np.einsum("nki,ij,nkj->nk", d, self.precision, d)

    def predict(self, features):
        return np.argmin(self.distances(features), axis=1)
