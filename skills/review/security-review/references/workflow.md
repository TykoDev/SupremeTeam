# Workflow Reference

## Contents

1. Security review sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Security Review Sequence

1. Map the scoped trust boundaries, privileged paths, secrets, and dependency changes before declaring risk.
2. Inspect the concrete security classes that fit the surface: authn/authz, exposure of sensitive data, injection paths, unsafe defaults, and third-party integration risk.
3. For each major issue, capture attacker path, preconditions, affected assets, and the narrowest viable fix.
4. Package the vulnerabilities and hardening gaps with any adversarial handoffs for `review/code-chief`.

## Decision Rules

- Prefer demonstrated reachability over dependency-list fear alone.
- Separate confirmed exploitation paths from defensive hardening advice.
- Treat generated or vendored code with tighter scrutiny, but keep first-party ownership explicit in the finding.
- Preserve missing runtime or deployment evidence as a conditional boundary rather than assuming the strongest or weakest posture.

## Acceptance Checklist

- Each major issue names the affected trust boundary or asset.
- Reachability and preconditions are explicit for confirmed vulnerabilities.
- Dependency and vendored-code findings distinguish exposure from ownership.
- Conditional risks are called out when deployment evidence is missing.

## Contract Notes

- Vendoring detection: Detect generated, vendored, or third-party imported content and treat it with tighter review rules than first-party changes.
- Before/After Evidence: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.

## Collaboration Notes

- `review/code-chief` merges the security packet with correctness, merge-readiness, and adversarial findings.
- `review/gatekeeper-code` verifies that blocking vulnerabilities and unresolved exposure questions remain visible in the final review package.
