# Benchmark and review scores — 2026-10-26, suites re-measured 2026-10-31

The timings and the rubric were measured on 2026-10-26 with 3.13.17 on Linux, after the audit
and hardening pass that followed the review-orchestration change; the suite table was
re-measured on 2026-10-31 (see its section). Baseline for the paired
timings: a `git archive` of the committed tree `a3ef604889749b9da1890f705ebf863d07fa1af7`
(`skills/` and `tools/`); candidate: the working tree. Local disposable fixtures only, no
production target and no host configuration change. The previous record is
[docs/reviews/review-orchestration-2026-10-25.json](docs/reviews/review-orchestration-2026-10-25.json)
with its [scorecard](docs/reviews/gatekeeper-rubric-2026-10-25.md).

## Whole-catalog verification

Re-measured on 2026-10-31 with 3.13.18 on Linux, on the tree this table ships with (after the
ST-AUD-004 to ST-AUD-012 and F-01 to F-07 fixes). The timings and the rubric further down are
the 2026-10-26 measurements and were not re-run.

Each suite was run twice: with PyYAML installed and in a virtual environment without it, the
two variants CI runs. PyYAML is optional, and two whole classes of the validation suite
(`ParserParityTests`, 3 tests, and `TriggerEvalTests`, 7 tests) compare the stdlib reader with
it, so they cannot run without it. unittest counts a class skipped in `setUpClass` as one skip
and leaves its tests out of "Ran", so its own figures (validation: `Ran 268, skipped=1` with
PyYAML, `Ran 258, skipped=3` without) hide how many checks did not execute. The table counts
them: **Tests** is every test the suite collects, **Not run** is how many of those did not
execute in that variant, whether skipped one by one or with their class. Every skip is a
platform or dependency condition, not a failed check.

| Suite | Tests | Not run, with PyYAML | Not run, without PyYAML | Result |
| --- | ---: | ---: | ---: | --- |
| Hooks (`skills/harness/hooks`) | 1114 | 4 | 4 | Pass, both |
| Gatekeeper (`skills/harness/gatekeeper`) | 342 | 1 | 1 | Pass, both |
| Validation (`skills/validation`) | 268 | 1 | 11 | Pass, both |
| Scripts (`skills/scripts`) | 412 | 2 | 7 | Pass, both |
| Taste (`skills/taste`) | 222 | 0 | 0 | Pass, both |
| Installers (`scripts`) | 79 | 0 | 0 | Pass, both |
| Skill-creator (`skills/skill-maker/skill-creator`) | 172 | 0 | 1 | Pass, both |
| Checkout tools (`tools/run-audit`, `tools/rescan-compare`) | 27 | 0 | 0 | Pass, both |

The seven catalog suites hold 2609 tests: 2601 execute with PyYAML and 2585 without it.
`check_runtime.py` reports ready, `validate_manifests.py` reports no error,
`package_check.py --root .` selects 470 files with no violation, and `ruff check .` is clean at
the CI pin (0.16.9), in both variants. On 2026-10-26, three tests failed on the committed tree
before that day's pass (the `ship` version record and the path resolver's `..` handling); all
three pass.

## Behaviour that changed

| Scenario | Committed tree | This tree |
| --- | --- | --- |
| `rm -r`, `mv`, `shutil.rmtree`, `find -delete` or `rsync --delete` aimed at `skillset-saves/runs/<run>/<phase>` | Allowed; the phase's verdict records and `verdict_<boundary>.cycles.json` go with it and the third-REVISE count starts again | Denied by Rule C; the files inside the phase stay the lead's to write or remove by name |
| `rm verdict_<boundary>.cycles.lock` | Allowed | Denied with the verdict records |
| `parallel 'rm src/payments/{}' ::: a` under a frozen boundary | Allowed: the quoted line read as a command named `{}` | Denied as the shell line it is |
| `cat src/payments/list \| xargs -I{} sh -c 'rm {}'` under a frozen boundary | Allowed: the program's write read as a placed write to a file named `{}` | Denied: the placeholder keeps its unresolved standing |
| `tar -xf a.tar -C Plugins` beside a guard record | Denied: an operand with a capital P read as the `-P` mode | Allowed; `-xPf` is still read as the mode |
| A `read_only` record whose `allow` is a string | Every path allowed (the string iterated as characters, `*` among them) | No allowance from it; the writer refuses the record |
| A run manifest inside a run that does not hash `intake/report_grilling.md` | Silent until the gatekeeper's judgment is rejected | The mechanical self-check warns |
| Two different Major findings in the same report slot | `rescan_compare` reports the reports equal | Different: a finding is identified by severity, location and statement |

