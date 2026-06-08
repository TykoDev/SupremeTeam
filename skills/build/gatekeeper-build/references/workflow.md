# Workflow Reference

## Contents

1. Build package validation sequence
2. Verdict rules
3. Acceptance checklist
4. Collaboration notes

## Build Package Validation Sequence

0. Run `scripts/check.py <package-dir> [--prior <prior-verdict>]` first. It returns the deterministic structural facts (required build artifacts present, single-revision lineage, skip-record completeness, blocked-phrase cleanliness, idempotency drift, harness-doctrine §5 structure) as `PASS` / `FAIL` / `UNCHECKED` findings and a `gate_status`. Read its findings into the steps below; do not re-derive these checks by hand. The script never emits a verdict.
1. Confirm the submitted build revision, implementation scope, and required artifacts for the build-to-review boundary.
2. Check that the package includes implementation evidence, test execution results, security findings or clean bill, and completeness certification for the same revision.
3. Inspect the changed surface for generated, vendored, or third-party content that requires tighter scrutiny than first-party edits.
4. Compare the package narrative against the attached evidence so no blocker clearance depends on summary text alone.
5. Write the verdict only after required fixes, residual risk, and resubmission expectations are explicit.

## Verdict Rules

- Return `APPROVED` only when the code, tests, security posture, and completeness claim all line up on the same revision.
- Return `REVISE` when the build packet can be repaired by adding missing evidence, correcting stale summaries, or addressing unresolved findings.
- Return `ESCALATE` when the build packet crosses into a design or release decision that build-management cannot settle on its own.
- Reuse a prior verdict only when the revision and evidence set are unchanged.

## Acceptance Checklist

- Implementation package and evidence point to the same submitted revision.
- Test and security results are current for the submitted change set.
- Generated or vendored content is explicitly identified and justified.
- The completeness certification is traceable to actual evidence.
- The verdict names the minimum changes required for the next submission.

## Contract Notes

- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- Vendoring detection: Detect generated, vendored, or third-party imported content and treat it with tighter review rules than first-party changes.

## Collaboration Notes

- `build/build-management` owns build package assembly, revision deltas, and resubmission after build-gate failures.
