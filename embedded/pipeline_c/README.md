# pipeline_c — adaptive receive pipeline in C99

Phase 2. Uses the frozen kernels of [`embedded/core`](../core/README.md) without modifying them.

| Mode | Algorithm | Use |
|---|---|---|
| `ABFP_PHASE1` | calibration, recursive covariance, MDL, root-MUSIC, LCMV with nulls | equality with Python |
| `ABFP_NOISE_LOADED` | MVDR, loading = factor × estimated noise | default, double precision |
| `ABFP_NOISE_LOADED_SQRT` | the same on the triangular factor | single precision, any interferer level |

| File | Content |
|---|---|
| `include/abf_pipeline.h` | interface |
| `include/abf_ring.h` | lock-free single-producer single-consumer ring (C11) |
| `src/abfp_numeric.c` | Jacobi eigensolver, MDL, root-MUSIC |
| `src/abfp_pipeline.c` | state machine, covariance, LCMV, MVDR |
| `src/abfp_sqrt.c` | Givens QR, one-sided Jacobi, square-root MVDR |
| `tools/abf_replay.c` | runs a recording, JSON lines out |
| `tools/abf_receiver.c` | live UDP receiver, POSIX threads |

```bash
cmake -S embedded/pipeline_c -B build && cmake --build build
ctest --test-dir build --output-on-failure
./build/bench_pipeline_f64
./build/abf_replay_f64 capture.abf out.cf32 noise 0 0.5 calibrated
./build/abf_receiver 5600 noise 0 0.5        # Linux, macOS
```

Precision is chosen at compile time: libraries `abfp_f32` and `abfp_f64` (define `ABFP_DOUBLE`).

Rules: no heap, no globals, caller-owned state; bad data never returns an error but sets status bits
(0 to 9 as in Python, bit 10 `ABFP_PRECISION_LIMITED`); no `-ffast-math`, which removes the NaN checks.

Measurements: [research/c_port/REPORT.md](../../research/c_port/REPORT.md). Not executed on a Raspberry
Pi, Jetson or microcontroller.
