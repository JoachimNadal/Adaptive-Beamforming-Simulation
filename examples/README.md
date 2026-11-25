# examples

Install once with `pip install -r requirements.txt`, then run any file. All use fixed seeds and
run without a display when `MPLBACKEND=Agg`.

| Demo | Shows |
|---|---|
| `run_steering_vector_demo.py` | phases across the array |
| `run_delay_and_sum_demo.py` | conventional beam |
| `run_null_steering_demo.py` | deterministic null |
| `run_multi_source_demo.py` | one snapshot of two sources |
| `run_covariance_demo.py` | covariance and eigenvalues |
| `run_spatiotemporal_demo.py` | IQ against time (animation) |
| `run_mvdr_demo.py` | MVDR, and its failure with coherent sources |
| `run_mvdr_from_timeseries_demo.py` | MVDR from IQ |
| `run_lms_demo.py`, `run_rls_demo.py` | supervised adaptation |
| `run_music_demo.py` | spectra, root-MUSIC, ESPRIT, Cramér–Rao bound |
| `run_realtime_beam_scan.py` | beam scan animation, `--save file.gif` |
| `run_full_pipeline.py` | calibration and adaptive reception, end to end |
| `run_ai_detection.py` | detection, direction and classification |
