import numpy as np


def compute_covariance_matrix(X):
    num_snapshots = X.shape[1]
    R = (X @ X.conj().T) / num_snapshots
    return R
