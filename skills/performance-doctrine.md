# Performance Doctrine

Optimize measured systems, not stories. Binding for any skill that claims a
performance improvement: `benchmark`, `frontier`, `health-check`,
`quality-review`, and any build work that changes a hot path.

1. Name the user-visible cost, the target, the workload, the environment, and
   the regression budget before changing anything.
2. Capture a repeatable baseline after warmup. Report median, tail, variance,
   memory, and the relevant resource counters, not a single sample.
3. Determine the active bound (CPU, memory, I/O, network, lock contention,
   allocation, or render) before choosing a remedy.
4. Change one mechanism at a time and measure on the same rig.
5. Reject wins inside noise, and wins that move an unacceptable cost elsewhere.
6. Preserve the win with a threshold, benchmark, assertion, or monitored budget,
   so the next change cannot silently undo it.

Optimization runs only against a measured bottleneck with a declared regression
budget. A request to "make it faster" without a baseline starts at step 1, not
step 4.

For rendering and interactive surfaces, measure frame pacing and worst frames,
the CPU and GPU split, draw and state cost, memory growth, resource lifetime,
and target-device evidence. Prefer stable delivery over peak throughput.
`frontier` owns the frontend measurement; `benchmark` owns comparative runs.

Evidence follows [contracts/evidence-standards.md](contracts/evidence-standards.md):
a performance claim is `exact` plus `observed` or `corroborated`, with units,
sample size, measurement window, and environment recorded beside it.
