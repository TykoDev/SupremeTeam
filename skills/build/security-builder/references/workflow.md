# Workflow Reference

## Contents

1. Hardening sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Hardening Sequence

1. Confirm the changed surface, data sensitivity, and trust boundaries touched by the submitted build revision.
2. Inspect first-party code, dependencies, and non-first-party surfaces for unsafe patterns, missing controls, and unresolved exposure paths.
3. Verify that each claimed remediation is tied to a focused rerun, scan result, or direct proof on the affected boundary.
4. Package the result so the build gate can see what was fixed, what remains risky, and what requires broader approval.

## Decision Rules

- Prefer the narrowest defensible security claim over a blanket “clean” statement.
- Treat vendored and generated content as higher-trust-cost surfaces that require explicit handling.
- Keep exploit paths visible until proof shows the path is actually closed.
- Escalate when the safe fix requires a design or scope decision beyond the build assignment.

## Acceptance Checklist

- Touched trust boundaries and sensitive surfaces are explicit.
- Dependency and non-first-party risks are addressed or bounded.
- Remediation proof matches the affected finding.
- Residual risk is recorded honestly.

## Contract Notes

- Vendoring detection: Detect generated, vendored, or third-party imported content and treat it with tighter review rules than first-party changes.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- Proactive triggers: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.

## Collaboration Notes

- `build/build-management` — delegating orchestrator; owns scope assignment, remediation routing, and resubmission after security findings are returned.
- `build/gatekeeper-build` — downstream gate; validates that security claims and evidence match the submitted build revision before the package can advance.
