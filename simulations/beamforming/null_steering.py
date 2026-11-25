import numpy as np

from dsp.adaptive_weights import null_steering_weights
from simulations.beamforming.base import Beamformer


class NullSteeringBeamformer(Beamformer):
    """Deterministic minimum-norm nulls toward known interference directions.

    ``theta_interference`` is one angle or a list of up to ``N - 1`` angles.
    """

    def compute_weights(
        self, theta_target, theta_interference, wavelength, unite="deg", regularization=0.0
    ):
        angles = [theta_target, *np.atleast_1d(theta_interference)]
        C = self.antenna_array.compute_steering_matrix(angles, wavelength, unite)
        f = np.zeros(len(angles), dtype=complex)
        f[0] = 1.0
        return null_steering_weights(C, f, regularization)

    def compute_beam_pattern(
        self, theta_target, theta_interference, wavelength, unite="deg", angles_deg=None
    ):
        weights = self.compute_weights(theta_target, theta_interference, wavelength, unite)
        return self.beam_pattern(weights, wavelength, angles_deg)
