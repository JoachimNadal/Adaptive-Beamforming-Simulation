# Receiver Requirements

What a coherent receiver must achieve for the algorithms of this repository to work as
simulated. Values are **derived from simulation or from first principles**; none has been
verified on hardware. Source data: [error_budget_results.md](error_budget_results.md).

Reference case: 4 elements, 2.4 GHz, one interferer at 30–40 dB INR.

## Channel coherence

| ID | Requirement | Target | Minimum | Justification |
|---|---|---|---|---|
| R1 | Residual phase error after calibration, RMS | 1° | 5° | deterministic null −43 dB at 1°, −29 dB at 5° (N=4) |
| R2 | Residual gain error after calibration, RMS | 0.1 dB | 0.5 dB | null −47 dB at 0.1 dB, −32 dB at 0.5 dB |
| R3 | Common LO or phase-locked LOs | required | required | independent LOs make phases meaningless |
| R4 | Common sampling clock | required | required | same reason |
| R5 | Clock/LO lock status available to software | required | required | `clock unlocked` flag invalidates the calibration |
| R6 | Phase repeatability after restart | known | measured at each start | calibration is discarded after a clock loss |
| R7 | In-situ calibration source | 20 dB SNR per channel | 10 dB | 0.24° residual with K=256 at 20 dB, 0.76° at 10 dB |

R1 and R2 apply to *explicit* nulls. Adaptive MVDR tolerates more (0.10 dB loss at 10° RMS with
30 dB INR and 0 dB SNR), as long as the target is weak and the weights are loaded.

Equivalent of R1 at 2.4 GHz:

| Phase | RF path length (air) | RF skew | Sampling skew at 1 MHz IF |
|---:|---:|---:|---:|
| 1° | 0.35 mm | 1.2 ps | 2.8 ns |
| 5° | 1.74 mm | 5.8 ps | 13.9 ns |

Static differences are calibrated out; what must stay below these values is the **drift between
two calibrations**.

## Dynamic range

| ID | Requirement | Value | Justification |
|---|---|---|---|
| R8 | ADC resolution | ≥ 10 bits for 40 dB INR, ≥ 14 bits for 60 dB | loss 0.4 dB (10 bits, 40 dB) and 0.2 dB (14 bits, 60 dB); 8 bits lose 4.2 dB at 40 dB |
| R9 | Gain control common to all channels, with a change flag | required | different gains are calibration errors; a change resets the covariance |
| R10 | Headroom above RMS | 15 dB | at 12 dB a Gaussian interferer clips 2e-4 of the samples: 0.2 dB loss at 40 dB INR, 4.2 dB at 60 dB |
| R11 | Overflow indication per block | required | clipped blocks must not be used for adaptation |
| R12 | Linearity | intermodulation of two interferers below the noise floor | spurious products look like new sources; value depends on the front end |

Clipping is the dominant error at high INR, before quantisation: an AGC set for 12 dB of headroom
wastes a 14-bit converter.

## Bandwidth and rate

| ID | Requirement | Value | Justification |
|---|---|---|---|
| R13 | Instantaneous bandwidth for narrowband processing | ≤ 1 % of the carrier (24 MHz at 2.4 GHz) | residual −49 dB (N=4), −53 dB (N=8) |
| R14 | Channel filters matched in amplitude and group delay | within R1, R2 over the band | mismatch is a frequency-dependent calibration error |
| R15 | Transport | $4Nf_s$ B/s | 16 MB/s for 4 channels at 1 MS/s |
| R16 | Frame length | 256 to 1024 samples | ≥ 2N for conditioning; latency |

Above 1 %, use subband processing (`embedded/jetson/orin_pipeline.py`).

## Array

| ID | Requirement | Value | Justification |
|---|---|---|---|
| R17 | Spacing | ≤ λ/2 | unambiguous angles; enforced by the configuration |
| R18 | Element position tolerance | ±0.35 mm for 1°, ±1.7 mm for 5° (worst case, endfire) | same phase error as R1, but angle-dependent: not removable by gain/phase calibration |
| R19 | Coupling and element patterns | measured or simulated | not modelled in software |
| R20 | Dummy elements or ground plane extension at both ends | recommended | equalises the embedded patterns of edge elements |

## Power, grounding, routing, EMC

These are design rules implied by the coherence requirements. They have no numeric validation.

| ID | Rule | Reason |
|---|---|---|
| R21 | Each receiver channel supplied through its own filtered rail or regulator | common-mode supply ripple modulates all channels; *differential* ripple is a phase error |
| R22 | LO and clock distribution as a symmetric tree, equal lengths, same layers | skew is calibrated out, its temperature drift is not |
| R23 | One continuous ground plane under RF paths; no split crossed by RF or clock traces | return-path discontinuities couple channels |
| R24 | 50 Ω controlled impedance for RF and single-ended clock traces | mismatch ripples vary with frequency (R14) |
| R25 | Channel-to-channel isolation better than the target null depth | a −40 dB leak limits a null to about −40 dB |
| R26 | Identical channel layouts, repeated rather than mirrored | equal parasitics and thermal gradients |
| R27 | Temperature monitored near the front ends | trigger for recalibration |
| R28 | Digital supplies and fast buses separated from the RF section | spurs are coherent across channels and look like a source at broadside |

## Compliance

Receive-only. A calibration source that radiates is a transmitter and needs its own regulatory
assessment; a conducted, switched noise source avoids the question
([legal and ethics](../safety/legal_and_ethics.md)).

## Verification plan for future hardware

| Test | Verifies | Method |
|---|---|---|
| T1 | R3–R6 | same tone split to all channels; phase drift over time, after restart, over temperature |
| T2 | R1, R2, R7 | conducted calibration, then compare with a second independent source |
| T3 | R8–R11 | two-tone and overload tests, overflow flag |
| T4 | R14 | swept tone over the band |
| T5 | R18–R19 | measured manifold against the model over angle |
| T6 | R25 | drive one channel, measure the others |
| T7 | all | null depth on a real source, compared with the error budget |
