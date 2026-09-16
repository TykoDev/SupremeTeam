# Workflow Reference

Read this when judging a diff for merge and deciding what blocks. `../SKILL.md`
holds the normative packet shape, severities, and save rules; this file holds the
sequence and the judgment calls inside it.

## Contents

1. Review sequence
2. Decision rules
3. Acceptance checklist
4. Contract notes
5. Collaboration notes

## Review Sequence

1. Read the actual diff and identify which interfaces, modules, and tests are affected by the change.
2. Inspect merge readiness through concrete lenses: readability, API stability, failure handling, test coverage, and reviewer load.
3. Split the report into blockers, major concerns, and optional cleanups so urgent issues are not buried under style commentary.
4. Package the findings with file anchors, rationale, and handoffs for `review/code-chief`.

## Decision Rules

- Judge the submitted change, not an imagined rewrite of the whole system.
- Prefer review comments that affect merge safety, future comprehension, or contract stability over cosmetic preferences.
- Mark missing caller context or migration evidence as a readiness gap when interface changes are visible.
- Keep generated or mechanical churn from distorting the signal in the report.
- Write a cleanup as a fix direction, never as an edit: the diff under judgment ends the pass byte-identical to the one submitted.

## Acceptance Checklist

- Blockers are tied to concrete files, interfaces, or tests.
- Cleanup suggestions are clearly separated from merge blockers.
- Any missing baseline or caller context is named explicitly.
- Reviewer burden and code clarity impacts are visible in the packet.
- Every item carries one of the four shared severities, and a diff with nothing to report returns the clean-pass packet rather than nothing.
- The reviewed files are unmodified, and the packet is saved under the filename the gate slot matches.

## Contract Notes

`../SKILL.md` states the contracts; this section records only where each one
lands in the sequence above, so the two documents do not restate each other.

- Read-only over the reviewed surface — binds from step 1 through packaging; the fix directions written at step 3 are the deliverable, and no step of this sequence touches the diff it judges.
- Before/After Evidence — the "before" is the submitted diff and the test output read at step 2, recorded so a later claim that the revision improved something can be checked instead of believed.
- Shared severity — assigned at step 3, when merge impact is known, and preserved unchanged through step 4.
- Save-Protocol Adherence — the step 4 packet is what the save path receives, under the filename `../SKILL.md` mandates for the gate slot.

## Collaboration Notes

- `review/code-chief` merges the code-review packet with the sibling lens outputs and owns the consolidated recommendation the gate reads.
- `review/gatekeeper-code` verifies that the final package preserves the merge blockers and readiness rationale accurately.
- `review/bug-review` takes exhaustive correctness work this lens surfaces but does not chase, and `review/quality-review` takes drift that outlives this diff.
