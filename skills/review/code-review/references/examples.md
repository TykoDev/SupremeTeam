# Example Invocations

Five passes — four fresh and one REVISE delta — each rendered in the full
packet shape `../SKILL.md` mandates:
Outcome, Evidence, Findings, Open risks, Next action, Revision, in that order and
with no verdict, because this lens owns no gate (`../../../execution-contract.md`,
clause 6). The graded passes carry the shape too, not just the clean one — a pass
with findings is where the merge recommendation and the evidence behind it have
to travel together, and an example that drops the fields there teaches the packet
as decoration. Severities are the shared four tiers —
`Critical | Major | Minor | Info` — and nothing else, and every finding carries its
status. A go recommendation never sits beside an `open` Critical or Major:
`../../../gates.yaml` `finding_policy` blocks the gate on either until it is
verified, not-applicable with a reason, or (a Major only) deferred by `code-chief`
with a named owner and reopen trigger.

## Example 1

**User request:** review this diff in the feature-flag rollout branch

**Output:**
- Outcome: code-review, r1, merge recommendation: no-go, 2 findings: 1 Critical, 0 Major, 1 Minor, 0 Info.
- Evidence: the full diff range `main...flags/rollout` judged hunk by hunk — flag evaluation, the fallback branch, and the tests added with them — with each changed call site read against its caller. `npm test -- flags` and the lint output from the build package were read as supplied. The regenerated lockfile was excluded as mechanical churn.
- Findings:
  - `CR-01` | Critical | open | `flags/evaluate.ts:57` | the new helper changes the default flag behavior while two call sites stay on the prior semantic, so the rollout ships two meanings of the same flag | migrate both call sites in this change, or gate the new default behind an explicit opt-in.
  - `CR-02` | Minor | open | `flags/evaluate.ts:71` | the inline conditionals would read better as a named predicate, but only once the semantic mismatch is resolved; extracting them first would hide it | fold into the `CR-01` fix rather than landing separately.
- Open risks: no rollout plan accompanies the diff, so whether the two semantics ever coexist in production is a deployment question this lens cannot answer from the change alone.
- Next action: `review/code-chief` returns `CR-01` to the change owner; the merge stays blocked until it is resolved.
- Revision: r1.

## Example 2

**User request:** check merge readiness for the billing service diff

**Output:**
- Outcome: code-review, r2, merge recommendation: no-go, 2 findings: 0 Critical, 1 Major, 0 Minor, 1 Info.
- Evidence: billing service handlers, the migration script, and the updated retry tests, read across the supplied diff range; the serializer's existing contract test read for the field it does not cover; the migration read forward and backward for reversibility. Generated protobuf stubs were excluded.
- Findings:
  - `CR-03` | Major | open | `billing/serializer.py:31` | the diff adds an API field with no serializer contract test, so the wire format changes without verification | extend the existing contract test rather than adding a new suite.
  - `CR-04` | Info | open | `migrations/0042_add_invoice_ref.py` | the migration is reversible and idempotent as written | recorded so the next round does not re-litigate it.
- Open risks: no consumer inventory accompanies the diff, so whether any client parses the wire format strictly is unknown; the API consumer list would answer it.
- Next action: `review/code-chief` returns `CR-03` to the change owner before the gate.
- Revision: r2.

## Example 3

**User request:** audit this diff in the controller refactor

**Output:**
- Outcome: code-review, r3, merge recommendation: no-go, 2 findings: 0 Critical, 1 Major, 0 Minor, 1 Info.
- Evidence: the controller refactor plus the error-mapping utility used by two endpoints, read hunk by hunk against both call sites; the endpoint tests run green in the build package and read for the exception path they do not exercise. Untouched sibling controllers were excluded as outside the diff.
- Findings:
  - `CR-05` | Major | open | `http/error_map.go:88` | one exception path drops the request id, so incidents on that branch lose traceability | thread the id through the mapper rather than reconstructing it at the edge.
  - `CR-06` | Info | open | `http/controllers/orders.go:120` | response status mapping is clearer than the code it replaces | handed to `review/quality-review` to judge whether the refactor also moves layering drift; no merge consequence is claimed here.
- Open risks: whether the incident tooling already relies on the dropped request id is not visible in the diff, so how much `CR-05` costs in production is unmeasured. That changes its priority, not its status: an `open` Major blocks the gate.
- Next action: `review/code-chief` returns `CR-05` to the change owner, or records it in `findings` as `deferred` with a named owner and reopen trigger if the change ships without the fix; it hands `CR-06` to `review/quality-review`. A deferral is `code-chief`'s decision, so this lens's recommendation stays no-go until one of the two happens.
- Revision: r3.

## Example 4 — clean pass

**User request:** is this good to merge — the retry-timeout constant change

**Output:**
- Outcome: code-review clean — go, 0 findings across a 2-file, 11-line diff.
- Evidence: both hunks read against their callers; the timeout constant is referenced in three places, all updated; the targeted suite ran green in the build package; the regenerated lockfile was excluded as mechanical churn.
- Findings: (none).
- Open risks: no load evidence accompanies the new timeout, so the change is judged safe to merge but not proven to improve the symptom that prompted it.
- Next action: none from this lens.
- Revision: r2.

## Example 5 — a REVISE delta pass

The round after Example 1. `review/code-chief` sub-delegates the part of the
`review-to-delivery` REVISE group this lens owns; `changed_evidence` names
`flags/evaluate.ts` and `flags/tests/test_evaluate.ts`.

**User request:** re-review the flag rollout diff against the REVISE packet

**Output:**
- Outcome: code-review delta, r2 <- r1, merge recommendation: go, 2 findings verified (`CR-01`, `CR-02`), 1 new out-of-delta (`CR-03`).
- Evidence: only the two paths in `changed_evidence`, plus the two call sites `CR-01` named because the finding's resolution is a claim about them. The rest of `main...flags/rollout` keeps its r1 judgment and was not re-read; the lockfile stays excluded.
- Findings:
  - `CR-01` | Critical | verified | `flags/evaluate.ts:57` | both call sites now take the new default, and the added table test covers the two semantics against one expectation. Same id and severity; the status moves from `open` to `verified`.
  - `CR-02` | Minor | verified | `flags/evaluate.ts:71` | the predicate was extracted in the same change, as the r1 finding directed.
  - `CR-03` | Minor | open | `flags/tests/test_evaluate.ts:40` | **out-of-delta** — the new table test asserts on the evaluation result but not on the fallback branch it also exercises, so a regression there would pass. Inside `changed_evidence` by path, outside the two findings the round was opened for; reported as out-of-delta rather than treated as a new blocker. `review/code-chief` decides the cycle.
- Open risks: unchanged from r1 — the rollout plan is still absent, so coexistence in production remains outside what the diff can answer.
- Next action: merge is unblocked from this lens's side. `review/code-chief` rules on `CR-03`; cycle 1 of a `cycle_cap` of 2 is spent.
- Revision: r2 <- r1.
