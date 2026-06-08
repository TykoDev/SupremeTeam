# Workflow Reference

## Contents

1. Build-pipeline sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Build-Pipeline Sequence

1. Establish the approved design boundary, active scope, and revision baseline the build pipeline must honor.
2. Delegate implementation, test, security, and completeness phases in order, reopening only the affected phase path when a later finding invalidates earlier evidence.
3. Assemble the consolidated build package only when code, tests, security disposition, and completeness certification all align on the same revision.
4. Send the package to `build/gatekeeper-build` with revision history, residual risk, and any bounded exceptions made explicit.

## Decision Rules

- Prefer replay of the affected phase chain over patching contradictory evidence into the final package.
- Treat stale evidence as a blocker even when the latest code looks correct locally.
- Keep phase ownership clear: build-management routes and assembles, specialists author, gatekeeper-build validates.
- Escalate when a required build fix changes the approved design or release contract.

## Acceptance Checklist

- Design input and active scope are explicit.
- Mandatory build phases have current outputs for the submitted revision.
- Non-first-party surfaces are identified and justified.
- The package is coherent enough for downstream review consumers to trust directly.

## Contract Notes

- Proactive triggers: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- Vendoring detection: Detect generated, vendored, or third-party imported content and treat it with tighter review rules than first-party changes.

## Save Instructions Per Phase

When persistence is active (Save Context received from admiral):

1. **Before delegating** a specialist: create `phase-{N}_{skill}/_phase-state.md` with `state: ACTIVE`. Include a `### Save Context` block in the delegation prompt pointing to `skillset-saves/runs/{run-id}/build/phase-{N}_{skill}/`.
2. **After specialist returns**: verify the specialist wrote `deliverable_{name}.md` to the save path.
3. **After gatekeeper-build verdict**: write `phase-{N}_{skill}/gatekeeper-verdict.md` with the full verdict. Update `_phase-state.md` to APPROVED, REVISING, or ESCALATED.
4. **On package consolidation**: write `build/build-package.md` and `build/delegation-log.md` summarizing all phase outcomes.

## Collaboration Notes

- `build/bob-the-builder` owns implementation delivery for the approved scope.
- `build/test-builder` owns automated validation coverage and test evidence.
- `build/security-builder` owns security hardening, dependency scrutiny, and residual security risk.
- `build/cross-check-build-confirm` owns final completeness confirmation before the build gate.
- `build/gatekeeper-build` owns build-readiness validation and resubmission verdicts.
- `session-memory` provides cross-session checkpoints when context pressure rises.
