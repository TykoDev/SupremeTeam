# Workflow Reference

## Contents

1. Review sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

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

## Acceptance Checklist

- Blockers are tied to concrete files, interfaces, or tests.
- Cleanup suggestions are clearly separated from merge blockers.
- Any missing baseline or caller context is named explicitly.
- Reviewer burden and code clarity impacts are visible in the packet.

## Contract Notes

- Before/After Evidence: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.

## Collaboration Notes

- `review/code-chief` merges the code-review packet with the sibling lens outputs.
- `review/gatekeeper-code` verifies that the final package preserves the merge blockers and readiness rationale accurately.
