import numpy as np


def simulate_single_source_snapshot(
    antenna_array,
    wavelength,
    angle,
    amplitude=1.0,
    noise_power=0.0,
    unite="deg"
):
    steering_vector = antenna_array.compute_steering_vector(
        theta=angle,
        wavelength=wavelength,
        unite=unite
    )

    noise_std = np.sqrt(noise_power)

    noise = noise_std * (
        np.random.normal(0, 1, antenna_array.num_elements)
        + 1j * np.random.normal(0, 1, antenna_array.num_elements)
    )

    x = steering_vector * amplitude + noise

    return x
