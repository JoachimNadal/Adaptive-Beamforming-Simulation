# Jetson: GPU Acceleration Notes

Not measured on a Jetson. GPU numbers are from a desktop RTX 2080 Ti with CuPy 14.2.0, CPU
numbers from the i7-9700K in the same PC.

## Is a GPU useful here?

For one narrowband beam, no: one 8×8 MVDR solve takes 0.6 µs on a CPU core. It becomes useful when
many independent problems run together: subbands of a wideband signal, many beams, many ranges.
`batched_mvdr` solves a whole batch in one call.

8 antennas, 128 snapshots per subband, transfers excluded:

| Subbands | NumPy (ms) | CuPy (ms) | Ratio |
|---:|---:|---:|---:|
| 64 | 1.95 | 2.92 | 0.7 |
| 256 | 6.69 | 3.36 | 2.0 |
| 1024 | 23.4 | 2.76 | 8.5 |
| 4096 | 99.6 | 5.59 | 17.8 |

Break-even near 100–250 subbands on that machine. A Jetson has a much smaller GPU but shares
memory with the CPU, so the break-even must be measured again:

```bash
python -m embedded.jetson.orin_pipeline --backend numpy --subbands 1024
python -m embedded.jetson.orin_pipeline --backend cupy  --subbands 1024
```

GPU and CPU results agree to 2e-16 in double precision.

## Wideband processing

`channelize` splits IQ into subbands with a windowed FFT and `subband_steering` uses the true RF
frequency of each one. With a single steering vector, 16 elements, 400 MHz of bandwidth at
2.4 GHz and a 50° steering angle lose 4.1 dB at the band edge (tested against the Dirichlet
kernel).

Limits of the current code: analysis only, no synthesis filter bank; the Hann window leaks
between neighbouring subbands; no overlap-save of the weights.

## Design rules

| Rule | Reason |
|---|---|
| Batch everything; never loop over subbands in Python | each call costs tens of microseconds |
| `complex64` | half the memory traffic; sufficient up to 60 dB INR with loading |
| Keep IQ on the GPU from capture to output | copies dominate at high rates |
| Fix the batch size | avoids allocations and plan creation |
| Synchronise before timing | CuPy calls are asynchronous |
| Keep control decisions on the CPU | order estimation and status logic branch too much |

## Classifier

The CNN has 23 910 parameters and takes about 3 ms on one CPU thread of the development PC: a GPU
is not needed for it.
