import numpy as np
import matplotlib.pyplot as plt

from simulations.antenna_array.linear_array import LinearArray
from simulations.scenarios.multi_source import simulate_multi_source_snapshot

array = LinearArray(
    num_elements=4,
    spacing=6.25
)

x = simulate_multi_source_snapshot(
    antenna_array=array,
    wavelength=12.5,
    desired_angle=np.radians(20),
    interference_angle=np.radians(-40),
    desired_amplitude=1.0,
    interference_amplitude=0.8,
    noise_power=0.05
)


amplitudes = np.abs(x)
phases = np.angle(x)

x = np.arange(array.num_elements)
y = phases

plt.plot(x,y)
plt.show()

