from simulations.antenna_array.linear_array import LinearArray
from simulations.scenarios.snapshot_generator import generate_snapshot_matrix
from dsp.covariance_matrix import compute_covariance_matrix
from simulations.beamforming.mvdr import MVDRBeamformer


array = LinearArray(
    num_elements=4,
    spacing=6.25
)

X = generate_snapshot_matrix(
    antenna_array=array,
    wavelength=12.5,
    desired_angle=20,
    interference_angle=-40,
    desired_amplitude=1.0,
    interference_amplitude=0.7,
    noise_power=0.02,
    num_snapshots=200000,
    unite="deg"
)


R = compute_covariance_matrix(X)


mvdr = MVDRBeamformer(antenna_array=array)


beam_pattern = mvdr.compute_beam_pattern(R, theta_target = 20, wavelength = 12.5, unite="deg")


