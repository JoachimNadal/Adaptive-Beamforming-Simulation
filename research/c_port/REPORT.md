# Study 3 — C port of the pipeline

Executed on the development PC and on CI runners (Linux x86-64 and **arm64**). Not executed on a
Raspberry Pi, Jetson or microcontroller. Code: [`embedded/pipeline_c`](../../embedded/pipeline_c/README.md).
Hypotheses: [HYPOTHESES.md](../HYPOTHESES.md).

```bash
python -m research.c_port.run
python -m research.c_port.report
```

## Summary

1. **In double precision the C pipeline is the Python pipeline**: on 7200 random blocks the detected
   order, status and method are identical and the weights agree to about 1e-7, for N = 4, 8, 16.
2. **Single precision is not enough for a covariance** beyond about 50–60 dB of interference: the noise
   eigenvalues fall below the rounding error and sources are miscounted.
3. **Square-root processing fixes this completely.** Updating the triangular factor by Givens rotations
   and taking its singular values needs only float32 up to 80 dB of interference, with less than 0.002 dB
   of difference, at 2.5 to 5 times the cost of the covariance mode and one third of the stack.
4. The covariance modes now **flag** blocks whose precision is insufficient. Every float32 block that
   deviates by more than 0.1 dB is flagged.
5. **60 × faster than Python** at N = 4, K = 256 (Phase 1 mode); no heap, 12.8 KiB of state in float32.

## 1. Theory

| Step | Python (Phase 1) | C |
|---|---|---|
| Covariance | matrix product, float64 | streaming upper triangle, `abfp_real` |
| Eigenproblem | LAPACK `eigh` | cyclic complex Jacobi |
| Source count | MDL | MDL, computed incrementally from the smallest eigenvalue |
| DOA | companion-matrix eigenvalues | Aberth iterations in double precision |
| LCMV | LU solves | Cholesky, trace-normalised |
| Noise loading | – | eigenvalues, Cholesky |
| Square root | – | Givens QR, one-sided Jacobi SVD, two triangular solves |

**Why Jacobi and Aberth.** Both are short, need no library, have no data-dependent memory, and converge
for the sizes involved (N ≤ 16, degree ≤ 30). LAPACK is not available on small targets.

**Why the square root helps.** With an interferer $P$ above unit noise the covariance eigenvalues span
$NP$ to 1. Rounding perturbs *all* of them by about $N\epsilon\,NP$: in float32 ($\epsilon=1.2\cdot10^{-7}$)
with $N=8$ and 60 dB that is 8 times the noise. The data have amplitudes $\sqrt P$: working on
$\mathbf T$ with $\mathbf T^H\mathbf T=\mathbf R$ spans only $\sqrt{NP}$ to 1, and orthogonal rotations do not amplify
errors. Loading is also a rotation: appending $\sqrt\alpha\,\mathbf I$ to $\mathbf T$.

## 2. Hypotheses and verdicts

| ID | Verdict | Evidence |
|---|---|---|
| H3.1 float32 within 0.1 dB for ≥ 99 % of blocks | **refuted** at first (94.2 % at N = 8, 97.3 % at N = 4); after clamping, 98.7 % at N = 4 and 100 % at N = 8, 16 in Phase 1 mode: still just under at N = 4 | accuracy table; the scenes include up to 60 dB |
| H3.2 ≥ 50 × faster at N = 4, K = 256 | supported | 60 × (Phase 1 pipeline, float64); 28 × for noise loading; 8–22 × at N ≥ 8 |
| H3.3 ≤ 16 KiB state and stack, no heap, N = 16 | supported in float32 (12.8 KiB, 3.1 KiB); **refuted in float64** (25.3 KiB of state) | memory table |
| H3.4 float32 loses ≤ 0.1 dB up to 60 dB | **refuted** before clamping (1.4 dB at N = 4, Phase 1 mode); supported afterwards for one interferer | precision table |
| H3.5 square root in float32 correct to 80 dB | supported | 100 % correct order, ≤ 0.001 dB loss, N = 4, 8, 16 |

A change made during this study made things worse before it made them better: lowering the floor inside
MDL for the square-root mode silently broke the float32 covariance modes (N = 16: 99 % → 85 % of blocks
within 0.1 dB). The rerun of the accuracy experiment caught it; the clamp now belongs to the covariance
path only.

## 3. Experiment

Frames are written once to an ABF1 file (float32) that both implementations read. `accuracy`: 120 random
scenes of 10 blocks per array size, 1 to N − 3 interferers of 10–60 dB, target −5 to 10 dB, K = 256.
`precision`: one interferer, 20–80 dB, 60 scenes. `timing`: median Python latency; C benchmark, best of
three. `memory`: `sizeof`, `-fstack-usage`, `size`.

## 4. Metrics

Absolute SINR difference per block on the true scene, relative weight and output differences, agreement
of order, status and method, time per block, bytes.