## Paired local timings

Warm-up: 5 discarded iterations per arm; pilot: 7 paired iterations; then 30 paired samples per
workload, alternating the baseline/candidate order, serial, warm file-system cache. The
percentage is the median of the per-pair changes with a 95% bootstrap interval (2,000 resamples);
the declared practical budget is 20%. Two pilots had a relative IQR above 15% and were kept at 30
samples, which the earlier protocol would have raised to 60; they are marked.

| Workload | Baseline median ms | This tree median ms | Baseline / this tree p95 ms | Baseline / this tree p99 ms | Paired change, 95% CI | Pilot rel. IQR |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| mechanical gate check, same schema-2 package | 123.566 | 120.370 | 169.721 / 149.764 | 190.864 / 159.931 | -0.45% [-7.11%, +6.44%] | 0.17 |
| APPROVED judgment persisted, same package | 127.063 | 125.589 | 168.580 / 149.455 | 185.405 / 168.303 | -2.17% [-5.33%, +3.43%] | 0.07 |
| full saved-run audit (32 runs, 64 phases, 512 hashes) | 113.266 | 122.453 | 167.553 / 176.016 | 184.482 / 183.355 | +8.67% [+2.94%, +16.53%] | 0.09 |
| scoped follow-up, one changed artifact, both trees | 1.223 | 1.421 | 1.816 / 2.356 | 2.594 / 2.550 | +14.04% [+11.04%, +26.49%] | 0.28 |
| guard hook, twelve commands through pre_tool_use.py | 1356.103 | 1357.702 | 1427.308 / 1413.162 | 1502.524 / 1470.431 | +0.04% [-2.99%, +0.88%] | 0.04 |

The two pilots above 15% are the mechanical gate check (0.17) and the scoped follow-up (0.28,
on a workload of about a millisecond).

On this tree alone, the scoped follow-up for one changed artifact runs in
1.315 ms against 109.445 ms for the full audit of the same
fixture: **83× less work in this fixture** (-98.83%
[-98.87%, -98.69%]). Both find the same
changed-artifact defect. This measures the reduction in work from scope selection; it is not a
speed-up of the same full audit.

The full audit costs about nine percent more on this tree: every `artifact_hashes` key is now
normalised and checked for an absolute or climbing path before it is hashed, and a symlinked
run or phase entry is reported instead of skipped. The scoped follow-up gains about 0.2 ms for
the same normalisation of the selector and the keys. Both stay inside the practical budget. The
gate check, the judgment persistence and the guard hook are unchanged within noise: the new
phase-directory rule adds no measurable cost to the twelve-command batch.

Absolute times are not comparable with the 2026-10-25 record, which ran on another host; the
paired percentages are. P95 and p99 with 30 samples are descriptive, not an SLA estimate.
Shared-VM load was not externally controlled. Raw samples, the environment fingerprint, the
plan and the twelve guard decisions of both trees:
[docs/reviews/review-orchestration-2026-10-26.json](docs/reviews/review-orchestration-2026-10-26.json).

## Four-Gatekeeper rubric

| Package | Score |
| --- | ---: |
| Gatekeeper Admiral | 97/100 |
| Gatekeeper Design | 97/100 |
| Gatekeeper Build | 97/100 |
| Gatekeeper Code | 97/100 |

