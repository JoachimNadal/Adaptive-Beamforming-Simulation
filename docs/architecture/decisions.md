# Architecture Decisions

| ID | Decision | Why | Consequence |
|---|---|---|---|
| ADR-001 | One phase convention, $e^{-jmkd\sin\theta}$, defined only in `dsp/steering.py` | It is the course's convention and `LinearArray`'s; duplicating it caused audit D1 | Generators must ask the array object for phases |
| ADR-002 | Keep the top-level packages (`dsp`, `simulations`, …) instead of a `src/` layout | They are the paths published in the README, the guide and the course | Package names are generic; install in a virtual environment |
| ADR-003 | Keep the parameter name `unite` | Public API since the first commit; used throughout the guide | Unknown values now raise |
| ADR-004 | `compute_beam_pattern` no longer opens a window | Computation and display must be separable to be testable | **Behaviour change**: call `plot_beam_pattern` to draw |
| ADR-005 | `generate_snapshot_matrix` draws uncorrelated sources by default | The old coherent sources made MVDR amplify the interferer | **Behaviour change**: pass `coherent=True` for the old scene; `noise_power` now means what it says |
| ADR-006 | Dashboard in Matplotlib, not PyQtGraph | 1–20 Hz refresh is enough; no extra dependency; testable headless | Not suitable for high-rate waterfalls |
| ADR-007 | Only NumPy and Matplotlib at run time; SciPy in tests; PyTorch optional | Small installation on embedded Linux | Filters, Welch PSD and root-finding are implemented here and checked against SciPy |
| ADR-008 | C99 float32 core, at most 16 antennas, no heap | Portable to every target; stack usage bounded | Larger arrays need recompilation with another limit |
| ADR-009 | Python remains the reference; C is tested against it | One source of truth for the mathematics | Python tests need CMake and a compiler to run the C checks (skipped otherwise) |
| ADR-010 | Pipeline uses LCMV + root-MUSIC, with fallback to MVDR and Delay-and-Sum | Course chapter 24; every step can fail on real data | Output always exists and carries a status |
| ADR-011 | Derivative constraint referenced to the array centre | Saves 5.2 dB of array gain for N=8 (erratum E7) | Differs from course listing 23.1 |
| ADR-012 | MDL on the unloaded covariance | Loading hides weak sources (erratum E3) | Differs from course listing 24.1 |
| ADR-013 | No SDR driver included | None could be tested | `IQFrame` iterators are the integration point |
| ADR-014 | No PCB or schematic in Phase 1 | None existed; inventing one was out of scope | [hardware](../hardware/README.md) holds requirements only |
| ADR-015 | LMS/RLS available but not used in the pipeline | They need a reference signal the receiver does not have, and RLS winds up without input | Available for supervised reception |
| ADR-016 | CNN shipped with a hand-crafted baseline | A network must be compared with something | Baseline is the default when PyTorch is absent |
| ADR-017 | Wideband, sparse, hybrid and 2-D methods deferred | Phase 2 scope; no folder existed for them | Listed in the [roadmap](../ROADMAP.md) |
