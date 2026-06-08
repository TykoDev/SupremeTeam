# Workflow Reference

## Contents

1. Guarding sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Guarding Sequence

1. Declare the boundary to protect and the operations that remain allowed inside it.
2. Compare the incoming request to those limits before any write or destructive step is attempted.
3. Record the guard state, blocked actions, and any override rule needed to cross the boundary.
4. Return the guarded next step so work outside the boundary can continue safely.

## Decision Rules

- Guard records must be specific enough to enforce, not broad enough to hide ambiguity.
- A guard is successful only when allowed and blocked actions are both explicit.
- Owner overrides must be verifiable, not implied by context or tone.
- Conflicting guards should be resolved before more work is attempted.

## Acceptance Checklist

- Boundary, blocked actions, and allowed actions are explicit.
- Override rules are visible when applicable.
- The next safe action stays inside the guard limits.
- Conflicts with other guards are recorded.

## Contract Notes

- Proactive triggers: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.

## Collaboration Notes

- None required beyond the active task surface.
