# Workflow Reference

Read this when running the correctness pass and deciding what counts as a
finding. `../SKILL.md` holds the normative packet shape, severities, and save
rules; this file holds the sequence and the judgment calls inside it.

## Contents

1. Defect-mapping sequence
2. Decision rules
3. Acceptance checklist
4. Contract notes
5. Collaboration notes

## Defect-Mapping Sequence

1. Identify the stateful surfaces in scope: mutable objects, caches, queues, retries, transactions, and persistence boundaries.
2. Walk the highest-risk correctness classes first: null handling, ordering mistakes, stale reads, missed writes, invalid assumptions, and crash recovery.
3. Capture each finding with the triggering condition, observable failure, blast radius, and smallest credible fix direction.
4. Package repro notes, unverified questions, and cross-lens handoffs for `review/code-chief`.

## Decision Rules

- Prefer deterministic failure paths over broad code-smell commentary.
- Treat missing runtime evidence as uncertainty, not proof that a bug exists.
- Collapse duplicate symptoms into one root-cause finding when they share the same broken invariant.
- Hand security-only or UX-only issues to the correct specialist instead of stretching the correctness lens beyond scope.
- Record a fix as a direction, never as an edit: the reviewed tree ends the pass exactly as it started.

## Acceptance Checklist

- Each major finding names the broken invariant or failure path.
- File, function, test, or artifact anchors are explicit.
- Repro notes or evidence reasoning are visible for every blocking issue.
- Out-of-scope dependencies and unverified assumptions are called out separately.
- Every item carries one of the four shared severities, and a pass with none returns the clean-pass packet rather than nothing.
- The reviewed files are unmodified, and the packet is saved under the filename the gate slot matches.

## Contract Notes

`../SKILL.md` states the contracts; this section records only where each one
lands in the sequence above, so the two documents do not restate each other.

- Read-only over the reviewed surface — applies from step 1 to the last line of the packet; the fix direction captured at step 3 is the deliverable, and no step of this sequence writes into the reviewed tree.
- Before/After Evidence — the "before" is captured at step 1, before any claim is written, so a later assertion that state changed has a baseline to be measured against.
- Shared severity — assigned at step 3, once trigger and impact are known, and not re-sorted while packaging at step 4.
- Save-Protocol Adherence — the step 4 packet is what the save path receives, under the filename `../SKILL.md` mandates for the gate slot.

## Collaboration Notes

- `review/code-chief` consumes the correctness packet, merges it with the sibling review lenses, and owns the graded `findings` record the gate reads.
- `review/gatekeeper-code` validates that blocking correctness defects are reflected accurately in the final review package.
- `review/code-review` receives merge-readiness questions this lens surfaces but does not judge, and returns diff-level context when a defect's reachability depends on the change boundary.
