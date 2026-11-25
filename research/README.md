# research — Phase 2

R&D built on the frozen baseline `v1.0.0-phase1`. Nothing here modifies it: CI runs
`python research/check_baseline.py`, which fails if a baseline file differs from the tag.

| Study | Report | State |
|---|---|---|
| Hypotheses | [HYPOTHESES.md](HYPOTHESES.md) | committed before the experiments |
| 1 Covariance estimation | [covariance/REPORT.md](covariance/REPORT.md) | done |
| 2 Unknown waveforms | [open_set/REPORT.md](open_set/REPORT.md) | done |
| 3 C port | [c_port/REPORT.md](c_port/REPORT.md) | done |
| 4 Sparse arrays | `sparse/REPORT.md` | planned |
| Receiver survey | `hardware/RECEIVER_SURVEY.md` | planned |

## Method

Every study has the same seven parts: theory, hypothesis, reproducible experiment, metrics, baseline
comparison, results with limitations, conclusions.

Rules:

1. Hypotheses carry a numeric refutation criterion and are committed first.
2. Every experiment is seeded and writes its numbers to a JSON file next to the report, with the
   environment and the commit. Tables in reports are generated from that file.
3. Methods are compared on the **same** random scenes (paired trials) and scored against the true
   scene.
4. Uncertainty is reported: bootstrap 95 % intervals, or the number of trials for proportions.
5. Refuted hypotheses stay in the report.
6. Simulation, execution on a PC, and physical validation are never mixed.
