import numpy as np

from simulations.antenna_array.base import AntennaArray


class CircularArray(AntennaArray):
    """Uniform circular array, for 360 degree azimuth coverage.

    Element ``m`` sits at ``radius * (cos(2 pi m / N), sin(2 pi m / N))`` and the phase
    reference is the centre, so no element has zero phase in general. The structure is not
    shift-invariant: ESPRIT, root-MUSIC and spatial smoothing do not apply directly.
    """

    def __init__(self, num_elements, radius):
        if num_elements < 3 or radius <= 0:
            raise ValueError("num_elements must be >= 3 and radius > 0")
        self.radius = radius
        phi = 2 * np.pi * np.arange(num_elements) / num_elements
        super().__init__(radius * np.column_stack((np.cos(phi), np.sin(phi))))

    @classmethod
    def from_spacing(cls, num_elements, spacing):
        """Array whose adjacent elements are ``spacing`` apart (chord length)."""
        return cls(num_elements, spacing / (2 * np.sin(np.pi / num_elements)))
