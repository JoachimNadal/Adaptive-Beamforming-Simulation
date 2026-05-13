from simulations.antenna_array.linear_array import LinearArray
from simulations.beamforming.delay_and_sum import DelayAndSumBeamformer


array = LinearArray(
    num_elements=4,
    spacing=6.25
)

beamformer = DelayAndSumBeamformer(array)

beamformer.compute_beam_pattern(
    theta_target=30,
    wavelength=12.5
)
