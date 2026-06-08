# Workflow Reference

## Contents

1. Security-oversight sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Security-Oversight Sequence

1. Confirm the business surface under review: product, release, operating model, or a specific high-risk decision.
2. Build the control map across trust boundaries, identity paths, secrets, data handling, dependencies, and operator workflows.
3. Distinguish immediate exploitability from broader governance debt so the review gives leadership a usable prioritization model.
4. Package the result as a security-chief packet for `review/code-chief` with evidence, compensating controls, accepted-risk candidates, and unresolved ownership decisions.

## Decision Rules

- Prefer the control boundary that actually governs the live system over the cleanest diagram or intended process.
- Treat third-party, vendored, and generated surfaces as part of the attack path whenever they influence the protected asset.
- Keep tactical bug findings distinct from strategic security-governance gaps.
- Escalate when the right mitigation requires policy, staffing, vendor, or product decisions beyond the current engineering scope.

## Acceptance Checklist

- The security surface and protected assets are explicit.
- Trust boundaries and control assumptions are named.
- Findings are prioritized by exploitability, blast radius, and decision owner.
- Compensating controls are evaluated honestly rather than credited automatically.
- Next actions clearly separate engineering fixes from leadership calls.

## Contract Notes

- Vendoring detection: Detect generated, vendored, or third-party imported content and treat it with tighter review rules than first-party changes.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- Proactive triggers: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.

## Collaboration Notes

- `review/code-chief` schedules this lens when the review scope includes security governance, accepted-risk decisions, release posture, operating model controls, or explicit CSO-style review language.
- `review/security-review` owns tactical defensive flaws; `review/cso` consumes those findings when they reveal broader control gaps or accepted-risk decisions.
- `review/mr-robot` owns attacker-chain narratives; `review/cso` consumes those findings when leadership must govern blast radius, compensating controls, or residual risk.
- `review/gatekeeper-code` validates that CSO findings are present when the consolidated package claims security leadership signoff or accepted-risk readiness.
