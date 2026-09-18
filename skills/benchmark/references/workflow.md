# Workflow Reference

## Contents

1. Benchmark sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Benchmark Sequence

1. Lock the workload, environment, and metrics before sampling. Pin software versions (OS, runtime, dependencies) and fix hardware or VM allocation. Declare the load ceiling — peak rate, peak concurrency, total duration, data volume — and the abort condition before the first sample, and name the owner of the shared target; `run-safety.md` carries both field sets. Validate that the baseline artifact is available and reproducible before proceeding.
2. Quiesce background load — close unrelated services, disable auto-updates, disable GC or background compaction where controllable — and record every one of those changes in the restore register **as it is made**, with the value it had before. The prior state is unknowable once the run is over, and a host left quiesced biases every later measurement taken on it.

   **Name the controls rather than "tightening" them.** "Increase controls" is not an action anyone can take twice the same way. These are the ones that move wall-clock variance most, in the order they usually matter:

   | Control | What it does to the numbers | How to hold it |
   |---|---|---|
   | CPU frequency governor | The largest single source of drift on a laptop or a burstable VM. A governor that ramps clocks under load makes the *second* arm faster than the first for reasons that have nothing to do with the code. | Pin to a fixed-frequency mode (`performance` on Linux `cpufreq`, "High performance" power plan on Windows), and record the prior setting in the restore register. Where it cannot be pinned — most shared cloud instances — say so and interleave the arms instead (below). |
   | Thermal headroom | Sustained load heats the package, the CPU throttles, and every later sample is slower. This biases whichever arm runs last, systematically. | Start from a cool machine, keep total run duration inside the declared ceiling, and watch for a monotonic slowdown across iterations — that pattern is thermal, not the candidate. |
   | Arm ordering | Any drift over the run — thermal, governor, a neighbour waking up — lands on one arm when the arms run back to back. | Interleave: alternate baseline and candidate samples rather than running all of one then all of the other. This converts a systematic bias into noise the confidence band already accounts for, and it is the single most effective control on a machine you do not own. |
   | Noisy neighbours and host contention | Invisible from inside the guest, and unrepeatable. | Prefer a dedicated node. Where impossible, raise the sample size, interleave, and report the wider band honestly rather than re-running until a quiet window produces the desired answer. |
   | Turbo / boost states | A short run sits entirely inside boost and reports numbers no sustained workload will ever see. | Either disable boost, or make the run long enough that boost is a small fraction of it — and say which. |

   Record every control's prior value in the restore register as it is set, exactly as for background load. An environment fingerprint that does not name which of these were held is not reproducible.
3. Run a short pilot (5–10 iterations) to observe variance. Use the pilot's standard deviation to choose a final sample size — a rule of thumb is 30+ iterations for wall-clock timings; high-variance systems (>20% CV) need more. Discard a warm-up phase of at least 3–5 iterations before collecting real samples to exclude cold-start JIT, cache fill, and connection establishment.
4. Compute median and tail percentiles (p95, p99) as primary reporting columns. Report a simple confidence band (±1 SD, IQR, or bootstrap CI at 95%) alongside point estimates. Only label a result a regression when it clears the variance boundary with the current sample size — state the threshold explicitly.
5. Restore every entry in the restore register in reverse order and confirm each restoration — on every exit path, including an aborted or failed run — then publish the benchmark result with a median/p95/p99 table, the confidence band, sample size, environment fingerprint, the declared ceiling and whether the run stayed inside it, and the restoration itself. Include a follow-up action that maps to the measured outcome (confirmed regression, watchlist noise, or within-budget change).

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
- Never run a resource-intensive benchmark against production without explicit owner authorization, and bound the non-production target too: declare the ceiling and the abort condition before the first sample, and abort at either rather than finishing the set.
- A partial sample set is discarded, never merged with a completed run; the surviving iterations are biased by whatever ended the run.
- Every host change made to reduce variance is registered with its prior value and restored in reverse order, including when the run aborts.
- An unavailable tool, target, or baseline store is a not-run result, never a number carried over from a previous run.

## Acceptance Checklist

- Baseline, workload, and environment are named and the baseline is reproducible.
- The load ceiling and abort condition were declared before sampling, and the report states whether the run stayed inside the ceiling.
- The restore register is empty at the end, and the restoration is stated in the report.
- Sample size, warm-up phase, and repeatability context are present.
- Median and tail percentiles (p95, p99) are reported alongside a confidence band.
- Signal and noise are separated clearly; regression label is tied to the variance boundary.
- Follow-up action matches the measured outcome.

## Contract Notes

The contracts this workflow runs under are stated in `../SKILL.md` § Required Contracts.

## Collaboration Notes

This skill's collaboration surface is stated in `../SKILL.md` § Collaboration Surface.
