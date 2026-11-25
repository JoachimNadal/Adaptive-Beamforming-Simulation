"""Where frames come from: simulation, recording or network.

Every source is an iterator of :class:`IQFrame`. A driver for a real coherent receiver only
has to implement the same iterator; none is included because none could be tested.
"""

import socket
import time

import numpy as np

from embedded.common.iq_frame import (
    HEADER_SIZE,
    FrameError,
    FrameFlag,
    IQFrame,
    pack_frame,
    parse_header,
    unpack_frame,
)
from simulations.antenna_array.linear_array import LinearArray
from simulations.channels.awgn import make_rng
from simulations.scenarios.array_snapshots import simulate_array_snapshots


class SimulatedSource:
    """Synthetic frames with known ground truth.

    Source 0 is the wanted signal. ``angles_deg`` may be a function of the frame index, to
    simulate motion.
    """

    def __init__(
        self,
        config,
        angles_deg,
        powers,
        num_frames=None,
        sample_rate_hz=1e6,
        noise_power=1.0,
        channel_gains=None,
        rng=None,
    ):
        self.config = config
        self.angles_deg = angles_deg
        self.powers = powers
        self.num_frames = num_frames
        self.sample_rate_hz = sample_rate_hz
        self.noise_power = noise_power
        self.channel_gains = channel_gains
        self.rng = make_rng(rng)
        self.array = LinearArray(config.num_elements, config.spacing_m)

    def scene(self, index=0):
        angles = self.angles_deg(index) if callable(self.angles_deg) else self.angles_deg
        return simulate_array_snapshots(
            self.array,
            self.config.wavelength_m,
            angles,
            self.powers,
            self.config.block_size,
            self.noise_power,
            self.rng,
            channel_gains=self.channel_gains,
        )

    def __iter__(self):
        index = 0
        while self.num_frames is None or index < self.num_frames:
            duration = self.config.block_size / self.sample_rate_hz
            yield IQFrame(
                samples=self.scene(index).X.astype(np.complex64),
                sequence=index,
                timestamp_ns=round(index * duration * 1e9),
                sample_rate_hz=self.sample_rate_hz,
                center_frequency_hz=self.config.carrier_hz,
                flags=FrameFlag.NONE,
            )
            index += 1


class FileSource:
    """Frames concatenated in a file, as written by :func:`record`."""

    def __init__(self, path):
        self.path = path

    def __iter__(self):
        with open(self.path, "rb") as stream:
            while head := stream.read(HEADER_SIZE):
                _, size = parse_header(head)
                yield unpack_frame(head + stream.read(size))


def record(frames, path, **pack_options):
    """Write frames to a file; returns how many."""
    count = 0
    with open(path, "wb") as stream:
        for frame in frames:
            stream.write(pack_frame(frame, **pack_options))
            count += 1
    return count


class UdpSource:
    """One frame per datagram. Corrupt datagrams are counted and skipped.

    The iterator ends after ``timeout_s`` without any datagram, or after ``max_frames``.
    """

    def __init__(self, host="127.0.0.1", port=0, timeout_s=1.0, max_frames=None):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1 << 22)
        self._socket.bind((host, port))
        self.address = self._socket.getsockname()
        self.timeout_s = timeout_s
        self.max_frames = max_frames
        self.rejected = 0

    def __iter__(self):
        received = 0
        deadline = time.monotonic() + self.timeout_s
        while self.max_frames is None or received < self.max_frames:
            # the deadline is only extended by valid frames: garbage cannot keep us alive
            self._socket.settimeout(max(1e-3, deadline - time.monotonic()))
            try:
                datagram, _ = self._socket.recvfrom(65535)
            except TimeoutError:
                return
            try:
                frame = unpack_frame(datagram)
            except FrameError:
                self.rejected += 1
                if time.monotonic() >= deadline:
                    return
                continue
            received += 1
            deadline = time.monotonic() + self.timeout_s
            yield frame

    def close(self):
        self._socket.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def send_udp(frames, address, **pack_options):
    """Send frames as datagrams; returns how many (used by tests and benchmarks)."""
    count = 0
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
        for frame in frames:
            sender.sendto(pack_frame(frame, **pack_options), address)
            count += 1
    return count
