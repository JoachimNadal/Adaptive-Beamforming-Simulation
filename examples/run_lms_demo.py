from simulations.antenna_array.linear_array import LinearArray
from simulations.scenarios.spatiotemporal_signal import simulate_spatiotemporal_sources
from simulations.beamforming.lms import LMSBeamformer

import numpy as np


array = LinearArray(
    num_elements=4,
    spacing=6.25
)

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

beamformer = LMSBeamformer(
    antenna_array=array,
    mu=0.001
)

weights, errors = beamformer.train(
    X_time,
    desired_signal
)

beamformer.plot_learning_curve(errors)