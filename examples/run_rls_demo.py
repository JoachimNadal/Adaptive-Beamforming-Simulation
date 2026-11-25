"""RLS learning curve with a known reference signal."""

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
from simulations.beamforming.rls import RLSBeamformer
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
    rls = RLSBeamformer(array, lambda_factor=0.99, delta=1.0)
    _, errors = rls.train(X, reference)
    print(f"RLS: final MSE {to_db(errors[-200:].mean()):.1f} dB")
    rls.plot_learning_curve(errors)
    show()


if __name__ == "__main__":
    main()
