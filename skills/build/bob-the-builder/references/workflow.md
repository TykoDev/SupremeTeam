# Workflow Reference

## Contents

1. Implementation sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Implementation Sequence

1. Confirm the approved scope, affected modules, and expected evidence for the build boundary.
2. Identify prerequisite gaps before editing anything.
3. Apply the change in the smallest coherent implementation slices you can defend.
4. Run the validation that proves the change works and record any remaining risk honestly.
5. Package the result so the build gate can review concrete evidence instead of promises.

## Decision Rules

- Do not turn a build task into a design rewrite.
- Keep generated or third-party surfaces on a short leash.
- Prefer one clean implementation slice over several entangled fixes.
- Escalate when proving the change would require unauthorized scope growth.

## Acceptance Checklist

- Scope and touched surfaces are explicit.
- Validation evidence matches the submitted change set.
- Residual risks or blocked dependencies are recorded.
- Non-first-party content is clearly identified.
- The package is ready for build-gate review.

## Contract Notes

- Atomic commit per fix: Keep each fix isolated, explain what changed, and preserve easy rollback boundaries even when several issues are found.
- Vendoring detection: Detect generated, vendored, or third-party imported content and treat it with tighter review rules than first-party changes.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.

## Collaboration Notes

- `build/build-management` owns scoped implementation assignment and package assembly.
- `build/gatekeeper-build` owns build-readiness validation for the returned package.
