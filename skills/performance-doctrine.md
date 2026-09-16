# Performance Doctrine

Optimize measured systems, not stories.

## Contents

- [Scope and authority](#scope-and-authority)
- [Enforcement status](#enforcement-status)
- [The six steps](#the-six-steps)
- [When the system cannot be measured](#when-the-system-cannot-be-measured)
- [Rendering and interactive surfaces](#rendering-and-interactive-surfaces)
- [Evidence](#evidence)
- [Failure paths](#failure-paths)

## Scope and authority

This file is canonical for one thing: what a performance *claim* must be backed
by before it is made. It is not canonical for which skill runs a measurement,
for gate evidence ([gates.yaml](gates.yaml)), or for the evidence vocabulary
([contracts/evidence-standards.md](contracts/evidence-standards.md)).

**The trigger is the claim, not the code.** Earlier revisions of this file
declared themselves binding for `benchmark`, `frontier`, `health-check`,
`quality-review`, "and any build work that changes a hot path". The last clause
had no boundary and no owner — every edit touches something that could be called
a hot path — and the four named skills were not bound in any operative sense
either: none of them references this file, so a run of any of them never loads
it. A doctrine no bound skill loads cannot bind that skill by assertion.

The honest scope is therefore narrower and sharper. This doctrine applies
whenever a run states that something is faster, lighter, or cheaper than it was,
or that a change will not make it slower. Touching a hot path without making
such a claim engages nothing here. Making such a claim engages all of it,
whatever skill is running.

Ownership follows the claim in the same way. The skill that states the
improvement owns the measurement behind it. Inside a delivery run that is the
phase lead who accepts the claim into the package — `build-management` for a
build-phase claim, `code-chief` for a review-phase one — and either may engage
`benchmark` for comparative runs or `frontier` for frontend measurement. Neither
delegation transfers the obligation: an unmeasured claim is the claiming skill's
defect regardless of who could have measured it.

**Reachability, stated plainly.** The only document in the catalog that links
this file is
[contracts/universal-frameworks.md](contracts/universal-frameworks.md), under
*Measured optimization*. No `SKILL.md` and no skill reference document points
here. In practice this doctrine is reached by a reader who already knows it
exists, which is a real gap and is recorded as one rather than papered over with
a binding claim. Closing it means adding a pointer from the skills that make
performance claims. By the ownership rule just above, that is the phase lead who
accepts such a claim into a package — `build-management` for a build-phase claim
and `code-chief` for a review-phase one — so the edit belongs to those two
skills, not to this file. `benchmark` and `frontier` may carry a pointer too, but
neither owns the obligation, so neither closes the gap on its own.

## Enforcement status

Nothing in this doctrine is machine-checked. There is no partial credit to
report, so the whole file is one row:

| Statement | Status | What actually checks it |
| --- | --- | --- |
| Every step, threshold, and evidence requirement below | **judgement** | nothing |

Concretely: no boundary in [gates.yaml](gates.yaml) requires a performance
evidence key, no typed evidence record exists for one (`evidence_types` has
`probe`, `render`, `scan`, `findings`, and the taste records, and none of them
carries a latency, throughput, or memory field), and no script in the catalog
checks these steps. An approved package therefore proves nothing about
performance on its own. A reviewer applying this doctrine by hand is the only
enforcement there is, and a reader must not infer otherwise from the fact that a
gate returned `APPROVED`.

The evidence vocabulary this file borrows is judgement-only too:
[contracts/evidence-standards.md](contracts/evidence-standards.md) states that
no comparator reads `exact`, `bounded`, `contextual`, `observed`, `corroborated`,
`reported`, or `inferred`. Labelling a performance claim `observed` asserts
something; it does not verify it.

## The six steps

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

Step 6 is the step most often skipped and the one that decides whether the work
lasts. A win with no preserved threshold is a win that the next change will
reverse without anyone noticing, which returns the system to the state step 1
described. Name the specific artifact that preserves it — the assertion, the
benchmark case, the budget and where it is watched — rather than the intention
to preserve it.

## When the system cannot be measured

Step 1 presupposes a system that can be measured. Where it cannot be, report the
gap rather than a number:

- No repeatable rig is available. The bound stays unmeasured and no win may be
  claimed. Either build the rig as the deliverable of this work, or return the
  request blocked on one, naming what the rig must exercise.
- Baseline and post-change environments differ. The comparison is void. Record
  both environments, re-baseline on the environment that will ship, and carry
  any cross-environment figure at `inferred` trust rather than `observed`.
- The regression budget cannot be measured. Name the cost that has no
  instrument, state the closest proxy with its error, and record the unbudgeted
  risk as a residual risk rather than absorbing it silently.

Each of these returns REVISE or ESCALATE with the gap stated. None of them
licenses an improvement claim.

## Rendering and interactive surfaces

A rendering claim is measured the same way as any other, with the quantities
named rather than gestured at. Before the work, the run declares four numbers
and one fact, and a rendering claim without all five is unmeasured:

- the **target device** the budget is stated for, by name, since a frame budget
  is meaningless without one;
- the **frame budget** in milliseconds per frame, with the refresh rate it
  implies (16.7 ms at 60 Hz, 8.3 ms at 120 Hz) — the budget is a declared
  number, not an inherited assumption;
- the **worst-frame threshold**: the percentile and the ceiling it must stay
  under, because a good median with a visible hitch is a failure the median
  hides;
- the **memory ceiling** over the measured window, and whether growth across
  that window is flat;
- the **measurement window** itself: how long, over which interaction, repeated
  how many times.

Against those, measure frame pacing and worst frames, the CPU and GPU split,
draw and state cost, memory growth, and resource lifetime, on target-device
evidence rather than a development machine. Prefer stable delivery over peak
throughput: a surface that holds its budget every frame beats one that averages
better and misses occasionally.

This doctrine names no measurement tool, because the catalog ships none for
rendering. The host's own profiler, a frame-timing capture, or an instrumented
build all satisfy the requirement; what does not satisfy it is a claim with no
declared budget and no named instrument. `frontier` owns frontend measurement
when one is engaged and `benchmark` owns comparative runs, but neither is
required by a gate and neither carries an evidence key, so engaging them is a
decision the claiming skill makes and records.

The one adjacent mechanical record is `rendered_verification`
([design-doctrine.md](design-doctrine.md) §8), a typed `render` record whose
shape `check.py` does verify. It carries captures, breakpoints, and themes. It
carries no timing, no frame data, and no memory figure, so it is evidence that a
surface renders, never evidence that it renders fast enough. Citing it as
performance evidence is exactly the overstatement this file exists to prevent.

## Evidence

Evidence follows
[contracts/evidence-standards.md](contracts/evidence-standards.md): a
performance claim is `exact` plus `observed` or `corroborated`, with units,
sample size, measurement window, and environment recorded beside it. Those
labels are applied by the author and read by a reviewer; no comparator reads
them.

## Failure paths

- **No rig, no baseline, or no instrument for the declared budget.** Covered
  above: report the gap, return REVISE or ESCALATE, and claim nothing. The gap
  is the deliverable when the measurement is not.
- **The measured win falls inside noise.** It is not a win. Record the attempt,
  the variance, and the decision not to claim it, so the next run does not
  repeat the experiment blind.
- **The win moves the cost somewhere else.** Reject it, and name where the cost
  went. A local improvement that degrades a different bound is a regression
  reported as a success, which is worse than no change.
- **Two mechanisms changed together and the result improved.** The attribution
  is unknown. Either separate them and re-measure, or claim the combined change
  as one mechanism and describe it as such; do not attribute the win to the half
  that seems more plausible.
- **The target device is unavailable.** Measure on what is available, label
  every figure `inferred`, state the device actually used, and do not present a
  development-machine number as target-device evidence.
- **A gate approves a package containing an unmeasured performance claim.** The
  gate did not check it and could not: no boundary requires performance
  evidence. The claim is still a defect, and the reviewer who let it through
  owns it. Approval is not verification.
- **This doctrine conflicts with a security, accessibility, or correctness
  requirement.** The requirement wins. Performance is a quality of a correct
  system, never a reason to weaken one, and a proposed optimization that trades
  a requirement away is refused rather than negotiated.
