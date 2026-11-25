import numpy as np

from simulations.channels.awgn import complex_noise


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
    unite="deg",
    rng=None,
):
    """Two complex tones received by the array, as ``(num_antennas, num_samples)`` IQ.

    The spatial phase comes from the array object itself, so it cannot disagree with the
    steering vectors used by the beamformers, and any geometry is supported.
    """
    t = np.asarray(time_vector)
    A = antenna_array.compute_steering_matrix(
        [desired_angle, interference_angle], wavelength, unite
    )
    S = np.stack(
        (
            desired_amplitude * np.exp(2j * np.pi * desired_frequency * t),
            interference_amplitude * np.exp(2j * np.pi * interference_frequency * t),
        )
    )
    return A @ S + complex_noise((antenna_array.num_elements, t.size), noise_power, rng)
