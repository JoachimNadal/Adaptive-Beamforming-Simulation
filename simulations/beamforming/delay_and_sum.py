from dsp.adaptive_weights import das_weights
from simulations.beamforming.base import Beamformer


class DelayAndSumBeamformer(Beamformer):
    """Conventional beamformer ``w = a / N``: optimal against spatially white noise only."""

    def compute_weights(self, theta_target, wavelength, unite="deg"):
        return das_weights(
            self.antenna_array.compute_steering_vector(theta_target, wavelength, unite)
        )

    def compute_beam_pattern(self, theta_target, wavelength, unite="deg", angles_deg=None):
        weights = self.compute_weights(theta_target, wavelength, unite)
        return self.beam_pattern(weights, wavelength, angles_deg)

    def plot_polar_beam_pattern(self, theta_target, wavelength, unite="deg", ax=None):
        angles_deg, gain = self.compute_beam_pattern(theta_target, wavelength, unite)
        return self.plot_polar_pattern(angles_deg, gain, ax, "Delay-and-Sum polar beam pattern")
