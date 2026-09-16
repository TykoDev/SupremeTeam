# Workflow Reference

Read this when comparing captures against an approved design and deciding what
counts as a fidelity break. `../SKILL.md` holds the normative packet shape, the
`rendered_verification` evidence contract, and the save rules; this file holds the
sequence and the judgment calls inside it.

## Contents

1. Visual QA sequence
2. Decision rules
3. Acceptance checklist
4. Contract notes
5. Collaboration notes

## Visual QA Sequence

1. Confirm the supplied snapshot digest equals the digest in the approved design package, then identify the screens, states, tiers, and design-system signals the evidence actually covers.
2. Compare hierarchy, spacing, typography, token use, composition, and finish against that visible target.
3. Record each deviation with the affected screen or tier, why it matters to cohesion, and the most direct correction.
4. Package the fidelity issues, the hashed capture set, and any runtime-behavior handoffs for `review/code-chief`.

## Decision Rules

- Judge only the rendered states that are in evidence; an uncaptured state is an evidence gap, not a pass.
- Keep visual-system drift separate from runtime behavior, which belongs to `review/frontier`: if answering the question requires resizing, tabbing, or interacting rather than looking, it is not this lens.
- Treat missing mocks, token references, or tier captures as evidence gaps rather than silent permission to guess.
- Preserve uncertainty whenever a deviation might be an intentional product decision.
- Resolve conformance against the design-time digest only; current preference state is drift to report, never a review criterion.
- Write a correction into the finding, never into the stylesheet: the captures must keep describing the surface that was reviewed.

## Acceptance Checklist

- Findings name the affected screen, state, or tier.
- Design-system impact is explicit: hierarchy, spacing, typography, or token use.
- Runtime-behavior handoffs to `review/frontier` are separated from visual-fidelity issues.
- The packet stays anchored to captures, and every capture referenced by the `rendered_verification` record is hashed into the manifest.
- Every item carries one of the four shared severities, and a surface that matches returns the clean-pass packet with the capture set still attached.

## Contract Notes

`../SKILL.md` states the contracts; this section records only where each one
lands in the sequence above, so the two documents do not restate each other.

- Read-only over the reviewed surface — binds from step 1 through packaging; the corrections written at step 3 are the deliverable, and editing the surface would invalidate the captures taken at step 1.
- Digest-bound Taste conformance — enforced at step 1, before any comparison: the digest check is the first action of the pass, because a comparison made against the wrong baseline cannot be repaired later in the sequence. The traceability rows filled at step 3 carry the effective preference ids this evidence answers for.
- Before/After Evidence — the "before" is the approved design and the baseline captures; the "after" is the capture set produced in this pass, which is why both are hashed rather than described.
- Shared severity — assigned at step 3, once the affected screen and rule are known, and preserved through packaging.
- Save-Protocol Adherence — the step 4 packet and its captures are what the save path receives; the captures land as hashed evidence because the gate checks the record, not the prose.

## Collaboration Notes

- `review/code-chief` merges the visual QA packet with the frontier and core review outputs and carries the `rendered_verification` record into the gate manifest unchanged.
- `review/gatekeeper-code` checks that important fidelity regressions stay visible in the final review package.
- `review/frontier` takes the runtime half of the interface — reflow, focus, motion, performance — and returns accessibility findings that may explain a visual deviation this lens can only observe.
