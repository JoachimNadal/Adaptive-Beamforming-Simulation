"""Train the interference classifier on synthetic data.

    python -m ai.training.train --per-class 2000 --epochs 12

Writes ``results/ai/model.pt`` and ``results/ai/training.json``. Training, validation and
test sets are generated with different seeds, so no example is shared.
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

from ai.datasets.generator import CLASSES, generate_dataset
from ai.preprocessing.spectrograms import classifier_input
from ai.training.metrics import accuracy
from ai.training.model import SpectrogramCNN, count_parameters, predict_logits

SEEDS = {"train": 1, "validation": 2, "test": 3}


def train(per_class=2000, epochs=12, batch_size=128, learning_rate=6e-3, seed=0, log=print):
    """Returns ``(model, history)``; the model is the best validation epoch."""
    torch.manual_seed(seed)
    data = generate_dataset(per_class, rng=SEEDS["train"])
    held_out = generate_dataset(max(per_class // 5, 10), rng=SEEDS["validation"])
    inputs = torch.from_numpy(classifier_input(data.iq))
    labels = torch.from_numpy(data.labels)
    validation_inputs = classifier_input(held_out.iq)

    model = SpectrogramCNN(len(CLASSES))
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    steps = epochs * (len(data) // batch_size + 1)
    schedule = torch.optim.lr_scheduler.OneCycleLR(optimizer, learning_rate, steps)
    loss_function = nn.CrossEntropyLoss()
    history, best_accuracy, best_state = [], -1.0, None
    for epoch in range(epochs):
        model.train()
        total = 0.0
        for batch in torch.randperm(len(data)).split(batch_size):
            optimizer.zero_grad()
            loss = loss_function(model(inputs[batch]), labels[batch])
            loss.backward()
            optimizer.step()
            schedule.step()
            total += loss.item() * len(batch)
        score = accuracy(held_out.labels, predict_logits(model, validation_inputs).argmax(1))
        history.append({"epoch": epoch, "loss": total / len(data), "validation_accuracy": score})
        log(f"epoch {epoch:2d}  loss {total / len(data):.4f}  validation accuracy {score:.4f}")
        if score > best_accuracy:
            best_accuracy = score
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)
    return model, history


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--per-class", type=int, default=2000)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--output", type=Path, default=Path("results/ai"))
    args = parser.parse_args(argv)
    start = time.perf_counter()
    model, history = train(args.per_class, args.epochs)
    args.output.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), args.output / "model.pt")
    report = {
        "classes": CLASSES,
        "per_class": args.per_class,
        "parameters": count_parameters(model),
        "seconds": round(time.perf_counter() - start, 1),
        "torch": torch.__version__,
        "numpy": np.__version__,
        "history": history,
    }
    (args.output / "training.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"saved {args.output / 'model.pt'}")


if __name__ == "__main__":
    main()
