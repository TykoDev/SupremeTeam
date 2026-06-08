# Workflow Reference

## Contents

1. Visual QA sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Visual QA Sequence

1. Identify the screens, states, breakpoints, and design-system signals that the evidence actually covers.
2. Compare hierarchy, spacing, typography, token use, composition, and interaction polish against that visible target.
3. Record each deviation with the affected screen or breakpoint, why it matters to cohesion or polish, and the most direct correction.
4. Package the fidelity issues and any runtime-behavior handoffs for `review/code-chief`.

## Decision Rules

- Judge only the rendered or recorded states that are in evidence.
- Keep visual-system drift separate from runtime behavior bugs handled by `review/frontier`.
- Treat missing mocks, token references, or breakpoint captures as evidence gaps rather than silent permission to guess.
- Preserve uncertainty whenever a deviation might be an intentional product decision.

## Acceptance Checklist

- Findings name the affected screen, state, or breakpoint.
- Design-system impact is explicit: hierarchy, spacing, typography, token use, or motion.
- Runtime behavior handoffs are separated from visual-fidelity issues.
- The packet stays anchored to screenshots, recordings, or rendered UI evidence.

## Contract Notes

- Before/After Evidence: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.

## Collaboration Notes

- `review/code-chief` merges the visual QA packet with the frontier and core review outputs.
- `review/gatekeeper-code` checks that important fidelity regressions stay visible in the final review package.
