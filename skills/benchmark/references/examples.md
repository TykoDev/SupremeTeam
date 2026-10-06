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
| Dashboard load (ms) | 640 / 910 / 1180 | 668 / 944 / 1205 | +4.4% | ±35 ms (95%) | watchlist — inside the band |

- Sample size: 30 iterations per arm after 5 warm-up discards; coefficient of variation 11%. That was enough for a stable median in each arm, and **not** enough to separate a 5% shift between the arms. The derivation, since the rule of thumb is where most benchmarks go wrong:

  The pilot gave a mean of 640 ms and an SD of 70 ms, so CV = 70/640 = 11%. The question is a difference between two arms, so the band that decides it is the band of a *difference*: its standard error is `SD x sqrt(2/n)`, and the 95% band is roughly `±1.96 x` that. The single-arm band (`±1.96 x SD/sqrt(n)`) describes how well one median is pinned down; it is the wrong figure for sizing a comparison.

  | n per arm | Single-arm band | Two-arm SE = 70 x sqrt(2/n) | Two-arm 95% band | Two-arm band as % of 640 ms |
  |---|---|---|---|---|
  | 10 | ±43 ms | 31.3 ms | ±61 ms | ±9.6% |
  | 30 | ±25 ms | 18.1 ms | ±35 ms | ±5.5% |
  | 40 | ±22 ms | 15.7 ms | ±31 ms | ±4.8% |
  | 60 | ±18 ms | 12.8 ms | ±25 ms | ±3.9% |

  The smallest shift worth reporting here was set at 5% (32 ms) before sampling. At n=30 the two-arm band is ±35 ms — wider than 32 ms — so a real 5% shift cannot be told from noise; the single-arm ±25 ms would have suggested otherwise, and reading it would have sized the run wrongly. The two-arm band first drops below 32 ms at n=37, so 40 per arm was the right plan and 60 gives a comfortable ±25 ms. This run is reported as what it is: under-powered for its own threshold.

  Note what the table shows about the cost curve: halving the band costs four times the samples, since every band scales with `1/sqrt(n)`. The two-arm band is sqrt(2) times the single-arm band at the same n (±35 against ±25 at n=30), not double it, because both arms carry their own error. That is why the sample size is chosen from a stated threshold and the right band rather than raised until the answer looks clean.
- Finding: the +28 ms median shift is smaller than the ±35 ms two-arm confidence band, so it stays on the watchlist rather than being labeled a confirmed regression. The margin is narrow — a shift of 36 ms on the same samples would have cleared the band — and the band itself was wider than the 5% threshold, so a watchlist result here says the run could not decide, not that the change is safe.
- Next action: rerun with tighter environment controls — a dedicated staging node and 60 iterations per arm, which narrows the two-arm band to ±25 ms by the same formula (1.96 x 70 x sqrt(2/60)) — before escalating.

## Example 4 — run aborted at the resource ceiling, partial set discarded

**User request:** benchmark the export path at production-scale concurrency

**Output:**
- Ceiling: 64 concurrent exporters, 30 minutes, ≤ 200k rows; abort conditions included staging host memory above 85% and export queue depth above 5,000.
- Abort: memory crossed 85% at iteration 19 of 40, at 52 concurrent exporters. The run stopped mid-sample rather than at the end.
- Partial set: 18 completed iterations discarded, not merged with the baseline arm — the surviving iterations are the ones that ran before memory pressure built, so their median is biased downward by an unknown amount.
- Register restored: exporter service returned to its prior replica count; confirmed.
- Reported as a finding in its own right: the export path reaches host memory pressure at 52 concurrent workers on a node sized for the current production peak of 40. That ceiling is the useful result; the rerun waits until the memory profile is understood.
