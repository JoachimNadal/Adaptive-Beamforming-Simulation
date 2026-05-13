import numpy as np
import matplotlib.pyplot as plt

from matplotlib.animation import FuncAnimation

from simulations.antenna_array.linear_array import LinearArray
from simulations.scenarios.spatiotemporal_signal import simulate_spatiotemporal_sources


array = LinearArray(
    num_elements=4,
    spacing=6.25
)

time_vector = np.linspace(0, 1, 1000)

X = simulate_spatiotemporal_sources(
    antenna_array=array,
    wavelength=12.5,
    time_vector=time_vector,
    desired_angle=20,
    interference_angle=-40,
    desired_frequency=5,
    interference_frequency=8,
    desired_amplitude=1.0,
    interference_amplitude=0.7,
    noise_power=0.02,
    unite="deg"
)

fig, ax = plt.subplots()

window_size = 200


def update(frame):
    ax.clear()

    start = frame
    end = frame + window_size

    for antenna_idx in range(array.num_elements):
        ax.plot(
            time_vector[start:end],
            np.real(X[antenna_idx, start:end]),
            label=f"Antenna {antenna_idx}"
        )

    ax.set_title("Spatiotemporal IQ Signal - Real Part")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Amplitude")
    ax.grid(True)
    ax.legend(loc="upper right")


animation = FuncAnimation(
    fig,
    update,
    frames=len(time_vector) - window_size,
    interval=30
)

plt.show()