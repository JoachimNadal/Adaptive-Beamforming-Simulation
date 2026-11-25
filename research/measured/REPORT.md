# Study 5 — Measured array data

**Measured by others, processed here.** The phases come from a real 2.4 GHz array in a real room. The
waveforms of the beamforming test are synthetic. No hardware of this project was involved, and nothing
here validates it. Hypotheses, registered before downloading: [HYPOTHESES.md](../HYPOTHESES.md).

```bash
python -m research.measured.run      # downloads 230 MB, checks the published MD5 sums
python -m research.measured.report
```

## Summary

1. **The main recommendation of study 1 does not survive real channels.** Noise-referenced loading
   (factor 10) loses 14 dB at the 90th percentile; relative loading 1e-2, which it beat in
   simulation, loses 7 dB.
2. **Eigenspace projection is the most robust**: 3.7 dB (10 dB target) and 12 dB (20 dB target) at the
   90th percentile, the lowest of the seven methods in all four cases.
3. Root-MUSIC with four elements has a **median error of 3.9°**, but a 90th percentile of 35°: multipath
   produces wrong answers, not just noisy ones.
4. Calibrating from **one** known position in a reflecting room makes things **worse** (median 5.2°),
   plausibly because it also calibrates the multipath of that position.
5. Phases between elements of this data jitter by 15° (median) from packet to packet, 9° RMS after
   averaging 10 packets: far from the 1° target of requirement R1.

## 1. Theory

Adaptive beamformers fail in two ways: estimation noise (too few snapshots) and **steering mismatch** (the
real channel vector of the target is not the one assumed, so the target is cancelled as if it were an
interferer). Loading fights both: a large loading tolerates mismatch, a small one keeps deep nulls. Study 1
drew mismatches of a few degrees; a real indoor channel is a sum of paths whose vector may be far from any
plane wave.

## 2. Hypotheses and verdicts

| ID | Verdict | Evidence |
|---|---|---|
| H5.1 median ≤ 5° and 90th percentile ≤ 15° | **refuted** | 3.9° and 35° |
| H5.2 one-position calibration reduces the median by ≥ 30 % | **refuted** | 3.9° → 5.2° |
| H5.3 drift ≤ 1° RMS over the static file | **refuted** | 8.9°; white from block to block except one element with a slow 30° change |
| H5.4 residual to a plane wave > 5° RMS | supported | 39° after calibration, 35° without |
| H5.5 noise × 10 better than relative 1e-2 (90th percentile) | **refuted** | 14.1 against 7.4 dB; 16.1 against 9.3 dB calibrated |
| H5.6 eigenspace better than noise × 10, 20 dB target | supported | 12.1 against 31.2 dB; 12.5 against 32.8 dB calibrated |

## 3. Experiment

Dataset espargos-0001: four arrays of 2 × 4 antennas, 60 mm apart (0.985 half wavelengths at
2.462 GHz), eight ESP32 Wi-Fi receivers per array sharing a clock and a phase reference; 117 subcarriers
over 36.6 MHz; line of sight according to its authors; transmitter position by tachymeter. Two files of
the twelve, 230 MB. One estimate uses 10 consecutive packets × 117 subcarriers.

`static_middle` (206 blocks, 16 s) served for calibration and conventions; `meanders_ns1_continued` (563
blocks, angles from −47° to 36°) for evaluation. Beamforming: the principal eigenvector of the
covariance of one block is the channel vector of a target, that of another block (at least 0.25 away in
sine, same row of 4 elements) the channel of an interferer; synthetic waveforms, white noise, K = 64,
40 dB INR, 2000 trials. The look direction is the geometric plane wave: a real receiver would not know it
better.

## 4. Metrics

Angle errors (median, 90th percentile), phase residual against plane and spherical waves, output-SINR
loss against the optimum for the measured vectors.

## 5. Baselines

Phase 1 loading (relative 1e-2), delay-and-sum, unloaded sample covariance.

## 6. Results

### Conventions (exploratory)

The dataset does not document the element order nor the sign. The order was chosen on the calibration
file, where the transmitter is nearly at broadside, so that the choice is weak; the evaluation file,
not used for it, agrees clearly. Beam power towards the known position (1 = plane wave):

<!-- conventions -->

| element order | calibration file | evaluation file |
|---:|---:|---:|
| columns +1 rows +1 | 0.50 | 0.47 |
| columns +1 rows -1 | 0.29 | 0.37 |
| columns -1 rows +1 | 0.41 | 0.14 |
| columns -1 rows -1 | 0.25 | 0.09 |

<!-- /conventions -->

### Direction of arrival, degrees

<!-- doa -->

| data | median | 90th percentile | mean | RMSE | median signed error | median, north | median, south | median, west | median, east |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| as published | 3.9 | 35.0 | 11.4 | 21.5 | -0.8 | 3.9 | 5.8 | 2.3 | 7.1 |
| calibrated | 5.2 | 40.9 | 12.7 | 23.0 | 0.5 | 4.4 | 6.3 | 2.9 | 12.6 |

<!-- /doa -->

### Phase residual against the known position, degrees RMS over 8 elements

<!-- phase -->

| data | wave model | 10th percentile | median | 90th percentile | median, north | median, south | median, west | median, east |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| as published | plane | 19 | 35 | 81 | 35 | 63 | 23 | 59 |
| as published | spherical | 20 | 36 | 81 | 35 | 63 | 24 | 60 |
| calibrated | plane | 22 | 39 | 83 | 31 | 59 | 36 | 66 |
| calibrated | spherical | 22 | 40 | 83 | 32 | 59 | 36 | 66 |

