import numpy as np

from simulations.scenarios.multi_source import simulate_multi_source_snapshot


def generate_snapshot_matrix(
    antenna_array,
    wavelength,
    desired_angle,
    interference_angle,
    desired_amplitude,
    interference_amplitude,
    noise_power,
    num_snapshots
):

    X = np.zeros((antenna_array.num_elements, num_snapshots),dtype=complex)

    for i in range(num_snapshots):

        X[:, i] = simulate_multi_source_snapshot(
            antenna_array,
            wavelength,
            desired_angle,
            interference_angle,
            desired_amplitude,
            interference_amplitude,
            noise_power
        )

    return X