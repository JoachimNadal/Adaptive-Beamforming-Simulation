# tests

```bash
pip install -e ".[dev]"
pytest                          # everything available on this machine
pytest -m "not ccore"           # without the C core
pytest --cov=dsp --cov=simulations --cov=embedded --cov=ai --cov=dashboard
python scripts/mutation_check.py
```

| File | Checks |
|---|---|
| `test_conventions.py` | same angle for every generator, beamformer and estimator |
| `test_channels.py` | noise power, coherence, fading, multipath, waveforms |
| `test_dsp.py` | kernels against definitions and SciPy; calibration |
| `test_beamformers.py` | optimum SINR, RMB loss, constraints, stability |
| `test_doa.py` | exactness, Cramér–Rao bound, counting, detection, tracking |
| `test_embedded.py` | frames, configuration, sources, pipeline, applications |
| `test_c_core.py` | C core against Python (needs CMake and a compiler) |
| `test_ai.py` | dataset, features, metrics, streaming; CNN if PyTorch is installed |
| `test_examples_and_dashboard.py` | every demo, dashboard |
| `test_documentation.py` | links, anchors, code blocks, no empty file |
| `test_delay_and_sum.py`, `test_lms.py`, `test_mvdr.py`, `test_null_steering.py`, `test_rls.py` | original tests, kept (reformatted only) |

The rule: compare with theory, with another implementation or with the true scene, never with the
algorithm's own output.
