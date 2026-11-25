"""Classification metrics (NumPy only)."""

from itertools import pairwise

import numpy as np


def confusion_matrix(labels, predictions, num_classes):
    """Rows are true classes, columns predictions."""
    matrix = np.zeros((num_classes, num_classes), dtype=int)
    np.add.at(matrix, (np.asarray(labels), np.asarray(predictions)), 1)
    return matrix


def accuracy(labels, predictions):
    return float(np.mean(np.asarray(labels) == np.asarray(predictions)))


def precision_recall_f1(matrix):
    """Per-class arrays; undefined ratios are reported as 0."""
    hits = np.diag(matrix).astype(float)
    precision = hits / np.maximum(matrix.sum(axis=0), 1)
    recall = hits / np.maximum(matrix.sum(axis=1), 1)
    f1 = 2 * precision * recall / np.maximum(precision + recall, 1e-12)
    return precision, recall, f1


def accuracy_by_snr(labels, predictions, snr_db, edges):
    """Accuracy per SNR bin ``[edge_i, edge_i+1)``; NaN where a bin is empty."""
    correct = np.asarray(labels) == np.asarray(predictions)
    result = []
    for low, high in pairwise(edges):
        inside = (snr_db >= low) & (snr_db < high)
        result.append(float(correct[inside].mean()) if inside.any() else float("nan"))
    return result