## 5. Baseline

The frozen Python pipeline, and for the noise-loaded modes the Python estimator of study 1.

## 6. Results

### Agreement with Python on identical input

<!-- accuracy -->

| mode | precision | N | blocks within 0.1 dB | max difference (dB) | median weight difference | same order | same method | flagged | unflagged > 0.1 dB |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| noise | f32 | 4 | 100.00 % | 0.0078 | 5e-05 | – | 100.0 % | 9.8 % | 0.00 % |
| noise | f32 | 8 | 89.42 % | 1.8668 | 1e-03 | – | 100.0 % | 44.6 % | 0.00 % |
| noise | f32 | 16 | 45.83 % | 13.4490 | 4e-02 | – | 100.0 % | 85.9 % | 0.00 % |
| noise | f64 | 4 | 100.00 % | 0.0000 | 3e-08 | – | 100.0 % | 0.0 % | 0.00 % |
| noise | f64 | 8 | 100.00 % | 0.0001 | 3e-08 | – | 100.0 % | 0.0 % | 0.00 % |
| noise | f64 | 16 | 100.00 % | 0.0001 | 3e-08 | – | 100.0 % | 0.0 % | 0.00 % |
| phase1 | f32 | 4 | 98.67 % | 2.4170 | 1e-05 | 98.5 % | 100.0 % | 9.8 % | 0.00 % |
| phase1 | f32 | 8 | 100.00 % | 0.0339 | 2e-05 | 96.3 % | 100.0 % | 44.6 % | 0.00 % |
| phase1 | f32 | 16 | 100.00 % | 0.0040 | 4e-05 | 78.2 % | 100.0 % | 85.9 % | 0.00 % |
| phase1 | f64 | 4 | 100.00 % | 0.0000 | 3e-08 | 100.0 % | 100.0 % | 0.0 % | 0.00 % |
| phase1 | f64 | 8 | 100.00 % | 0.0000 | 4e-08 | 100.0 % | 100.0 % | 0.0 % | 0.00 % |
| phase1 | f64 | 16 | 100.00 % | 0.0000 | 5e-08 | 100.0 % | 100.0 % | 0.0 % | 0.00 % |
| sqrt | f32 | 4 | 100.00 % | 0.0015 | 7e-07 | – | 100.0 % | 0.0 % | 0.00 % |
| sqrt | f32 | 8 | 100.00 % | 0.0013 | 3e-06 | – | 100.0 % | 0.0 % | 0.00 % |
| sqrt | f32 | 16 | 100.00 % | 0.0020 | 1e-05 | – | 100.0 % | 0.0 % | 0.00 % |
| sqrt | f64 | 4 | 100.00 % | 0.0000 | 3e-08 | – | 100.0 % | 0.0 % | 0.00 % |
| sqrt | f64 | 8 | 100.00 % | 0.0001 | 3e-08 | – | 100.0 % | 0.0 % | 0.00 % |
| sqrt | f64 | 16 | 100.00 % | 0.0001 | 3e-08 | – | 100.0 % | 0.0 % | 0.00 % |

<!-- /accuracy -->

`flagged` is the share of blocks with `ABFP_PRECISION_LIMITED`. `noise f32` at N = 16 differs from Python
in half of the blocks: the clamp raises the noise estimate, hence the loading, and the mean loss rises
from 1.51 to 2.41 dB. These blocks are flagged. The last column is the safety property: no silent
failure.

### float32 against float64, one interferer (SINR loss in dB)

<!-- precision -->

| N | INR (dB) | phase1 mean | noise mean | sqrt mean | phase1 max | noise max | sqrt max |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 40 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 4 | 60 | 0.000 | 0.000 | 0.000 | 0.000 | 0.002 | 0.001 |
| 4 | 70 | 0.000 | 0.000 | 0.000 | 0.004 | 0.004 | 0.002 |
| 4 | 80 | 0.000 | 0.001 | 0.001 | 0.009 | 0.020 | 0.012 |
| 8 | 40 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 8 | 60 | 0.000 | 0.000 | 0.000 | 0.000 | 0.003 | 0.001 |
| 8 | 70 | 0.000 | 0.000 | 0.000 | 0.000 | 0.014 | 0.003 |
| 8 | 80 | 0.000 | 0.000 | 0.001 | 0.000 | 0.043 | 0.009 |
| 16 | 40 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 16 | 60 | 0.000 | 0.000 | 0.000 | 0.000 | 0.004 | 0.001 |
| 16 | 70 | 0.000 | 0.000 | 0.000 | 0.000 | 0.029 | 0.004 |
| 16 | 80 | 0.000 | 0.013 | 0.000 | 0.000 | 0.147 | 0.011 |

<!-- /precision -->

### Square-root prototype in NumPy float32 (written before the C code)

<!-- square_root -->

