# Workflow Reference

Read this when a routed design or redesign submission is in hand and the question
is *what order to check things in*. `../SKILL.md` states the contract; this file
states the sequence, the verdict rules, and the checklist a verdict is written
against.

## Contents

1. Design packet validation sequence
2. Verdict rules
3. Acceptance checklist
4. Contract notes
5. Collaboration notes

## Design Packet Validation Sequence

1. Classify the boundary from the submitted manifest's `boundary` and `owner`, against `../../../gates.yaml` and the Boundary Contract in `../SKILL.md`. `design-to-build` is submitted by `commander`; `redesign-review` by `redesign`. The two evidence sets share only `taste_snapshot`, so a misclassification checks the wrong facts rather than checking them badly.
2. Run the package-shape validator for that boundary — `../scripts/check.py <package-dir>` at `design-to-build`, `../scripts/check_redesign.py <redesign-phase-dir>` at `redesign-review`, each with `[--prior <prior-verdict>]`. Confirm first that the path exists, is a directory, and sits inside the working tree; both scripts enforce the same guard and exit 2 without checking anything when it does not hold. The script returns the structural facts — required files present, conditional artifacts reported `UNCHECKED`, single-revision lineage, skip-record completeness, blocked-phrase cleanliness, idempotency drift, harness-doctrine §5 structure — as `PASS` / `FAIL` / `UNCHECKED` findings and a `gate_status`. Read those findings into the steps below rather than re-deriving them. It never emits a verdict and never judges design coherence.
3. Run the boundary validator, `../../../harness/gatekeeper/check.py --boundary <boundary>`, against `../../../gates.yaml`. `design-to-build` requires `decisions`, `architecture`, `interfaces`, `plan`, `acceptance`, `security_seed`, `stack_lock`, `taste_snapshot`, and `ui_evidence`, with `decisions`, `architecture`, `plan`, and `taste_snapshot` backed by hashed artifacts. `redesign-review` requires `design_inventory`, `taste_grilling`, `taste_snapshot`, `design_directions`, `variant_set`, `parity_evidence`, `rendered_verification`, `accessibility_evidence`, `recommendation`, and `residual_risk`, with only the last three unbacked. Read both key lists from the spec, never from memory; `boundary-evidence.md` carries the per-key detail.
4. Resolve every `UNCHECKED` finding explicitly. At `design-to-build` the conditional artifacts are the API contracts and the frontend/UI handoff; at `redesign-review` it is `rendered_verification`, where an `UNCHECKED` is never a waiver — that key is `no_fallback` at this boundary.
5. Check the packet for alignment across problem framing, constraints, architecture, API contracts, implementation specification, and locked technology choices. At `redesign-review`, judge instead whether the four directions are genuinely differentiated, whether the comparison is honest, and whether the recommendation follows from it.
6. Verify that unresolved decisions are explicit and that the package does not ask downstream stages to discover foundational design intent on their own.
7. Compare the current packet against the previous verdict so the new submission explains what changed; with `--prior`, re-judge only `changed_evidence`.
8. Write the verdict only after the contradictions, missing artifacts, and remediation ownership are explicit, grouped by the owner each failing key belongs to.

## Verdict Rules

- Return `APPROVED` only when the packet is coherent enough that the next design phase or the build phase could consume it without inventing missing structure.
- Return `REVISE` when the packet can be repaired by reconciling contradictions, restoring missing artifacts, or tightening decision ownership.
- Return `ESCALATE` when the packet reaches a product, scope, or risk decision that the design pipeline cannot settle on its own — and whenever a validator exits 2, because an unrun check is not a clean one.
- Reuse a prior verdict only when the packet revision and evidence set are unchanged.

## Acceptance Checklist

- The declared boundary and `owner` match the spec row being judged.
- Phase-exit artifacts for the active boundary are present.
- Every required evidence key for that boundary is present and non-falsy, and each artifact-backed key resolves to a hashed file.
- Any waiver is a typed applicability record for a sanctioned reason; `rendered_verification` at `redesign-review` accepts none, because that boundary lists it under `no_fallback`.
- At `redesign-review`: exactly four variants with unique ids and hashed per-variant artifacts, and one parity probe per variant bound by `inputs` to the inventory.
- Architecture, contracts, and stack locks do not contradict each other.
- API endpoint contracts satisfy the endpoint inventory, schema, auth, error-envelope, idempotency, observability, frontend-handoff, and contract-test requirements when endpoints are in scope.
- Frontend/UI packages include both the shadcn Component Template and UI/UX Handoff sections with route inventory, state matrix, API/data dependency mapping, validation behavior, and responsive evidence when user-facing surfaces are in scope.
- Open questions are explicit and owned.
- Approval lineage matches the submitted revision.
- The verdict names the minimum changes required for the next submission, grouped by owner.

## Contract Notes

The contracts this workflow runs under are stated in `../SKILL.md` § Required Contracts. What this workflow adds:

- Frontend/UI handoff schema: `../../../design-doctrine.md` §9 also governs direction differentiation at `redesign-review`, the boundary the SKILL.md contract does not name.

## Collaboration Notes

- `design/commander` owns design packet assembly, revision deltas, and resubmission after design-gate failures at `design-to-build`.
- `design/redesign` owns the same at `redesign-review`, and carries the chosen variant back into DESIGN.
- `gatekeeper-admiral` re-validates both boundaries afterwards with `--prior` pointed at this gate's verdict record.

## Cross-references

- `boundary-evidence.md` — per-key record types, artifact-backing, and sanctioned waivers.
- `examples.md` — six worked submissions, three at each boundary.
- `../../../harness/gatekeeper/README.md` — the engine and the deterministic-vs-judgment split.
