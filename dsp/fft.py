"""Spectral analysis of complex IQ. Every function works along the last axis."""

import numpy as np

_WINDOWS = {"hann": np.hanning, "hamming": np.hamming, "blackman": np.blackman}


def get_window(name, length, periodic=True):
    """``rect``, ``hann``, ``hamming`` or ``blackman``.

    Use ``periodic=True`` for spectral analysis and ``False`` (symmetric) for FIR design,
    where symmetry is what makes the phase exactly linear.
    """
    if name == "rect":
        return np.ones(length)
    if name not in _WINDOWS:
        raise ValueError(f"unknown window {name!r}, choose from rect, {', '.join(_WINDOWS)}")
    return _WINDOWS[name](length + 1)[:-1] if periodic else _WINDOWS[name](length)


def frequency_axis(nfft, sample_rate=1.0):
    """Centred frequency axis matching the other functions, in the unit of sample_rate."""
    return np.fft.fftshift(np.fft.fftfreq(nfft, 1 / sample_rate))


def frame_signal(x, frame_length, hop):
    """Overlapping frames of the last axis: ``(..., num_frames, frame_length)``."""
    x = np.asarray(x)
    if hop <= 0 or frame_length <= 0:
        raise ValueError("frame_length and hop must be positive")
    if x.shape[-1] < frame_length:
        raise ValueError(f"need at least {frame_length} samples, got {x.shape[-1]}")
    view = np.lib.stride_tricks.sliding_window_view(x, frame_length, axis=-1)
    return view[..., ::hop, :]


def stft(x, nfft=256, hop=None, window="hann"):
    """Short-time FFT, centred in frequency: ``(..., num_frames, nfft)``."""
    frames = frame_signal(x, nfft, hop or nfft // 2)
    return np.fft.fftshift(np.fft.fft(frames * get_window(window, nfft), axis=-1), axes=-1)


def power_spectral_density(x, sample_rate=1.0, nfft=256, hop=None, window="hann"):
    """Welch PSD, normalised so that ``sum(psd) * sample_rate / nfft`` is the mean power."""
    w = get_window(window, nfft)
    spec = np.mean(np.abs(stft(x, nfft, hop, window)) ** 2, axis=-2)
    return frequency_axis(nfft, sample_rate), spec / (sample_rate * np.sum(w**2))