| N | INR (dB) | covariance: order | covariance: loss (dB) | square root: order | square root: loss (dB) |
|---:|---:|---:|---:|---:|---:|
| 4 | 40 | 100 % | -0.000 | 100 % | 0.000 |
| 4 | 60 | 42 % | 0.005 | 100 % | 0.000 |
| 4 | 70 | 6 % | 3.946 | 100 % | -0.000 |
| 4 | 80 | 40 % | 5.031 | 100 % | 0.000 |
| 8 | 40 | 100 % | 0.000 | 100 % | -0.000 |
| 8 | 60 | 0 % | 2.762 | 100 % | 0.000 |
| 8 | 70 | 0 % | 8.460 | 100 % | -0.000 |
| 8 | 80 | 0 % | 8.256 | 100 % | -0.000 |
| 16 | 40 | 100 % | 0.000 | 100 % | -0.000 |
| 16 | 60 | 0 % | 12.753 | 100 % | 0.000 |
| 16 | 70 | 0 % | 11.506 | 100 % | 0.000 |
| 16 | 80 | 0 % | 11.663 | 100 % | -0.000 |

<!-- /square_root -->

### Time per block of 256 snapshots, i7-9700K, one core

<!-- timing -->

| mode | N | Python (µs) | C float32 (µs) | C float64 (µs) | float32, -march=native (µs) | Python / float64 | float32 MS/s |
|---:|---:|---:|---:|---:|---:|---:|---:|
| phase1 | 4 | 661 | 10.8 | 11.1 | 10.1 | 60 × | 23.7 |
| phase1 | 8 | 845 | 34.2 | 38.9 | 32.4 | 22 × | 7.5 |
| phase1 | 16 | 1502 | 149.0 | 182.4 | 137.4 | 8 × | 1.7 |
| noise | 4 | 247 | 8.5 | 8.7 | 7.8 | 28 × | 30.2 |
| noise | 8 | 315 | 23.9 | 29.3 | 22.3 | 11 × | 10.7 |
| noise | 16 | 620 | 96.5 | 129.7 | 87.2 | 5 × | 2.7 |
| sqrt | 4 | – | 40.2 | 38.5 | 38.7 | – | 6.4 |
| sqrt | 8 | – | 90.9 | 92.6 | 86.7 | – | 2.8 |
| sqrt | 16 | – | 248.8 | 269.6 | 231.5 | – | 1.0 |

<!-- /timing -->

`-march=native` brings under 15 %: the loops are short and not vectorised by the compiler. Python times
are medians on a loaded PC and vary by a factor of two between sessions.

Same benchmark on the **arm64 CI runner** (GCC, one cloud core, not a Raspberry Pi or Jetson):

| mode | N=4 f32 / f64 (µs) | N=8 f32 / f64 (µs) | N=16 f32 / f64 (µs) |
|---|---:|---:|---:|
| phase1 | 9.3 / 11.6 | 34 / 44 | 170 / 217 |
| noise | 7.0 / 9.2 | 23 / 33 | 110 / 156 |
| sqrt | 28 / 34 | 73 / 90 | 239 / 311 |

With K = 256 and one core, the noise-loaded mode sustains 36 MS/s (N = 4) and 11 MS/s (N = 8) there, in
float32.

### Memory (N up to 16)

<!-- memory -->

| precision | state (bytes) | deepest stack chain (bytes) | stack, square-root mode (bytes) | code, x86-64 -Os (bytes) | static data (bytes) |
|---:|---:|---:|---:|---:|---:|
| f32 | 12804 | 3184 | 944 | 20760 | 0 |
| f64 | 25296 | 5904 | 1408 | 21516 | 0 |

<!-- /memory -->

State for N = 16 whatever the configured N: the arrays are sized at compile time by `ABF_MAX_ANTENNAS`.

## 7. Limitations and conclusions

Limitations:

- No target board. Cortex-A76 and A78AE have different caches and NEON behaviour from the CI machine.
- Covariance and rotations are scalar code; no NEON, no fixed point.
- Steering vectors use `sin`/`cos` per block; they could be cached.
- The live receiver (`abf_receiver`) is tested over loopback with 50 frames only.
- The Phase 1 mode inherits the fragility documented in [study 1](../covariance/REPORT.md).

Conclusions:

| Decision | Reason |
|---|---|
| Default mode for embedded Linux: `ABFP_NOISE_LOADED` in float64 | best tail behaviour (study 1), cheap, no precision limit; 25 KiB is nothing there |
| Single-precision targets (Cortex-M7, FPGA soft core): `ABFP_NOISE_LOADED_SQRT` | only float32 option that is correct at any interferer level |
| Keep Phase 1 mode as a reference | equality with Python |
| Acquisition and processing separated by a lock-free ring | acquisition never blocks; drops are counted |
| Next: NEON for the covariance, then measurements on a real board | 80 % of the time at N = 4 is the covariance loop |
