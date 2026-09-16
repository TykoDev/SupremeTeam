---
name: benchmark
description: >-
  Measures comparative performance against a pinned baseline on a non-production
  target, separating real regressions from noise with sample sizes, tail
  percentiles, and a confidence band. Use for "benchmark this change", "compare
  performance", "measure the regression", or "time the workflow" — even when the
  request is only "is this faster?". Quantitative measurement only; defers
  functional testing to `qa` and report-only defect hunting to
  `qa-only`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---


# Benchmark

## Purpose

A performance number is a claim about the environment that produced it, and most benchmark disputes are really disputes about that environment. This skill is built around that fact: it pins the environment, declares the load it will impose before imposing it, sizes the sample from observed variance rather than habit, and prints the variance band beside every point estimate — so whether a change is a regression or noise is settled by the data rather than by the direction of the arrow. Every alteration it makes to a host to reduce variance is written down and undone.

## Use This Skill When

Use this skill for **quantitative performance measurement** — comparing speed with repeatable evidence:

- "benchmark this change" / "compare performance" — measure before/after with a repeatable method
- "measure the regression" — quantify and isolate a performance regression
- "time the workflow" — capture workflow timing under controlled conditions

Route elsewhere for functional product testing with fixes (`qa`) or test-and-report-only defect hunting (`qa-only`).

## Inputs

- Baseline version, workload definition, and the performance metrics to compare.
- Environment specification including hardware, concurrency, warm-up requirements, and cache state.
- Regression threshold or performance budget that defines a meaningful change.

## Outputs

- Benchmark report with baseline comparison, confidence intervals, variance notes, and sample sizes.
- Regression analysis identifying which code paths, workflows, or resources account for meaningful changes.
- Next-action recommendation based on whether regressions are confirmed, noise, or within budget.

## Workflow

1. Define the baseline, workload, environment, and performance metrics before capturing any benchmark result. Pin software versions and fix hardware or VM allocation. Declare the **load ceiling** and the **abort condition** in the same step, before the first sample: peak request rate or operations per second, peak concurrency, total wall-clock duration, and the data volume the run will create — plus the observable signal that stops the run mid-sample. A confirmed non-production target is shared infrastructure, not unlimited infrastructure, and a benchmark is the one workload deliberately designed to saturate something.
2. Quiesce background load, recording each change in a **restore register** as it is made — which service was stopped, which setting was changed, and the prior value of each. Closing services, disabling auto-updates, and disabling GC or background compaction all reduce variance, and all of them silently distort the next run and everything else sharing that host if they are left in place.
3. Choose sample size deliberately: run a short pilot (5–10 iterations) to observe variance, then calculate how many runs are needed for a stable median — typically 30+ for wall-clock timings and more for high-variance systems. Always include a warm-up phase (at least 3–5 discarded iterations) before collecting samples so cold-start effects stay out of the main dataset.
4. Report median and tail percentiles (p95, p99) rather than mean alone; compute a simple confidence band (e.g., ±1 SD or IQR) and record it alongside the point estimates. Separate meaningful regressions from measurement noise — only label a result a regression when it clears the variance boundary with the current sample size.
5. Restore every entry in the register in reverse order and confirm each restoration, then return a benchmark report with baseline comparison, median/p95/p99 columns, confidence band, sample size, environment fingerprint, the declared ceiling and whether the run stayed inside it, and the next performance action worth taking. Report the restoration alongside the numbers: a host left quiesced is a defect this run introduced. See `references/run-safety.md` for the ceiling and register detail, `references/workflow.md` for the full decision rules, and `references/examples.md` for a sample report structure.

## Required Contracts

- **Before/After Evidence**: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../execution-contract.md` defines, so upstream and downstream packages interpret risk consistently.
- **Input validation**: Validate that the workload definition, baseline reference, and environment specification are present and coherent before executing any benchmark run. Refuse to proceed if inputs are ambiguous or contradictory.
- **Production safety and a declared load ceiling**: Never run a load-intensive or resource-intensive benchmark against a production environment without explicit owner authorization; require a named approver and a confirmed non-production target before starting. The non-production target is then bounded too, because staging and CI hosts are shared and an unbounded load test on one is an outage for everyone else using it. Declare the ceiling — peak rate, peak concurrency, total duration, data volume — and the abort condition before the first sample, and abort at either rather than finishing the sample set; a completed run that took the host down is not a better outcome than an aborted one. `references/run-safety.md` carries the ceiling fields, the abort conditions, and the restore register. Treat sensitive performance data (e.g., throughput figures revealing business load) with the same care as any internal metric.
- **Leave the host as it was found**: Every change made to reduce variance — stopped services, disabled auto-updates, disabled GC or background compaction, altered CPU governor or power profile, dropped caches — is recorded with its prior value when it is made and restored in reverse order when the run ends, including when the run aborts or fails. An unrestored host quietly biases every later measurement taken on it and misleads whoever uses it next, who has no way to know what was changed.
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
| The workload definition, metrics, or environment specification is missing, empty, or contradicts the baseline being compared against | Refuse to sample and name the specific gap. A benchmark run against an under-specified workload still produces confident numbers, and those numbers are the hardest kind of wrong result to catch afterwards. |
| The harness, host, or workload fails part-way through a sample set | Discard the partial set; never merge it with a completed run. A truncated set is biased by construction — the iterations that survived are the ones that ran before whatever caused the failure — so averaging it into a full run moves the median by an unknown amount. Report the failure, the iteration it stopped at, the ceiling and abort state at that moment, restore the register, and rerun the set from the beginning once the cause is understood. |
| The workload exhausts host memory, disk, file handles, or another shared resource | Abort at the declared abort condition rather than at the crash. Stop the run, restore the register, and report the resource that ran out with the load level that reached it — that ceiling is itself a finding worth reporting. Never retry at the same load on the same host hoping for a different outcome, and never continue on the assumption that the surviving samples are still comparable. |
| The measurement tool, baseline artifact store, or benchmark target cannot be reached | Record the run as not-run with the reason and report nothing as measured. An unavailable measurement is a data gap, never a neutral result, and never a number carried over from a previous run. |
| The run ends — completed, aborted, or failed — with entries still in the restore register | Restore them before reporting anything, then state the restoration in the report. An unrestored host is a defect the benchmark introduced, and it is invisible to the next person who measures on it. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Never write `_phase-state.md`. No class in the save-ownership policy declares that path, so it is not an orchestrator-owned file either — phase state is published only through `save_run.py checkpoint`, which keeps revision lineage and the audit trail coherent.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed operating sequence and decision rules.
- `references/run-safety.md` for the load-ceiling fields, the abort conditions, the restore register, and the partial-sample rule.
- `references/examples.md` for concrete request patterns and response shapes with worked numbers.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/run-safety.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
