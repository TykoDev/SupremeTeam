# Workflow Reference

## Contents

1. Package validation sequence
2. Verdict rules
3. Acceptance checklist
4. Collaboration notes

## Package Validation Sequence

0. Run `scripts/check.py <package-dir> [--prior <prior-verdict>]` first. It returns the deterministic structural facts (the five core lenses present; the CSO lens reported as an `UNCHECKED` conditional artifact; single-revision lineage, skip-record completeness, blocked-phrase cleanliness, idempotency drift, harness-doctrine §5 structure) as `PASS` / `FAIL` / `UNCHECKED` findings and a `gate_status`. Read its findings into the steps below; do not re-derive these checks by hand. The script never emits a verdict and never adjudicates conflicting specialist findings.
1. Confirm the package revision, upstream lineage, and the set of specialist reports it claims to include.
2. Check that the five core review lenses are present, `review/cso` is present or explicitly skipped when security governance/accepted-risk/release-posture claims are in scope, and any skipped optional lens has a written reason tied to the actual scope.
3. Audit the package narrative against the attached evidence so no blocker, approval, or skip depends on an unstated assumption.
4. Write the verdict only after the evidence map, contradictions, and remediation requirements are all visible in one place.

## Verdict Rules

- Return `APPROVED` only when the package is internally consistent and every blocking claim is backed by visible evidence.
- Return `REVISE` when the package can be repaired by adding missing reports, clarifying contradictions, or tightening remediation guidance.
- Return `ESCALATE` when the disagreement requires scope judgment, risk acceptance, or an upstream decision that the review package cannot make on its own.
- Preserve idempotency by comparing the current submission against the previous verdict before issuing a new one.

## Acceptance Checklist

- Core review lenses are present: bug, code, quality, security, and adversarial.
- CSO lens evidence is present or explicitly skipped when security leadership, accepted-risk, release posture, regulated-data governance, or operating-model control claims are in scope.
- Optional lens skips are explicit and justified.
- Each major or critical finding can be traced to a specialist report and evidence anchor.
- Contradictions are preserved instead of normalized away.
- The verdict names the minimum changes required for the next submission.

## Contract Notes

- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.

## Collaboration Notes

- `review/code-chief` owns package assembly, revision deltas, and resubmission.
