import numpy as np

from dsp.adaptive_weights import lms_update, nlms_update
from simulations.beamforming.base import Beamformer, plot_learning_curve


class LMSBeamformer(Beamformer):
    """Least-mean-squares beamformer trained on a reference signal.

    Stable in the mean for ``0 < mu < 2 / lambda_max(R)``; ``mu < 1 / tr(R)`` is a safe
    choice that needs no eigenvalue.
    """

    def __init__(self, antenna_array, mu=0.01):
        super().__init__(antenna_array)
        self.mu = mu

    def _update(self, w, x, error):
        return lms_update(w, x, error, self.mu)

    def train(self, X, desired_signal):
        """Adapt over all snapshots; returns final weights and squared a-priori errors."""
        num_antennas, num_samples = X.shape
        w = np.zeros(num_antennas, dtype=complex)
        errors = np.empty(num_samples)
        for i in range(num_samples):
            x = X[:, i]
            e = desired_signal[i] - np.vdot(w, x)
            w = self._update(w, x, e)
            errors[i] = abs(e) ** 2
        self.weights = w
        return w, errors

    def plot_learning_curve(self, errors, ax=None):
        return plot_learning_curve(errors, f"{type(self).__name__} learning curve", ax)


class NLMSBeamformer(LMSBeamformer):
    """LMS with the step normalised by the snapshot power; stable for ``0 < mu < 2``.

    Preferred over LMS when the interference level can change abruptly.
    """

    def __init__(self, antenna_array, mu=0.5):
        super().__init__(antenna_array, mu)

    def _update(self, w, x, error):
        return nlms_update(w, x, error, self.mu)
