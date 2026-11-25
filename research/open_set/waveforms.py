"""Synthetic signals outside the training classes, and receiver impairments.

Written independently of ``simulations.channels.interference_models`` so that the unseen
families do not share code with the training classes. Everything has unit mean power before
noise is added.
"""

import numpy as np

from dsp.signal_metrics import from_db
from simulations.channels.awgn import complex_noise, make_rng


def _unit(x):
    return x / np.sqrt(np.mean(np.abs(x) ** 2))


def _carrier(n, f):
    return np.exp(2j * np.pi * f * np.arange(n))


# -------------------------------------------------------------------- unseen families


def ofdm(n, rng):
    """64-point OFDM, QPSK subcarriers, cyclic prefix of 16."""
    used = int(rng.integers(20, 52))
    blocks = []
    for _ in range(n // 80 + 2):
        spectrum = np.zeros(64, complex)
        bins = np.arange(-(used // 2), used - used // 2)
        spectrum[bins] = np.exp(0.5j * np.pi * rng.integers(0, 4, used))
        symbol = np.fft.ifft(spectrum)
        blocks.append(np.concatenate((symbol[-16:], symbol)))
    start = rng.integers(0, 80)
    return _unit(np.concatenate(blocks)[start : start + n] * _carrier(n, rng.uniform(-0.1, 0.1)))


def gfsk(n, rng):
    """Gaussian-filtered FSK, modulation index 0.3 to 1."""
    sps = int(rng.integers(8, 25))
    bits = np.repeat(rng.choice([-1.0, 1.0], n // sps + 3), sps)
    t = np.arange(-sps, sps + 1) / sps
    pulse = np.exp(-((t * 2.0) ** 2))
    smooth = np.convolve(bits, pulse / pulse.sum(), "same")[sps : sps + n]
    h = rng.uniform(0.3, 1.0)
    phase = np.pi * h / sps * np.cumsum(smooth)
    return np.exp(1j * phase) * _carrier(n, rng.uniform(-0.2, 0.2))


def dsss(n, rng):
    """Direct-sequence spread spectrum: 11-chip Barker code, BPSK data."""
    barker = np.array([1, -1, 1, 1, -1, 1, 1, 1, -1, -1, -1.0])
    spc = int(rng.integers(2, 5))
    data = rng.choice([-1.0, 1.0], n // (11 * spc) + 2)
    chips = np.repeat(np.outer(data, barker).ravel(), spc)
    return _unit(chips[:n] * _carrier(n, rng.uniform(-0.1, 0.1)))


def multitone(n, rng):
    """Two to five unrelated tones."""
    x = sum(
        rng.uniform(0.5, 1)
        * _carrier(n, rng.uniform(-0.4, 0.4))
        * np.exp(2j * np.pi * rng.random())
        for _ in range(rng.integers(2, 6))
    )
    return _unit(x)


def triangular_fm(n, rng):
    """Frequency swept up and down."""
    period = int(rng.integers(n // 6, n))
    span = rng.uniform(0.2, 0.5)
    u = (np.arange(n) + rng.integers(0, period)) % period / period
    f = span * (2 * np.abs(2 * u - 1) - 1) / 1.0
    return np.exp(2j * np.pi * (np.cumsum(f / 2) + rng.random()))


def pulsed_chirp(n, rng):
    """Radar-like: chirps separated by silence."""
    period = int(rng.integers(128, 400))
    length = int(period * rng.uniform(0.15, 0.4))
    span = rng.uniform(0.2, 0.6) * rng.choice([-1, 1])
    k = (np.arange(n) + rng.integers(0, period)) % period
    phase = np.pi * span / length * (k - length / 2) ** 2
    return _unit((k < length) * np.exp(1j * phase) + 0j)


def chirp_spread(n, rng):
    """LoRa-like: cyclically shifted up-chirps, random symbols."""
    size = int(rng.choice([64, 128, 256]))
    bandwidth = rng.uniform(0.25, 0.6)
    t = np.arange(size) / size
    out = []
    for _ in range(n // size + 2):
        f = (t + rng.random()) % 1 - 0.5
        out.append(bandwidth * f)
    return np.exp(2j * np.pi * np.cumsum(np.concatenate(out)[:n]))


def frequency_hopping(n, rng):
    dwell = int(rng.integers(48, 160))
    f = np.repeat(rng.uniform(-0.4, 0.4, n // dwell + 2), dwell)
    start = rng.integers(0, dwell)
    return np.exp(2j * np.pi * np.cumsum(f[start : start + n]))


def am_voice(n, rng):
    """Amplitude modulation by low-pass noise, with carrier."""
    m = np.convolve(rng.standard_normal(n + 64), np.hanning(64), "same")[32 : 32 + n]
    m = m / np.max(np.abs(m))
    return _unit((1 + rng.uniform(0.5, 0.95) * m) * _carrier(n, rng.uniform(-0.3, 0.3)))


def impulsive(n, rng):
    """Sparse strong impulses, as from switching equipment."""
    x = np.zeros(n, complex)
    count = int(rng.integers(5, 40))
    index = rng.integers(0, n, count)
    x[index] = complex_noise(count, 1.0, rng) + 0.5
    return _unit(np.convolve(x, np.hanning(5), "same"))


def mixture(n, rng):
    """Two overlapping known-class-like signals: a tone and a random QPSK stream."""
    sps = int(rng.integers(4, 12))
    symbols = np.exp(0.5j * np.pi * rng.integers(0, 4, n // sps + 1) + 0.25j * np.pi)
    q = np.repeat(symbols, sps)[:n] * _carrier(n, rng.uniform(-0.3, 0.3))
    return _unit(q + rng.uniform(0.5, 1.5) * _carrier(n, rng.uniform(-0.4, 0.4)))


FAMILIES = {
    "ofdm": ofdm,
    "gfsk": gfsk,
    "dsss": dsss,
    "multitone": multitone,
    "triangular FM": triangular_fm,
    "pulsed chirp": pulsed_chirp,
    "chirp spread": chirp_spread,
    "hopping": frequency_hopping,
    "AM": am_voice,
    "impulsive": impulsive,
    "mixture": mixture,
}


def generate(family, count, snr_range_db=(0.0, 20.0), num_samples=1024, rng=None):
    rng = make_rng(rng)
    out = np.empty((count, num_samples), np.complex64)
    snr = rng.uniform(*snr_range_db, count)
    for i in range(count):
        x = FAMILIES[family](num_samples, rng)
        out[i] = np.sqrt(from_db(snr[i])) * x + complex_noise(num_samples, 1.0, rng)
    return out, snr


# ------------------------------------------------------------------------ impairments


def iq_imbalance(x, rng):
    """1 dB of gain and 5 degrees of phase imbalance."""
    g, p = 10 ** (1 / 20), np.radians(5)
    return x.real + 1j * g * (x.imag * np.cos(p) + x.real * np.sin(p))


def dc_offset(x, rng):
    """Constant 6 dB below the total power."""
    power = np.mean(np.abs(x) ** 2, axis=-1, keepdims=True)
    return x + np.sqrt(power / 4) * np.exp(2j * np.pi * rng.random((len(x), 1)))


def phase_noise(x, rng):
    """Random-walk phase, about 10 degrees RMS over 100 samples."""
    steps = rng.standard_normal(x.shape) * np.radians(1.0)
    return x * np.exp(1j * np.cumsum(steps, axis=-1))


def quantisation(x, rng):
    """4-bit converter at 12 dB of headroom."""
    full_scale = 4 * np.sqrt(np.mean(np.abs(x) ** 2, axis=-1, keepdims=True) / 2)
    step = full_scale / 8

    def rail(v):
        return np.clip(np.round(v / step) * step, -full_scale, full_scale - step)

    return rail(x.real) + 1j * rail(x.imag)


def multipath(x, rng):
    """One echo of random phase, -6 dB, 3 to 20 samples late."""
    y = x.copy()
    for row, delay in enumerate(rng.integers(3, 21, len(x))):
        echo = 0.5 * np.exp(2j * np.pi * rng.random())
        y[row, delay:] += echo * x[row, :-delay]
    return y


def band_edge(x, rng):
    """Receiver filter roll-off: 3 dB down at 0.4 of the sample rate."""
    f = np.abs(np.fft.fftfreq(x.shape[-1]))
    return np.fft.ifft(np.fft.fft(x, axis=-1) / np.sqrt(1 + (f / 0.4) ** 6), axis=-1)


def frequency_offset(x, rng):
    """Whole band shifted by up to 0.15 of the sample rate."""
    n = np.arange(x.shape[-1])
    return x * np.exp(2j * np.pi * rng.uniform(-0.15, 0.15, (len(x), 1)) * n)


def clipping(x, rng):
    """Saturation at the RMS level of each rail times 1.5."""
    level = 1.5 * np.sqrt(np.mean(np.abs(x) ** 2, axis=-1, keepdims=True) / 2)
    return np.clip(x.real, -level, level) + 1j * np.clip(x.imag, -level, level)


IMPAIRMENTS = {
    "IQ imbalance": iq_imbalance,
    "DC offset": dc_offset,
    "phase noise": phase_noise,
    "4-bit ADC": quantisation,
    "multipath": multipath,
    "band edge": band_edge,
    "frequency offset": frequency_offset,
    "clipping": clipping,
}


def impair(name, iq, rng=None):
    rng = make_rng(rng)
    return IMPAIRMENTS[name](np.asarray(iq), rng).astype(np.complex64)


def random_impairments(iq, rng=None, probability=0.5):
    """Each example gets each impairment with the given probability (training augmentation)."""
    rng = make_rng(rng)
    out = np.array(iq)
    for name in IMPAIRMENTS:
        chosen = rng.random(len(out)) < probability / 2
        if chosen.any():
            out[chosen] = impair(name, out[chosen], rng)
    return out
