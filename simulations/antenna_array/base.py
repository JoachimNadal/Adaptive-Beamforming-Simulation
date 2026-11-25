"""Interface shared by every array geometry."""

import matplotlib.pyplot as plt
import numpy as np

from dsp.steering import steering_derivative, steering_matrix, to_radians


class AntennaArray:
    """Array of isotropic, identical, uncoupled elements in the (x, y) plane.

    ``positions_xy`` has shape ``(N, 2)``. Positions and wavelength must use the same
    length unit; the project examples use centimetres.
    """

    def __init__(self, positions_xy):
        self.positions_xy = np.asarray(positions_xy, dtype=float)
        if self.positions_xy.ndim != 2 or self.positions_xy.shape[1] != 2:
            raise ValueError("positions_xy must have shape (N, 2)")
        self.num_elements = len(self.positions_xy)

    def compute_steering_vector(self, theta, wavelength, unite="rad"):
        """Steering vector ``a(theta)``, shape ``(N,)``."""
        return self.compute_steering_matrix(theta, wavelength, unite)[:, 0]

    def compute_steering_matrix(self, thetas, wavelength, unite="rad"):
        """Steering vectors as columns, shape ``(N, len(thetas))``."""
        return steering_matrix(self.positions_xy, to_radians(thetas, unite), wavelength)

    def compute_steering_derivative(self, theta, wavelength, unite="rad"):
        """``da/dtheta`` per radian, shape ``(N,)``, whatever the unit of ``theta``."""
        return steering_derivative(self.positions_xy, to_radians(theta, unite), wavelength)[:, 0]

    def plot_array(self, ax=None):
        """Draw the element positions; returns the axes."""
        ax = ax or plt.subplots()[1]
        ax.scatter(self.positions_xy[:, 0], self.positions_xy[:, 1])
        for index, (x, y) in enumerate(self.positions_xy):
            ax.annotate(f"A{index}", (x, y), textcoords="offset points", xytext=(4, 6))
        ax.set(xlabel="x", ylabel="y", title="Array geometry")
        ax.set_aspect("equal", adjustable="datalim")
        return ax

    def plot_steering_phases(self, theta, wavelength, unite="rad", ax=None):
        """Plot the wrapped phase seen by each element; returns the axes."""
        ax = ax or plt.subplots()[1]
        phases = np.angle(self.compute_steering_vector(theta, wavelength, unite), deg=True)
        ax.stem(np.arange(self.num_elements), phases)
        ax.set(xlabel="Antenna index", ylabel="Phase (deg)", title="Steering vector phases")
        ax.set_xticks(range(self.num_elements))
        return ax
