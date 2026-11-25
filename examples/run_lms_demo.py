"""LMS and NLMS learning curves with a known reference signal."""

import numpy as np

from dsp.signal_metrics import to_db
from examples.common import (
    INTERFERER_DEG,
    SEED,
    TARGET_DEG,
    WAVELENGTH,
    reference_array,
    show,
)
from simulations.beamforming.lms import LMSBeamformer, NLMSBeamformer
from simulations.scenarios.spatiotemporal_signal import simulate_spatiotemporal_sources


def main():
    array = reference_array()
    time_vector = np.linspace(0, 1, 2000)
    X = simulate_spatiotemporal_sources(
        antenna_array=array,
        wavelength=WAVELENGTH,
        time_vector=time_vector,
        desired_angle=TARGET_DEG,
        interference_angle=INTERFERER_DEG,
        desired_frequency=5,
        interference_frequency=12,
        desired_amplitude=1.0,
        interference_amplitude=0.8,
        noise_power=0.06,
        rng=SEED,
    )
    reference = np.exp(2j * np.pi * 5 * time_vector)
    for beamformer in (LMSBeamformer(array, mu=0.01), NLMSBeamformer(array, mu=0.1)):
        _, errors = beamformer.train(X, reference)
        print(f"{type(beamformer).__name__}: final MSE {to_db(errors[-200:].mean()):.1f} dB")
        beamformer.plot_learning_curve(errors)
    show()


if __name__ == "__main__":
    main()
