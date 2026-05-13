from simulations.antenna_array.linear_array import LinearArray
from simulations.beamforming.delay_and_sum import DelayAndSumBeamformer
from matplotlib.animation import FuncAnimation
import numpy as np
import matplotlib.pyplot as plt

array = LinearArray(
    num_elements=4,
    spacing=6.25
)

beamformer = DelayAndSumBeamformer(array)

fig, ax = plt.subplots(subplot_kw={'projection': 'polar'})

def update(frame):
    ax.clear()

    theta_target = -60 + frame

    weights = beamformer.compute_weights(
        theta_target,
        12.5,
        unite="deg"
    )

    angles_deg = np.arange(-90, 91, 1)
    angles_rad = np.radians(angles_deg)

    beam_pattern = np.zeros(len(angles_deg), dtype=complex)

    for idx, angle in enumerate(angles_deg):
        a = array.compute_steering_vector(
            angle,
            12.5,
            unite="deg"
        )

        beam_pattern[idx] = np.vdot(weights, a)

    gain = np.abs(beam_pattern) ** 2

    ax.plot(angles_rad, gain)
    ax.set_title(f"Realtime Beam Scan - Target: {theta_target}°")



animation = FuncAnimation(
    fig,
    update,
    frames=121,
    interval=50
)
animation.save(
    "assets/gifs/realtime_beam_scan.gif",
    writer="pillow"
)
plt.show()