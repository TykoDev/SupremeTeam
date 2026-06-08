---
name: benchmark
description: >-
  Measures comparative performance or workflow speed and highlights meaningful
  regressions with repeatable evidence. Use when the user asks to benchmark this
  change, compare performance, measure the regression, or time the workflow — even
  when they only ask "is this faster?". Focuses on quantitative performance
  measurement; defers functional product testing to `testing-and-qa/qa` and
  report-only defect testing to `testing-and-qa/qa-only`.
version: 1.0.0
---


# Benchmark

## Purpose

Measures comparative performance or workflow speed and highlights meaningful regressions with repeatable evidence.

## Use This Skill When

Use this skill for **quantitative performance measurement** — comparing speed with repeatable evidence:

- "benchmark this change" / "compare performance" — measure before/after with a repeatable method
- "measure the regression" — quantify and isolate a performance regression
- "time the workflow" — capture workflow timing under controlled conditions

Route elsewhere for functional product testing with fixes (`testing-and-qa/qa`) or test-and-report-only defect hunting (`testing-and-qa/qa-only`).

## Inputs

- Baseline version, workload definition, and the performance metrics to compare.
- Environment specification including hardware, concurrency, warm-up requirements, and cache state.
- Regression threshold or performance budget that defines a meaningful change.

## Outputs

- Benchmark report with baseline comparison, confidence intervals, variance notes, and sample sizes.
- Regression analysis identifying which code paths, workflows, or resources account for meaningful changes.
- Next-action recommendation based on whether regressions are confirmed, noise, or within budget.

## Workflow

1. Define the baseline, workload, environment, and performance metrics before capturing any benchmark result. Pin software versions, fix hardware or VM allocation, and quiesce background load so environment variance does not contaminate the signal.
2. Choose sample size deliberately: run a short pilot (5–10 iterations) to observe variance, then calculate how many runs are needed for a stable median — typically 30+ for wall-clock timings and more for high-variance systems. Always include a warm-up phase (at least 3–5 discarded iterations) before collecting samples so cold-start effects stay out of the main dataset.
3. Report median and tail percentiles (p95, p99) rather than mean alone; compute a simple confidence band (e.g., ±1 SD or IQR) and record it alongside the point estimates. Separate meaningful regressions from measurement noise — only label a result a regression when it clears the variance boundary with the current sample size.
4. Return a benchmark report with baseline comparison, median/p95/p99 columns, confidence band, and the next performance action worth taking. See `references/workflow.md` for the full decision rules and `references/examples.md` for a sample report structure.

## Required Contracts

- **Before/After Evidence**: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Input validation**: Validate that the workload definition, baseline reference, and environment specification are present and coherent before executing any benchmark run. Refuse to proceed if inputs are ambiguous or contradictory.
- **Production safety**: Never run a load-intensive or resource-intensive benchmark against a production environment without explicit owner authorization. Require a named approver and a confirmed non-production target before starting. Treat sensitive performance data (e.g., throughput figures revealing business load) with the same care as any internal metric.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- None required beyond the active task surface.

## Review Expectations

- Ground every performance claim in repeatable measurements with variance and sample-size data — not in single runs.
- Separate meaningful regressions from measurement noise so the caller can prioritize with confidence.
- Shape the report so downstream performance decisions can reference the data without re-running the benchmark.

## Skip Rule

Skip only when the requested surface, tool, or environment does not exist and a safe fallback is unavailable.

## Failure Modes

| Scenario | Response |
| --- | --- |
| There is no trustworthy baseline or previous sample to compare against | Capture the current run as a baseline candidate and avoid labeling anything a regression yet. |
| The baseline version is unavailable or the build is not reproducible | Stop, report the missing artifact, and request a reproducible baseline before proceeding — do not substitute an approximate baseline without stating the substitution explicitly. |
| The environment is too noisy to distinguish signal from measurement variance | Record the instability, increase controls or sample size if possible, and do not overstate the result. |
| The compared workloads are not truly equivalent | Stop the comparison, restate the mismatch, and rebuild the benchmark so the scenarios align. |
| A measured slowdown is below the confidence threshold for a meaningful regression | Report it as watchlist noise rather than a confirmed performance problem. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Do not create or manage `_phase-state.md` — that is the delegating orchestrator's responsibility.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed operating sequence and decision rules.
- `references/examples.md` for concrete request patterns and response shapes.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
