# Workflow Reference

## Contents

1. Build-debugging sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Build-Debugging Sequence

1. Confirm the failing boundary, the current revision, and the environments or tests that expose the defect.
2. Gather the evidence set from logs, traces, diffs, failing assertions, and runtime checks before choosing a theory.
3. Reproduce or narrow the failure until one repair path is supported and adjacent regression risk is visible.
4. Package the result so build-management and gatekeeper-build can see the root cause, repair scope, and residual risk clearly.

## Decision Rules

- Prefer the smallest explanation that accounts for all surviving evidence, not the first explanation that matches part of the symptom.
- Keep mitigation separate from confirmed root cause when the evidence is incomplete.
- Treat environment drift and data-shape differences as part of the debug boundary, not background noise.
- Escalate when the credible fix requires design, architecture, or scope changes outside the assigned build slice.

## Acceptance Checklist

- Failure boundary and affected revision are explicit.
- Evidence sources and reproduction steps are named.
- Root cause or bounded suspect set is supported.
- Candidate fix is tested against the real failure mode.
- Remaining regression risk or escalation conditions are clear.

## Contract Notes

- Before/After Evidence: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- Atomic commit per fix: Keep each fix isolated, explain what changed, and preserve easy rollback boundaries even when several issues are found.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.

## Collaboration Notes

- `build/build-management` — delegating orchestrator; routes debug assignments, receives the root-cause report, and owns resubmission.
- `build/gatekeeper-build` — downstream gate; consumes fix-path evidence and decides whether the build revision can advance.
