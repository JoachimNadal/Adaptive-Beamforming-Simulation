from dsp.adaptive_weights import mvdr_weights
from dsp.covariance_matrix import loading_level
from simulations.beamforming.base import Beamformer


class MVDRBeamformer(Beamformer):
    """Minimum variance distortionless response (Capon) beamformer.

    ``relative_loading`` adds ``relative_loading * tr(R)/N`` to the diagonal. The default 0
    is the textbook beamformer, which raises ``IllConditionedError`` when the covariance is
    rank deficient (for instance fewer snapshots than antennas).
    """

    def __init__(self, antenna_array, relative_loading=0.0):
        super().__init__(antenna_array)
        self.relative_loading = relative_loading

    def compute_weights(self, covariance_matrix, theta_target, wavelength, unite="deg"):
        a = self.antenna_array.compute_steering_vector(theta_target, wavelength, unite)
        loading = loading_level(covariance_matrix, self.relative_loading)
        return mvdr_weights(covariance_matrix, a, loading)

    def compute_beam_pattern(
        self, covariance_matrix, theta_target, wavelength, unite="deg", angles_deg=None
    ):
        weights = self.compute_weights(covariance_matrix, theta_target, wavelength, unite)
        return self.beam_pattern(weights, wavelength, angles_deg)
