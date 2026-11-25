"""Interference detection with the array, then classification of its waveform.

The detector says *whether* and *where*; the classifier says *what*. By default the
hand-crafted baseline is used, which needs no training step. Pass a checkpoint written by
``python -m ai.training.train`` to use the CNN instead (requires PyTorch).

    python examples/run_ai_detection.py [results/ai/model.pt]
"""

import sys

import numpy as np

from ai.datasets.generator import CLASSES, waveform
from ai.interference.realtime_classifier import (
    RealtimeClassifier,
    baseline_classifier,
    cnn_classifier,
)
from dsp.adaptive_weights import das_weights
from examples.common import SEED, WAVELENGTH, reference_array
from simulations.channels.awgn import complex_noise, make_rng
from simulations.scenarios.interference_detection import InterferenceDetector

SNAPSHOTS = 4096


def main(checkpoint=None):
    rng = make_rng(SEED)
    array = reference_array(4)
    detector = InterferenceDetector(array, WAVELENGTH, SNAPSHOTS, rng=rng)
    classify = cnn_classifier(checkpoint) if checkpoint else baseline_classifier()
    print(f"classifier: {'CNN' if checkpoint else 'hand-crafted baseline'}")
    for name in CLASSES:
        angle = rng.uniform(-50, 50)
        X = complex_noise((4, SNAPSHOTS), 1.0, rng)
        if name != "noise":
            a = array.compute_steering_vector(angle, WAVELENGTH, "deg")
            X = X + np.sqrt(3.0) * np.outer(a, waveform(name, SNAPSHOTS, rng))
        detection = detector.detect(X)
        truth = "no source" if name == "noise" else f"{name} at {angle:+.1f} deg"
        if not detection.detected:
            print(f"truth: {truth:24s} -> nothing detected")
            continue
        # a conventional beam on the estimate gives the classifier 6 dB more SNR
        direction = detection.angles_deg[0]
        w = das_weights(array.compute_steering_vector(direction, WAVELENGTH, "deg"))
        decision = RealtimeClassifier(classify).push(w.conj() @ X)[-1]
        print(
            f"truth: {truth:24s} -> {decision.label} at {direction:+.1f} deg"
            f" (confidence {decision.confidence:.2f})"
        )


if __name__ == "__main__":
    main(*sys.argv[1:2])
