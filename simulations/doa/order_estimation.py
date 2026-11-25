"""Number-of-sources detection with information criteria (Wax and Kailath, 1985)."""

import numpy as np


def _criterion(R, num_snapshots, penalty):
    eigenvalues = np.sort(np.linalg.eigvalsh(R))[::-1]
    n = eigenvalues.size
    floor = np.finfo(float).eps * max(eigenvalues[0], np.finfo(float).tiny)
    eigenvalues = np.maximum(eigenvalues, floor)
    scores = []
    for order in range(n):
        tail = eigenvalues[order:]
        sphericity = np.log(np.mean(tail)) - np.mean(np.log(tail))
        parameters = order * (2 * n - order)
        scores.append(num_snapshots * (n - order) * sphericity + penalty(parameters))
    return int(np.argmin(scores))


def estimate_order_mdl(R, num_snapshots):
    """Minimum description length: consistent, tends to underestimate with few snapshots.

    ``R`` must be the *unloaded* sample covariance: diagonal loading or smoothing changes
    the noise eigenvalues the test relies on.
    """
    return _criterion(R, num_snapshots, lambda p: 0.5 * p * np.log(num_snapshots))


def estimate_order_aic(R, num_snapshots):
    """Akaike criterion: more sensitive than MDL, but overestimates asymptotically."""
    return _criterion(R, num_snapshots, lambda p: p)
