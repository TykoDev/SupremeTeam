# Workflow Reference

Read this when exercising an interface at runtime and deciding what an observation
supports. `../SKILL.md` holds the normative packet shape, the gate-evidence table,
and the save rules; this file holds the sequence and the judgment calls inside it.

## Contents

1. Frontend review sequence
2. The six tiers, and what to capture at each
3. Deriving a budget when the handoff supplies none
4. Decision rules
3. Acceptance checklist
4. Contract notes
5. Collaboration notes

## Frontend Review Sequence

1. Confirm the snapshot digest against the approved design package, then identify the visible flows, key states, devices, and tiers in scope.
2. Exercise interaction behavior, responsive reflow across the six tiers, loading and error handling, accessibility paths, and performance for those specific flows.
3. Record findings with user impact, reproduction steps, and the affected tier or state.
4. Package runtime behavior issues, the traces behind them, and handoffs for `review/code-chief`.

## The Six Tiers, and What to Capture at Each

`../../../design-doctrine.md` §4 is canonical for the widths and the required
behavior; this table maps each tier to the observation that settles it, which is
the part this lens owns. Capture at the tier's *narrowest* width — a layout that
holds at 374 px holds at 375 px, and the reverse is not true.

| Tier | Capture at | The failure this tier is for |
| --- | --- | --- |
| Small mobile | 320 px | Horizontal scroll, truncated primary content, tap targets under 44 px |
| Mobile | 375 px | Measure too wide to read; a primary action that scrolls out of reach |
| Tablet | 640 px | A two-column layout forced where one column reads better |
| Desktop | 1024 px | Prose stretching past 72ch; regions that collapse at the low end of the range |
| Large desktop | 1440 px | Text regions stretched edge to edge with no max-width container |
| Ultrawide | 1920 px | Extra columns invented to fill width instead of whitespace; no content-width cap |

Both themes at every tier where the surface resolves a theme-dependent token. A
tier that cannot be reached — a route gated behind a viewport check, a component
that only mounts above a width — is recorded as unexercised with the reason, not
silently dropped from the set.

## Deriving a Budget When the Handoff Supplies None

The handoff is meant to carry the performance budget, and `../SKILL.md` Failure
Modes says what to do when it does not: measure, record the measurement as the
baseline, and report the missing budget as its own finding. Two judgment calls
sit inside that, and they are this file's to state.

**What the baseline is.** Three runs against the disposable target, the median
reported, the spread stated. One run is a sample, not a baseline, and a single
cold-start measurement is the most common way a frontier packet reports a
regression that does not exist.

**What may be said about it.** A measurement with no budget supports "this is
what it does now" and nothing more. It does not support "this is slow", "this
regressed", or a recommendation to optimize — those are claims against a
threshold, and there is no threshold. Where a prior revision's capture exists in
the run, a comparison against it is a *delta*, still not a verdict: whether the
delta matters is the budget's question, and the budget is what is missing. Invent
no threshold, borrow none from another project, and take none from a framework's
published defaults; report the absence and let the owner set one.

## Decision Rules

- Judge the rendered experience that is actually evidenced, not a hypothetical full application surface.
- Keep accessibility and performance findings tied to concrete interactions, states, or traces.
- Separate runtime behavior failures from visual-fidelity drift when the latter belongs with `review/design-qa`: if the question can be answered by looking at a still capture, it is not this lens.
- Preserve uncertainty when device, tier, or assistive-technology evidence is incomplete.
- Measure before recommending, and measure again before calling a performance fix verified.
- Write a fix as a root cause and a direction, never as an edit: a patched surface makes every later measurement in the pass un-attributable.

## Acceptance Checklist

- Findings name the affected screen, interaction, and tier or state.
- Accessibility and performance issues are backed by observable evidence, and the run that produced it is named.
- Visual-only handoffs to `review/design-qa` are called out when appropriate.
- Reproduction steps are clear enough for downstream validation.
- Every item carries one of the four shared severities, and an interface that holds returns the clean-pass packet with the runs named.
- The reviewed files are unmodified, and the packet is saved as `deliverable_frontier.md` so it stays distinguishable from mr-robot's packet in the shared lens slot.

## Contract Notes

`../SKILL.md` states the contracts; this section records only where each one
lands in the sequence above, so the two documents do not restate each other.

- Read-only over the reviewed surface — binds from step 1 through packaging; the root cause written at step 3 is the deliverable, and a mid-pass patch would break the attribution of every measurement taken after it.
- Digest-bound Taste conformance — enforced at step 1, before any flow is exercised, because a run judged against the wrong baseline cannot be re-attributed afterwards. Behavior and accessibility findings recorded at step 3 carry the effective preference ids and the design-time digest they answer for; later Taste changes are reported as drift.
- Shared severity — assigned at step 3 on user impact, so an accessibility barrier is graded by what it costs a user rather than filed under a category label.
- Save-Protocol Adherence — the step 4 packet is what the save path receives, under the filename `../SKILL.md` mandates, with traces stored as evidence beside it.

## Collaboration Notes

- `review/code-chief` merges the frontier packet with the other review lenses and owns the graded record the gate reads.
- `review/gatekeeper-code` checks that user-facing behavior risks survive the final consolidation intact, and matches this packet through the `lens_adversarial` slot it shares with `review/mr-robot`.
- `review/design-qa` takes static fidelity questions this lens surfaces but does not judge, and supplies the capture set that shows what the surface looked like when it was exercised.
- `design/redesign` consumes the `accessibility_evidence` record for the selected variant at `redesign-review`, and `design/prototyper` repairs that variant before the package gates when it carries a Critical accessibility finding. The four mocks are never graded here: they wire nothing, and the stage runs only when a variant was selected.
