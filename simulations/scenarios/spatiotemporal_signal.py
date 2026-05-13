import numpy as np
import math


def simulate_spatiotemporal_sources(
    antenna_array,
    wavelength,
    time_vector,
    desired_angle,
    interference_angle,
    desired_frequency,
    interference_frequency,
    desired_amplitude,
    interference_amplitude,
    noise_power,
    unite="deg"
):
    if unite == "deg":
        desired_angle = math.radians(desired_angle)
        interference_angle = math.radians(interference_angle)

    k = 2 * math.pi / wavelength
    noise_std = math.sqrt(noise_power)

    num_antennas = antenna_array.num_elements
    num_samples = len(time_vector)

    X = np.zeros((num_antennas, num_samples), dtype=complex)

    for antenna_idx in range(num_antennas):
        spatial_phase_desired = (
            antenna_idx
            * k
            * antenna_array.spacing
            * math.sin(desired_angle)
        )

        spatial_phase_interference = (
            antenna_idx
            * k
            * antenna_array.spacing
            * math.sin(interference_angle)
        )

        for time_idx in range(num_samples):
            t = time_vector[time_idx]

            desired_signal = desired_amplitude * np.exp(
                1j * (2 * math.pi * desired_frequency * t + spatial_phase_desired)
            )

            interference_signal = interference_amplitude * np.exp(
                1j * (2 * math.pi * interference_frequency * t + spatial_phase_interference)
            )

            noise = noise_std * (
                np.random.normal(0, 1)
                + 1j * np.random.normal(0, 1)
            )

            X[antenna_idx, time_idx] = (
                desired_signal
                + interference_signal
                + noise
            )

    return X