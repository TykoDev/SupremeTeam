# Benchmark

Measured on 2026-10-22 against the current tree, with Python 3.14.2 and PyYAML 6.0.3
on Windows 10. Only results re-measured on this tree are listed.

| Measure | Result |
|---|---|
| Test suites | 7 of 7 pass: 2,586 tests, 0 failures, 166 skipped |
| Validators | 3 of 3 pass |
| Lint | `ruff check .` clean at the CI pin, ruff 0.16.9 |
| Gate boundaries | 10 of 10 accept a well-formed package |

## Tests

| Suite | Tests | Skipped | Command |
|---|---:|---:|---|
| hooks | 1,084 | 88 | `python -m unittest discover -s skills/harness/hooks -p "test_*.py"` |
| gates | 323 | 9 | `python -m unittest discover -s skills/harness/gatekeeper -p "test_*.py"` |
| validation | 297 | 1 | `python -m unittest discover -s skills/validation -p "test_*.py"` |
| scripts | 410 | 8 | `python -m unittest discover -s skills/scripts -p "test_*.py"` |
| taste | 222 | 4 | `python -m unittest discover -s skills/taste -p "test_*.py"` |
| installers | 79 | 44 | `python -m unittest discover -s scripts -p "test_*.py"` |
| skill_creator | 171 | 12 | `python -m unittest discover -s skills/skill-maker/skill-creator -p "test_*.py"` |

Skips are counted by `unittest`. Nearly all of them need a POSIX host (the bash
installer runs, permission bits, symbolic links, a pseudo-terminal), and CI runs
them on Linux and macOS.

The validators are `check_runtime.py`, `validate_manifests.py` and
`package_check.py --root .` in `skills/scripts/`. The gate-boundary result is
`BoundarySatisfiabilityTests` in `skills/validation/test_pipeline_workflows.py`.

## Not measured

- Skill and doctrine rubric scores. They are model judgements and were not re-run on
  this tree.
- Routing accuracy. It is a paid model run, about $7:
  `python skills/validation/trigger_eval.py --mode both --paraphrase --per-skill 4`.
- Host registration (`python skills/validation/run_eval.py --registration`),
  behaviour after a skill is selected, end-to-end task success, and hook firing on
  a given host.
