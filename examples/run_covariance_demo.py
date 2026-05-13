import numpy as np
import matplotlib.pyplot as plt

from simulations.antenna_array.linear_array import LinearArray
from simulations.scenarios.snapshot_generator import generate_snapshot_matrix
from dsp.covariance_matrix import compute_covariance_matrix


array = LinearArray(
    num_elements=4,
    spacing=6.25
)

X = generate_snapshot_matrix(
    antenna_array=array,
    wavelength=12.5,
    desired_angle=np.radians(20),
    interference_angle=np.radians(-40),
    desired_amplitude=1.0,
    interference_amplitude=0.8,
    noise_power=0.05,
    num_snapshots=500
)

R = compute_covariance_matrix(X)

print(R)

plt.imshow(np.abs(R))
plt.title("Covariance Matrix Magnitude")
plt.colorbar()
plt.show()