"""Sample covariance of two uncorrelated sources, and its eigenvalues."""

import matplotlib.pyplot as plt
import numpy as np

from dsp.covariance_matrix import compute_covariance_matrix
from examples.common import (
    INTERFERER_DEG,
    SEED,
    TARGET_DEG,
    WAVELENGTH,
    reference_array,
    show,
)
from simulations.scenarios.snapshot_generator import generate_snapshot_matrix


def main():
    X = generate_snapshot_matrix(
        antenna_array=reference_array(),
        wavelength=WAVELENGTH,
        desired_angle=TARGET_DEG,
        interference_angle=INTERFERER_DEG,
        desired_amplitude=1.0,
        interference_amplitude=0.8,
        noise_power=0.05,
        num_snapshots=500,
        rng=SEED,
    )
    R = compute_covariance_matrix(X)
    print("eigenvalues:", np.round(np.linalg.eigvalsh(R)[::-1], 3), "(2 sources + noise 0.05)")
    plt.imshow(np.abs(R))
    plt.title("Covariance matrix magnitude")
    plt.colorbar()
    show()


if __name__ == "__main__":
    main()
