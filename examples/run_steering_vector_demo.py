from simulations.antenna_array.linear_array import LinearArray


array = LinearArray(
    num_elements=4,
    spacing=6.25
)

print(array.compute_steering_vector(
    theta=30,
    wavelength=12.5,
    unite="deg"
))

array.plot_steering_phases(
    theta=30,
    wavelength=12.5,
    unite="deg"
)
