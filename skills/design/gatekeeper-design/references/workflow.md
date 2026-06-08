# Workflow Reference

## Contents

1. Design packet validation sequence
2. Verdict rules
3. Acceptance checklist
4. Collaboration notes

## Design Packet Validation Sequence

0. Run `scripts/check.py <package-dir> [--prior <prior-verdict>]` first. It returns the deterministic structural facts (required design artifacts present; API contracts and frontend/UI handoff reported as `UNCHECKED` conditional artifacts; single-revision lineage, skip-record completeness, blocked-phrase cleanliness, idempotency drift, harness-doctrine §5 structure) as `PASS` / `FAIL` / `UNCHECKED` findings and a `gate_status`. Read its findings into the steps below; do not re-derive these checks by hand. The script never emits a verdict and never judges design coherence.
1. Confirm the active design boundary and the artifact set that phase is required to exit with.
2. Check the packet for alignment across problem framing, constraints, architecture, API contracts, implementation specification, and locked technology choices.
3. Verify that unresolved decisions are explicit and that the package does not ask downstream stages to discover foundational design intent on their own.
4. Compare the current packet against the previous verdict so the new submission explains what changed.
5. Write the verdict only after the contradictions, missing artifacts, and remediation ownership are explicit.

## Verdict Rules

- Return `APPROVED` only when the design packet is coherent enough that the next design phase or the build phase could consume it without inventing missing structure.
- Return `REVISE` when the packet can be repaired by reconciling contradictions, restoring missing artifacts, or tightening decision ownership.
- Return `ESCALATE` when the packet reaches a product, scope, or risk decision that the design pipeline cannot settle on its own.
- Reuse a prior verdict only when the packet revision and evidence set are unchanged.

## Acceptance Checklist

- Phase-exit artifacts for the active boundary are present.
- Architecture, contracts, and stack locks do not contradict each other.
- API endpoint contracts satisfy the endpoint inventory, schema, auth, error-envelope, idempotency, observability, frontend-handoff, and contract-test requirements when endpoints are in scope.
- Frontend/UI packages include both the shadcn Component Template and UI/UX Handoff sections with route inventory, state matrix, API/data dependency mapping, validation behavior, and responsive evidence when user-facing surfaces are in scope.
- Open questions are explicit and owned.
- Approval lineage matches the submitted revision.
- The verdict names the minimum changes required for the next submission.

## Contract Notes

- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- API endpoint contract schema: Use `../architect/references/api-endpoint-design.md` as the required shape for API, webhook, event-ingest, and internal service endpoint evidence.
- Frontend/UI handoff schema: Use `../../design-doctrine.md` as the required shape for component-template and UI/UX handoff evidence.

## Collaboration Notes

- `design/commander` owns design packet assembly, revision deltas, and resubmission after design-gate failures.
