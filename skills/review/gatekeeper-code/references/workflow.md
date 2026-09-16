# Workflow Reference

Read this when a routed review submission is in hand and the question is *what
order to check things in*. `../SKILL.md` states the contract; this file states
the sequence, the verdict rules, and the checklist a verdict is written against.

## Contents

1. Package validation sequence
2. Verdict rules
3. Acceptance checklist
4. Contract notes
5. Collaboration notes

## Package Validation Sequence

1. Confirm the package revision, upstream lineage, the set of specialist reports it claims to include, and that the declared `boundary` and `owner` match the `review-to-delivery` row in `../../../gates.yaml` — submitter `code-chief`.
2. Run `../scripts/check.py <package-dir> [--prior <prior-verdict>]`. Confirm first that the path exists, is a directory, and sits inside the working tree; the script enforces the same guard and exits 2 without checking anything when it does not hold. It returns the structural facts — the five core lenses present, the CSO lens reported as an `UNCHECKED` conditional artifact, single-revision lineage, skip-record completeness, blocked-phrase cleanliness, idempotency drift, harness-doctrine §5 structure — as `PASS` / `FAIL` / `UNCHECKED` findings and a `gate_status`. Read those findings into the steps below rather than re-deriving them. It never emits a verdict and never adjudicates conflicting specialist findings.
3. Run the boundary validator, `../../../harness/gatekeeper/check.py --boundary review-to-delivery`, against `../../../gates.yaml` and confirm the six required evidence keys — `review_verdict`, `findings`, `executed_probes`, `rendered_verification`, `residual_risk`, `revision_lineage` — are present and non-falsy, with `executed_probes` and `rendered_verification` resolving to hashed artifacts whose `inputs` still match their sources by sha256. Read the key list from the spec, never from memory; `boundary-evidence.md` carries the per-key detail.
4. Keep the two key spaces apart. The shape keys (`lens_bug`, `lens_code`, `lens_quality`, `lens_security`, `lens_adversarial`, `lens_cso`) share no name with the evidence keys, so a clean lens sweep is compatible with every required evidence key being absent. Neither result substitutes for the other.
5. Check that the five core review lenses are present, `review/cso` is present or explicitly skipped when security governance, accepted-risk, or release-posture claims are in scope, and any skipped optional lens has a written reason tied to the actual scope.
6. Audit the package narrative against the attached evidence so no blocker, approval, or skip depends on an unstated assumption.
7. Route each failing key to its owner. `rendered_verification` is owned by `design-qa`, not by the submitter, so a failure on that key routes there; every other key at this boundary is `code-chief`'s.
8. Write the verdict only after the evidence map, contradictions, and remediation requirements are all visible in one place, grouped by owner.

## Verdict Rules

- Return `APPROVED` only when the package is internally consistent and every blocking claim is backed by visible evidence.
- Return `REVISE` when the package can be repaired by adding missing reports, re-running stale evidence, clarifying contradictions, or tightening remediation guidance. Input-hash drift belongs here: the evidence is stale, not disputed.
- Return `ESCALATE` when the disagreement requires scope judgment, risk acceptance, or an upstream decision that the review package cannot make on its own — and whenever a validator fails to run or exits 2, because an unrun check is not a clean one.
- Preserve idempotency by comparing the current submission against the previous verdict before issuing a new one.

## Acceptance Checklist

- The declared boundary and `owner` match the spec row being judged.
- All six `review-to-delivery` evidence keys are present and non-falsy, and `executed_probes` and `rendered_verification` are backed by hashed artifacts at `result.status: pass` (or `inferred`, with its limitation statement, for a render).
- Every `inputs` binding still matches its source by sha256 — no input-hash drift.
- Any `rendered_verification` waiver is the typed applicability record carrying the one sanctioned reason, and its reason is true of the diff.
- `review_verdict` carries its challenge record whenever it is not APPROVED, and the challenge survives into the verdict record.
- Core review lenses are present: bug, code, quality, security, and adversarial.
- CSO lens evidence is present or explicitly skipped when security leadership, accepted-risk, release posture, regulated-data governance, or operating-model control claims are in scope.
- Optional lens skips are explicit and justified.
- Each major or critical finding can be traced to a specialist report and evidence anchor.
- Contradictions are preserved instead of normalized away.
- The verdict names the minimum changes required for the next submission, grouped by owner.

## Contract Notes

- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- CSO lens coverage: A security-leadership, accepted-risk, or release-posture claim in the package puts `review/cso` in scope, and the conditional `UNCHECKED` becomes a `REVISE` unless a validated skip record exists.
- Batched REVISE: one packet per pass, grouped by owner, so `design-qa` and `code-chief` never wait on each other.

## Collaboration Notes

- `review/code-chief` owns package assembly, revision deltas, and resubmission.
- `design-qa` owns `rendered_verification` and is the destination for any failure on that key.
- `gatekeeper-admiral` re-validates this boundary afterwards with `--prior review/verdict_review-to-delivery.json`.

## Cross-references

- `boundary-evidence.md` — per-key record types, artifact-backing, input-hash drift, and the one sanctioned waiver.
- `examples.md` — five worked submissions at this boundary.
- `../../../harness/gatekeeper/README.md` — the engine and the deterministic-vs-judgment split.
