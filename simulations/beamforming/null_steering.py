import numpy as np
import matplotlib.pyplot as plt


class NullSteeringBeamformer:

    def __init__(self, antenna_array):
        self.antenna_array = antenna_array


    def compute_weights(
        self,
        theta_target,
        theta_interference,
        wavelength,
        unite="deg"
    ):
        
        a_target = self.antenna_array.compute_steering_vector(
            theta_target,
            wavelength,
            unite)
        
        a_interference = self.antenna_array.compute_steering_vector(
            theta_interference,
            wavelength,
            unite)
        

        A = np.column_stack((a_target, a_interference))

        g = np.array([1,0])

        w = A @ np.linalg.inv(A.conj().T @ A) @ g

        return w
    
    def compute_beam_pattern(
        self,
        theta_target,
        theta_interference,
        wavelength,
        unite="deg"
    ):
        weights = self.compute_weights(
            theta_target,
            theta_interference,
            wavelength,
            unite
        )

        angles_deg = np.arange(-90,91,5)

        beam_pattern = np.zeros(len(angles_deg),dtype=complex)

        for i in range(len(angles_deg)):
            
            a = self.antenna_array.compute_steering_vector(
                angles_deg[i],
                wavelength,
                unite
            )

            beam_pattern[i] = np.vdot(weights,a)
        
        gain = abs(beam_pattern)**2

        x = angles_deg
        y = gain
        plt.plot(x,y)
        plt.title("Null Steering Beam Pattern")
        plt.xlabel("Angle (degrees)")
        plt.ylabel("Normalized Gain")
        plt.grid(True)
        plt.show()
        
        return angles_deg, gain
    
