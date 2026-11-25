# RF Environment and Interference Models

What the simulated environment contains, how it is calibrated, and where it stops being
realistic. These are receive-side numerical models; nothing here transmits.

## Noise

`simulations/channels/awgn.py` is the only noise source of the project:
$n=\sqrt{\sigma^2/2}\,(n_I+jn_Q)$, so $E\lvert n\rvert^2=\sigma^2$. SNR and INR are per antenna. Before
Phase 1 the noise was twice too strong ([audit D4](../PROJECT_AUDIT.md)).

## Sources

`simulate_array_snapshots` returns a `Scene` holding the snapshots *and* the ground truth, so an
algorithm is always scored against the true scene and not against its own estimate.

| Property | Default | Why it matters |
|---|---|---|
| Waveform | independent circular Gaussian | constant amplitudes would make sources coherent (audit D3) |
| Power | per source, linear | defines SNR/INR |
| `channel_gains` | ones | uncalibrated receivers: $\mathbf x=\mathrm{diag}(\mathbf g)\,\mathbf A\mathbf s+\mathbf n$ |

Coherent sources remain available on purpose (`coherent=True`, multipath) to study the failure
they cause.

## Interference waveforms

`simulations/channels/interference_models.py`, all of unit mean power:

| Waveform | Parameters | Spatial remark |
|---|---|---|
| CW tone | frequency | easiest to null spatially and spectrally |
| Linear chirp | span, period | looks stationary to the covariance if the period is short |
| QPSK | symbol length, offset | communication-like co-channel signal |
| Band-limited noise | bandwidth, centre | no temporal structure: only spatial rejection works |
| Pulsed tone | duty, period | covariance blocks may fall between pulses |

A block-adaptive beamformer is blind to a pulse that starts after the block used to compute the
weights. Reducing the block length or the recursive memory is the only remedy implemented.

## Propagation

| Model | File | Validation |
|---|---|---|
| Rayleigh, Rician | `fading.py` | unit power, $K\to\infty$ limit |
| Clarke Doppler | `fading.py` | autocorrelation against $J_0(2\pi f_D\tau)$ |
| Specular multipath | `multipath.py` | exact fractional delay, rank of the covariance |

Delays are narrowband at RF and exact at baseband. Not modelled: mutual coupling, element
patterns, polarisation, near field, diffuse scattering.

## Suppression: what each stage can do

| Stage | Rejects | Implementation |
|---|---|---|
| FIR channel filter | out-of-band | `dsp/filters.py`, identical for all channels |
| Adaptive beamformer | spatially separated | [adaptive_algorithms.md](adaptive_algorithms.md) |
| Nothing | in-band **and** co-directional | no linear processing can separate it |

`dsp/filters.py` applies the same coefficients to every channel; a test checks that inter-channel
phases are preserved, since any difference would look like a direction.

## SINR accounting

Output SINR is computed from the known scene:
$\mathrm{SINR}=\sigma_s^2\lvert\mathbf w^H\mathbf a\rvert^2/(\mathbf w^H\mathbf R_{i+n}\mathbf w)$, with the steering vectors
*as received*, channel errors included. It is compared with
$\sigma_s^2\,\mathbf a^H\mathbf R_{i+n}^{-1}\mathbf a$.

## Calibration and robustness

| Error | Effect measured in simulation | Counter-measure implemented |
|---|---|---|
| Channel phase 5° RMS | deterministic null −29 dB (N=4) | `dsp/calibration.py`: 0.4° RMS residual at 10 dB SNR, K=1024 |
| Channel phase 10° RMS | −23 dB null; only 0.1 dB MVDR loss (INR 30 dB, SNR 0 dB, loading 1e-2) | adaptive beats deterministic when uncalibrated |
| Pointing 0.5° | 14 dB self-cancellation of a 10 dB target | loading, derivative constraint |
| Clock loss | calibration meaningless | pipeline discards it and stops adapting |
| ADC clipping | corrupted covariance | pipeline skips the block for adaptation |

Full tables: [error budget](../hardware/error_budget_results.md).

## Classification

The [AI chain](../../ai/README.md) labels the waveform after beamforming. It is trained on the
waveforms above only, so it has never seen a real signal.
