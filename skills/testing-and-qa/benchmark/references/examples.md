# Example Invocations

## Example 1

**User request:** benchmark this change in the search endpoint

**Output:**

| Metric | Baseline med/p95/p99 | Candidate med/p95/p99 | Delta (p95) | CI band | Verdict |
|--------|----------------------|-----------------------|-------------|---------|---------|
| Latency (ms) | 38 / 72 / 95 | 39 / 85 / 110 | +18% | ±6 ms (95%) | p95/p99 regression confirmed |

- Sample size: 50 runs after 5 warm-up discards; hardware pinned, background load quiesced.
- Median is unchanged; tail latency (p95/p99) regressed beyond the variance boundary — confirmed regression.
- Follow-up: inspect the new ranking sort step before calling this release-blocking.

## Example 2

**User request:** compare performance of the import worker

**Output:**
- Workload: 10,000-row CSV import with identical attachment payloads.
- Confidence note: the first run was noisy because the worker cache was cold, so only the steady-state samples are used for comparison.
- Delivery: benchmark report that separates warm-up effects from the real throughput comparison.

## Example 3

**User request:** measure the regression in dashboard load time

**Output:**
- Baseline: last release build on the same staging dataset.
- Finding: the measured slowdown is smaller than the current variance band, so it stays on the watchlist instead of being labeled a confirmed regression.
- Next action: rerun with tighter environment controls before escalating.
