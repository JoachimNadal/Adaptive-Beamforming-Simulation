"""Beam pattern panel."""

import numpy as np

from dsp.signal_metrics import to_db
from simulations.plot_style import REFERENCE, SERIES

FLOOR_DB = -50


class PolarPatternPanel:
    """Current beam pattern in dB, with the target and the explicit nulls."""

    def __init__(self, ax, array, wavelength, target_deg):
        self.ax = ax
        self.angles_deg = np.arange(-90, 90.5, 0.5)
        self.A = array.compute_steering_matrix(self.angles_deg, wavelength, "deg")
        ax.set_theta_zero_location("N")
        ax.set_thetalim(-np.pi / 2, np.pi / 2)
        ax.set_ylim(FLOOR_DB, 5)
        ax.set_yticks([-40, -20, 0])
        ax.set_title("Beam pattern (dB)")
        (self.line,) = ax.plot([], [], color=SERIES[0])
        (self.nulls,) = ax.plot(
            [], [], linestyle="none", marker="v", color=SERIES[1], label="explicit nulls"
        )
        ax.axvline(np.radians(target_deg), color=REFERENCE, linestyle=":", label="target")
        ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.05), ncol=2)

    def update(self, weights, nulls_deg):
        gain = to_db(np.abs(weights.conj() @ self.A) ** 2)
        self.line.set_data(np.radians(self.angles_deg), np.maximum(gain, FLOOR_DB))
        self.nulls.set_data(np.radians(nulls_deg), np.full(len(nulls_deg), -8.0))
