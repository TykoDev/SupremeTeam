# Workflow Reference

## Contents

1. Defect-mapping sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

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

## Acceptance Checklist

- Each major finding names the broken invariant or failure path.
- File, function, test, or artifact anchors are explicit.
- Repro notes or evidence reasoning are visible for every blocking issue.
- Out-of-scope dependencies and unverified assumptions are called out separately.

## Contract Notes

- Before/After Evidence: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.

## Collaboration Notes

- `review/code-chief` consumes the correctness packet and merges it with the sibling review lenses.
- `review/gatekeeper-code` validates that blocking correctness defects are reflected accurately in the final review package.
