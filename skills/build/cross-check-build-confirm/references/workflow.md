# Workflow Reference

## Contents

1. Build confirmation sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Build Confirmation Sequence

1. List the required build outputs, approval lineage, and declared scope for the package under review.
2. Match each deliverable to concrete proof: code output, tests, security evidence, and package metadata.
3. Flag missing or contradictory artifacts before the package moves to the build gate.
4. Publish a confirmation packet that the gate can consume without guessing what is complete.

## Decision Rules

- Completeness claims must map to visible deliverables.
- Missing proof is a blocker even when the implementation looks finished locally.
- Contradictory build evidence should stay visible until reconciled.
- Scope drift belongs with the build owner, not hidden inside the confirmation pass.

## Acceptance Checklist

- Required deliverables are listed explicitly.
- Each deliverable has matching proof.
- Contradictions and blockers are recorded.
- Downstream review readiness is stated narrowly and honestly.

## Contract Notes

- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- Before/After Evidence: Capture observable state before and after each intervention so improvements can be verified instead of asserted.

## Collaboration Notes

- `build/build-management` — delegating orchestrator; owns remediation routing and resubmission after gaps are identified.
- `build/gatekeeper-build` — downstream gate; consumes the confirmation packet and issues the advance/revise verdict.
