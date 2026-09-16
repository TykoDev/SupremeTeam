# Worked Review-Gate Submissions

Every example below is a **routed submission**, not a cold request.
`review/code-chief` reached this gate with an active handoff — a
`### Save Context` block naming run, phase, submission id, revision, and owner —
because `../SKILL.md` Entry Routing forbids running standalone: with no
submission there is no package, no lens set, and no approval lineage to judge. A
prompt that arrives as a bare "validate the review package" with none of that is
answered by routing to `admiral`, not by returning a verdict.

Five submissions at the one boundary this gate owns.

## Contents

1. `REVISE` — `rendered_verification` routed to `design-qa`, not to the submitter
2. `REVISE` — input-hash drift on `executed_probes`
3. `APPROVED` — a sanctioned waiver and two justified lens skips
4. `ESCALATE` — two lenses that cannot both be right
5. `ESCALATE` — the boundary validator exits 2

## Example 1 — `REVISE` on `rendered_verification`, routed to `design-qa`

**Submission:** `review/code-chief` submits the consolidated review package. Save
Context: run `r-5140`, phase `review`, submission `r-5140-v1`, revision 1, owner
`code-chief`, return boundary `review-to-delivery`.

**Validators:**
- `../scripts/check.py skillset-saves/runs/r-5140/review`: `NEEDS_JUDGMENT`. All five core lenses present; `lens_cso` reported `UNCHECKED`.
- Boundary validator `--boundary review-to-delivery`: exit 1. `rendered_verification` carries the bare string "UI unchanged in this round".

**Output:**
- Verdict: `REVISE`.
- Boundary: `review-to-delivery`, submitted by `code-chief`, revision 1.
- Evidence, batched and grouped by `../../../gates.yaml` `evidence_owners`:
  - `design-qa` — `rendered_verification` is a bare explanatory string, not a `render` record and not the sanctioned waiver. Two things fail at once: it names no path in `artifact_hashes`, and "UI unchanged in this round" is not the admissible reason. The only accepted waiver is the typed applicability record naming reason, scope, and decided_by for "no visible surface changed - rendered verification not applicable" — and the diff changes the settings panel, so that statement is not true here either.
  - `code-chief` — the `UNCHECKED` CSO lens is unresolved. The package's delivery-readiness claim says the release is "cleared for production", which is a release-posture claim, so `review/cso` is in scope and a skip record is not available for it.
- **Routing note.** The first group goes to `design-qa`, not to `code-chief`, even though `code-chief` assembled and submitted the package. The submitter cannot capture a render, so a `REVISE` addressed to them parks the defect with an owner who cannot clear it. This is the one key at this boundary whose owner is not the submitter, and it is the one most often mis-routed.
- Next action: both owners fix in parallel; `code-chief` resubmits once at revision 2.
- Revision: 1.

## Example 2 — `REVISE` on input-hash drift

**Submission:** `review/code-chief` resubmits at revision 2. Save Context: run
`r-5140`, submission `r-5140-v2`, owner `code-chief`;
`--prior review/verdict_review-to-delivery.json`.

**Validators:**
- `../scripts/check.py`: `STRUCTURE_OK`. The CSO lens is now present.
- Boundary validator: exit 1. `executed_probes` names a hashed log, but its `inputs` entry for `src/api/session.py` carries a sha256 that no longer matches the file on disk.

**Output:**
- Verdict: `REVISE`.
- Boundary: `review-to-delivery`, submitted by `code-chief`, revision 2.
- Evidence: `code-chief` — input-hash drift on `executed_probes`. The probe log itself is intact and correctly hashed in `artifact_hashes`; what failed is the binding. `inputs` records the sha256 of each source the probe examined, and `src/api/session.py` changed after the probe ran, so the log proves a state the package no longer ships. Re-run the probes against the current source and re-capture.
- Carried forward: `rendered_verification` now carries a `render` record with hashed captures at all six responsive tiers in both themes, `inputs` bound to the rendered source, clearing the revision-1 finding. `findings`, `residual_risk`, and `revision_lineage` are in `unchanged_evidence` and keep their prior judgment.
- Note: drift is a `REVISE`, not an `ESCALATE`. Nothing is contradictory and nothing needs a scope decision — the evidence is simply stale.
- Next action: `code-chief` re-runs and resubmits at revision 3.
- Revision: 2.

