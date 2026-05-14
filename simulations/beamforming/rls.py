import numpy as np
import matplotlib.pyplot as plt


class RLSBeamformer:

    def __init__(self, antenna_array, lambda_factor=0.99, delta=1.0):
        self.antenna_array = antenna_array
        self.lambda_factor = lambda_factor
        self.delta = delta

    def train(self, X, desired_signal):
        
        num_antennas, num_samples = X.shape

        w = np.zeros(num_antennas,dtype=complex)

        P = (1/self.delta)*np.eye(num_antennas,dtype=complex)

        errors = []

        for n in range(num_samples):
            x_n = X[:, n]

            y_n = np.vdot(w, x_n)

            e_n = desired_signal[n] - y_n

            Px = P @ x_n

            denominator = self.lambda_factor + np.vdot(x_n, Px)

            k_n = Px / denominator

            w = w + k_n * np.conjugate(e_n)

            P = (P - np.outer(k_n, np.conjugate(x_n)) @ P) / self.lambda_factor

            errors.append(abs(e_n) ** 2)

        self.weights = w

        return w, np.array(errors)
    
    def plot_learning_curve(self, errors):
        iterations = np.arange(len(errors))

        plt.plot(iterations, errors)
        plt.xlabel("Iteration")
        plt.ylabel("Squared Error")
        plt.title("RLS Learning Curve")
        plt.grid(True)
        plt.show()