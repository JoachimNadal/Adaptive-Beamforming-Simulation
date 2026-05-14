import numpy as np

from simulations.antenna_array.linear_array import LinearArray
from simulations.scenarios.spatiotemporal_signal import simulate_spatiotemporal_sources
from simulations.beamforming.lms import LMSBeamformer
from simulations.beamforming.rls import RLSBeamformer


def test_rls_converges_faster_than_lms():
    array = LinearArray(num_elements=4, spacing=6.25)

    time_vector = np.linspace(0, 1, 2000)

    desired_frequency = 5
    interference_frequency = 12

    X_time = simulate_spatiotemporal_sources(
        antenna_array=array,
        wavelength=12.5,
        time_vector=time_vector,
        desired_angle=20,
        interference_angle=-40,
        desired_frequency=desired_frequency,
        interference_frequency=interference_frequency,
        desired_amplitude=1.0,
        interference_amplitude=0.8,
        noise_power=0.03,
        unite="deg"
    )

    desired_signal = np.exp(
        1j * 2 * np.pi * desired_frequency * time_vector
    )

    lms = LMSBeamformer(array, mu=0.001)
    rls = RLSBeamformer(array, lambda_factor=0.99, delta=1.0)

    _, lms_errors = lms.train(X_time, desired_signal)
    _, rls_errors = rls.train(X_time, desired_signal)

    lms_early_error = np.mean(lms_errors[:200])
    rls_early_error = np.mean(rls_errors[:200])

    assert rls_early_error < lms_early_error