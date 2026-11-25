"""Beam pattern computation and plotting shared by every beamformer."""

import matplotlib.pyplot as plt
import numpy as np

from dsp.signal_metrics import beam_response, to_db


def default_angles():
    """Scan grid in degrees. 0.25 deg resolves the nulls of small arrays."""
    return np.arange(-90, 90.25, 0.25)


class Beamformer:
    """Base class: pattern evaluation and plots. Computation never opens a window."""

    def __init__(self, antenna_array):
        self.antenna_array = antenna_array

    def beam_pattern(self, weights, wavelength, angles_deg=None):
        """Return ``(angles_deg, |w^H a|^2)`` for given weights."""
        angles_deg = default_angles() if angles_deg is None else np.asarray(angles_deg)
        A = self.antenna_array.compute_steering_matrix(angles_deg, wavelength, "deg")
        return angles_deg, np.abs(beam_response(weights, A)) ** 2

    def plot_beam_pattern(self, angles_deg, gain, ax=None, decibels=False, title="Beam pattern"):
        """Cartesian plot of a pattern; returns the axes."""
        ax = ax or plt.subplots()[1]
        ax.plot(angles_deg, to_db(gain) if decibels else gain)
        if decibels:
            ax.set_ylim(-60, max(5, np.ceil(to_db(gain).max()) + 2))
        ax.set(
            title=title,
            xlabel="Angle (degrees)",
            ylabel="Gain (dB)" if decibels else "Normalized gain",
        )
        ax.grid(True)
        return ax

    def plot_polar_pattern(self, angles_deg, gain, ax=None, title="Polar beam pattern"):
        """Polar plot (0 degrees up, as in the course); returns the axes."""
        if ax is None:
            ax = plt.subplots(subplot_kw={"projection": "polar"})[1]
        ax.set_theta_zero_location("N")
        ax.set_thetalim(np.radians(np.min(angles_deg)), np.radians(np.max(angles_deg)))
        ax.plot(np.radians(angles_deg), gain)
        ax.set_title(title)
        return ax


def plot_learning_curve(errors, title, ax=None):
    """Squared error in dB against iteration; returns the axes."""
    ax = ax or plt.subplots()[1]
    ax.plot(to_db(errors))
    ax.set(xlabel="Iteration", ylabel="Squared error (dB)", title=title)
    ax.grid(True)
    return ax
