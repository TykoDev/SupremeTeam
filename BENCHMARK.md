# Benchmark and review scores — 2026-10-25

Measured the changed orchestration controls with Python 3.13.5 on Linux. Baseline:
`db059745ba1df235bf2c0ebaf2017cd24c7f13de` (a clean archive captured before editing).
The run used local disposable fixtures, with no production target or host configuration changes.

## Affected verification

831 distinct test cases were selected for the changed gate, contract, manifest,
guard and audit surfaces: 823 executed, 8 skipped, no unresolved failures.
Unchanged catalog suites were carried rather than rerun.

| Affected surface | Tests | Skipped | Result |
| --- | ---: | ---: | --- |
| Gate engine, all boundary types and revision cycles | 342 | 6 | Pass |
| Related orchestration, pipeline, documentation and save contracts | 174 | 1 | Pass after focused correction |
| Manifest and package validators | 125 | 1 | Pass |
| Gate-related guard and watcher checks | 178 | 0 | Pass |
| Saved-run audit, including scoped follow-ups | 12 | 0 | Pass |

The first contract run found one stale documentation-phrase assertion. The
wording was corrected and its 11-test class passed; a later 90-test pass covered
the changed contract/documentation surfaces. The final gate regression includes
the additional drift, persistence and table-citation cases. Follow-up executions
are not added to the distinct-case count. Skips are platform/dependency conditions
reported by unittest, not failed checks.

Runtime readiness, manifest validation and package validation passed. Ruff
0.16.9 is clean on the changed Python surfaces. Ten of ten declared boundaries
accept their well-formed fixture packages (`BoundarySatisfiabilityTests`).

## Before/after behavior

| Scenario | Baseline | Changed implementation |
| --- | --- | --- |
| Third consecutive valid REVISE | Returns another REVISE | Writes ESCALATE to user, holds boundary, exits 1 |
| Major finding missing focused verification | Accepted | Rejected before persisting judgment or cycle |
| D-999 appears only in prose, outside Intake tables | Accepted as a decision citation | Rejected; citations must identify table rows |

Additional regressions cover all four Gatekeeper identities, resume without
`--prior`, changed submission/output filenames, duplicate retries, same-revision
fingerprint drift, phase/cross-stage shared budgets, user holds, explicit reopen,
corrupt/lost history and mechanical pre-check protection. These are deterministic
scenarios, not live-model task evaluations.

## Paired local timings

Warm-up: 5 discarded iterations per arm; pilot: 7 paired iterations. Pilot
relative IQR was below 15%, so every workload used 30 paired samples, alternating
the baseline/candidate execution order. The filesystem cache was warm. The report
includes medians, p95/p99, IQRs and a 95% bootstrap interval (2,000 resamples) for
the median paired percentage change. The declared practical budget was 20%.

| Workload | Baseline median ms | Changed median ms | Baseline / changed p95 ms | Baseline / changed p99 ms | Paired change, 95% CI |
| --- | ---: | ---: | ---: | ---: | --- |
| mechanical_gate_same_package | 57.676 | 58.620 | 60.695 / 61.489 | 61.198 / 62.178 | +0.77% [-0.69%, +3.20%] |
| approved_judgment_same_package | 59.056 | 61.745 | 63.971 / 71.873 | 66.157 / 72.239 | +6.27% [+4.01%, +8.28%] |
| full_audit_same_scope | 59.161 | 59.057 | 65.142 / 62.763 | 67.738 / 87.269 | +0.30% [-1.54%, +1.91%] |
| one_changed_artifact_followup | 57.433 | 0.281 | 59.428 / 0.368 | 60.983 / 0.400 | -99.51% [-99.54%, -99.48%] |

