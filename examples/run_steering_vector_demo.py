"""Steering vector of the reference array for a source at 30 degrees."""

import numpy as np

from examples.common import WAVELENGTH, reference_array, show


def main():
    array = reference_array()
    a = array.compute_steering_vector(30, WAVELENGTH, unite="deg")
    print("a(30 deg) =", np.round(a, 3), " (expected 1, -j, -1, +j)")
    array.plot_steering_phases(30, WAVELENGTH, unite="deg")
    show()


if __name__ == "__main__":
    main()