<!-- /phase -->

Spherical waves do not explain the residual. Multipath, channel offsets and element patterns remain
possible; they were not separated. The second
eigenvalue is only 5 to 10 dB below the first at the evaluation positions (median, by array).

### Phase stability, static transmitter

<!-- stability -->

| quantity (degrees) | value |
|---:|---:|
| 10-packet blocks: RMS deviation, all elements | 8.9 |
| same, by array | 6.3 / 6.4 / 6.9 / 13.7 |
| same, worst element | 34.3 |
| single packets: median absolute deviation | 14.9 |
| single packets: standard deviation | 30.0 |
| single packets: lag-1 correlation (no unit) | -0.00 |

<!-- /stability -->

The cause was not identified (receiver phase noise, timing, 8-bit channel estimates, motion in the room).
The data were published in 2024, two years before the commercial product examined in the
[receiver survey](../hardware/RECEIVER_SURVEY.md): they say nothing certain about that product.

### Beamforming with measured channel vectors, loss in dB

<!-- beam -->

| target (dB) | data | method | median loss (dB) | 90th percentile | 99th |
|---:|---:|---:|---:|---:|---:|
| 10 | as published | OAS | 3.0 | 7.6 | 16.2 |
| 10 | as published | delay-and-sum | 37.3 | 43.1 | 53.4 |
| 10 | as published | eigenspace | 1.4 | 3.7 | 6.6 |
| 10 | as published | noise x10 | 6.1 | 14.1 | 24.9 |
| 10 | as published | noise x30 | 3.6 | 9.4 | 19.5 |
| 10 | as published | relative 1e-2 | 2.8 | 7.4 | 16.3 |
| 10 | as published | sample | 22.1 | 30.6 | 40.7 |
| 10 | calibrated | OAS | 3.2 | 9.5 | 18.7 |
| 10 | calibrated | delay-and-sum | 36.9 | 44.5 | 53.0 |
| 10 | calibrated | eigenspace | 1.3 | 3.6 | 7.2 |
| 10 | calibrated | noise x10 | 6.4 | 16.1 | 24.1 |
| 10 | calibrated | noise x30 | 3.8 | 11.5 | 19.9 |
| 10 | calibrated | relative 1e-2 | 3.1 | 9.3 | 18.3 |
| 10 | calibrated | sample | 22.5 | 31.8 | 42.1 |
| 20 | as published | OAS | 9.0 | 14.8 | 23.7 |
| 20 | as published | delay-and-sum | 37.3 | 43.1 | 53.4 |
| 20 | as published | eigenspace | 7.0 | 12.1 | 18.1 |
| 20 | as published | noise x10 | 21.6 | 31.2 | 41.8 |
| 20 | as published | noise x30 | 14.4 | 23.2 | 34.0 |
| 20 | as published | relative 1e-2 | 9.7 | 16.0 | 25.9 |
| 20 | as published | sample | 40.1 | 48.9 | 58.5 |
| 20 | calibrated | OAS | 9.3 | 16.4 | 24.6 |
| 20 | calibrated | delay-and-sum | 36.9 | 44.5 | 53.0 |
| 20 | calibrated | eigenspace | 6.8 | 12.5 | 20.5 |
| 20 | calibrated | noise x10 | 22.0 | 32.8 | 43.1 |
| 20 | calibrated | noise x30 | 14.7 | 25.2 | 33.3 |
| 20 | calibrated | relative 1e-2 | 10.0 | 17.7 | 26.1 |
| 20 | calibrated | sample | 40.2 | 48.4 | 58.6 |

<!-- /beam -->

Less loading is worse here in every case: noise × 10 < noise × 30 < relative 1e-2, which is the
largest loading of the three in these scenes: with 40 dB of interference it is about 100 times the noise.
This accident of scale protects it from mismatch. Study 1 measured the other side of
that compromise.

## 7. Limitations and conclusions

Limitations: one room, one evaluation trajectory (the 2000 trials reuse 563 blocks and are not
independent, so no confidence interval is claimed); vectors that include the jitter of the data
and an average over 36.6 MHz (a narrowband system would see other mismatches); synthetic waveforms and
noise; a Wi-Fi channel sounder rather than raw samples; only rows of 4 elements for beamforming; the look
direction is geometric, not estimated; the evaluation angles of the arrays differ.

| Decision | Reason |
|---|---|
| **Do not** change the default loading to noise × 10 | it would have been worse on the only measured data available |
| Study the choice of loading against the expected mismatch, not against simulated pointing errors only | the two studies disagree because their mismatches differ |
| Eigenspace projection is the first candidate for a robust mode | best on measured data; already better than noise loading for strong targets in study 1 |
| Estimate steering vectors from data before adapting | 35° residual makes any geometric model insufficient indoors |
| Calibrate with conducted signals or in free space, never from one indoor position | H5.2 |
| Use medians and tails for DOA claims | 3.9° and 35° are both true |

## Reference

- F. Euchner, S. ten Brink, "CSI Dataset espargos-0001: Four antenna arrays in indoor lab room", DaRUS,
  2024, [doi:10.18419/DARUS-4352](https://doi.org/10.18419/DARUS-4352), CC BY 4.0.
