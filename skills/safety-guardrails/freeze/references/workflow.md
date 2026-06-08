# Workflow Reference

## Contents

1. Freeze sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Freeze Sequence

1. Name the boundary to freeze and confirm why it must stop changing.
2. Check for active work inside that boundary and capture any bounded exception that must complete first.
3. Record the frozen state, blocked actions, and release conditions.
4. Route work toward safe surfaces that remain outside the freeze.

## Decision Rules

- Freezes must be specific enough to enforce mechanically or socially.
- Freeze records should stop ambiguous writes, deploys, and deletes inside the protected boundary.
- Exceptions must stay explicit so the freeze is not eroded by side agreements.
- Reuse an active freeze record when it already governs the same boundary and revision context.

## Acceptance Checklist

- Boundary and blocked actions are explicit.
- Release conditions are written down.
- Active overlapping work is addressed directly.
- Safe work outside the freeze is named.

## Contract Notes

- Proactive triggers: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.

## Collaboration Notes

- None required beyond the active task surface.
