# Hypotheses

Written and committed **before** the corresponding experiments were run, so that they can be
refuted. Verdicts are added afterwards in each study report; the text below is not edited except to
add a link to the verdict.

Prior knowledge, disclosed: the probes of [docs/RND_ROADMAP.md](../docs/RND_ROADMAP.md) were known
when these were written (loading strategies at K=256; Mahalanobis on two unseen families; one sparse
scene at K=4000). Hypotheses marked † extend a probe and are therefore less blind than the others.

Loss means SINR in dB below the optimum of the true scene, averaged over trials on the linear ratio.

## Priority 1 — covariance estimation

| ID | Hypothesis | Refuted if |
|---|---|---|
| H1.1 † | Noise-referenced loading (10 × estimated noise) keeps the mean loss ≤ 1 dB for N ∈ {4, 8}, K ≥ 4N, INR 0–60 dB, no pointing error, 0 dB target in the data | any such point exceeds 1 dB |
| H1.2 | Ledoit–Wolf and OAS minimise Frobenius error, not SINR: their loss grows with INR, and at 60 dB INR with K = 4N both exceed noise-referenced loading by ≥ 1 dB | either is within 1 dB |
| H1.3 † | Covariance reconstruction beats every loading method by ≥ 0.5 dB with a 2° pointing error and a 10 dB target, but loses that advantage when channel phase errors exceed 5° RMS | it does not win at 0°, or still wins by ≥ 0.5 dB at 10° |
| H1.4 | With Student-t noise (ν = 3) or 5 % impulsive snapshots, regularised Tyler gains ≥ 1 dB over the sample covariance with the same loading, and costs ≤ 0.5 dB in Gaussian noise | either part fails |
| H1.5 | Reconstruction costs ≥ 5 × the loaded sample covariance in computing time; noise-referenced loading ≤ 3 × | measured otherwise |
| H1.6 | On nominal scenes, the best estimator without any DOA step is within 0.5 dB of the Phase 1 pipeline, which uses explicit nulls | worse by more than 0.5 dB |

## Priority 2 — unknown waveforms

| ID | Hypothesis | Refuted if |
|---|---|---|
| H2.1 † | Distances in the CNN embedding (Mahalanobis or k-NN) reach a mean AUROC ≥ 0.90 over at least eight unseen synthetic families; softmax confidence stays below 0.75 | either part fails |
| H2.2 | On real recordings, the false-alarm rate on noise-only segments exceeds 4 × the 5 % design value without recalibration | it stays below 20 % |
| H2.3 | Hand-crafted features lose less AUROC than the CNN between synthetic and real unseen signals | CNN loses less |
| H2.4 | Leaving one training class out gives AUROC < 0.90 for at least one class with every detector | some detector is ≥ 0.90 for all classes |
| H2.5 | Receiver impairments (IQ imbalance, DC, phase noise, quantisation, multipath) raise the false-alarm rate on *known* classes above 10 % at a 5 % design point | it stays below 10 % |

## Priority 3 — C port

| ID | Hypothesis | Refuted if |
|---|---|---|
| H3.1 | On identical input, the float32 C pipeline is within 0.1 dB of the Python pipeline in output SINR for ≥ 99 % of blocks, on nominal scenes | below 99 % |
| H3.2 | It is ≥ 50 × faster per block at N = 4, K = 256 on the same PC | less than 50 × |
| H3.3 | It needs ≤ 16 KiB of state and ≤ 16 KiB of stack for N = 16, with no heap | more |
| H3.4 | float32 loses ≤ 0.1 dB against float64 up to 60 dB INR | more |

## Priority 4 — sparse arrays

| ID | Hypothesis | Refuted if |
|---|---|---|
| H4.1 † | Five sources with four antennas: success (all errors < 3°) ≥ 90 % at 10 dB needs at least several hundred snapshots; it is < 50 % at K = 100 | success at K = 100 is ≥ 50 % |
| H4.2 | With more sources than antennas the error saturates with SNR: from 20 to 40 dB it improves by < 10 % | improves more |
| H4.3 | Correlation between two sources of \|ρ\| ≥ 0.5 brings success below 50 % | stays above |
| H4.4 | 5° RMS channel phase error brings success below 90 % | stays above |
| H4.5 | MVDR on the minimum-redundancy array gains ≥ 3 dB over the uniform array for an interferer 5–12° from the target, and loses < 1 dB on average beyond 15° | either part fails |
| H4.6 | A 10 dB spread between source powers brings the weakest-source success below 90 % at K = 1000 | stays above |

## Priority 1, second round

Registered **after** the first round of results (which showed that explicit nulls and reconstruction
collapse with 1° of channel error) and **before** the methods below were implemented or run.

| ID | Hypothesis | Refuted if |
|---|---|---|
| H1.7 | The minimum-norm eigencanceler, which nulls the *measured* interference subspace, keeps the loss ≤ 1 dB for channel errors up to 10° RMS (N ∈ {4, 8}, K = 256, INR 40 dB, 10 dB target, pointing 0 and 2°) | any of these points exceeds 1 dB |
| H1.8 | Keeping the Phase 1 pipeline but replacing relative by noise-referenced loading reduces its loss at 1–5° RMS by ≥ 3 dB | smaller reduction at any of 1, 2, 5° |
| H1.9 | The reduced-rank sidelobe canceller (principal components of the blocked covariance) needs about twice the number of *interferers* in snapshots, not twice the number of antennas: ≤ 1.5 dB loss at K = N, INR 40 dB, 0 dB target, N ∈ {4, 8} | exceeds 1.5 dB |
| H1.10 | No single method is within 1 dB of the best one in every experiment | one is |

## Priority 1, held-out validation

A hybrid was designed after looking at rounds 1 and 2 (eigenspace projection; eigencanceler when MDL
saturates). Choosing it on the same scenes would be selection bias, so it is judged on **new random
scenes**: N ∈ {4, 8}, 1 to N − 2 interferers at random angles at least 12° from the target, INR
0–60 dB, SNR −5 to 10 dB, pointing error ±2°, channel errors 0–5° RMS, K from 4N to 256, Gaussian or
impulsive noise. 2000 scenes, seeds never used before. Registered before the run.

| ID | Hypothesis | Refuted if |
|---|---|---|
| H1.11 | The hybrid has the smallest 90th-percentile loss of all methods and it is ≤ 3 dB | another method has a smaller one, or it exceeds 3 dB |
| H1.12 | The Phase 1 pipeline has a 90th-percentile loss ≥ 5 dB on these scenes | less than 5 dB |

## Priority 1, loading factor

H1.11 was refuted: plain noise-referenced loading beats the hybrid. Its factor (10) was never tuned.
It is now tuned on a **design set** (1000 scenes, own seeds) and judged on a **second held-out set**
(2000 scenes, own seeds). Registered before both runs.

| ID | Hypothesis | Refuted if |
|---|---|---|
| H1.13 | A factor chosen on the design set (with or without derivative constraint) reduces the 90th-percentile loss by ≥ 1 dB against factor 10 on the second held-out set | smaller reduction |

## Priority 3, second round

Registered after the first C results (float32 miscounts sources from 60 dB INR because the noise
eigenvalues drown in the rounding error of the covariance) and before the prototype was written.

| ID | Hypothesis | Refuted if |
|---|---|---|
| H3.5 | Square-root processing in float32 (QR of the data instead of a covariance, SVD of the triangular factor) counts the sources correctly in ≥ 99 % of blocks and loses ≤ 0.1 dB against float64, up to 80 dB INR, for N ∈ {4, 8, 16} | any of these points fails |
