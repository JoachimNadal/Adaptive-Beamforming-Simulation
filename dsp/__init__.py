"""Array-processing kernels.

Everything here works on plain NumPy arrays and is free of plotting, simulation and
I/O, because it is the reference for the embedded C core in ``embedded/core``.

Project-wide conventions (course chapter "Conventions and Notation"):

* ``X`` has shape ``(num_antennas, num_snapshots)``.
* Beamformer output is ``y = w^H x``.
* ULA steering vector is ``a_m = exp(-j m k d sin(theta))``, angles from broadside.
* Powers are ``E|x|^2``; complex noise of power ``s2`` has ``s2 / 2`` per quadrature.
"""
