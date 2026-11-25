"""Synthetic labelled IQ for interference classification.

Every example is one channel of complex baseband at unit noise power. The generator is the
only data source of the project: results obtained with it say nothing about real signals
until checked on recordings.
"""

from dataclasses import dataclass

import numpy as np

from dsp.signal_metrics import from_db
from simulations.channels import interference_models as models
from simulations.channels.awgn import complex_noise, make_rng

CLASSES = ("noise", "cw", "chirp", "qpsk", "band_noise", "pulsed")


@dataclass(frozen=True)
class Dataset:
    iq: np.ndarray  # complex64, (examples, samples)
    labels: np.ndarray  # int64 index into CLASSES
    snr_db: np.ndarray  # NaN for the noise class

    def __len__(self):
        return len(self.labels)


def waveform(name, num_samples, rng):
    """Unit-power waveform with randomised parameters."""
    frequency = rng.uniform(-0.3, 0.3)
    if name == "cw":
        return models.cw_tone(num_samples, frequency, rng)
    if name == "chirp":
        span = rng.uniform(0.2, 0.6) * rng.choice([-1, 1])
        period = int(rng.integers(num_samples // 8, num_samples + 1))
        center = rng.uniform(-0.15, 0.15)
        return models.linear_chirp(num_samples, center - span / 2, center + span / 2, period, rng)
    if name == "qpsk":
        return models.qpsk(num_samples, int(rng.integers(4, 17)), frequency, rng)
    if name == "band_noise":
        return models.band_limited_noise(num_samples, rng.uniform(0.1, 0.5), frequency, rng)
    if name == "pulsed":
        period = int(rng.integers(64, num_samples // 3))
        length = int(period * rng.uniform(0.1, 0.4))
        return models.pulsed(num_samples, length, period, frequency, rng)
    raise ValueError(f"unknown class {name!r}")


def make_example(name, num_samples, snr_db, rng=None):
    """One example; ``snr_db`` is ignored for the noise class."""
    rng = make_rng(rng)
    x = complex_noise(num_samples, 1.0, rng)
    if name != "noise":
        x = x + np.sqrt(from_db(snr_db)) * waveform(name, num_samples, rng)
    return x.astype(np.complex64)


def generate_dataset(per_class, num_samples=1024, snr_range_db=(-5.0, 20.0), rng=None):
    """Balanced, shuffled dataset with uniformly distributed SNR."""
    rng = make_rng(rng)
    iq, labels, snrs = [], [], []
    for label, name in enumerate(CLASSES):
        for _ in range(per_class):
            snr = rng.uniform(*snr_range_db)
            iq.append(make_example(name, num_samples, snr, rng))
            labels.append(label)
            snrs.append(np.nan if name == "noise" else snr)
    order = rng.permutation(len(labels))
    return Dataset(
        np.stack(iq)[order], np.array(labels, dtype=np.int64)[order], np.array(snrs)[order]
    )
