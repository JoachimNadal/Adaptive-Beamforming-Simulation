import numpy as np
import matplotlib.pyplot as plt
import cmath,math

class LinearArray:

    def __init__(self, num_elements, spacing):
        self.num_elements = num_elements
        self.spacing = spacing
        self.positions = np.arange(0,num_elements) * spacing


    def get_positions(self):
        return(self.positions)


    def plot_array(self):
        x = self.get_positions()
        y = np.zeros(self.num_elements)
        plt.scatter(x,y)
        plt.show()


    def compute_steering_vector(self,theta,wavelength,unite="rad"):
        if unite == "deg":
            theta = math.radians(theta)
        k = 2*math.pi / wavelength
        self.a = np.zeros(self.num_elements,dtype=complex)
        for i in range(self.num_elements):
            self.a[i] = cmath.exp(-1j*i*k*self.spacing*cmath.sin(theta))
        return self.a


    def plot_steering_phases(self,theta,wavelength,unite="rad"):
        self.phases = np.angle(self.compute_steering_vector(theta,wavelength,unite))
        x = self.get_positions()
        y = self.phases
        print(self.phases)
        plt.scatter(x,y)
        plt.show()


    def compute_delay_and_sum_weights(self, theta_target, wavelength, unite="rad"):
        a = self.compute_steering_vector(theta_target,wavelength,unite)
        w = a/ self.num_elements
        return w

    def compute_beam_pattern(self, theta_target, wavelength, unite="deg"):
        
        w = self.compute_delay_and_sum_weights(theta_target, wavelength, unite)
        angles_deg = np.arange(-90, 91, 5)           
        
        self.B = np.zeros(len(angles_deg), dtype=complex)
        
        for idx, angle in enumerate(angles_deg):
            a = self.compute_steering_vector(angle, wavelength, unite)
            self.B[idx] = np.vdot(w, a)
        
        plt.plot(angles_deg, np.abs(self.B)**2)
        plt.xlabel("Angle (°)")
        plt.ylabel("|B(θ)|²")
        plt.title("Delay-and-Sum Beam Pattern")
        plt.grid(True)
        plt.show()
