"""Deterministic null toward a known interferer."""

from dsp.signal_metrics import white_noise_gain
from examples.common import (
    INTERFERER_DEG,
    TARGET_DEG,
    WAVELENGTH,
    mark_directions,
    reference_array,
    show,
)
from simulations.beamforming.null_steering import NullSteeringBeamformer


def main():
    array = reference_array()
    beamformer = NullSteeringBeamformer(array)
    weights = beamformer.compute_weights(TARGET_DEG, INTERFERER_DEG, WAVELENGTH)
    a = array.compute_steering_vector(TARGET_DEG, WAVELENGTH, "deg")
    print(f"white noise gain {white_noise_gain(weights, a):.2f} (maximum {array.num_elements})")
    ax = beamformer.plot_beam_pattern(
        *beamformer.beam_pattern(weights, WAVELENGTH), decibels=True, title="Null steering"
    )
    mark_directions(ax)
    show()


if __name__ == "__main__":
    main()
