"""Direction-time waterfall panel."""

import numpy as np

from dsp.covariance_matrix import compute_covariance_matrix
from dsp.signal_metrics import to_db
from simulations.doa.capon import capon_spectrum
from simulations.plot_style import SEQUENTIAL


class DoaHeatmapPanel:
    """Capon spectrum of the last ``history`` blocks, newest at the top."""

    def __init__(self, ax, array, wavelength, history=80, span_db=40):
        self.ax = ax
        self.angles_deg = np.arange(-90, 91, 1.0)
        self.A = array.compute_steering_matrix(self.angles_deg, wavelength, "deg")
        self.data = np.full((history, self.angles_deg.size), np.nan)
        self.image = ax.imshow(
            self.data,
            aspect="auto",
            origin="lower",
            extent=(-90, 90, -history, 0),
            cmap=SEQUENTIAL,
            vmin=-span_db,
            vmax=0,
        )
        ax.grid(False)
        ax.set(xlabel="Angle (degrees)", ylabel="Block", title="Direction of arrival (Capon)")
        ax.figure.colorbar(self.image, ax=ax, label="dB below maximum", shrink=0.8)

    def update(self, X):
        R = compute_covariance_matrix(np.asarray(X, dtype=complex))
        spectrum = to_db(capon_spectrum(R, self.A, relative_loading=1e-4))
        self.data = np.vstack((self.data[1:], spectrum - spectrum.max()))
        self.image.set_data(self.data)
