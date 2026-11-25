# Project Roadmap

## Phase 1 — complete the baseline

| Work | State |
|---|---|
| Audit | done |
| Phase convention, noise, coherence, units (D1–D8, D13, D17) | done |
| Numerically safe kernels, LCMV, NLMS, metrics, packaging, CI (D9–D12, D14–D20) | done |
| DOA estimators, channel models, calibration | done |
| Embedded: protocol, pipeline, receiver, C core | done in simulation and on PC |
| AI chain, dashboard, demos | done, synthetic data only |
| Hardware requirements | done; **no hardware exists** |
| Theory, guide, errata, figures | done |

Audit items and their resolution:

| Items | Resolution |
|---|---|
| D1, D2, D3, D4, D5, D6, D25 | fixed; regression tests |
| D7, D8, D9, D10, D11, D12, D13 | fixed; regression tests |
| D14, D15, D16, D17, D18, D19, D20, D21, D22, D23, D24 | fixed |
| E1–E5, E7 | code differs from the PDF on purpose, documented |
| E6 | script written |

## Known limits after Phase 1

| ID | Limit | Why it remains | What would remove it |
|---|---|---|---|
| L1 | No physical validation | no hardware | a coherent receiver and test plan T1–T7 |
| L2 | No execution on Raspberry Pi, Jetson, FPGA | no boards | boards |
| L3 | No PCB, schematic, BOM, Gerber | never existed | Phase 2 design |
| L4 | AI never saw real signals; no novelty detection | no recordings | dataset, open-set method |
| L5 | Course PDFs uncorrected | LaTeX sources not in the repository | sources |
| L6 | Narrowband only; subband analysis without synthesis | scope | Phase 2 |
| L7 | ULA-only DOA in the pipeline | root-MUSIC | manifold-based MUSIC in the pipeline |
| L8 | Loading relative to total power: at 60 dB INR the default 1e-2 costs 2.8 dB (MVDR) and 8.0 dB (LCMV with derivative, no explicit null), N=4. Explicit nulls hide it in the pipeline while the DOA is found | simple and safe | noise-referenced or WNG-constrained loading |
| L9 | Fast interferers look like several sources | covariance memory | tracking, shorter blocks |
| L10 | Python pipeline below 1 MS/s on a desktop | interpreter overhead | C port of order/DOA, or MVDR-only path |
| L11 | Mutual coupling and element patterns not modelled | needs measurement or EM simulation | Phase 2 |
| L12 | Bare-metal Cortex-M not built | `arm-none-eabi-gcc` not on the PATH; Zig has no C library for it | arm-none-eabi |

## Phase 2 — R&D

Separate programme, on its own branch: [RND_ROADMAP.md](RND_ROADMAP.md) and
[research/](../research/README.md). Candidate directions at the end of Phase 1: robust and
noise-referenced loading, wideband processing, sparse arrays, fixed-point study, calibration
drift tracking, open-set classification, first receiver hardware.
