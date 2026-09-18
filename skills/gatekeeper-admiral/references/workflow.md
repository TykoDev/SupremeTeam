# Workflow Reference

Read this when a routed submission is in hand and the question is *what order to
check things in*. `../SKILL.md` states the contract; this file states the
sequence, the verdict rules, and the checklist a verdict is written against.

## Contents

1. Boundary validation sequence
2. Verdict rules
3. Acceptance checklist
4. Contract notes
5. Collaboration notes

## Boundary Validation Sequence

1. Confirm which of the ten boundaries is under review, against `../../gates.yaml` and the Boundary Contract in `../SKILL.md`: `design-to-build`, `redesign-review`, `build-to-review`, `review-to-delivery`, `security-review`, `investigation-review`, `qa-review`, `taste-review`, `skill-maker-to-delivery`, or `deploy-readiness`. The declared `boundary` and `owner` must match the spec's submitter for that row; a mismatch is a failure, not a labelling slip.
2. Run the boundary validator for that boundary — `../../harness/gatekeeper/check.py --boundary <boundary> --package <phase>/manifest.json` — with `--prior` pointed at the phase gatekeeper's `verdict_<boundary>.json` when one exists. Read the required-evidence, artifact-backed, and waiver lists from the spec, never from memory; `boundary-evidence.md` carries them per boundary. A boundary-level `no_fallback` entry — `mock_rendering` at `redesign-review` — overrides any global fallback for that key; note that the same boundary *replaces* the list for `rendered_verification` (and for `selected_variant`, `parity_evidence`, `accessibility_evidence`) with two deferred/merge reasons, which shadow the global entry rather than extending it — the global `rendered_verification` reason is not sanctioned at that boundary.
3. Run the package-shape validator, `../scripts/check.py <package-dir> [--prior <prior-verdict>]`, against the run's `delivery/` directory. Confirm first that the path exists, is a directory, and sits inside the working tree; the script enforces the same guard and exits 2 without checking anything when it does not hold. It returns the structural facts — package shape, single-revision lineage, one submission id, skip-record completeness, blocked-phrase cleanliness, idempotency drift, harness-doctrine §5 structure — as `PASS` / `FAIL` / `UNCHECKED` findings and a `gate_status`. Read those findings into the steps below rather than re-deriving them by hand. Neither script emits a verdict.
4. Check that the package revision, approval lineage, and attached deliverables all belong to the same submission.
5. Verify the artifact set the next consumer needs, including mandatory approvals, revision notes, and any explicit skip justifications.
6. Treat any blocked-phrase hit as package contamination and a boundary failure, not a cosmetic issue.
7. Write the verdict only after the package shape, evidence anchors, and remediation ownership are all explicit and grouped by the owner each failing key belongs to.

## Verdict Rules

- Return `APPROVED` only when the package is internally coherent and the next stage could consume it without guessing.
- Return `REVISE` when the owning orchestrator can fix the package by restoring lineage, filling a missing artifact, or cleaning package contamination.
- Return `ESCALATE` when the package conflict requires user judgment, risk acceptance, or a broader scope change — and whenever a validator exits 2, because an unrun check is not a clean one.
- Preserve idempotency by comparing the current submission against the previous verdict before issuing a new one.

## Acceptance Checklist

- The declared handoff boundary matches the attached package set, and the declared `owner` is the spec submitter for that boundary.
- Every required evidence key for the boundary is present and non-falsy; each artifact-backed key resolves to a hashed file.
- Any waiver is a typed applicability record carrying a sanctioned reason, and no waiver is granted on a key the boundary lists under `no_fallback`.
- Upstream approvals and package revision all point to the same lineage.
- Any skip or defer decision is explicit and evidence-backed, with an owner and a reopen trigger where the finding policy requires them.
- Blocked phrases are absent from the submitted package.
- The verdict names the minimum changes required for the next submission, grouped by owner.

## Contract Notes

The contracts this workflow runs under are stated in `../SKILL.md` § Required Contracts.

## Collaboration Notes

- `admiral` owns package assembly, revision deltas, and resubmission after cross-stage failures.
- The phase gatekeepers — `design/gatekeeper-design`, `build/gatekeeper-build`, `review/gatekeeper-code` — run first and leave the `verdict_<boundary>.json` this gate consumes through `--prior` and never overwrites.

## Cross-references

- `boundary-evidence.md` — per-boundary artifact-backed keys, typed records, and sanctioned waivers.
- `examples.md` — seven worked submissions across six boundaries.
- `../../harness/gatekeeper/README.md` — the engine and the deterministic-vs-judgment split.
