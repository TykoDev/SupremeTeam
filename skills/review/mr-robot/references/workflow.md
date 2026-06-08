# Workflow Reference

## Contents

1. Adversarial review sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Adversarial Review Sequence

1. Map attacker starting points, trust boundaries, privileged actions, and assets worth targeting in the scoped surface.
2. Search for abuse chains that combine weak authorization, unsafe defaults, race conditions, data exposure, or privileged state transitions.
3. Record the chain with preconditions, steps, impact, and the controls that would break it.
4. Package confirmed and conditional exploit paths separately for `review/code-chief`.

## Decision Rules

- Favor chained attacker behavior over isolated lint-style security comments.
- Preserve uncertainty whenever a link in the chain depends on missing runtime or tenancy evidence.
- Keep offensive reasoning safe: describe the path and mitigation without escalating into unsafe reproduction.
- Hand non-chained defensive flaws back to `review/security-review` so the adversarial packet stays focused.

## Acceptance Checklist

- Each major chain names attacker entry point, steps, and impacted asset.
- Confirmed and conditional links are separated clearly.
- Containment or break-the-chain guidance is explicit.
- Cross-handoffs to the defensive security lens are named when needed.

## Contract Notes

- Before/After Evidence: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.

## Collaboration Notes

- `review/code-chief` merges the adversarial packet with correctness, security, and merge-readiness findings.
- `review/gatekeeper-code` verifies that exploit-chain evidence survives consolidation without being softened away.
