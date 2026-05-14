import numpy as np


def generate_snapshots_from_timeseries(
    X_time,
    snapshot_step=1
):
    """
    Convert a spatio-temporal IQ signal matrix into a snapshot matrix.

    Parameters
    ----------
    X_time : np.ndarray
        Spatio-temporal signal matrix with shape (num_antennas, num_time_samples).

    snapshot_step : int
        Step between selected time samples.

    Returns
    -------
    X_snapshots : np.ndarray
        Snapshot matrix with shape (num_antennas, num_snapshots).
    """

    if X_time.ndim != 2:
        raise ValueError("X_time must be a 2D matrix with shape (num_antennas, num_time_samples).")

    if snapshot_step <= 0:
        raise ValueError("snapshot_step must be a positive integer.")

    return X_time[:, ::snapshot_step]