## Example 3 — `APPROVED` with a sanctioned waiver and two justified skips

**Submission:** `review/code-chief` submits a review package for a scheduled-job
change with no user-facing surface. Save Context: run `r-5208`, phase `review`,
submission `r-5208-v1`, revision 1, owner `code-chief`.

**Validators:**
- `../scripts/check.py`: `STRUCTURE_OK`. `lens_cso` absent with an explicit `_skip-record.md` whose required fields the engine validated; `review/frontier` likewise.
- Boundary validator: exit 0.

**Output:**
- Verdict: `APPROVED`.
- Boundary: `review-to-delivery`, submitted by `code-chief`, revision 1.
- Evidence map: all five core lenses present and current for revision 1. `executed_probes` names `review/evidence/probes-r1.log`, hashed, `result.status: pass`, `inputs` matching every source it examined. `rendered_verification` carries the sanctioned applicability record for "no visible surface changed - rendered verification not applicable", scoped to the changed job module and decided by `design-qa` — and the diff touches no template, component, or stylesheet, so the reason is honest rather than merely well-formed. `review_verdict` is APPROVED with no challenge record attached.
- Skips: `review/cso` skipped with a no-accepted-risk / no-release-posture justification tied to the actual scope; `review/frontier` skipped with a no-rendered-UI justification consistent with the waiver above.
- Open risks: `residual_risk` records one deferred Major owned by `code-chief` with a reopen trigger on any change to the retry schedule, which the finding policy admits.
- Next action: hand off to delivery.
- Revision: 1. Preserve the approval record and reuse it on resume only while the package revision is unchanged.

## Example 4 — `ESCALATE` on two lenses that cannot both be right

**Submission:** `review/code-chief` submits the consolidated package. Save
Context: run `r-5301`, phase `review`, submission `r-5301-v2`, revision 2, owner
`code-chief`.

**Validators:** both pass mechanically — all six keys resolve, two hashed.

**Output:**
- Verdict: `ESCALATE`.
- Boundary: `review-to-delivery`, submitted by `code-chief`, revision 2.
- Conflict: `review/security-review` records a token exposure as release-blocking; `review/code-review` marks the same path unreachable because the deployment configuration that would expose it is absent from the repository. `review_verdict` is REVISE with a challenge record naming `security-review` as `by` and the unreachability claim as the disputed `reason`.
- Evidence: the challenge is preserved as a disputed recommendation rather than resolved. This gate does not pick a lens. The missing deployment configuration is the fact that would settle it, and it is not in the package.
- Open risks: the exposure remains live as a risk-acceptance question, recorded in `residual_risk` with no owner able to close it inside review.
- Next action: obtain the deployment configuration as runtime evidence, which would turn this into a `REVISE`, or ask the user to resolve the risk-acceptance question. Either is a decision outside this boundary.
- Revision: 2.

## Example 5 — `ESCALATE` when the boundary validator exits 2

**Submission:** `review/code-chief` resubmits at revision 3, but the boundary
validator is pointed at a gate spec copy that was truncated during an archive
step.

**Validators:**
- `../scripts/check.py`: `STRUCTURE_OK`.
- Boundary validator: exit 2, `gate spec unreadable`.

**Output:**
- Verdict: `ESCALATE`.
- Boundary: `review-to-delivery`, revision 3. Not judged.
- Evidence: exit 2 is an engine error, not a result. The shape check passing says nothing about the six evidence keys, because the two key spaces do not overlap — five green lenses and a clean structure report are compatible with every required evidence key being absent.
- Next action: restore `../../../gates.yaml` from the canonical source, confirm the gate spec digest, and resubmit unchanged. The gate spec is never bypassed to keep a run moving, and an unknown pre-check result is not evidence of readiness.
- Revision: 3.
