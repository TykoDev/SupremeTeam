# Workflow Reference

## Contents

1. Boundary validation sequence
2. Verdict rules
3. Acceptance checklist
4. Collaboration notes

## Boundary Validation Sequence

0. Run `scripts/check.py <package-dir> [--prior <prior-verdict>]` first. It returns the deterministic structural facts (package shape, single-revision lineage, one submission id, skip-record completeness, blocked-phrase cleanliness, idempotency drift, harness-doctrine §5 structure) as `PASS` / `FAIL` / `UNCHECKED` findings and a `gate_status`. Read its `FAIL` and `UNCHECKED` findings into the steps below; do not re-derive these checks by hand. The script never emits a verdict.
1. Confirm which handoff is under review: design to build, build to review, review to delivery, or the skill-maker utility path.
2. Check that the package revision, approval lineage, and attached deliverables all belong to the same submission.
3. Verify the artifact set required for the next consumer, including mandatory approvals, revision notes, and any explicit skip justifications.
4. Run the blocked-phrase check on the candidate package and treat package contamination as a boundary failure, not a cosmetic issue.
5. Write the verdict only after the package shape, evidence anchors, and remediation ownership are all explicit.

## Verdict Rules

- Return `APPROVED` only when the package is internally coherent and the next stage could consume it without guessing.
- Return `REVISE` when the owning orchestrator can fix the package by restoring lineage, filling a missing artifact, or cleaning package contamination.
- Return `ESCALATE` when the package conflict requires user judgment, risk acceptance, or a broader scope change.
- Preserve idempotency by comparing the current submission against the previous verdict before issuing a new one.

## Acceptance Checklist

- The declared handoff boundary matches the attached package set.
- Upstream approvals and package revision all point to the same lineage.
- Any skip or defer decision is explicit and evidence-backed.
- Blocked phrases are absent from the submitted package.
- The verdict names the minimum changes required for the next submission.

## Contract Notes

- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- Forbidden-strings scan ownership: Own the scan that rejects blocked phrases and treat any hit as a blocking package defect.

## Collaboration Notes

- `admiral` owns package assembly, revision deltas, and resubmission after cross-stage failures.
