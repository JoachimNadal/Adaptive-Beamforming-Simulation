# simulations — models and algorithms

| Folder | Content |
|---|---|
| `antenna_array/` | `LinearArray`, `CircularArray`, common `AntennaArray` interface |
| `beamforming/` | Delay-and-Sum, null steering, MVDR, LCMV, LMS, NLMS, RLS |
| `channels/` | noise, fading, multipath, interference waveforms |
| `doa/` | Bartlett, Capon, MUSIC, root-MUSIC, ESPRIT, MDL/AIC, Cramér–Rao bound, peak search |
| `scenarios/` | snapshot generators with ground truth, tracking, interference detection |
| `plot_style.py` | shared figure style |

Angles are passed with `unite="deg"` or `"rad"` (`deg` is the default of beamformers and
generators, `rad` of array objects). Every random function takes `rng`: a seed or a
`numpy.random.Generator`. See the example in the [main README](../README.md#example).
