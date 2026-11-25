"""Experiments of the open-set study.

    python -m research.open_set.run baseline        # Phase 1 CNN, needs results/ai/model.pt
    python -m research.open_set.run leave_one_out   # six small trainings
    python -m research.open_set.run augmented       # CNN retrained with impairments

Real recordings must have been fetched (``python -m research.open_set.recordings``).
"""

import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

from ai.datasets.generator import CLASSES, generate_dataset
from ai.preprocessing.spectrograms import classifier_input
from ai.training.baseline import extract_features
from ai.training.model import SpectrogramCNN
from research.harness import ROOT, auroc, progress, proportion_interval, save_results
from research.open_set import recordings
from research.open_set import waveforms as wf
from research.open_set.detectors import (
    ClassMahalanobis,
    NearestNeighbours,
    SpectrogramResidual,
    energy_score,
    extended_features,
    rank_fusion,
    softmax_score,
)

FALSE_ALARM = 0.05
SEED_FIT, SEED_VALIDATION, SEED_TEST = 1, 20, 21
CHECKPOINT = ROOT / "results" / "ai" / "model.pt"


def forward(model, spectrograms, batch=256):
    """Logits and embeddings."""
    model.eval()
    logits, embeddings = [], []
    with torch.no_grad():
        for i in range(0, len(spectrograms), batch):
            e = model.features(torch.from_numpy(spectrograms[i : i + batch])[:, None])
            e = e.mean(dim=(2, 3))
            embeddings.append(e.numpy())
            logits.append(model.head(e).numpy())
    return np.concatenate(logits), np.concatenate(embeddings).astype(float)


class Suite:
    """All detectors, fitted on the same training data and thresholded on the same validation."""

    def __init__(self, model, fit_iq, fit_labels, validation_iq):
        self.model = model
        s = classifier_input(fit_iq)
        _, embedding = forward(model, s)
        basic, extended = extract_features(fit_iq), extended_features(fit_iq)
        self.parts = {
            "CNN Mahalanobis": ClassMahalanobis().fit(embedding, fit_labels),
            "CNN k-NN": NearestNeighbours().fit(embedding),
            "features Mahalanobis": ClassMahalanobis().fit(basic, fit_labels),
            "features k-NN": NearestNeighbours().fit(basic),
            "extended Mahalanobis": ClassMahalanobis().fit(extended, fit_labels),
            "extended k-NN": NearestNeighbours().fit(extended),
            "spectrogram residual": SpectrogramResidual().fit(s),
        }
        self.reference = None
        self.reference = self._raw(validation_iq)
        scores = self.scores(validation_iq)
        self.thresholds = {k: np.quantile(v, 1 - FALSE_ALARM) for k, v in scores.items()}

    def _raw(self, iq):
        s = classifier_input(iq)
        logits, embedding = forward(self.model, s)
        basic, extended = extract_features(iq), extended_features(iq)
        return {
            "softmax": softmax_score(logits),
            "energy": energy_score(logits),
            "CNN Mahalanobis": self.parts["CNN Mahalanobis"].score(embedding),
            "CNN k-NN": self.parts["CNN k-NN"].score(embedding),
            "features Mahalanobis": self.parts["features Mahalanobis"].score(basic),
            "features k-NN": self.parts["features k-NN"].score(basic),
            "extended Mahalanobis": self.parts["extended Mahalanobis"].score(extended),
            "extended k-NN": self.parts["extended k-NN"].score(extended),
            "spectrogram residual": self.parts["spectrogram residual"].score(s),
        }

    def scores(self, iq):
        raw = self._raw(iq)
        pair = ("CNN Mahalanobis", "extended Mahalanobis")
        raw["fusion"] = rank_fusion([self.reference[k] for k in pair], [raw[k] for k in pair])
        return raw

    def predictions(self, iq):
        return forward(self.model, classifier_input(iq))[0].argmax(axis=1)

    def rates(self, scores):
        return {k: float(np.mean(v > self.thresholds[k])) for k, v in scores.items()}


def cluster_interval(flags, groups, resamples=1000):
    """95 % interval of a rate, resampling whole recordings: windows of one are not independent."""
    rng = np.random.default_rng(0)
    names = np.unique(groups)
    if len(names) < 3:
        return None
    sums = np.array([flags[groups == g].sum() for g in names])
    counts = np.array([np.sum(groups == g) for g in names])
    index = rng.integers(0, len(names), (resamples, len(names)))
    rates = sums[index].sum(axis=1) / counts[index].sum(axis=1)
    return [float(v) for v in np.percentile(rates, [2.5, 97.5])]