The changed-artifact follow-up is **204.6× faster in this fixture**. The
baseline scans 32 runs, 64 phases and 512 artifact hashes; the scoped candidate
scans 1 run, 1 phase and 1 artifact hash. Both find the same changed-artifact
defect. This measures the reduction in work from the new scope selection; it
does not claim a 204× speedup for the same full audit. The equivalent full-audit
workload is effectively unchanged. Durable approval adds about 2.7 ms at the
median for Intake validation, locking and atomic history persistence. Its paired
overhead is measurable but remains inside the declared practical budget.

The percentage column summarizes individual pairs; it need not equal the ratio
of the two independently summarized medians. P99 with 30 samples is descriptive,
not an SLA estimate. Shared-VM load was not externally controlled. Samples were
captured serially after the regression jobs completed; a preliminary run that
overlapped tests was discarded. Final report/prose updates do not change the
measured algorithm.

Load ceiling: concurrency 1, at most 100 CLI operations/s or 10,000 audit
operations/s, 180 seconds total, less than 8 MiB generated fixture data. Abort
on a failed command, inconsistent affected-artifact findings, ceiling breach or
free disk below 128 MiB. The valid sample run completed in 17.6 seconds,
with no abort; temporary fixtures were removed and the restore register was
empty because no host settings or services were changed.

Raw samples, environment fingerprint, exact workload definitions, plan and
before/after scenario results:
[benchmark JSON](docs/reviews/review-orchestration-2026-10-25.json).

## Four-Gatekeeper rubric

| Package | Score |
| --- | ---: |
| Gatekeeper Admiral | 96/100 |
| Gatekeeper Design | 97/100 |
| Gatekeeper Build | 97/100 |
| Gatekeeper Code | 97/100 |

Mean: **96.75/100**. The reviewer applied all ten dimensions of the repository
rubric to the four changed Gatekeeper packages. Remaining deductions are existing
inline reference bulk and one voice inconsistency. There is no measured baseline
rubric score, no claimed score delta and no claim of 100/100 SHIP. No unresolved
change-focused correctness blocker was found. This is a score for these four
packages, not for all 53 skills or a task-success percentage.

[Full scorecards and cited deductions](docs/reviews/gatekeeper-rubric-2026-10-25.md),
[metrics](docs/reviews/gatekeeper-rubric-2026-10-25.metrics.json), and
[resolved resource pointers](docs/reviews/gatekeeper-rubric-2026-10-25.links.md).

## Reproduce affected checks

Run from a checkout with Python 3.13 or newer; `python` below names that interpreter.

```bash
python -m unittest discover -s skills/harness/gatekeeper -p "test_*.py"
PYTHONPATH=skills/validation:skills/scripts python -m unittest test_orchestration test_pipeline_contracts test_pipeline_workflows test_docs_inventory test_contract_mirrors test_save_contracts test_catalog_contracts test_save_prose test_stdlib_only
PYTHONPATH=skills/scripts python -m unittest test_validate_manifests test_package_check
PYTHONPATH=skills/harness/hooks:skills/scripts python -m unittest test_guard_harness_files test_guard_rules test_gate_watch
python -m unittest discover -s tools/run-audit/tests -p "test_run_audit.py"
python skills/scripts/check_runtime.py
python skills/scripts/validate_manifests.py
python skills/scripts/package_check.py --root .
```

To reproduce the timing workload, create the identical schema-2 flat design
package from `DesignPackage` in `test_gate_judgment.py` in two disposable
directories. Time each checkout's `check.py` subprocess with and without a valid
APPROVED `--judgment ... --verdict-out ...`. For audit timing, construct 32 saved
runs with build/review phases and eight hashed Markdown artifacts per phase;
change only `run-00/build/changed-0.md`. Time `build_model(root)` in each version,
then compare baseline full audit with changed `build_model(root, ["run-00"],
["build"], artifacts=["changed-0.md"])`. Apply the warmup, pilot, pairing, sample
counts and limits above; retain all raw timings.

## Not measured

Paid trigger-routing, live host registration, end-to-end model task success,
actual hook firing on another host, and unchanged whole-catalog suites. These
results do not claim those evaluations passed.
