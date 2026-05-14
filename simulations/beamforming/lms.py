import numpy as np
import matplotlib.pyplot as plt

from dsp.adaptive_weights import lms_update

class LMSBeamformer:

    def __init__(self, antenna_array, mu=0.01):
        self.antenna_array = antenna_array
        self.mu = mu

    def train(self, X, desired_signal):
        num_antennas, num_samples = X.shape

        w = np.zeros(num_antennas, dtype=complex)

        errors = []

        for i in range(num_samples):
            x_n = X[:, i]

            y_n = np.vdot(w, x_n)

            e_n = desired_signal[i] - y_n

            w = lms_update(w, x_n, e_n, self.mu)

            errors.append(abs(e_n) ** 2)

        self.weights = w

        return w, np.array(errors)
    
    def plot_learning_curve(self, errors):

        iterations = np.arange(len(errors))

        plt.plot(iterations, errors)
        plt.xlabel("Iteration")
        plt.ylabel("Errors")
        plt.title("Learning curve")
        plt.grid(True)
        plt.show()

    