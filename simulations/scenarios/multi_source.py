import numpy as np


def simulate_multi_source_snapshot(
    antenna_array,
    wavelength,
    desired_angle,
    interference_angle,
    desired_amplitude,
    interference_amplitude,
    noise_power
):
    a1 = antenna_array.compute_steering_vector(desired_angle, wavelength, unite="rad")
    a2 = antenna_array.compute_steering_vector(interference_angle, wavelength, unite="rad")

    noise_std = np.sqrt(noise_power)

    noise = noise_std * (
        np.random.normal(0, 1, antenna_array.num_elements)
        + 1j * np.random.normal(0, 1, antenna_array.num_elements)
    )

    x = a1 * desired_amplitude + a2 * interference_amplitude + noise

    return x