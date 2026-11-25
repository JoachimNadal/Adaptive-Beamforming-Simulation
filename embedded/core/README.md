# abf core — C99 kernels

Single precision, at most 16 antennas, no heap, no global state, reentrant.

| Header function | Purpose |
|---|---|
| `abf_steering_ula`, `abf_das_weights` | steering vector, conventional weights |
| `abf_covariance_update` | recursive Hermitian covariance |
| `abf_mvdr_weights` | loaded MVDR by Cholesky |
| `abf_apply_weights` | y = wᴴx for a block |
| `abf_lms_step`, `abf_nlms_step`, `abf_rls_step` | supervised adaptation |
| `abf_white_noise_gain` | health indicator |
| `abf_frame_parse`, `abf_frame_samples`, `abf_crc32` | ABF1 frames |

## Build and test

```bash
cmake -S embedded/core -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
ctest --test-dir build --output-on-failure
./build/bench_abf
```

Options: `-DABF_SANITIZE=ON` (Linux/macOS), `-DABF_WERROR=OFF`, `-DABF_BUILD_TESTS=OFF`.

Cross-compilation without a board (Zig as compiler):

```bash
pip install ziglang
python -m ziglang cc -target aarch64-linux-gnu -std=c99 -O3 -Iembedded/core/include \
    embedded/core/src/*.c embedded/core/tests/test_abf.c -lm -o test_abf_arm64
```

`tests/test_c_core.py` builds the shared library and compares every function with Python.

## Error handling

Functions return `abf_status` and leave their outputs untouched on error. NaN and infinity are
rejected before any state changes, so one bad sample cannot poison the weights. Do not compile
with `-ffast-math`: it removes those checks.

## Limits

No eigenvalue solver: source counting, MUSIC and LCMV stay in Python. No hand-written SIMD. Not
built for bare-metal Cortex-M.
