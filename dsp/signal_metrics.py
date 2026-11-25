"""Quantitative figures of merit. All powers linear unless the name ends in ``_db``."""

import numpy as np

_TINY = np.finfo(float).tiny


def to_db(power):
    """10 log10 of a power, floored to avoid -inf."""
    return 10 * np.log10(np.maximum(power, _TINY))


def from_db(level_db):
    return 10.0 ** (np.asarray(level_db) / 10)


def signal_power(x):
    """Mean power ``E|x|^2``."""
    return float(np.mean(np.abs(x) ** 2))


def beam_response(weights, steering):
    """Complex response ``w^H a`` for a steering vector or a matrix of them."""
    return weights.conj() @ steering


def scene_covariance(A, powers, noise_power):
    """Theoretical covariance ``A diag(powers) A^H + noise_power I``."""
    return (A * np.asarray(powers)) @ A.conj().T + noise_power * np.eye(A.shape[0])


def output_sinr(weights, a_signal, signal_power_in, R_interference_noise):
    """Output SINR for a known scene, which is what adaptive algorithms are judged on."""
    num = signal_power_in * abs(np.vdot(weights, a_signal)) ** 2
    return float(num / np.vdot(weights, R_interference_noise @ weights).real)


def optimal_sinr(a_signal, signal_power_in, R_interference_noise):
    """Upper bound of :func:`output_sinr` over all weights."""
    x = np.linalg.solve(R_interference_noise, a_signal)
    return float(signal_power_in * np.vdot(a_signal, x).real)


def white_noise_gain(weights, a_signal):
    """Array gain against white noise; at most N, reached by delay-and-sum."""
    return float(abs(np.vdot(weights, a_signal)) ** 2 / np.vdot(weights, weights).real)


def null_depth_db(weights, a_target, a_null):
    """Response toward ``a_null`` relative to ``a_target`` (negative means rejection)."""
    return float(
        to_db(abs(np.vdot(weights, a_null)) ** 2) - to_db(abs(np.vdot(weights, a_target)) ** 2)
    )


def half_power_beamwidth(angles_deg, gain):
    """-3 dB width around the maximum, interpolated; NaN if it leaves the grid."""
    gain = np.asarray(gain) / np.max(gain)
    peak = int(np.argmax(gain))
    edges = []
    for step in (-1, 1):
        i = peak
        while 0 <= i + step < len(gain) and gain[i + step] >= 0.5:
            i += step
        if not 0 <= i + step < len(gain):
            return float("nan")
        g0, g1 = gain[i], gain[i + step]
        frac = (g0 - 0.5) / (g0 - g1)
        edges.append(angles_deg[i] + frac * (angles_deg[i + step] - angles_deg[i]))
    return float(edges[1] - edges[0])


def peak_sidelobe_db(gain):
    """Highest sidelobe relative to the main lobe; NaN if there is none."""
    gain = np.asarray(gain) / np.max(gain)
    left = right = int(np.argmax(gain))
    while left > 0 and gain[left - 1] < gain[left]:
        left -= 1
    while right < len(gain) - 1 and gain[right + 1] < gain[right]:
        right += 1
    outside = np.concatenate((gain[:left], gain[right + 1 :]))
    return float(to_db(outside.max())) if outside.size else float("nan")


def error_vector_magnitude(received, reference):
    """RMS EVM after removing the best complex gain (so a constant phase is free)."""
    received, reference = np.asarray(received), np.asarray(reference)
    gain = np.vdot(reference, received) / np.vdot(reference, reference)
    err = received / gain - reference
    return float(np.sqrt(np.mean(np.abs(err) ** 2) / np.mean(np.abs(reference) ** 2)))


def angle_rmse(estimates, truth):
    """RMSE between two equally long angle sets, matched in sorted order."""
    e, t = np.sort(np.ravel(estimates)), np.sort(np.ravel(truth))
    if e.shape != t.shape:
        raise ValueError(f"got {e.size} estimates for {t.size} true angles")
    return float(np.sqrt(np.mean((e - t) ** 2)))
