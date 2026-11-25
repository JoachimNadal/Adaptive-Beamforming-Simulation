# ABF1 IQ Frame Protocol

The contract between a multichannel receiver and the processing. Implemented twice and tested
for interoperability: `embedded/common/iq_frame.py` and `embedded/core/src/abf_frame.c`.

One frame = 64-byte header + payload. Little-endian. One frame per UDP datagram, or frames
concatenated in a file.

| Offset | Type | Field | Meaning |
|---:|---|---|---|
| 0 | char[4] | magic | `ABF1` |
| 4 | u8 | version | 1 |
| 5 | u8 | sample format | 0 = int16 I,Q; 1 = float32 I,Q |
| 6 | u16 | channels | 1 to 64 |
| 8 | u32 | samples | per channel, 1 to 65536 |
| 12 | u32 | sequence | increments by 1, wraps |
| 16 | u32 | flags | bit 0 ADC overflow, 1 clock unlocked, 2 calibration source on, 3 gain changed |
| 20 | u32 | reserved | 0 |
| 24 | u64 | timestamp | ns, first sample |
| 32 | f64 | sample rate | Hz |
| 40 | f64 | centre frequency | Hz |
| 48 | f32 | scale | value of one raw unit |
| 52 | u32 | payload CRC-32 | IEEE 802.3 |
| 56 | u32 | reserved | 0 |
| 60 | u32 | header CRC-32 | bytes 0 to 59 |

Payload: sample-interleaved, `I0 Q0 I1 Q1 … I(N-1) Q(N-1)` then the next sample. This is the
order a multichannel ADC produces and the order the C core consumes, so no transposition is
needed on the target.

## Rationale

| Choice | Reason |
|---|---|
| 64-byte header | cache line and DMA friendly; all fields naturally aligned |
| Two CRCs | the header must be trusted before its sizes are used; CRC-32 matches zlib and common DMA peripherals |
| Flags in band | clock loss and clipping must reach the adaptation with the samples they affect |
| Explicit scale | int16 payloads keep physical units without a side channel |
| Sequence number | loss detection; UDP gives none |

## Receiver obligations

- Reject on any CRC, size, version or range error. Never use a field of a rejected header.
- Report sequence gaps; do not interpolate.
- On `clock unlocked`, discard the calibration.

Tests flip every single byte of a frame and check that both parsers reject it, feed random
bytes, and cut frames at several lengths.

## Data rates

$4N f_s$ bytes/s for int16, plus 64 bytes per frame.

| Channels | Rate (MS/s) | int16 payload | Gigabit Ethernet (125 MB/s) |
|---:|---:|---:|---|
| 4 | 1 | 16 MB/s | fits |
| 4 | 5 | 80 MB/s | fits, little margin |
| 4 | 10 | 160 MB/s | does not fit |
| 8 | 1 | 32 MB/s | fits |
| 8 | 5 | 160 MB/s | does not fit |

A UDP datagram holds at most 65 507 bytes: 4 × 1024 int16 samples (16 448 bytes) is a safe
choice, at the cost of IP fragmentation with standard 1500-byte frames. Enable jumbo frames or
use at most 89 samples per frame (1488 bytes) to avoid it.

## Limits

No authentication or encryption: use it on a trusted link. No retransmission. Version 1 has no
extension mechanism; an incompatible change must increment the version.
