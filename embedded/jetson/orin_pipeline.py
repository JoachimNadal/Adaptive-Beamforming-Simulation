"""Batched subband MVDR for GPU-class targets.

A GPU is not useful for one 4x4 solve; it is for many at once. Here the batch dimension is
the frequency subband: IQ is split with a filter bank, each subband gets its own covariance
and weights, and all solves run as a single batched call. The same code runs on NumPy and,
if installed, on CuPy. **It has not been run on a Jetson.**

    python -m embedded.jetson.orin_pipeline --backend numpy
"""

import argparse
import json
import sys
import time

import numpy as np

from dsp.fft import frame_signal, get_window


def get_backend(name="auto"):
    """Array module: ``numpy``, ``cupy`` or ``auto`` (CuPy when it can see a GPU)."""
    if name not in ("auto", "numpy", "cupy"):
        raise ValueError(f"unknown backend {name!r}")
    if name != "numpy":
        try:
            import cupy

            if cupy.cuda.runtime.getDeviceCount() > 0:
                return cupy
        except Exception:  # missing package, driver or library: all mean "no GPU"
            if name == "cupy":
                raise
        if name == "cupy":
            raise RuntimeError("CuPy is installed but no GPU is visible")
    return np


def channelize(X, num_subbands, hop=None):
    """Split ``(N, T)`` IQ into ``(num_subbands, N, frames)`` with a windowed FFT.

    Subband ``p`` is centred at ``p / num_subbands`` (FFT order, normalised frequency).
    """
    frames = frame_signal(X, num_subbands, hop or num_subbands // 2)
    spectra = np.fft.fft(frames * get_window("hann", num_subbands), axis=-1)
    return np.moveaxis(spectra, -1, 0)


def subband_steering(positions_m, theta_rad, center_hz, sample_rate_hz, num_subbands):
    """Steering vectors at the true RF frequency of each subband, ``(num_subbands, N)``.

    Using one vector for all subbands would make the beam squint over a wide band.
    """
    rf = center_hz + np.fft.fftfreq(num_subbands, 1 / sample_rate_hz)
    delays = np.asarray(positions_m) * np.sin(theta_rad) / 299_792_458.0
    return np.exp(-2j * np.pi * np.outer(rf, delays))


def batched_mvdr(X, a, relative_loading=1e-2, xp=np):
    """MVDR over a batch. ``X``: ``(P, N, K)``, ``a``: ``(P, N)``; returns ``(w, y)``."""
    if X.ndim != 3 or a.shape != X.shape[:2]:
        raise ValueError("X must be (P, N, K) and a must be (P, N)")
    _, n, k = X.shape
    R = X @ xp.conj(xp.swapaxes(X, 1, 2)) / k
    trace = xp.trace(R, axis1=1, axis2=2).real
    R = R + (relative_loading * trace / n)[:, None, None] * xp.eye(n)
    u = xp.linalg.solve(R, a[:, :, None])[:, :, 0]
    w = u / xp.sum(xp.conj(a) * u, axis=1, keepdims=True)
    y = xp.matmul(xp.conj(w)[:, None, :], X)[:, 0, :]
    return w, y


def benchmark(backend="auto", subbands=256, antennas=8, snapshots=128, repeats=20):
    """Wall-clock time of :func:`batched_mvdr`, transfers excluded."""
    xp = get_backend(backend)
    rng = np.random.default_rng(0)
    shape = (subbands, antennas, snapshots)
    X = xp.asarray((rng.standard_normal(shape) + 1j * rng.standard_normal(shape)).astype("c8"))
    a = xp.asarray(np.ones((subbands, antennas), dtype="c8"))

    def once():
        _, y = batched_mvdr(X, a, xp=xp)
        if xp is not np:
            xp.cuda.get_current_stream().synchronize()
        return y

    once()  # warm-up: compilation and allocation
    durations = []
    for _ in range(repeats):
        start = time.perf_counter()
        once()
        durations.append(time.perf_counter() - start)
    return {
        "backend": xp.__name__,
        "subbands": subbands,
        "antennas": antennas,
        "snapshots": snapshots,
        "median_ms": round(float(np.median(durations)) * 1e3, 3),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--backend", default="auto", choices=("auto", "numpy", "cupy"))
    parser.add_argument("--subbands", type=int, default=256)
    parser.add_argument("--antennas", type=int, default=8)
    parser.add_argument("--snapshots", type=int, default=128)
    args = parser.parse_args(argv)
    print(json.dumps(benchmark(args.backend, args.subbands, args.antennas, args.snapshots)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
