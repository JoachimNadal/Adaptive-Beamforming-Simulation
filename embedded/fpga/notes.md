# FPGA Notes

Design notes only. **No HDL exists and nothing was synthesised.** Operation counts are exact;
resource mapping depends on the device.

## Partition

| Function | Rate | Where | Why |
|---|---|---|---|
| Channel filter, decimation | sample | fabric | regular, parallel |
| Calibration (complex gain per channel) | sample | fabric | one complex multiplier per channel |
| Weight application $\mathbf w^H\mathbf x$ | sample | fabric | N complex multipliers and an adder tree |
| Covariance accumulation | sample | fabric | $N(N+1)/2$ complex MAC |
| Weight computation | ≈100 Hz | CPU, with `embedded/core` | irregular, float32, rare |
| Order, DOA, status | ≈10 Hz | CPU | branching |

This split keeps every matrix solve out of the fabric and reuses the tested C code.

## Multipliers

A complex product needs 3 real multipliers (with pre-adders) or 4. With one sample per clock
(no time sharing), 3 per product:

| N | Calibration | Weights | Covariance, N(N+1)/2 | Total |
|---:|---:|---:|---:|---:|
| 4 | 12 | 12 | 30 | 54 |
| 8 | 24 | 24 | 108 | 156 |
| 16 | 48 | 48 | 408 | 504 |

When the clock is $M$ times the sample rate, divide by $M$: at 10 MS/s and 100 MHz, the 16-channel
case fits in about 51 multipliers. Diagonal covariance terms are real and cheaper; they are
counted as complex here.

## Word lengths

| Signal | Suggested format | Reason |
|---|---|---|
| ADC samples | 12 to 16 bits | [error budget](../../docs/hardware/error_budget_results.md): 10 bits for 40 dB INR |
| Calibration gains | 16 bits, 2 integer bits | 1° resolution needs 7 bits with sign; margin for gain |
| Weights | 16 to 18 bits | $\lvert w_m\rvert\le1$ in practice with loading; check overflow of the adder tree |
| Covariance accumulator | 2·16 + log2(K) + 1 = 41 bits for K=256 | full precision, no rounding |

A fixed-point study (quantised weights, accumulator truncation) is a Phase 2 item; the formats
above are bounds, not results.

## Interfaces

- Weight registers double-buffered, swapped on a block boundary: a partial update would point the
  beam nowhere for a few samples.
- Covariance read-out through DMA, one triangle.
- Overflow and lock flags latched per block and sent in the ABF1 header.
- ABF1 framing in fabric or in software; the header is 64-byte aligned for this purpose.

## Verification strategy

1. Generate stimulus and expected output with the Python reference.
2. Bit-accurate fixed-point model in Python before writing HDL.
3. HDL simulation against the model, sample by sample.
4. Hardware-in-the-loop with recorded ABF1 files.
