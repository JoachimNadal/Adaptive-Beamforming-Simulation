"""ABF1 multichannel IQ frame: the contract between a receiver and the processing.

Little-endian, 64-byte header followed by the payload. Specification and rationale:
``docs/architecture/iq_frame_protocol.md``. The C parser is ``embedded/core/src/abf_frame.c``
and the two are tested against each other.
"""

import math
import struct
import zlib
from dataclasses import dataclass
from enum import IntEnum, IntFlag

import numpy as np

MAGIC = b"ABF1"
VERSION = 1
HEADER = struct.Struct("<4sBBHIIIIQddfIII")
HEADER_SIZE = HEADER.size  # 64
_CRC_OFFSET = HEADER_SIZE - 4
MAX_CHANNELS = 64
MAX_SAMPLES = 1 << 16


class FrameError(ValueError):
    """The bytes are not a valid ABF1 frame."""


class SampleFormat(IntEnum):
    CI16 = 0  # int16 I, int16 Q
    CF32 = 1  # float32 I, float32 Q


class FrameFlag(IntFlag):
    NONE = 0
    ADC_OVERFLOW = 1  # at least one sample clipped
    CLOCK_UNLOCKED = 2  # channel phases are not trustworthy
    CALIBRATION_ON = 4  # reference source active
    GAIN_CHANGED = 8  # front-end gain differs from the previous frame


_BYTES_PER_SAMPLE = {SampleFormat.CI16: 4, SampleFormat.CF32: 8}


@dataclass(frozen=True)
class IQFrame:
    samples: np.ndarray  # complex64, (channels, samples)
    sequence: int
    timestamp_ns: int
    sample_rate_hz: float
    center_frequency_hz: float
    flags: FrameFlag = FrameFlag.NONE


def pack_frame(frame, sample_format=SampleFormat.CF32, scale=1.0):
    """Serialise a frame. ``scale`` is the physical value of one raw unit."""
    x = np.asarray(frame.samples, dtype=np.complex64)
    if x.ndim != 2 or not 0 < x.shape[0] <= MAX_CHANNELS or not 0 < x.shape[1] <= MAX_SAMPLES:
        raise FrameError(f"unsupported sample array shape {x.shape}")
    if not (math.isfinite(scale) and scale > 0):
        raise FrameError("scale must be finite and positive")
    interleaved = x.T.copy().view(np.float32) / np.float32(scale)
    if sample_format == SampleFormat.CI16:
        rounded = np.rint(interleaved)
        if np.any(np.abs(rounded) > 32767):
            raise FrameError("samples exceed the int16 range for this scale")
        payload = rounded.astype("<i2").tobytes()
    else:
        payload = interleaved.astype("<f4").tobytes()
    fields = (
        MAGIC,
        VERSION,
        int(sample_format),
        x.shape[0],
        x.shape[1],
        frame.sequence & 0xFFFFFFFF,
        int(frame.flags),
        0,
        frame.timestamp_ns,
        frame.sample_rate_hz,
        frame.center_frequency_hz,
        scale,
        zlib.crc32(payload),
        0,
    )
    head = HEADER.pack(*fields, 0)[:_CRC_OFFSET]
    return head + struct.pack("<I", zlib.crc32(head)) + payload


def parse_header(buffer):
    """Validate the 64-byte header; returns its fields and the payload size."""
    if len(buffer) < HEADER_SIZE:
        raise FrameError(f"truncated header: {len(buffer)} bytes")
    head = bytes(buffer[:HEADER_SIZE])
    f = HEADER.unpack(head)
    if f[0] != MAGIC:
        raise FrameError("bad magic")
    if f[1] != VERSION:
        raise FrameError(f"unsupported version {f[1]}")
    if f[14] != zlib.crc32(head[:_CRC_OFFSET]):
        raise FrameError("header CRC mismatch")
    if f[2] not in _BYTES_PER_SAMPLE:
        raise FrameError(f"unknown sample format {f[2]}")
    channels, samples = f[3], f[4]
    if not 0 < channels <= MAX_CHANNELS or not 0 < samples <= MAX_SAMPLES:
        raise FrameError(f"unsupported size {channels} x {samples}")
    if not (math.isfinite(f[9]) and f[9] > 0 and math.isfinite(f[10])):
        raise FrameError("invalid sample rate or centre frequency")
    if not (math.isfinite(f[11]) and f[11] > 0):
        raise FrameError("invalid scale")
    return f, channels * samples * _BYTES_PER_SAMPLE[SampleFormat(f[2])]


def unpack_frame(buffer):
    """Parse and validate one frame; raises :class:`FrameError` on any inconsistency."""
    f, payload_size = parse_header(buffer)
    if len(buffer) != HEADER_SIZE + payload_size:
        raise FrameError(f"expected {HEADER_SIZE + payload_size} bytes, got {len(buffer)}")
    payload = bytes(buffer[HEADER_SIZE:])
    if zlib.crc32(payload) != f[12]:
        raise FrameError("payload CRC mismatch")
    dtype = "<i2" if f[2] == SampleFormat.CI16 else "<f4"
    raw = np.frombuffer(payload, dtype=dtype).astype(np.float32) * np.float32(f[11])
    samples = raw.view(np.complex64).reshape(f[4], f[3]).T
    return IQFrame(
        samples=np.ascontiguousarray(samples),
        sequence=f[5],
        timestamp_ns=f[8],
        sample_rate_hz=f[9],
        center_frequency_hz=f[10],
        flags=FrameFlag(f[6]),
    )
