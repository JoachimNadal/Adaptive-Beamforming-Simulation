import numpy as np

from simulations.antenna_array.linear_array import LinearArray
from simulations.beamforming.delay_and_sum import DelayAndSumBeamformer


def test_delay_and_sum_peak_near_target():
    array = LinearArray(num_elements=4, spacing=6.25)
    beamformer = DelayAndSumBeamformer(array)

    angles_deg, gain = beamformer.compute_beam_pattern(
        theta_target=30,
        wavelength=12.5
    )

    peak_angle = angles_deg[np.argmax(gain)]

    assert abs(peak_angle - 30) <= 5