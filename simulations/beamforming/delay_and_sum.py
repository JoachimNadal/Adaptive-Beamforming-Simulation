import numpy as np
import matplotlib.pyplot as plt


class DelayAndSumBeamformer:

    def __init__(self, antenna_array):
        self.antenna_array = antenna_array

    def compute_weights(self, theta_target, wavelength, unite="deg"):
        a = self.antenna_array.compute_steering_vector(
            theta_target,
            wavelength,
            unite
        )

        return a / self.antenna_array.num_elements

    def compute_beam_pattern(self, theta_target, wavelength, unite="deg"):
        weights = self.compute_weights(theta_target, wavelength, unite)

        angles_deg = np.arange(-90, 91, 5)
        beam_pattern = np.zeros(len(angles_deg), dtype=complex)

        for idx, angle in enumerate(angles_deg):
            a = self.antenna_array.compute_steering_vector(
                angle,
                wavelength,
                "deg"
            )

            beam_pattern[idx] = np.vdot(weights, a)

        gain = np.abs(beam_pattern) ** 2

        plt.plot(angles_deg, gain)
        plt.title("Delay-and-Sum Beam Pattern")
        plt.xlabel("Angle (degrees)")
        plt.ylabel("Normalized Gain")
        plt.grid(True)
        plt.show()

        return angles_deg, gain

    def plot_polar_beam_pattern(self, theta_target, wavelength, unite="deg"):
        weights = self.compute_weights(theta_target, wavelength, unite)

        angles_deg = np.arange(-90, 91, 5)
        angles_rad = np.radians(angles_deg)

        beam_pattern = np.zeros(len(angles_deg), dtype=complex)

        for idx, angle in enumerate(angles_deg):
            a = self.antenna_array.compute_steering_vector(
                angle,
                wavelength,
                "deg"
            )

            beam_pattern[idx] = np.vdot(weights, a)

        gain = np.abs(beam_pattern) ** 2

        plt.polar(angles_rad, gain)
        plt.title("Delay-and-Sum Polar Beam Pattern")
        plt.show()





