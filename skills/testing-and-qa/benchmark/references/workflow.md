# Workflow Reference

## Contents

1. Benchmark sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Benchmark Sequence

1. Lock the workload, environment, and metrics before sampling. Pin software versions (OS, runtime, dependencies), fix hardware or VM allocation, and quiesce background load (close unrelated services, disable auto-updates, disable GC or background compaction where controllable). Validate that the baseline artifact is available and reproducible before proceeding.
2. Run a short pilot (5–10 iterations) to observe variance. Use the pilot's standard deviation to choose a final sample size — a rule of thumb is 30+ iterations for wall-clock timings; high-variance systems (>20% CV) need more. Discard a warm-up phase of at least 3–5 iterations before collecting real samples to exclude cold-start JIT, cache fill, and connection establishment.
3. Compute median and tail percentiles (p95, p99) as primary reporting columns. Report a simple confidence band (±1 SD, IQR, or bootstrap CI at 95%) alongside point estimates. Only label a result a regression when it clears the variance boundary with the current sample size — state the threshold explicitly.
4. Publish the benchmark result with a median/p95/p99 table, the confidence band, sample size, and environment fingerprint. Include a follow-up action that maps to the measured outcome (confirmed regression, watchlist noise, or within-budget change).

## Sample Report Structure

| Metric | Baseline (median / p95 / p99) | Candidate (median / p95 / p99) | Delta | CI band | Verdict |
|--------|-------------------------------|-------------------------------|-------|---------|---------|
| Endpoint latency (ms) | 42 / 89 / 130 | 44 / 112 / 165 | +5% / +26% / +27% | ±8 ms (95%) | p95/p99 regression confirmed |
| Throughput (req/s) | 820 / — / — | 815 / — / — | -0.6% | ±18 req/s | within noise band |

## Decision Rules

- Comparable workloads matter more than raw speed numbers.
- Baselines must be named explicitly and the artifact must be reproducible; if not, stop and report.
- Noise and confidence limits must stay visible in the report — never report only a point estimate.
- Only label a regression when the measurement meaningfully clears the variance boundary.
- Never run a resource-intensive benchmark against production without explicit owner authorization.

## Acceptance Checklist

- Baseline, workload, and environment are named and the baseline is reproducible.
- Sample size, warm-up phase, and repeatability context are present.
- Median and tail percentiles (p95, p99) are reported alongside a confidence band.
- Signal and noise are separated clearly; regression label is tied to the variance boundary.
- Follow-up action matches the measured outcome.

## Contract Notes

- Before/After Evidence: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.

## Collaboration Notes

- None required beyond the active task surface.
