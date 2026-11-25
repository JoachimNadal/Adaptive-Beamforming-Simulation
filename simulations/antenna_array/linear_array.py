import numpy as np

from simulations.antenna_array.base import AntennaArray


class LinearArray(AntennaArray):
    """Uniform linear array on the x axis: ``a_m = exp(-j m k d sin(theta))``."""

    def __init__(self, num_elements, spacing):
        if num_elements < 1 or spacing <= 0:
            raise ValueError("num_elements must be >= 1 and spacing > 0")
        self.spacing = spacing
        self.positions = np.arange(num_elements) * spacing
        super().__init__(np.column_stack((self.positions, np.zeros(num_elements))))

    def get_positions(self):
        return self.positions
