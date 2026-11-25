"""Normalisation, so that classifiers cannot use absolute level (it depends on the gain)."""

import numpy as np


def unit_power(x):
    """Scale each signal (last axis) to unit mean power; silence stays zero."""
    power = np.mean(np.abs(x) ** 2, axis=-1, keepdims=True)
    return x / np.sqrt(np.where(power > 0, power, 1.0))


def standardize(x, axes=(-2, -1)):
    """Zero mean and unit variance per example."""
    mean = x.mean(axis=axes, keepdims=True)
    std = x.std(axis=axes, keepdims=True)
    return (x - mean) / np.where(std > 0, std, 1.0)
