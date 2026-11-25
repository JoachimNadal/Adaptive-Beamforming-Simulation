from simulations.channels.awgn import complex_noise


def simulate_multi_source_snapshot(
    antenna_array,
    wavelength,
    desired_angle,
    interference_angle,
    desired_amplitude,
    interference_amplitude,
    noise_power,
    unite="deg",
    rng=None,
):
    """One snapshot of two sources with the given complex amplitudes, plus noise.

    Amplitudes are deterministic, so stacking several of these snapshots yields fully
    coherent sources. Use ``generate_snapshot_matrix`` to estimate a covariance.
    """
    a1 = antenna_array.compute_steering_vector(desired_angle, wavelength, unite)
    a2 = antenna_array.compute_steering_vector(interference_angle, wavelength, unite)
    noise = complex_noise(antenna_array.num_elements, noise_power, rng)
    return a1 * desired_amplitude + a2 * interference_amplitude + noise
