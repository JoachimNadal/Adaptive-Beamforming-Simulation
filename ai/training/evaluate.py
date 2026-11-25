"""Evaluate the trained CNN against the hand-crafted baseline.

    python -m ai.training.evaluate --model results/ai/model.pt

Reports accuracy overall and per SNR, the confusion matrix, behaviour on waveforms absent
from training, and inference time.
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch

from ai.datasets.generator import CLASSES, generate_dataset
from ai.preprocessing.spectrograms import classifier_input
from ai.training.baseline import LinearDiscriminant, extract_features
from ai.training.metrics import (
    accuracy,
    accuracy_by_snr,
    confusion_matrix,
    precision_recall_f1,
)
from ai.training.model import SpectrogramCNN, predict_logits
from ai.training.train import SEEDS
from dsp.signal_metrics import from_db
from simulations.channels import interference_models as models
from simulations.channels.awgn import complex_noise, make_rng

SNR_EDGES = (-5, 0, 5, 10, 15, 20.001)


def load_model(path):
    model = SpectrogramCNN(len(CLASSES))
    model.load_state_dict(torch.load(path, map_location="cpu", weights_only=True))
    return model.eval()


def softmax(logits):
    z = np.exp(logits - logits.max(axis=1, keepdims=True))
    return z / z.sum(axis=1, keepdims=True)


def unseen_waveforms(count, num_samples=1024, snr_db=10.0, rng=None):
    """Two-tone and pulsed-chirp signals, deliberately outside the training classes."""
    rng = make_rng(rng)
    examples = []
    for i in range(count):
        if i % 2:
            x = models.cw_tone(num_samples, rng.uniform(-0.3, 0), rng)
            x = models.unit_power(x + models.cw_tone(num_samples, rng.uniform(0.05, 0.3), rng))
        else:
            gate = np.abs(models.pulsed(num_samples, 40, 160, 0.0, rng)) > 0
            x = models.unit_power(gate * models.linear_chirp(num_samples, period=160, rng=rng))
        examples.append(np.sqrt(from_db(snr_db)) * x + complex_noise(num_samples, 1.0, rng))
    return np.stack(examples).astype(np.complex64)


def evaluate(model, per_class=500, confidence=0.9):
    test = generate_dataset(per_class, rng=SEEDS["test"])
    fit = generate_dataset(per_class, rng=SEEDS["train"])
    logits = predict_logits(model, classifier_input(test.iq))
    baseline = LinearDiscriminant().fit(extract_features(fit.iq), fit.labels)
    predictions = {
        "cnn": logits.argmax(axis=1),
        "baseline": baseline.predict(extract_features(test.iq)),
    }
    report: dict = {"classes": CLASSES, "test_examples": len(test), "snr_bins_db": SNR_EDGES}
    for name, predicted in predictions.items():
        matrix = confusion_matrix(test.labels, predicted, len(CLASSES))
        precision, recall, f1 = precision_recall_f1(matrix)
        report[name] = {
            "accuracy": accuracy(test.labels, predicted),
            "accuracy_by_snr": accuracy_by_snr(test.labels, predicted, test.snr_db, SNR_EDGES),
            "precision": precision.round(4).tolist(),
            "recall": recall.round(4).tolist(),
            "f1": f1.round(4).tolist(),
            "confusion": matrix.tolist(),
        }
    known = softmax(logits).max(axis=1)
    unseen = softmax(predict_logits(model, classifier_input(unseen_waveforms(400, rng=9))))
    report["novelty"] = {
        "confidence_threshold": confidence,
        "known_rejected": float(np.mean(known < confidence)),
        "unseen_rejected": float(np.mean(unseen.max(axis=1) < confidence)),
    }
    durations = []
    threads = torch.get_num_threads()
    torch.set_num_threads(1)  # several threads are slower than one on such a small model
    for i in range(60):
        start = time.perf_counter()
        predict_logits(model, classifier_input(test.iq[i : i + 1]))
        durations.append(time.perf_counter() - start)
    torch.set_num_threads(threads)
    report["single_inference_ms"] = round(float(np.median(durations[10:])) * 1e3, 3)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--model", type=Path, default=Path("results/ai/model.pt"))
    parser.add_argument("--per-class", type=int, default=500)
    args = parser.parse_args(argv)
    report = evaluate(load_model(args.model), args.per_class)
    text = json.dumps(report, indent=2)
    args.model.with_name("evaluation.json").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
