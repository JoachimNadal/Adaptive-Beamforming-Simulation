"""One snapshot of two superposed sources: amplitude and phase across the array."""

import matplotlib.pyplot as plt
import numpy as np

from examples.common import (
    INTERFERER_DEG,
    SEED,
    TARGET_DEG,
    WAVELENGTH,
    reference_array,
    show,
)
from simulations.scenarios.multi_source import simulate_multi_source_snapshot


def main():
    x = simulate_multi_source_snapshot(
        antenna_array=reference_array(),
        wavelength=WAVELENGTH,
        desired_angle=TARGET_DEG,
        interference_angle=INTERFERER_DEG,
        desired_amplitude=1.0,
        interference_amplitude=0.8,
        noise_power=0.05,
        rng=SEED,
    )
    fig, (top, bottom) = plt.subplots(2, 1, sharex=True)
    top.stem(np.abs(x))
    top.set(ylabel="Amplitude", title="Snapshot of two sources")
    bottom.stem(np.angle(x, deg=True))
    bottom.set(ylabel="Phase (deg)", xlabel="Antenna index")
    bottom.set_xticks(range(len(x)))
    fig.tight_layout()
    show()


if __name__ == "__main__":
    main()
