# Beamforming Theory

## Introduction

Beamforming is a signal processing technique used with antenna arrays to:

- enhance signals coming from a desired direction,
- attenuate interference,
- improve signal-to-noise ratio (SNR),
- increase spatial selectivity.

Beamforming is widely used in:

- radar systems,
- wireless communications,
- satellite communications,
- passive RF sensing,
- 5G/6G networks,
- embedded RF systems.

---

# Antenna Arrays

A beamforming system uses multiple antennas arranged in a known geometry.

Typical geometries:

- Linear array
- Circular array
- Planar array

Each antenna receives the same signal with:

- different phase,
- different delay,
- different amplitude.

---

# Steering Vector

The steering vector models how a signal arrives at the antenna array.

For a uniform linear array:

$$
\mathbf{a}(\theta)=
\begin{bmatrix}
1 \\
e^{-jkd\sin(\theta)} \\
e^{-j2kd\sin(\theta)} \\
\vdots
\end{bmatrix}
$$

Where:

$$
\theta = \text{signal angle}
$$

$$
d = \text{antenna spacing}
$$

$$
k = \frac{2\pi}{\lambda}
$$

---

# Delay-and-Sum Beamforming

The simplest beamforming technique.

Signals are delayed and summed coherently.

$$
y(t)=\sum_{n=1}^{N} w_n x_n(t)
$$

Advantages:

- simple,
- low computational cost.

Limitations:

- poor interference rejection,
- limited adaptability.

---

# Adaptive Beamforming

Adaptive beamforming adjusts antenna weights dynamically.

Goals:

- maximize desired signal,
- suppress interference,
- optimize SNR.

Common algorithms:

- LMS
- RLS
- MVDR
- LCMV

---

# MVDR Beamforming

The MVDR beamformer minimizes interference while preserving the desired signal.

$$
\mathbf{w}_{MVDR} =
\frac{\mathbf{R}^{-1}\mathbf{a}(\theta)}
{\mathbf{a}^H(\theta)\mathbf{R}^{-1}\mathbf{a}(\theta)}
$$

Where:

- \( \mathbf{R} \) = covariance matrix
- \( \mathbf{a}(\theta) \) = steering vector

---

# Null Steering

Null steering creates spatial nulls toward interference sources.

This reduces received interference power while preserving useful signals.

Applications:

- interference mitigation,
- resilient communications,
- passive RF sensing.

---

# Applications

Beamforming is used in:

- passive RF analysis,
- radar,
- direction finding,
- resilient communication systems,
- embedded DSP systems.
