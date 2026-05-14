import numpy as np

from simulations.antenna_array.linear_array import LinearArray

from simulations.scenarios.spatiotemporal_signal import (
    simulate_spatiotemporal_sources
)

from simulations.scenarios.timeseries_snapshot_generator import (
    generate_snapshots_from_timeseries
)

from dsp.covariance_matrix import compute_covariance_matrix

from simulations.beamforming.mvdr import MVDRBeamformer


array = LinearArray(
    num_elements=4,
    spacing=6.25
)

time_vector = np.linspace(0, 1, 10000)

X_time = simulate_spatiotemporal_sources(
    antenna_array=array,
    wavelength=12.5,
    time_vector=time_vector,
    desired_angle=20,
    interference_angle=-40,
    desired_frequency=5,
    interference_frequency=8,
    desired_amplitude=1.0,
    interference_amplitude=0.8,
    noise_power=0.02,
    unite="deg"
)

X_snapshots = generate_snapshots_from_timeseries(
    X_time,
    snapshot_step=5
)

R = compute_covariance_matrix(X_snapshots)

mvdr = MVDRBeamformer(array)

mvdr.compute_beam_pattern(
    covariance_matrix=R,
    theta_target=20,
    wavelength=12.5,
    unite="deg"
)