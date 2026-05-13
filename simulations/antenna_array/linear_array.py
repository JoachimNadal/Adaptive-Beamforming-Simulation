import numpy as np
import matplotlib.pyplot as plt
import cmath
import math


class LinearArray:

    def __init__(self, num_elements, spacing):
        self.num_elements = num_elements
        self.spacing = spacing
        self.positions = np.arange(0, num_elements) * spacing

    def get_positions(self):
        return self.positions

    def plot_array(self):
        x = self.get_positions()
        y = np.zeros(self.num_elements)

        plt.scatter(x, y)
        plt.title("Linear Antenna Array")
        plt.xlabel("Position")
        plt.ylabel("Y")
        plt.grid(True)
        plt.show()

    def compute_steering_vector(self, theta, wavelength, unite="rad"):
        if unite == "deg":
            theta = math.radians(theta)

        k = 2 * math.pi / wavelength
        a = np.zeros(self.num_elements, dtype=complex)

        for i in range(self.num_elements):
            a[i] = cmath.exp(1j * i * k * self.spacing * math.sin(theta))

        return a

    def plot_steering_phases(self, theta, wavelength, unite="rad"):
        steering_vector = self.compute_steering_vector(theta, wavelength, unite)
        phases = np.angle(steering_vector)

        x = self.get_positions()
        y = phases

        plt.scatter(x, y)
        plt.title(f"Steering Vector Phase Progression - θ = {theta}°")
        plt.xlabel("Antenna Position")
        plt.ylabel("Phase (rad)")
        plt.grid(True)
        plt.show()
