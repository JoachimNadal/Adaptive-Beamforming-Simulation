"""General-purpose snapshot generator with known ground truth."""

from dataclasses import dataclass

import numpy as np

from dsp.signal_metrics import scene_covariance
from simulations.channels.awgn import complex_noise, make_rng


@dataclass(frozen=True)
class Scene:
    """Snapshots plus the ground truth needed to score an algorithm.

    Source 0 is the wanted one; the others are interferers.
    """

    X: np.ndarray  # (N, K) received snapshots
    A: np.ndarray  # (N, L) ideal steering vectors
    S: np.ndarray  # (L, K) source waveforms, power included
    powers: np.ndarray  # (L,)
    noise_power: float
    channel_gains: np.ndarray  # (N,) true gain/phase errors (ones if ideal)

    @property
    def A_effective(self):
        """Steering vectors as actually received, i.e. including channel errors."""
        return self.channel_gains[:, None] * self.A

    @property
    def R_interference_noise(self):
        """Theoretical covariance of everything except source 0."""
        return scene_covariance(self.A_effective[:, 1:], self.powers[1:], self.noise_power)

    @property
    def R(self):
        """Theoretical total covariance for uncorrelated sources."""
        return scene_covariance(self.A_effective, self.powers, self.noise_power)


def simulate_array_snapshots(
    antenna_array,
    wavelength,
    angles_deg,
    powers,
    num_snapshots,
    noise_power=1.0,
    rng=None,
    waveforms=None,
    channel_gains=None,
):
    """Simulate ``x = diag(g) A s + n``.

    ``waveforms`` (``(L, K)``, unit power) defaults to independent circular Gaussian
    sources. ``channel_gains`` models uncalibrated receiver channels.
    """
    rng = make_rng(rng)
    powers = np.atleast_1d(np.asarray(powers, dtype=float))
    angles_deg = np.atleast_1d(np.asarray(angles_deg, dtype=float))
    if powers.shape != angles_deg.shape:
        raise ValueError("angles_deg and powers must have the same length")
    n, num_sources = antenna_array.num_elements, len(powers)
    A = antenna_array.compute_steering_matrix(angles_deg, wavelength, "deg")
    if waveforms is None:
        waveforms = complex_noise((num_sources, num_snapshots), 1.0, rng)
    S = np.sqrt(powers)[:, None] * np.asarray(waveforms)
    g = np.ones(n, dtype=complex) if channel_gains is None else np.asarray(channel_gains)
    X = g[:, None] * (A @ S) + complex_noise((n, num_snapshots), noise_power, rng)
    return Scene(X, A, S, powers, noise_power, g)


def random_channel_gains(num_channels, gain_std_db=1.0, phase_std_deg=20.0, rng=None):
    """Random channel errors, channel 0 being the reference."""
    rng = make_rng(rng)
    g = 10 ** (gain_std_db * rng.standard_normal(num_channels) / 20) * np.exp(
        1j * np.radians(phase_std_deg) * rng.standard_normal(num_channels)
    )
    return g / g[0]
