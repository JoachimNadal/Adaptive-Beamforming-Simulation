import numpy as np

from simulations.antenna_array.linear_array import LinearArray
from simulations.beamforming.null_steering import NullSteeringBeamformer


def test_null_steering_suppresses_interference():
    array = LinearArray(num_elements=4, spacing=6.25)
    beamformer = NullSteeringBeamformer(array)

    weights = beamformer.compute_weights(
        theta_target=20,
        theta_interference=-40,
        wavelength=12.5,
        unite="deg"
    )

    a_interference = array.compute_steering_vector(
        theta=-40,
        wavelength=12.5,
        unite="deg"
    )

    response = np.vdot(weights, a_interference)
    gain = np.abs(response) ** 2

    assert gain < 0.01