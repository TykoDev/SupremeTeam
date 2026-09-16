# Example Invocations

## Example 1 — confirmed tail regression

**User request:** benchmark this change in the search endpoint

**Output:**

| Metric | Baseline med/p95/p99 | Candidate med/p95/p99 | Delta (p95) | CI band | Verdict |
|--------|----------------------|-----------------------|-------------|---------|---------|
| Latency (ms) | 38 / 72 / 95 | 39 / 85 / 110 | +18% | ±6 ms (95%) | p95/p99 regression confirmed |

- Sample size: 50 runs after 5 warm-up discards; hardware pinned, background load quiesced.
- Ceiling: 120 req/s, 16 concurrent, 18 minutes total, no data written — declared before sampling; the run peaked at 118 req/s and stayed inside it.
- Register restored: `backup-agent` restarted, auto-update schedule returned to daily 03:00, `GOGC` unset. Confirmed individually.
- Median is unchanged; tail latency (p95/p99) regressed beyond the variance boundary — confirmed regression.
- Follow-up: inspect the new ranking sort step before calling this release-blocking.

## Example 2 — cold-cache samples excluded, throughput within noise

**User request:** compare performance of the import worker

**Output:**
- Workload: 10,000-row CSV import with identical attachment payloads, 3 attachments per row.
- Ceiling: 4 concurrent workers, 20 minutes, ≤ 40k rows written to `bench_imports` and dropped at the end; abort on staging DB connection pool above 80%.

| Metric | Baseline med/p95/p99 | Candidate med/p95/p99 | Delta (median) | CI band | Verdict |
|--------|----------------------|-----------------------|----------------|---------|---------|
| Rows/s | 412 / 356 / 301 | 418 / 362 / 298 | +1.5% | ±14 rows/s (95%) | within noise band |
| Import wall-clock (s) | 24.3 / 28.1 / 31.6 | 23.9 / 27.8 / 32.0 | -1.6% | ±1.1 s (95%) | within noise band |

- Confidence note: the first 6 iterations ran with a cold worker cache and sat 3.1× above the steady-state median, so they are discarded as warm-up rather than averaged in. 44 steady-state iterations remain per arm.
- Delivery: benchmark report separating warm-up effects from the real throughput comparison; the +1.5% delta sits inside a ±3.4% band, so no regression and no improvement is claimed.
- Register restored: compaction on `bench_db` returned to auto; confirmed by status read.

## Example 3 — slowdown smaller than the variance band

**User request:** measure the regression in dashboard load time

**Output:**
- Baseline: last release build (`web-2026.04.12`) on the same staging dataset, same pinned runtime.

| Metric | Baseline med/p95/p99 | Candidate med/p95/p99 | Delta (median) | CI band | Verdict |
|--------|----------------------|-----------------------|----------------|---------|---------|
| Dashboard load (ms) | 640 / 910 / 1180 | 668 / 944 / 1205 | +4.4% | ±58 ms (95%) | watchlist — inside the band |

- Sample size: 30 iterations per arm after 5 warm-up discards; coefficient of variation 11%, so 30 was sufficient for a stable median.
- Finding: the +28 ms median shift is smaller than the ±58 ms confidence band, so it stays on the watchlist rather than being labeled a confirmed regression.
- Next action: rerun with tighter environment controls — a dedicated staging node and 60 iterations per arm would narrow the band to roughly ±40 ms — before escalating.

## Example 4 — run aborted at the resource ceiling, partial set discarded

**User request:** benchmark the export path at production-scale concurrency

**Output:**
- Ceiling: 64 concurrent exporters, 30 minutes, ≤ 200k rows; abort conditions included staging host memory above 85% and export queue depth above 5,000.
- Abort: memory crossed 85% at iteration 19 of 40, at 52 concurrent exporters. The run stopped mid-sample rather than at the end.
- Partial set: 18 completed iterations discarded, not merged with the baseline arm — the surviving iterations are the ones that ran before memory pressure built, so their median is biased downward by an unknown amount.
- Register restored: exporter service returned to its prior replica count; confirmed.
- Reported as a finding in its own right: the export path reaches host memory pressure at 52 concurrent workers on a node sized for the current production peak of 40. That ceiling is the useful result; the rerun waits until the memory profile is understood.
