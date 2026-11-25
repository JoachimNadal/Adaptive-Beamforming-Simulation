# Embedded Targets

Planned targets named by the project. **None of these boards was available: nothing below was
measured on them.** Board facts come from the manufacturers' pages listed at the end; everything
else is computed or measured on the development PC and marked as such.

## Boards

| | Raspberry Pi 5 | Jetson Orin Nano (Super) | Zynq-7000 class |
|---|---|---|---|
| CPU | 4 × Cortex-A76 at 2.4 GHz, 512 KB L2 per core, 2 MB L3 | 6 × Cortex-A78AE, up to 1.7 GHz | Cortex-A9 + FPGA fabric |
| Accelerator | – | 1024-core Ampere GPU | DSP48E1 slices (count depends on the device) |
| Memory | 32-bit LPDDR4X-4267 | 8 GB LPDDR5, 102 GB/s | board dependent |
| I/O relevant here | Gigabit Ethernet, PCIe 2.0 x1, USB 3 | carrier dependent | direct ADC interface |
| Role in this project | receiver application, C core | many subbands or beams | sample-rate filtering and weights |
| Code in this repository | `embedded/raspberry_pi`, `embedded/core` | `embedded/jetson` | notes only |

## Computational load

Complex multiply-accumulates per second, from the operation counts in
[adaptive_algorithms.md](../theory/adaptive_algorithms.md); weights at 100 Hz.

| N | $f_s$ | apply weights | covariance (all samples) | MVDR at 100 Hz |
|---:|---:|---:|---:|---:|
| 4 | 1 MS/s | 4 M | 10 M | < 0.1 M |
| 4 | 10 MS/s | 40 M | 100 M | < 0.1 M |
| 8 | 10 MS/s | 80 M | 360 M | < 0.1 M |
| 16 | 10 MS/s | 160 M | 1360 M | 0.1 M |

The solve is negligible; the covariance dominates. It does not need every sample: 256 snapshots
per update are enough for $N\le16$, so sub-sampling it is the first optimisation.

## Measured on the development PC (one core, i7-9700K, GCC 13 -O3)

| N | apply (MS/s) | covariance (MS/s) | MVDR (µs) | RLS (µs/sample) |
|---:|---:|---:|---:|---:|
| 4 | 153 | 37 | 0.25 | 0.12 |
| 8 | 87 | 15 | 0.63 | 0.25 |
| 16 | 54 | 6.6 | 1.7 | 0.70 |

Python pipeline on the same machine: 0.2 MS/s (N=4, K=256) to 0.75 MS/s (K=1024). Conclusion:
Python is suitable for control-rate work, recorded data and demonstrations; sample-rate work
belongs in the C core. The C core is not vectorised by hand; see
[optimization.md](../../embedded/raspberry_pi/optimization.md).

## Memory

The C core uses only caller-owned memory and at most 2 KiB of stack for the $16\times16$ work
matrix (`16·16·8` bytes).

| Buffer (N=4, K=256, cf32) | Bytes |
|---|---:|
| Block | 8192 |
| Covariance | 128 |
| Weights | 32 |
| Output | 2048 |

## Timing budget

With one block per frame, the latency is $K/f_s$ plus processing. Example for $f_s=1$ MS/s,
$K=256$: 256 µs to fill the block, so 256 µs to process it.

| Step (N=4, K=256) | C core, measured on the PC |
|---|---:|
| Covariance | 6.8 µs |
| MVDR | 0.3 µs |
| Apply | 1.7 µs |

Order estimation and root-MUSIC are not in the C core: they need an eigenvalue solver and only
run at the weight rate, so they stay in Python (≈1 ms) or use a separate thread. Using MVDR
instead of LCMV on the target avoids them altogether.

## Choosing a receiver

Requirements: [hardware/requirements.md](../hardware/requirements.md). Two facts that constrain
the choice:

- **KrakenSDR** has five coherent channels with a built-in noise source for phase
  synchronisation, but tunes 24–1766 MHz with 8-bit ADCs and 2.56 MHz bandwidth: it does **not**
  cover the 2.4 GHz reference frequency. The array would have to be rescaled (for example
  λ/2 = 17.3 cm at 868 MHz), and 8 bits limit the rejection (4.2 dB SINR loss at 40 dB INR in the
  [error budget](../hardware/error_budget_results.md)).
- **AD9361** transceivers have two receivers each and no internal RF phase synchronisation:
  four channels need two devices, and the LO phase must be measured and corrected after every
  start. Analog Devices' FMCOMMS5 reference design does this. The pipeline handles it through
  the `clock unlocked` flag and `calibrate_from`.

## Portability evidence for the C core

| Check | Result |
|---|---|
| GCC 13, `-Wall -Wextra -Wpedantic -Wshadow -Wconversion -Wdouble-promotion -Werror` | clean |
| Unit tests on the development PC | pass |
| Cross-compiled and linked with Zig/Clang for aarch64, armhf, riscv64, x86-64 Linux | success, not executed |
| CI on native arm64 runners, GCC and Clang, with sanitizers | pass, see [VALIDATION.md](../VALIDATION.md#ci-results) |
| Bare-metal Cortex-M | not built: no C library with the toolchain used |

## Sources

- [Raspberry Pi 5 product brief](https://pip-assets.raspberrypi.com/categories/892-raspberry-pi-5/documents/RP-008348-DS-6-raspberry-pi-5-product-brief.pdf?disposition=inline),
  [processors documentation](https://www.raspberrypi.com/documentation/computers/processors.html)
- [Jetson Orin Nano Super developer kit](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/nano-super-developer-kit/),
  [NVIDIA blog](https://developer.nvidia.com/blog/nvidia-jetson-orin-nano-developer-kit-gets-a-super-boost/)
- [KrakenSDR specifications (Elektor)](https://www.elektor.com/products/krakensdr-5-ch-sdr-based-on-rtl-sdr),
  [announcement (RTL-SDR.com)](https://www.rtl-sdr.com/?p=51356)
- [FMCOMMS5 phase synchronisation](https://analogdevicesinc.github.io/documentation/solutions/reference-designs/fmcomms5/phase-sync.html),
  [AD9361 multichip synchronisation](https://analogdevicesinc.github.io/documentation/solutions/reference-designs/fmcomms5/multi-chip-sync.html)
- [DSP48E1 primitive, UG953](https://docs.amd.com/r/en-US/ug953-vivado-7series-libraries/DSP48E1)
