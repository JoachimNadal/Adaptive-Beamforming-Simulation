# Raspberry Pi: Optimization Notes

Not measured on a Raspberry Pi. Numbers are from the development PC; the method is what carries
over. Run these first on the board:

```bash
python -m embedded.raspberry_pi.pi_receiver --benchmark
cmake -S embedded/core -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build && ./build/bench_abf
```

## Where the time goes

Python pipeline, N=4, K=256, i7-9700K: 1.2 ms per block, nearly independent of K (1.4 ms at
K=64 and at K=1024). The cost is many small NumPy calls, not arithmetic. Hence:

1. Use larger blocks before anything else: 1024 samples give 3.5 times the throughput of 256.
2. Move covariance, MVDR and weight application to `embedded/core` (8.8 µs per block in total).
3. Keep order estimation and root-MUSIC in Python at the weight rate, or drop them by using
   MVDR with loading.

## Checklist

| Item | Why |
|---|---|
| `OPENBLAS_NUM_THREADS=1` | threads cost more than they save on 4×4 to 16×16 matrices |
| Performance CPU governor, adequate cooling | frequency scaling shows up as latency jitter |
| Pin the receiver thread to one core (`taskset`) | avoids migration |
| `SCHED_FIFO` for the acquisition thread only | never for Python: a busy loop would starve the system |
| Larger socket buffers (`net.core.rmem_max`) | `UdpSource` asks for 4 MiB, the kernel may cap it |
| Jumbo frames, or at most 89 samples per frame (4 channels, int16) | avoids IP fragmentation |
| int16 payloads | half the traffic of float32 |

## Compiling the core

Start with `-O3 -mcpu=native`. Do **not** use `-ffast-math`: the code relies on NaN and infinity
checks to reject bad input.

Vectorisation candidates, in order: `abf_covariance_update` (dominant), `abf_apply_weights`.
Storing I and Q in separate arrays would help NEON, at the cost of a de-interleave; measure
before changing the data layout. Sub-sampling the covariance to 256 snapshots per update is
simpler and has the same effect.

## Memory and allocation

The C core allocates nothing. In Python, frames are short-lived arrays of 8 KiB; keep the garbage
collector out of the acquisition loop by not storing results.

## What to record when testing on a board

Model, OS and kernel, compiler and flags, NumPy and BLAS versions, governor, temperature,
throttling status (`vcgencmd get_throttled`), median **and** 99th percentile latency.