Mean: **97.0/100** (2026-10-25: 96.75). All ten rubric dimensions were applied to the four
packages at version 2.0.1. The one Minor finding of the previous scorecard (a second-person slip
in the admiral gatekeeper's boundary reference) is resolved; the remaining deduction in every
package is the reference material still carried inline in the skill body, which the drift-tested
boundary tables make a deliberate refactor rather than a rewording. No unresolved change-focused
correctness blocker was found. This is a score for these four packages, not for all 53 skills
or a task-success percentage, and there is no claim of 100/100 SHIP.

[Scorecards and the cited deduction](docs/reviews/gatekeeper-rubric-2026-10-26.md) and
[metrics](docs/reviews/gatekeeper-rubric-2026-10-26.metrics.json).

## Reproduce

Run from a checkout with Python 3.13 or newer; `python` names that interpreter. Run the suites
once with PyYAML installed (`python -m pip install pyyaml`) and once without it, as CI does,
because the counts differ (see the table above):

```bash
python -m venv .venv          # a bare environment has no PyYAML
.venv/bin/python -m unittest discover -s skills/validation -p "test_*.py"   # .venv\Scripts\python on Windows
```

unittest's `skipped=` counts a class skipped in `setUpClass` once. To count the tests that did
not run, compare `suite.countTestCases()` of `unittest.TestLoader().discover(...)` with the tests
that executed (`testsRun` minus the skips of single tests).

```bash
python -m unittest discover -s skills/harness/hooks -p "test_*.py"
python -m unittest discover -s skills/harness/gatekeeper -p "test_*.py"
python -m unittest discover -s skills/validation -p "test_*.py"
python -m unittest discover -s skills/scripts -p "test_*.py"
python -m unittest discover -s skills/taste -p "test_*.py"
python -m unittest discover -s scripts -p "test_*.py"
python -m unittest discover -s skills/skill-maker/skill-creator -p "test_*.py"
python -m unittest discover -s tools/run-audit/tests -p "test_*.py"
python -m unittest discover -s tools/rescan-compare/tests -p "test_*.py"
python skills/scripts/check_runtime.py
python skills/scripts/validate_manifests.py
python skills/scripts/package_check.py --root .
```

To reproduce the timings, `git archive HEAD skills tools` into a disposable directory as the
baseline. Gate workloads: the schema-2 design package `DesignPackage` of each tree's own
`skills/harness/gatekeeper/test_gate_judgment.py`, checked by that tree's `check.py` as a
subprocess, mechanically and with a valid APPROVED `--judgment ... --verdict-out ...`. Audit
workload: 32 saved runs with `build` and `review` phases and eight hashed Markdown artifacts
per phase, `run-00/build/changed-0.md` altered; time `build_model(root)` and
`build_model(root, ["run-00"], ["build"], artifacts=["changed-0.md"])` in a subprocess. Guard
workload: the twelve commands listed in the JSON, each sent to `pre_tool_use.py` as the Bash
tool's payload against a populated run. Apply the warm-up, pilot, pairing and sample counts
above and keep every raw timing.

## Not measured

Paid trigger routing, live host registration, end-to-end model task success and actual hook
firing on another host. These results do not claim those evaluations passed.

Routing is the one of these the repository can measure on its own, with a model run that costs
money. `skills/validation/trigger_eval.py` routes the catalog's own trigger corpus (183 queries
from 53 skills: each skill's advertised phrases and the phrases a sibling says belong to it)
against the whole roster, optionally restated by a model in a user's own words first, which is
the only form whose score is worth quoting:

```bash
python skills/validation/trigger_eval.py --pilot --mode both --paraphrase --out pilot.json   # one batch, to price it
python skills/validation/trigger_eval.py --mode both --paraphrase --out routing.json         # the full corpus
```

A pilot on 2026-10-31 (one batch of 15 paraphrased queries, the CLI's default model) cost
$0.40, so the full corpus of 13 batches is about $5. One batch is not a score, and none is
published here until the full corpus has run.
