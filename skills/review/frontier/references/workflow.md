# Workflow Reference

Read this when exercising an interface at runtime and deciding what an observation
supports. `../SKILL.md` holds the normative packet shape, the gate-evidence table,
and the save rules; this file holds the sequence and the judgment calls inside it.

## Contents

1. Frontend review sequence
2. Decision rules
3. Acceptance checklist
4. Contract notes
5. Collaboration notes

## Frontend Review Sequence

1. Confirm the snapshot digest against the approved design package, then identify the visible flows, key states, devices, and tiers in scope.
2. Exercise interaction behavior, responsive reflow across the six tiers, loading and error handling, accessibility paths, and performance for those specific flows.
3. Record findings with user impact, reproduction steps, and the affected tier or state.
4. Package runtime behavior issues, the traces behind them, and handoffs for `review/code-chief`.

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
- `design/redesign` consumes the per-variant `accessibility_evidence` record at `redesign-review`, and `design/prototyper` repairs any variant carrying a Critical accessibility finding before comparison.
