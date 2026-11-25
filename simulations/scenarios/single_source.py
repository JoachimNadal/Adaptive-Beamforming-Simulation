from simulations.channels.awgn import complex_noise


def simulate_single_source_snapshot(
    antenna_array,
    wavelength,
    angle,
    amplitude=1.0,
    noise_power=0.0,
    unite="deg",
    rng=None,
):
    """One snapshot ``a(angle) * amplitude + n`` with ``E|n_m|^2 = noise_power``."""
    a = antenna_array.compute_steering_vector(angle, wavelength, unite)
    return a * amplitude + complex_noise(antenna_array.num_elements, noise_power, rng)
