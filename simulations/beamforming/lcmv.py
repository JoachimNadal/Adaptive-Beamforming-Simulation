import numpy as np

from dsp.adaptive_weights import lcmv_weights
from dsp.covariance_matrix import loading_level
from simulations.beamforming.base import Beamformer


class LCMVBeamformer(Beamformer):
    """Linearly constrained minimum variance beamformer (course chapters 11 and 23).

    Unit response toward the target, optional zero slope there (tolerance to pointing
    errors) and optional explicit nulls, each consuming one degree of freedom.
    """

    def __init__(self, antenna_array, relative_loading=0.0, derivative_constraint=False):
        super().__init__(antenna_array)
        self.relative_loading = relative_loading
        self.derivative_constraint = derivative_constraint

    def constraints(self, theta_target, theta_nulls, wavelength, unite="deg"):
        """Constraint matrix ``C`` and response vector ``f``."""
        array = self.antenna_array
        columns = [array.compute_steering_vector(theta_target, wavelength, unite)]
        if self.derivative_constraint:
            # Projected orthogonally to a(theta), i.e. referenced to the array centroid. With
            # the phase origin on element 0 the constraint would also force the phase centre
            # there, which costs 5.2 dB of array gain for N = 8 (docs/theory/course_errata.md).
            a = columns[0]
            d = array.compute_steering_derivative(theta_target, wavelength, unite)
            d = d - a * np.vdot(a, d) / np.vdot(a, a).real
            norm = np.linalg.norm(d)
            if norm > 1e-9 * np.linalg.norm(a):
                columns.append(d * np.linalg.norm(a) / norm)  # same scale as a: conditioning
        columns += [array.compute_steering_vector(t, wavelength, unite) for t in theta_nulls]
        f = np.zeros(len(columns), dtype=complex)
        f[0] = 1.0
        return np.column_stack(columns), f

    def compute_weights(
        self, covariance_matrix, theta_target, wavelength, theta_nulls=(), unite="deg"
    ):
        C, f = self.constraints(theta_target, theta_nulls, wavelength, unite)
        loading = loading_level(covariance_matrix, self.relative_loading)
        return lcmv_weights(covariance_matrix, C, f, loading)

    def compute_beam_pattern(
        self,
        covariance_matrix,
        theta_target,
        wavelength,
        theta_nulls=(),
        unite="deg",
        angles_deg=None,
    ):
        weights = self.compute_weights(
            covariance_matrix, theta_target, wavelength, theta_nulls, unite
        )
        return self.beam_pattern(weights, wavelength, angles_deg)
