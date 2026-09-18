# Workflow Reference

## Contents

1. QA execution sequence
2. Coverage destination
3. Decision rules
4. Acceptance checklist
5. Collaboration notes

## QA Execution Sequence

0. Resolve the entry mode first and state it: a `### Save Context` block or an active run lock means pipeline mode, which persists to the run's `qa/` phase directory and closes at `qa-review`; neither present means standalone mode, which persists nothing and submits no gate. Every step below is identical in both modes until the close.
1. Define the workflows, environments, and success checkpoints that must be tested. Design test cases with three layers: happy path (expected normal usage), boundary conditions (edge inputs, limits, empty states), and negative/error scenarios (invalid input, missing auth, unavailable dependencies).
2. Run the targeted checks. For each defect, capture: (a) numbered reproduction steps, (b) expected vs. actual behavior, (c) environment details (OS, browser/runtime version, test data), (d) relevant logs or screenshots. Isolate the defect to a minimal reproduction — bisect commits or narrow input conditions — before writing a fix.
3. Apply one atomic fix at a time and retest the touched path plus its closest risk neighbors. Never perform destructive operations or touch production environments without explicit owner approval; if a fix would exceed QA scope, stop and report instead of proceeding.
4. Stop when the surface stabilizes or when a blocker requires escalation. **Stabilized** means: all targeted defects no longer reproduce across at least 3 consecutive clean runs and no new regressions were introduced during the fix cycle.
5. Close according to the mode. In pipeline mode, write the matrix and probe log to the run's `evidence/` destination, assemble the manifest, self-check it with `check.py`, submit at `qa-review`, and return the verdict with the record; `gate-package.md` carries the manifest shape and the `REVISE` mechanics. In standalone mode, return the record inline and state that no package was assembled and no verdict was sought.

## Sample QA Execution Record Entry

| # | Flow | Defect | Severity | Repro steps | Expected | Actual | Fix applied | After-fix result |
|---|------|--------|----------|-------------|----------|--------|-------------|-----------------|
| 1 | Checkout | Submit button disabled after payment error | Major | 1. Add item. 2. Enter invalid card. 3. Dismiss error. | Button re-enables | Button stays disabled | Reset button state on error dismissal (commit abc123) | Pass — 3 consecutive clean runs |

## Coverage Destination

Any targeted check run through the project's test tooling sends its coverage data
and reports to the run, not the project root. Resolve the destination first —
`python skills/scripts/output_paths.py --run-id <run-id> --phase qa --kind coverage --name .coverage --mkdir`,
which is `skillset-saves/runs/<run-id>/qa/evidence/coverage/` — then point
`COVERAGE_FILE` / `--data-file`, `--cov-report=<fmt>:<dest>/...`,
`--coverage.reportsDirectory`, or `--report-dir` + `--temp-dir` at it. Never run
coverage in parallel or per-process mode (`-p`, `--parallel-mode`,
`parallel = True`) unless the same command finishes with `coverage combine` into
that destination, and never loop a coverage run per test file: per-process mode
with nothing combining it is what produced an observed `.coverage` tree of over
three thousand files in under two minutes. When the step ends the project root
holds no `.coverage`, `.coverage.*`, `.coverage/`, `htmlcov/`, or `.nyc_output/`,
and in standalone mode — which persists nothing — that means the surface ends as
it started. A coverage percentage is not evidence; the hashed data file or report
under `evidence/coverage/` is. The per-runner flags are in
`../../build/test-builder/references/workflow.md` § Coverage destination.

## Decision Rules

- Prefer honest coverage over inflated claims that skip missing environments or test accounts.
- Send coverage data and reports to the run's `qa/evidence/coverage/` destination before the runner starts; the project root is never where coverage output lives.
- Keep each fix atomic so rollback and blame remain clear.
- Treat intermittent failures as evidence gaps until the triggering condition is narrow enough to verify.
- Preserve residual risks explicitly when the surface improves but is not fully stable.
- Stabilization requires the targeted defects to not reproduce across at least 3 consecutive runs with no new regressions introduced.
- Never perform destructive or irreversible operations; stop and hand off if a fix exceeds QA scope.
- An unavailable browser, host, or fixture produces a not-run record with its reason; an unavailable check is a data gap, never a pass, and never an outcome inferred from an adjacent layer.
- A second `REVISE` on the same package hits `cycle_cap: 2` and escalates with both packets; it does not start a third cycle.

## Acceptance Checklist

- Tested workflows and environments are named explicitly.
- Every defect has numbered reproduction steps, expected vs. actual, and environment details.
- Every fix has before and after evidence and a minimal reproduction rationale.
- Retest scope is recorded for each change.
- Remaining risks and blockers are visible in the QA record.
- Stabilization criterion is stated and met (or blocker is named).
- The entry mode is stated, and in pipeline mode the package was self-checked before submission and the verdict is reported with the record.

## Contract Notes

The contracts this workflow runs under are stated in `../SKILL.md` § Required Contracts.

## Collaboration Notes

This skill's collaboration surface is stated in `../SKILL.md` § Collaboration Surface.
