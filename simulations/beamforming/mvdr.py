import numpy as np
import matplotlib.pyplot as plt



class MVDRBeamformer:
    def __init__(self,antenna_array):
        self.antenna_array = antenna_array


    def compute_weights(self, covariance_matrix, theta_target, wavelength, unite="deg"):
        R_inv = np.linalg.inv(covariance_matrix)
        a = self.antenna_array.compute_steering_vector(theta_target,wavelength,unite=unite)
        num = R_inv@a
        denum = np.vdot(a,num)
        w = num/denum
        return w
    

    def compute_beam_pattern(self, covariance_matrix, theta_target, wavelength, unite="deg"):
        weights = self.compute_weights(
            covariance_matrix,
            theta_target,
            wavelength,
            unite=unite)
        
        angles_deg = np.arange(-90,91,5)

        beam_pattern = np.zeros(len(angles_deg),dtype = complex)

        for i in range(len(angles_deg)):
            a = self.antenna_array.compute_steering_vector(
                angles_deg[i],
                wavelength,
                unite=unite)
            beam_pattern[i] = np.vdot(weights,a)


        gain = abs(beam_pattern)**2

        x = angles_deg
        y = gain
        plt.plot(x,y)
        plt.title("MVDR Beam Pattern")
        plt.xlabel("Angle (degrees)")
        plt.ylabel("Normalized Gain")
        plt.grid(True)
        plt.show()
        
        return angles_deg, gain