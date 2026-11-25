# dsp — array-processing kernels

Pure NumPy functions, no plotting, no randomness. They are the reference for the C core in
`embedded/core`.

| File | Content |
|---|---|
| `steering.py` | the **only** definition of the phase convention; steering vectors and derivatives |
| `covariance_matrix.py` | sample and recursive covariance, loading, forward-backward, spatial smoothing |
| `adaptive_weights.py` | DAS, MVDR, LCMV, null steering; LMS, NLMS, RLS updates |
| `calibration.py` | per-channel gain/phase estimation and correction |
| `signal_metrics.py` | SINR, optimum SINR, white noise gain, null depth, beamwidth, sidelobes, EVM |
| `fft.py` | windows, STFT, Welch PSD |
| `filters.py` | channel-coherent FIR, decimation, frequency shift, DC removal |

Conventions: [docs/theory/beamforming.md](../docs/theory/beamforming.md#conventions).
