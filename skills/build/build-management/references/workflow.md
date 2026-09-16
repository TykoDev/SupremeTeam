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

When persistence is active (Save Context received from admiral), the phase lead
writes only the classes `../../../save-ownership.yaml` grants it under
`skillset-saves/runs/{run-id}/build/`:

1. **Before delegating** a specialist: checkpoint through `session-memory` (`save_run.py checkpoint --expect-revision <n> --set active_owner=build-management --set phase_state=BUILD_ACTIVE`) and include the canonical `### Save Context` block naming the specialist as `Owner` and its `reports/`, `artifacts/`, or `evidence/` destination as `Expected artifact`. Do not create per-specialist directories or phase-state files.
2. **After specialist returns**: verify the named artifact exists at its destination (for example `reports/report_implementation.md` or `evidence/tests.log`), then checkpoint with `--evidence <path>` so its sha256 is registered.
3. **After gatekeeper-build verdict**: the gatekeeper has written `build/verdict_build-to-review.json`; record the semantic verdict and next action in the next checkpoint (`--set phase_state=BUILD_GATE_PENDING`, `BUILD_GATE_REVISE`, or the next active state). Never edit the verdict record.
4. **On package consolidation**: write `build/reports/build-package.md` and `build/manifest.json` (schema 2) summarizing all phase outcomes with hashes; admiral submits that manifest to `gatekeeper-admiral`.

## Collaboration Notes

- `build/bob-the-builder` owns implementation delivery for the approved scope.
- `build/test-builder` owns automated validation coverage and test evidence.
- `build/security-builder` owns security hardening, dependency scrutiny, and residual security risk.
- `build/cross-check-build-confirm` owns final completeness confirmation before the build gate.
- `build/gatekeeper-build` owns build-readiness validation and resubmission verdicts.
- `session-memory` provides cross-session checkpoints when context pressure rises.
