# Example Invocations

Four passes, each rendered in the full packet shape `../SKILL.md` mandates:
Outcome, Evidence, Findings, Open risks, Next action, Revision, in that order and
with no verdict, because this lens owns no gate (`../../../execution-contract.md`,
clause 6). The graded passes carry the shape too, not just the clean one — a pass
with findings is where the merge recommendation and the evidence behind it have
to travel together, and an example that drops the fields there teaches the packet
as decoration. Severities are the shared four tiers —
`Critical | Major | Minor | Info` — and nothing else.

## Example 1

**User request:** review this diff in the feature-flag rollout branch

**Output:**
- Outcome: code-review, r1, merge recommendation: no-go, 2 findings: 1 Critical, 0 Major, 1 Minor, 0 Info.
- Evidence: the full diff range `main...flags/rollout` judged hunk by hunk — flag evaluation, the fallback branch, and the tests added with them — with each changed call site read against its caller. `npm test -- flags` and the lint output from the build package were read as supplied. The regenerated lockfile was excluded as mechanical churn.
- Findings:
  - `CR-01` | Critical | `flags/evaluate.ts:57` | the new helper changes the default flag behavior while two call sites stay on the prior semantic, so the rollout ships two meanings of the same flag | migrate both call sites in this change, or gate the new default behind an explicit opt-in.
  - `CR-02` | Minor | `flags/evaluate.ts:71` | the inline conditionals would read better as a named predicate, but only once the semantic mismatch is resolved; extracting them first would hide it | fold into the `CR-01` fix rather than landing separately.
- Open risks: no rollout plan accompanies the diff, so whether the two semantics ever coexist in production is a deployment question this lens cannot answer from the change alone.
- Next action: `review/code-chief` returns `CR-01` to the change owner; the merge stays blocked until it is resolved.
- Revision: r1.

## Example 2

**User request:** check merge readiness for the billing service diff

**Output:**
- Outcome: code-review, r2, merge recommendation: no-go, 2 findings: 0 Critical, 1 Major, 0 Minor, 1 Info.
- Evidence: billing service handlers, the migration script, and the updated retry tests, read across the supplied diff range; the serializer's existing contract test read for the field it does not cover; the migration read forward and backward for reversibility. Generated protobuf stubs were excluded.
- Findings:
  - `CR-03` | Major | `billing/serializer.py:31` | the diff adds an API field with no serializer contract test, so the wire format changes without verification | extend the existing contract test rather than adding a new suite.
  - `CR-04` | Info | `migrations/0042_add_invoice_ref.py` | the migration is reversible and idempotent as written | recorded so the next round does not re-litigate it.
- Open risks: no consumer inventory accompanies the diff, so whether any client parses the wire format strictly is unknown; the API consumer list would answer it.
- Next action: `review/code-chief` returns `CR-03` to the change owner before the gate.
- Revision: r2.

## Example 3

**User request:** audit this diff in the controller refactor

**Output:**
- Outcome: code-review, r3, merge recommendation: go with one Major tracked, 2 findings: 0 Critical, 1 Major, 0 Minor, 1 Info.
- Evidence: the controller refactor plus the error-mapping utility used by two endpoints, read hunk by hunk against both call sites; the endpoint tests run green in the build package and read for the exception path they do not exercise. Untouched sibling controllers were excluded as outside the diff.
- Findings:
  - `CR-05` | Major | `http/error_map.go:88` | one exception path drops the request id, so incidents on that branch lose traceability | thread the id through the mapper rather than reconstructing it at the edge.
  - `CR-06` | Info | `http/controllers/orders.go:120` | response status mapping is clearer than the code it replaces | handed to `review/quality-review` to judge whether the refactor also moves layering drift; no merge consequence is claimed here.
- Open risks: whether the dropped request id is already relied on by the incident tooling is not visible in the diff, so `CR-05` is tracked rather than blocking on this lens's evidence alone.
- Next action: `review/code-chief` carries `CR-05` into the gate as tracked and hands `CR-06` to `review/quality-review`.
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
