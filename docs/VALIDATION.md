# Validation Report

State of Phase 1. Only executed checks are reported; the last section lists what was **not**
verified.

## Environments

| ID | Environment |
|---|---|
| PC | Windows 11, i7-9700K, Python 3.11.18, NumPy 2.4.6, SciPy 1.17.1, Matplotlib 3.11.2, PyTorch 2.15.0 CPU, GCC 13.2 (MinGW), CMake 3.29 |
| GPU | same PC, RTX 2080 Ti, CuPy 14.2.0 |
| CI | GitHub Actions: Ubuntu x86-64, Ubuntu arm64, Windows |

## Summary

| Check | Where | Result |
|---|---|---|
| Unit and integration tests | PC | 249 passed, 0 failed, 0 skipped |
| Statement coverage (`dsp`, `simulations`, `embedded`, `ai`, `dashboard`) | PC | 96 % |
| Mutation check, 18 injected bugs | PC | 18 caught |
| Lint and format (`ruff`) | PC | clean |
| Types (`mypy`, 80 files) | PC | clean |
| Oldest supported dependencies (NumPy 1.26.4, Matplotlib 3.8.4) | PC | 246 passed, 3 skipped (no SciPy/PyTorch there) |
| Python 3.14.0rc2 | PC | passed, 1 skipped (no PyTorch) |
| README quick start from a clean copy and new environment | PC | works |
| Wheel build | PC | works |
| C core: strict warnings as errors, unit tests | PC | pass |
| C core against Python, 19 tests | PC | pass |
| C core: `clang-tidy`, `gcc -fanalyzer` | PC | clean |
| C core: cross-compile and link, aarch64, armhf, riscv64, x86-64 (Zig) | PC | success, not executed |
| Figures regenerated | PC | byte-identical, except `dashboard.png` which shows a measured latency |
| Batched MVDR on GPU | GPU | equal to CPU within 2e-16 |
| CI matrix | CI | see [CI results](#ci-results) |

## How correctness was established

| Property | Reference used | Test |
|---|---|---|
| Phase convention | every generator × Bartlett, root-MUSIC, ESPRIT, three angles | `test_conventions.py` |
| MVDR | closed-form optimum SINR | `test_mvdr_equals_theoretical_optimum` |
| Sample MVDR | Reed–Mallett–Brennan loss, 1500 trials | `test_smi_loss_follows_reed_mallett_brennan` |
| LCMV | equals MVDR and null steering in its limits | `test_lcmv_generalises_mvdr_and_null_steering` |
| RLS | batch weighted least squares, 1e-8 | `test_rls_matches_batch_least_squares` |
| LMS | stability bound, both sides | `test_lms_diverges_beyond_its_stability_bound` |
| root-MUSIC, ESPRIT | Cramér–Rao bound, 200 trials per SNR | `test_root_music_is_statistically_efficient` |
| Cramér–Rao bound | single-source closed form | `test_crb_matches_single_source_closed_form` |
| PSD | `scipy.signal.welch`, 1e-9 | `test_psd_matches_scipy_and_parseval` |
| Doppler fading | Bessel autocorrelation | `test_doppler_fading_has_clarke_autocorrelation` |
| Array metrics | textbook 8-element values | `test_metrics_on_known_patterns` |
| Frame parser | every byte corrupted, random bytes, truncation, in Python and C | `test_embedded.py`, `test_c_core.py` |
| C kernels | Python, float32 tolerance, n = 1 to 16, up to 60 dB INR, levels 1e-12 to 1e8 | `test_c_core.py`, `test_abf.c` |

## Before and after

Same scenes, original code (`8f91f28`) against this version.

| Scene | Before | After |
|---|---|---|
| `test_mvdr.py` scene, real output SINR | −28.2 dB | 20.0 dB (optimum) |
| Source simulated at +20°, estimated | −20° | +20° |
| Noise power requested 0.02 | 0.0397 | 0.020 |
| `run_mvdr_demo.py`, gain toward the interferer | +2.9 dB | −31 dB |
| `run_covariance_demo.py`, simulated target angle | 0.35° | 20° |
| `MVDR` with K = 2 < N | meaningless weights, no error | `IllConditionedError` |
| README quick start | fails | works |
| Tests able to see the phase bug | 0 | several |

The first row is the same physical scene: the old `noise_power=0.02` actually produced 0.04. In the
fourth row the interferer also moved from −40° to −25° (audit D25); the cause of the improvement is
the uncorrelated sources, verified by mutation.

## Simulated performance

| Item | Result | Source |
|---|---|---|
| Pipeline SINR | 8.79 dB against 8.79 dB optimum (N=8, two 35 dB interferers) | [pipeline](architecture/signal_pipeline.md) |
| End-to-end with calibration | 9.3 dB mean, optimum 9.7, Delay-and-Sum −10.7 | `examples/run_full_pipeline.py` |
| Tracking | RLS 5.3, recursive 4.6, SMI 4.1, optimum 5.9 dB | [adaptive](theory/adaptive_algorithms.md#tracking) |
| Detector | 0.6 % false alarms, 100 % detection from −6 dB (N=4, K=128) | [DOA](theory/doa_estimation.md#detection) |
| Classifier | 99.2 %, baseline 91.2 %, synthetic | [ai](../ai/README.md) |
| Error budget | tables | [hardware](hardware/error_budget_results.md) |

## Known bugs and limits

No known incorrect result. Limits L1–L12 are in the [roadmap](ROADMAP.md#known-limits-after-phase-1).
Behaviour worth remembering:

- An interferer within the guard zone of the target cannot be rejected; the pipeline falls back to
  Delay-and-Sum and says so.
- RLS overflows if adapted without input signal.
- The classifier never answers "unknown" reliably.
- The local `cppcheck` package was broken (missing `std.cfg`); it runs in CI only.

## Not verified

| Item | Reason |
|---|---|
| Any physical measurement | no hardware |
| Raspberry Pi, Jetson, Zynq execution | no boards |
| Real IQ data, real interference | no recordings |
| Mutual coupling, element patterns, polarisation, near field | not modelled |
| Long-run stability over hours | not tested |
| UDP reception above test rates | loopback test only, 3 frames |
| macOS | not tested |
| Fixed-point implementation | not implemented |

## Reproduction

```bash
pip install -e ".[dev,ai]"
pytest
ruff check . && ruff format --check . && mypy
python scripts/mutation_check.py
python scripts/check_course_errata.py
python scripts/hardware_error_budget.py
python scripts/generate_figures.py
python -m ai.training.train && python -m ai.training.evaluate

cmake -S embedded/core -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build && ctest --test-dir build --output-on-failure
```

## CI results

First run: [45603333830](https://github.com/JoachimNadal/Adaptive-Beamforming-Simulation/actions/runs/45603333830).
8 jobs out of 9 passed; the benchmark did not compile with the newer Clang of the x86-64 runner
(enum/double arithmetic, warnings as errors). Fixed in the following commit; later runs are on the
[Actions page](https://github.com/JoachimNadal/Adaptive-Beamforming-Simulation/actions).

| Job | Result of the first run |
|---|---|
| Python 3.11 and 3.13, Ubuntu x86-64 | 248 passed, 1 skipped (no PyTorch) |
| Python 3.12, Windows | 248 passed, 1 skipped |
| Python 3.12, Ubuntu **arm64** | 248 passed, 1 skipped, including C core against Python |
| C core, GCC and Clang, **arm64**: tests, address and UB sanitizers | pass |
| C core, GCC, x86-64: tests, sanitizers | pass |
| C core, Clang, x86-64 | build failure in the benchmark, fixed |
| cppcheck, `gcc -fanalyzer` | clean |

Throughput on the arm64 CI runner (GCC, one core of a cloud server; **not** a Raspberry Pi or
Jetson):

| N | apply (MS/s) | covariance (MS/s) | MVDR (µs) | RLS (µs/sample) |
|---:|---:|---:|---:|---:|
| 4 | 247 | 77 | 0.11 | 0.08 |
| 8 | 126 | 28 | 0.29 | 0.20 |
| 16 | 64 | 9.0 | 1.2 | 0.62 |
