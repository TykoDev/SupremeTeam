# Workflow Reference

## Contents

1. Frontend review sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Frontend Review Sequence

1. Identify the visible flows, key states, devices, and breakpoints in scope.
2. Inspect interaction behavior, loading and error handling, accessibility, and performance evidence for those specific flows.
3. Record findings with user impact, reproduction steps, and the affected viewport or state.
4. Package runtime behavior issues and handoffs for `review/code-chief`.

## Decision Rules

- Judge the rendered experience that is actually evidenced, not a hypothetical full application surface.
- Keep accessibility and performance findings tied to concrete interactions, states, or traces.
- Separate runtime behavior failures from visual-fidelity drift when the latter belongs with `review/design-qa`.
- Preserve uncertainty when device, breakpoint, or assistive-technology evidence is incomplete.

## Acceptance Checklist

- Findings name the affected screen, interaction, and breakpoint or state.
- Accessibility and performance issues are backed by observable evidence.
- Visual-only handoffs to `review/design-qa` are called out when appropriate.
- Reproduction steps are clear enough for downstream validation.

## Contract Notes

- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.

## Collaboration Notes

- `review/code-chief` merges the frontier packet with the other review lenses.
- `review/gatekeeper-code` checks that user-facing behavior risks survive the final consolidation intact.
