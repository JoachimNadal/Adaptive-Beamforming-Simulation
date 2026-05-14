from simulations.antenna_array.linear_array import LinearArray
from simulations.beamforming.null_steering import NullSteeringBeamformer


array = LinearArray(
    num_elements=4,
    spacing=6.25
)

beamformer = NullSteeringBeamformer(array)

beamformer.compute_beam_pattern(
    theta_target=20,
    theta_interference=-40,
    wavelength=12.5,
    unite="deg"
)

