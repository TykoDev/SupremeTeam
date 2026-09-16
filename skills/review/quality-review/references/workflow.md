# Workflow Reference

Read this when assessing structural health and deciding what counts as drift.
`../SKILL.md` holds the normative packet shape, the severity mapping for blocking
and tracked debt, and the save rules; this file holds the sequence and the
judgment calls inside it.

## Contents

1. Structural review sequence
2. Decision rules
3. Acceptance checklist
4. Contract notes
5. Collaboration notes

## Structural Review Sequence

1. Identify the boundaries in scope: modules, layers, configuration seams, and shared abstractions.
2. Compare the current change against those boundaries for duplication, drift, ownership confusion, and long-term maintenance cost.
3. Write findings that explain why the issue will increase future delivery cost or fragility, not just why the reviewer dislikes the shape.
4. Package the maintainability concerns with pragmatic remediation order for `review/code-chief`.

## Decision Rules

- Judge architecture drift against the existing system commitments, not against a theoretical greenfield target.
- Distinguish one-off cleanup from structural debt that will recur across future changes.
- Prefer evidence of change friction, configuration sprawl, or ownership confusion over abstract design purity arguments.
- Merge duplicate symptoms when they come from the same layering or abstraction failure.
- Carry an inferred architecture as an inference, labelled, so a reader can challenge the premise instead of inheriting it.
- Write a refactor as a remediation direction, never as an edit: the assessed modules end the pass unchanged.

## Acceptance Checklist

- Structural findings name the affected modules, layers, or abstractions.
- Long-term cost is explicit for each major issue.
- Lower-confidence items are graded Minor with the confidence gap stated, rather than raised to Major.
- Every deferred Major carries the owner and reopen trigger that make it tracked debt.
- Remediation order is practical for the current system constraints.
- A surface assessed with nothing found returns the clean-pass packet, and the packet is saved under the filename the gate slot matches.

## Contract Notes

`../SKILL.md` states the contracts; this section records only where each one
lands in the sequence above, so the two documents do not restate each other.

- Read-only over the reviewed surface — binds from step 1 through packaging; the remediation order produced at step 4 is the deliverable, and no step of this sequence restructures the code it judges.
- Before/After Evidence — the "before" is the boundary map built at step 1, which is what a later claim of reduced coupling is measured against.
- Shared severity — assigned at step 3 using the grade table in `../SKILL.md`, so blocking and tracked debt stay inside the four tiers instead of becoming a parallel vocabulary.
- Save-Protocol Adherence — the step 4 packet is what the save path receives, under the filename `../SKILL.md` mandates for the gate slot.

## Collaboration Notes

- `review/code-chief` consumes the maintainability packet, merges it with correctness, security, and adversarial findings, and owns the graded record the gate reads.
- `review/gatekeeper-code` checks that architecture drift and debt findings are preserved accurately in the final package.
- `review/code-review` takes the subset of drift that already blocks the diff in flight; this lens keeps the part that outlives it.
