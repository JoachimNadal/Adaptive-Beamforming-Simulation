import numpy as np

from dsp.adaptive_weights import rls_update
from simulations.beamforming.base import Beamformer, plot_learning_curve


class RLSBeamformer(Beamformer):
    """Recursive least squares beamformer trained on a reference signal.

    ``lambda_factor`` sets the memory, about ``1 / (1 - lambda)`` snapshots. ``P`` starts
    at ``I / delta``; small ``delta`` trusts the data sooner.
    """

    def __init__(self, antenna_array, lambda_factor=0.99, delta=1.0):
        if not 0 < lambda_factor <= 1:
            raise ValueError("lambda_factor must be in (0, 1]")
        if delta <= 0:
            raise ValueError("delta must be positive")
        super().__init__(antenna_array)
        self.lambda_factor = lambda_factor
        self.delta = delta

    def train(self, X, desired_signal):
        """Adapt over all snapshots; returns final weights and squared a-priori errors."""
        num_antennas, num_samples = X.shape
        w = np.zeros(num_antennas, dtype=complex)
        P = np.eye(num_antennas, dtype=complex) / self.delta
        errors = np.empty(num_samples)
        for n in range(num_samples):
            x = X[:, n]
            e = desired_signal[n] - np.vdot(w, x)
            w, P = rls_update(w, P, x, e, self.lambda_factor)
            errors[n] = abs(e) ** 2
        self.weights = w
        return w, errors

    def plot_learning_curve(self, errors, ax=None):
        return plot_learning_curve(errors, "RLSBeamformer learning curve", ax)