def evaluate(suite, families=True, per_family=300):
    """Every test of the study for one fitted suite."""
    test = generate_dataset(200, rng=SEED_TEST)
    known = suite.scores(test.iq)
    result: dict = {
        "known": {
            "count": len(test),
            "false_alarm": suite.rates(known),
            "interval": {
                k: proportion_interval(int(np.sum(v > suite.thresholds[k])), len(v))
                for k, v in known.items()
            },
            "accuracy": float(np.mean(suite.predictions(test.iq) == test.labels)),
        }
    }
    if families:
        result["unseen"] = {}
        for i, name in enumerate(wf.FAMILIES):
            iq, _ = wf.generate(name, per_family, rng=1000 + i)
            scores = suite.scores(iq)
            result["unseen"][name] = {
                "auroc": {k: auroc(known[k], v) for k, v in scores.items()},
                "detected": suite.rates(scores),
                "predicted": np.bincount(suite.predictions(iq), minlength=len(CLASSES)),
            }
    result["impaired"] = {}
    for i, name in enumerate(wf.IMPAIRMENTS):
        iq = wf.impair(name, test.iq, rng=2000 + i)
        result["impaired"][name] = {
            "false_alarm": suite.rates(suite.scores(iq)),
            "accuracy": float(np.mean(suite.predictions(iq) == test.labels)),
        }
    data, origin, counts = recordings.collect()
    real = {name: suite.scores(iq) for name, iq in data.items()}
    result["real"] = {"recordings": counts}
    noise = np.concatenate([origin["noise_white"], origin["noise_other"]])
    for name, scores in real.items():
        entry = {
            "windows": len(data[name]),
            "recordings": len(set(origin[name].tolist())),
            "flagged": suite.rates(scores),
            "interval": {
                k: cluster_interval(v > suite.thresholds[k], origin[name])
                for k, v in scores.items()
            },
            "predicted": np.bincount(suite.predictions(data[name]), minlength=len(CLASSES)),
        }
        if name.startswith("signal"):
            entry["auroc_vs_known"] = {k: auroc(known[k], v) for k, v in scores.items()}
            entry["auroc_vs_real_noise"] = {
                k: auroc(np.concatenate((real["noise_white"][k], real["noise_other"][k])), v)
                for k, v in scores.items()
            }
        result["real"][name] = entry
    result["real"]["noise_recordings"] = len(set(noise.tolist()))
    return result


def train_classifier(iq, labels, num_classes, epochs=8, batch=128, seed=0, rate=6e-3):
    torch.manual_seed(seed)
    inputs = torch.from_numpy(classifier_input(iq))
    targets = torch.from_numpy(labels)
    model = SpectrogramCNN(num_classes)
    optimizer = torch.optim.Adam(model.parameters(), lr=rate)
    steps = epochs * (len(iq) // batch + 1)
    schedule = torch.optim.lr_scheduler.OneCycleLR(optimizer, rate, steps)
    loss_function = nn.CrossEntropyLoss()
    for _ in range(epochs):
        model.train()
        for index in torch.randperm(len(iq)).split(batch):
            optimizer.zero_grad()
            loss_function(model(inputs[index]), targets[index]).backward()
            optimizer.step()
            schedule.step()
    return model.eval()


# ------------------------------------------------------------------------- experiments


def baseline():
    model = SpectrogramCNN(len(CLASSES))
    model.load_state_dict(torch.load(CHECKPOINT, map_location="cpu", weights_only=True))
    fit = generate_dataset(500, rng=SEED_FIT)
    validation = generate_dataset(200, rng=SEED_VALIDATION)
    return evaluate(Suite(model, fit.iq, fit.labels, validation.iq))


def leave_one_out(per_class=800):
    """Remove one class from training, then try to detect it."""
    fit = generate_dataset(per_class, rng=SEED_FIT)
    validation = generate_dataset(200, rng=SEED_VALIDATION)
    test = generate_dataset(200, rng=SEED_TEST)
    result = {}
    for held_out, name in enumerate(CLASSES):
        start = time.perf_counter()
        keep = fit.labels != held_out
        labels = fit.labels[keep]
        labels = labels - (labels > held_out)
        model = train_classifier(fit.iq[keep], labels, len(CLASSES) - 1)
        suite = Suite(model, fit.iq[keep], labels, validation.iq[validation.labels != held_out])
        known = suite.scores(test.iq[test.labels != held_out])
        unknown = suite.scores(test.iq[test.labels == held_out])
        remaining = test.labels[test.labels != held_out]
        remaining = remaining - (remaining > held_out)
        predicted = suite.predictions(test.iq[test.labels != held_out])
        result[name] = {
            "auroc": {k: auroc(known[k], unknown[k]) for k in known},
            "detected": suite.rates(unknown),
            "false_alarm": suite.rates(known),
            "accuracy": float(np.mean(predicted == remaining)),
        }
        progress(f"without {name}: {time.perf_counter() - start:.0f} s")
    return result


def augmented(per_class=1500):
    """CNN and detectors fitted on data with random receiver impairments."""
    rng = np.random.default_rng(77)
    fit = generate_dataset(per_class, rng=SEED_FIT)
    fit_iq = wf.random_impairments(fit.iq, rng)
    model = train_classifier(fit_iq, fit.labels, len(CLASSES), epochs=10)
    validation = generate_dataset(200, rng=SEED_VALIDATION)
    suite = Suite(
        model, fit_iq[:3000], fit.labels[:3000], wf.random_impairments(validation.iq, rng)
    )
    return evaluate(suite)


EXPERIMENTS = {f.__name__: f for f in (baseline, leave_one_out, augmented)}


def main(names):
    torch.set_num_threads(6)
    for name, experiment in EXPERIMENTS.items():
        if names and name not in names:
            continue
        start = time.perf_counter()
        path = save_results("open_set", name, experiment())
        progress(f"{Path(path).name}: {time.perf_counter() - start:.0f} s")


if __name__ == "__main__":
    main(sys.argv[1:])
