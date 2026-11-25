# scripts

Run from the repository root.

| Script | Purpose | Time on an i7-9700K |
|---|---|---:|
| `generate_figures.py` | every figure of the documentation | 15 s |
| `hardware_error_budget.py` | tables of `docs/hardware/error_budget_results.md` | < 1 min |
| `check_course_errata.py` | reproduces `docs/theory/course_errata.md` | seconds |
| `mutation_check.py` | injects known bugs and checks that tests fail | minutes |
