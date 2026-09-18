# Workflow Reference

Read this when a routed build submission is in hand and the question is *what
order to check things in*. `../SKILL.md` states the contract; this file states
the sequence, the verdict rules, and the checklist a verdict is written against.

## Contents

1. Build package validation sequence
2. Verdict rules
3. Acceptance checklist
4. Contract notes
5. Collaboration notes

## Build Package Validation Sequence

1. Confirm the submitted build revision, the implementation scope, and that the declared `boundary` and `owner` match the `build-to-review` row in `../../../gates.yaml` — submitter `build-management`.
2. Run `../scripts/check.py <package-dir> [--prior <prior-verdict>]`. Confirm first that the path exists, is a directory, sits inside the expected build working area, and carries no traversal sequences; the script enforces only the containment half of that — it resolves the path, requires an existing directory, and requires that directory to sit under the working-tree root, exiting 2 without checking anything otherwise. `Path(raw).resolve()` normalises `../` away, so the script never detects traversal as such, and it has no build-working-area concept; both of those remain gatekeeper checks, made by reading the path rather than by the script. It returns the structural facts — required build artifacts present, single-revision lineage, skip-record completeness, blocked-phrase cleanliness, idempotency drift, harness-doctrine §5 structure — as `PASS` / `FAIL` / `UNCHECKED` findings and a `gate_status`. Read those findings into the steps below rather than re-deriving them. It never emits a verdict.
3. Run the boundary validator, `../../../harness/gatekeeper/check.py --boundary build-to-review`, against `../../../gates.yaml`, and confirm the six required evidence keys — `approved_design_revision`, `implementation`, `tests`, `runtime`, `traceability`, `security_evidence` — are present and non-falsy, with `tests` (the test-runner log) and `runtime` (the startup / entry-point smoke log) resolving to hashed probe artifacts under `build/evidence/`. Read the key list from the spec, never from memory; `boundary-evidence.md` carries the per-key detail.
4. Check the shape keys against the evidence keys rather than through them. `implementation` and `tests` exist in both spaces meaning different objects, `security` in the script is `security_evidence` in the spec, and `runtime`, `traceability`, and `approved_design_revision` have no shape-key counterpart at all — so a clean shape check says nothing about three of the six required keys.
5. Check that the package includes implementation evidence, test execution results, security findings or clean bill, and completeness certification for the same revision.
6. Inspect the changed surface for generated, vendored, or third-party content that requires tighter scrutiny than first-party edits.
7. Compare the package narrative against the attached evidence so no blocker clearance depends on summary text alone.
8. Write the verdict only after required fixes, residual risk, and resubmission expectations are explicit, grouped by the owner each failing key belongs to.

## Verdict Rules

- Return `APPROVED` only when the code, tests, security posture, and completeness claim all line up on the same revision.
- Return `REVISE` when the build packet can be repaired by adding missing evidence, correcting stale summaries, or addressing unresolved findings.
- Return `ESCALATE` when the build packet crosses into a design or release decision that build-management cannot settle on its own — and whenever a validator fails to run or exits 2, because an unrun check is not a clean one.
- Reuse a prior verdict only when the revision and evidence set are unchanged.

## Acceptance Checklist

- The declared boundary and `owner` match the spec row being judged.
- All six `build-to-review` evidence keys are present and non-falsy, and `tests` and `runtime` are backed by hashed probe logs at `result.status: pass`.
- `approved_design_revision` names the design revision this build was actually authorised against, and an approval record exists for it.
- Any `security_evidence` waiver is the typed applicability record carrying the one sanctioned reason, and its reason is true of the diff.
- Implementation package and evidence point to the same submitted revision.
- Test and security results are current for the submitted change set.
- Generated or vendored content is explicitly identified and justified.
- The completeness certification is traceable to actual evidence.
- The verdict names the minimum changes required for the next submission, grouped by owner.

## Contract Notes

The contracts this workflow runs under are stated in `../SKILL.md` § Required Contracts. What this workflow adds:

- Batched REVISE: one packet per pass, grouped by owner, so `test-builder`, `health-check`, and `security-builder` never wait on each other.

## Collaboration Notes

- `build/build-management` owns build package assembly, revision deltas, and resubmission after build-gate failures.
- `gatekeeper-admiral` re-validates this boundary afterwards with `--prior build/verdict_build-to-review.json`.

## Cross-references

- `boundary-evidence.md` — per-key record types, artifact-backing, and the one sanctioned waiver.
- `examples.md` — five worked submissions at this boundary.
- `../../../harness/gatekeeper/README.md` — the engine and the deterministic-vs-judgment split.
