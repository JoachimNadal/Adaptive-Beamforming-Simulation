"""MVDR whose covariance comes from IQ time series (two tones)."""

import numpy as np

from dsp.covariance_matrix import compute_covariance_matrix
from dsp.signal_metrics import output_sinr, scene_covariance, to_db
from examples.common import (
    INTERFERER_DEG,
    SEED,
    TARGET_DEG,
    WAVELENGTH,
    mark_directions,
    reference_array,
    show,
)
from simulations.beamforming.mvdr import MVDRBeamformer
from simulations.scenarios.spatiotemporal_signal import simulate_spatiotemporal_sources
from simulations.scenarios.timeseries_snapshot_generator import (
    generate_snapshots_from_timeseries,
)


def main():
    array = reference_array()
    X_time = simulate_spatiotemporal_sources(
        antenna_array=array,
        wavelength=WAVELENGTH,
        time_vector=np.linspace(0, 1, 10000),
        desired_angle=TARGET_DEG,
        interference_angle=INTERFERER_DEG,
        desired_frequency=5,
        interference_frequency=8,
        desired_amplitude=1.0,
        interference_amplitude=0.8,
        noise_power=0.04,
        rng=SEED,
    )
    R = compute_covariance_matrix(generate_snapshots_from_timeseries(X_time, snapshot_step=5))
    mvdr = MVDRBeamformer(array)
    weights = mvdr.compute_weights(R, TARGET_DEG, WAVELENGTH)
    A = array.compute_steering_matrix([TARGET_DEG, INTERFERER_DEG], WAVELENGTH, "deg")
    sinr = output_sinr(weights, A[:, 0], 1.0, scene_covariance(A[:, 1:], [0.64], 0.04))
    print(f"output SINR {to_db(sinr):.1f} dB")
    ax = mvdr.plot_beam_pattern(
        *mvdr.beam_pattern(weights, WAVELENGTH), decibels=True, title="MVDR from time series"
    )
    mark_directions(ax)
    show()


if __name__ == "__main__":
    main()
