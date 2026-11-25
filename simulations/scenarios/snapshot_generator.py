import numpy as np

from simulations.channels.awgn import complex_noise, make_rng


def generate_snapshot_matrix(
    antenna_array,
    wavelength,
    desired_angle,
    interference_angle,
    desired_amplitude,
    interference_amplitude,
    noise_power,
    num_snapshots,
    unite="deg",
    rng=None,
    coherent=False,
):
    """Snapshot matrix ``(num_antennas, num_snapshots)`` of two sources in white noise.

    Each source is an independent circular Gaussian process whose RMS value is the given
    amplitude. ``coherent=True`` keeps both amplitudes constant over time instead: the
    source covariance is then rank 1 and MVDR cancels the wanted signal. It is kept to
    demonstrate that failure, which was the only behaviour before Phase 1.
    """
    rng = make_rng(rng)
    A = antenna_array.compute_steering_matrix(
        [desired_angle, interference_angle], wavelength, unite
    )
    amplitudes = np.array([[desired_amplitude], [interference_amplitude]])
    if coherent:
        S = amplitudes * np.ones((2, num_snapshots))
    else:
        S = amplitudes * complex_noise((2, num_snapshots), 1.0, rng)
    return A @ S + complex_noise((antenna_array.num_elements, num_snapshots), noise_power, rng)
