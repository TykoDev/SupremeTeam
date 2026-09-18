# Run Safety Reference

Read this before the first sample of any run that imposes load, and again when a run aborts or
fails part-way. SKILL.md Workflow steps 1, 2, and 5 name the load ceiling, the restore register,
and the restoration; this file carries their fields, the abort conditions, and the rule for a
partial sample set.

## Contents

1. Why a non-production target still needs a ceiling
2. Declaring the load ceiling
3. Abort conditions
4. The restore register
5. Partial sample sets
6. Sensitive performance data
7. Where the load generator runs

## 1. Why a Non-Production Target Still Needs a Ceiling

A confirmed non-production target removes the risk to customers; it does not remove the risk to
colleagues. Staging clusters, CI runners, and shared database hosts serve everyone at once, and a
benchmark is the one workload deliberately built to saturate a resource until something gives.
Declaring the bound before the first sample turns "how hard did it get pushed" from a question
answered afterwards, by a graph of somebody else's failed pipeline, into a number the run
already agreed to.

The ceiling is also a measurement instrument. A run that reports its peak rate and concurrency is
reproducible; a run whose only stated bound is "as hard as it took" is not.

## 2. Declaring the Load Ceiling

Four fields, stated before sampling and carried into the report:

| Field | What it bounds | Example |
| --- | --- | --- |
| Peak rate | Requests or operations per second, per target | 200 req/s against one staging API instance |
| Peak concurrency | Simultaneous in-flight requests, connections, or workers | 32 connections, 4 worker processes |
| Total duration | Wall-clock time the whole run may occupy the target | 25 minutes including warm-up and both arms |
| Data volume | Rows, messages, files, or bytes the run creates, and their cleanup | ≤ 50k rows in `bench_orders`, dropped at the end |

Two rules keep the ceiling honest. Set it from the target's normal operating envelope rather than
from the load required to prove a point — a ceiling chosen to guarantee an interesting number is
not a bound. And name the owner of the shared target, so a ceiling that has to rise is raised by
the person who lives with the consequence rather than by the person waiting on the result.

## 3. Abort Conditions

The abort condition stops the run mid-sample. It exists because the alternative — noticing at the
end — means the damage is already done and the numbers are unusable anyway. Declare at least:

- **Ceiling breach** — measured rate, concurrency, or elapsed duration exceeds the declared
  value. A run that has exceeded its own bound is no longer the run that was approved.
- **Host resource exhaustion** — memory, disk, file handles, or connection pool approaching
  their limit on the target or the load generator. Abort on approach, not on failure: an OOM kill
  takes the register with it.
- **Collateral impact** — error rates, queue depth, or latency on *other* workloads sharing the
  target crossing their own alert thresholds.
- **Measurement invalidity** — the target restarting, the baseline artifact changing under the
  run, or variance so wide the sample cannot separate signal from noise.

On abort: stop sampling immediately, restore the register (section 4), discard the partial set
(section 5), and report the abort with the condition that fired and the load level it fired at.
An abort is a result, and often a more useful one than the measurement would have been.

## 4. The Restore Register

Every change made to reduce variance is recorded **as it is made**, with the value it had before,
because the state to restore is unknowable afterwards:

| # | Change | Prior value | Restored | Confirmed by |
| --- | --- | --- | --- | --- |
| 1 | Stopped `backup-agent` | running, enabled at boot | yes | `systemctl is-active backup-agent` → active |
| 2 | Disabled OS auto-update | scheduled daily 03:00 | yes | policy re-read shows daily 03:00 |
| 3 | `GOGC=off` in the harness env | unset (default 100) | yes | env unset in a fresh shell |
| 4 | Paused compaction on `bench_db` | auto | yes | compaction status auto |

Restore in reverse order and confirm each entry rather than assuming the undo command worked. The
register is restored on **every** exit path — completion, abort, and failure — and the report
states the restoration, because a host left quiesced biases every later measurement taken on it
and gives no sign of doing so. Anything that cannot be restored is reported as an outstanding
change with a named owner, not left in the register.

## 5. Partial Sample Sets

A sample set interrupted mid-run is discarded, never merged with a completed one. The surviving
iterations are exactly the ones that ran before whatever caused the interruption, so the set is
biased in an unknown direction by construction: a harness that died on iteration 23 of 50 may
have been dying slowly for ten iterations, and those ten are in the data. Merging it into a full
run moves the median by an amount nobody can estimate, and the resulting number looks entirely
ordinary.

Report the failure instead — the iteration it stopped at, the abort or failure condition, the
load level at that point — restore the register, and rerun the whole set once the cause is
understood. A rerun on a host whose cause is not understood produces a second discarded set.

## 6. Sensitive Performance Data

Throughput ceilings, queue depths, and latency distributions describe business load as well as
code. Treat a benchmark report as an internal metric: keep customer identifiers out of workload
descriptions, keep production-derived volume figures out of anything externally circulated, and
name the owner when a figure has to travel further than the team.

## 7. Where the Load Generator Runs

The generator is part of the measured system whether or not it is meant to be.
Running it on the host that runs the target means the two compete for the same
CPU, the same memory bandwidth, and the same network stack, and the contention
grows with the load — so the measurement degrades exactly where the numbers
matter most, at the top of the range.

- **Default: a separate host on the same network segment.** The generator's own CPU should stay below roughly 50% at peak; a saturated generator reports its own queueing delay as the target's latency, and the two are indistinguishable from the result.
- **When it must share the host**, say so in the environment fingerprint, pin the generator and the target to disjoint CPU sets where the platform allows it, and treat the absolute numbers as comparative only. A same-host run can still answer "is the candidate slower than the baseline?" — it cannot answer "what is the latency?"
- **Check for self-contention before trusting a result**: re-run the baseline arm at half the load. If per-request latency drops more than the load reduction alone explains, the generator or the host was the bottleneck, and the full-load numbers describe the harness rather than the target.
- **Network position is part of the workload.** A generator on the loopback interface skips the network stack the real client traverses. That is a legitimate choice for isolating a code change, and a misleading one for a latency budget; name which the run is for.
- The generator's own version, concurrency model, and connection-reuse settings belong in the environment fingerprint alongside the target's. A generator upgrade between baseline and candidate invalidates the comparison as surely as a runtime upgrade would.
