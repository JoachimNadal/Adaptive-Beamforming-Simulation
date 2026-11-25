"""MVDR against delay-and-sum, and the coherent-source failure of MVDR."""

import matplotlib.pyplot as plt
import numpy as np

from dsp.covariance_matrix import compute_covariance_matrix
from dsp.signal_metrics import to_db
from examples.common import (
    INTERFERER_DEG,
    SEED,
    TARGET_DEG,
    WAVELENGTH,
    mark_directions,
    reference_array,
    show,
)
from simulations.beamforming.delay_and_sum import DelayAndSumBeamformer
from simulations.beamforming.mvdr import MVDRBeamformer
from simulations.scenarios.snapshot_generator import generate_snapshot_matrix


def main():
    array = reference_array()
    das, mvdr = DelayAndSumBeamformer(array), MVDRBeamformer(array)
    a_int = array.compute_steering_vector(INTERFERER_DEG, WAVELENGTH, "deg")
    _, ax = plt.subplots()
    das.plot_beam_pattern(*das.compute_beam_pattern(TARGET_DEG, WAVELENGTH), ax, True)
    ax.get_lines()[-1].set_label("delay-and-sum")
    for coherent in (False, True):
        X = generate_snapshot_matrix(
            antenna_array=array,
            wavelength=WAVELENGTH,
            desired_angle=TARGET_DEG,
            interference_angle=INTERFERER_DEG,
            desired_amplitude=1.0,
            interference_amplitude=0.7,
            noise_power=0.04,
            num_snapshots=2000,
            rng=SEED,
            coherent=coherent,
        )
        w = mvdr.compute_weights(compute_covariance_matrix(X), TARGET_DEG, WAVELENGTH)
        label = "MVDR, coherent sources" if coherent else "MVDR, uncorrelated sources"
        print(f"{label}: gain toward interferer {to_db(abs(np.vdot(w, a_int)) ** 2):.1f} dB")
        mvdr.plot_beam_pattern(*mvdr.beam_pattern(w, WAVELENGTH), ax, True)
        ax.get_lines()[-1].set_label(label)
    ax.set_title("MVDR")
    mark_directions(ax)
    show()


if __name__ == "__main__":
    main()
