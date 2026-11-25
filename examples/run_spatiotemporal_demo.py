"""Animated IQ time series received by each antenna."""

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation

from examples.common import (
    INTERFERER_DEG,
    SEED,
    TARGET_DEG,
    WAVELENGTH,
    is_headless,
    reference_array,
    show,
)
from simulations.scenarios.spatiotemporal_signal import simulate_spatiotemporal_sources

WINDOW = 200


def main():
    array = reference_array()
    time_vector = np.linspace(0, 1, 1000)
    X = simulate_spatiotemporal_sources(
        antenna_array=array,
        wavelength=WAVELENGTH,
        time_vector=time_vector,
        desired_angle=TARGET_DEG,
        interference_angle=INTERFERER_DEG,
        desired_frequency=5,
        interference_frequency=8,
        desired_amplitude=1.0,
        interference_amplitude=0.7,
        noise_power=0.04,
        rng=SEED,
    )
    fig, ax = plt.subplots()

    def update(frame):
        ax.clear()
        window = slice(frame, frame + WINDOW)
        for index in range(array.num_elements):
            ax.plot(time_vector[window], X[index, window].real, label=f"Antenna {index}")
        ax.set(title="Spatiotemporal IQ signal, real part", xlabel="Time (s)", ylabel="Amplitude")
        ax.set_ylim(-2.5, 2.5)
        ax.grid(True)
        ax.legend(loc="upper right")

    update(0)
    animation = FuncAnimation(fig, update, frames=len(time_vector) - WINDOW, interval=30)
    animation._draw_was_started = is_headless()  # nothing to animate without a window
    show()


if __name__ == "__main__":
    main()
