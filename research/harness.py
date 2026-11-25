"""Shared tools of the Phase 2 studies: results files, uncertainty, tables."""

import json
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np

from dsp.signal_metrics import to_db

ROOT = Path(__file__).resolve().parents[1]


def environment():
    """What is needed to interpret a result later."""
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    return {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "machine": platform.machine(),
        "system": platform.system(),
        "commit": commit,
    }


def _plain(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"cannot store {type(value)}")


def save_results(study, name, data):
    """Write ``research/<study>/results/<name>.json``."""
    path = ROOT / "research" / study / "results" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    content = {"environment": environment(), "data": data}
    path.write_text(
        json.dumps(content, indent=1, default=_plain, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def load_results(study, name):
    path = ROOT / "research" / study / "results" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))["data"]


def loss_db(ratios):
    """Mean SINR loss in dB from linear ratios ``SINR / optimum``."""
    return float(-to_db(np.mean(ratios)))


def bootstrap_loss(ratios, resamples=1000, seed=0):
    """95 % bootstrap interval of :func:`loss_db`."""
    ratios = np.asarray(ratios)
    rng = np.random.default_rng(seed)
    index = rng.integers(0, len(ratios), (resamples, len(ratios)))
    losses = -to_db(ratios[index].mean(axis=1))
    return [float(v) for v in np.percentile(losses, [2.5, 97.5])]


def proportion_interval(successes, trials, z=1.96):
    """95 % Wilson interval of a proportion."""
    p = successes / trials
    centre = (p + z**2 / (2 * trials)) / (1 + z**2 / trials)
    half = z * np.sqrt(p * (1 - p) / trials + z**2 / (4 * trials**2)) / (1 + z**2 / trials)
    return [float(centre - half), float(centre + half)]


def auroc(negatives, positives):
    """Probability that a positive scores above a negative (ties count half)."""
    negatives, positives = np.sort(np.asarray(negatives)), np.asarray(positives)
    below = np.searchsorted(negatives, positives, side="left")
    equal = np.searchsorted(negatives, positives, side="right") - below
    return float(np.mean(below + 0.5 * equal) / len(negatives))


def markdown_table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "---:|" * len(header)]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


def replace_block(path, name, text):
    """Replace the text between ``<!-- name -->`` and ``<!-- /name -->`` in a report."""
    path = Path(path)
    content = path.read_text(encoding="utf-8")
    start, stop = f"<!-- {name} -->", f"<!-- /{name} -->"
    if start not in content or stop not in content:
        raise ValueError(f"{path} has no block {name}")
    head, rest = content.split(start, 1)
    tail = rest.split(stop, 1)[1]
    path.write_text(f"{head}{start}\n\n{text}\n\n{stop}{tail}", encoding="utf-8", newline="\n")


def progress(message):
    print(message, file=sys.stderr, flush=True)
