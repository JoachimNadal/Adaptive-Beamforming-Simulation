"""Steering vectors: the single place where the phase convention is defined."""

import numpy as np

_UNITS = ("rad", "deg")


def to_radians(theta, unite="rad"):
    """Convert an angle to radians, rejecting unknown unit names."""
    if unite not in _UNITS:
        raise ValueError(f"unite must be one of {_UNITS}, got {unite!r}")
    theta = np.asarray(theta, dtype=float)
    return np.radians(theta) if unite == "deg" else theta


def _path_and_derivative(positions, thetas):
    """Extra path length of each element and its derivative with respect to theta."""
    p = np.asarray(positions, dtype=float)
    s, c = np.sin(thetas), np.cos(thetas)
    if p.ndim == 1:
        return np.outer(p, s), np.outer(p, c)
    if p.ndim == 2 and p.shape[1] == 2:
        return p @ np.vstack((s, -c)), p @ np.vstack((c, s))
    raise ValueError("positions must have shape (N,) or (N, 2)")


def steering_matrix(positions, thetas, wavelength):
    """Far-field narrowband steering matrix for elements in the (x, y) plane.

    A source at angle ``theta`` is seen in direction ``(-sin(theta), cos(theta))``: 0 is
    broadside (+y) and positive angles turn toward -x, so its wavefront travels along
    ``kappa = (sin(theta), -cos(theta))`` and element ``m`` lags by ``kappa . p_m / c``.
    For elements on the x axis this reduces to ``exp(-j k x_m sin(theta))``.

    Parameters
    ----------
    positions : array_like, shape (N,) or (N, 2)
        Element coordinates, in the unit of ``wavelength``. 1-D means the x axis.
    thetas : array_like
        Angles in radians.

    Returns
    -------
    np.ndarray, shape (N, number of angles)
    """
    if wavelength <= 0:
        raise ValueError("wavelength must be positive")
    path, _ = _path_and_derivative(positions, np.atleast_1d(np.asarray(thetas, dtype=float)))
    return np.exp(-2j * np.pi / wavelength * path)


def steering_derivative(positions, thetas, wavelength):
    """Derivative of :func:`steering_matrix` with respect to theta (per radian)."""
    if wavelength <= 0:
        raise ValueError("wavelength must be positive")
    path, dpath = _path_and_derivative(positions, np.atleast_1d(np.asarray(thetas, dtype=float)))
    k = 2 * np.pi / wavelength
    return -1j * k * dpath * np.exp(-1j * k * path)


def ula_steering_vector(theta, num_elements, d_over_lambda=0.5):
    """ULA steering vector ``exp(-j 2 pi m (d / lambda) sin(theta))``, theta in radians."""
    return steering_matrix(np.arange(num_elements) * d_over_lambda, theta, 1.0)[:, 0]
