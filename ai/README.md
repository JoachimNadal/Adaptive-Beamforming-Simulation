# ai — interference classification

| Folder | Content |
|---|---|
| `datasets/` | synthetic generator, 6 classes |
| `preprocessing/` | normalisation, log-spectrum, spectrogram |
| `training/` | CNN, hand-crafted baseline, training, evaluation, metrics |
| `interference/` | streaming classifier |

```bash
pip install -e ".[ai]"
python -m ai.training.train --per-class 2000 --epochs 12   # results/ai/model.pt
python -m ai.training.evaluate                             # results/ai/evaluation.json
python examples/run_ai_detection.py results/ai/model.pt
```

Without PyTorch, `run_ai_detection.py` uses the baseline.

## Results

Synthetic data only. 12 000 training examples, 3000 test examples from a different seed, SNR
uniform in −5 to 20 dB, 1024 samples per example. PyTorch 2.15.0 CPU, 12 epochs, 527 s on an
i7-9700K.

| | CNN (23 910 parameters) | Baseline (6 features + LDA) |
|---|---:|---:|
| Accuracy | 99.2 % | 91.2 % |
| −5 to 0 dB | 94.8 % | 65.7 % |
| 0 to 5 dB | 100 % | 85.6 % |
| 5 to 10 dB | 100 % | 94.2 % |
| above 10 dB | 100 % | 98.9 to 100 % |

CNN confusion (rows: truth). The only real confusion is QPSK with band-limited noise at low SNR.

| | noise | cw | chirp | qpsk | band_noise | pulsed |
|---|---:|---:|---:|---:|---:|---:|
| noise | 500 | | | | | |
| cw | | 500 | | | | |
| chirp | 1 | | 499 | | | |
| qpsk | | | | 488 | 12 | |
| band_noise | | | | 11 | 489 | |
| pulsed | | | | | | 500 |

Inference: 0.7 ms features + 3.3 ms network on one thread. Eight threads are slower (16 ms).

## Limits

- **No novelty detection.** With a 0.9 confidence threshold, 2.8 % of two-tone and pulsed-chirp
  signals (absent from training) are rejected, and 2.9 % of known ones: the threshold does not
  separate them. The classifier always answers one of its six classes.
- **No real data.** Accuracy on recordings is unknown, and near-perfect synthetic scores mostly
  show that the synthetic problem is easy.
- One signal at a time; no mixture in training.
