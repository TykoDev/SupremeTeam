# Worked Cross-Stage Submissions

Every example below is a **routed submission**, not a cold request. `admiral`
reached this gate with an active handoff — a `### Save Context` block naming run,
phase, submission id, revision, and owner — because `../SKILL.md` Entry Routing
forbids running standalone: with no submission there is no package, no evidence
bundle, and no approval lineage to judge. A prompt that arrives as a bare
"validate the handoff" with none of that is answered by starting `admiral`, not
by returning a verdict.

Seven submissions across six of the ten boundaries.

## Contents

1. `build-to-review` — batched `REVISE` to three owners
2. `build-to-review` — engine failure, `ESCALATE`
3. `review-to-delivery` — `APPROVED` with a reusable prior verdict
4. `design-to-build` — `APPROVED` on a shadcn/ui design package
5. `redesign-review` — `REVISE` on a refused waiver
6. `taste-review` — `REVISE` split between two owners
7. `deploy-readiness` — `ESCALATE` on an unresolved go decision

## Example 1 — `build-to-review`, batched `REVISE` to three owners

**Submission:** `admiral` routes the build package for cross-stage re-validation.
Save Context: run `r-2214`, phase `build`, submission `r-2214-b4`, revision 4,
owner `build-management`, return boundary `build-to-review`. The phase gate
already wrote `build/verdict_build-to-review.json`, passed back through `--prior`.

**Validators:**
- Boundary validator, `--boundary build-to-review --package build/manifest.json --prior build/verdict_build-to-review.json`: exit 1. `runtime` absent; `tests` present but its value is the string "suite green - 412 passed"; `security_evidence` carries "no security work needed".
- Package-shape validator on `delivery/`: `STRUCTURE_OK`, blocked-phrase scan clean.

**Output:**
- Verdict: `REVISE`.
- Boundary: `build-to-review`, submitted by `build-management`, revision 4.
- Evidence: three mechanical failures and one judgment finding, batched into one packet grouped by `../../gates.yaml` `evidence_owners`.
  - `health-check` — `runtime` is missing. The build compiles, which is not the same fact as the entry point starting; capture the startup smoke log as a hashed `probe` artifact under `build/evidence/`.
  - `test-builder` — `tests` is a claim, not a log. `evidence_type_rules` makes `tests` the test-runner log itself; a passing count cannot be re-read by the next consumer.
  - `security-builder` — `security_evidence` carries an unsanctioned string. The only admissible waiver text is "no trust-boundary change - security-builder not engaged", as a typed applicability record naming reason, scope, and decided_by.
  - `build-management` (judgment) — `traceability` maps four changed modules to approved design items but omits the migration script, which is in the diff.
- Open risks: none preserved; nothing here is a contradiction, all four are absences.
- Next action: the three owner groups are independent and fix in parallel; `build-management` resubmits once at revision 5.
- Revision: 4.

## Example 2 — `build-to-review`, engine failure

**Submission:** the same run resubmits at revision 5, but the boundary validator
is invoked with `--gates` pointing at a copy of the spec that was truncated during
an archive step.

**Validators:**
- Boundary validator: exit 2, `gate spec unreadable`.
- Package-shape validator: not run.

**Output:**
- Verdict: `ESCALATE`.
- Boundary: `build-to-review`, revision 5. Not judged.
- Evidence: exit 2 is an engine error, not a result. Nothing about the package was checked, so no statement about its readiness is available — an unrun gate is not a clean one.
- Next action: restore `../../gates.yaml` from the canonical source, confirm the gate spec digest, and resubmit unchanged. The gate spec is never bypassed to keep a run moving.
- Revision: 5.

## Example 3 — `review-to-delivery`, `APPROVED` with a reusable prior verdict

**Submission:** `admiral` routes the consolidated review package. Save Context:
run `r-2214`, phase `review`, submission `r-2214-v2`, revision 7, owner
`code-chief`. `--prior review/verdict_review-to-delivery.json` from the phase gate.

**Validators:**
- Boundary validator: exit 0, `prior_reusable: true` — same boundary, submission, revision, package fingerprint, and gate spec digest.
- Package-shape validator on `delivery/`: `STRUCTURE_OK`.

**Output:**
- Verdict: `APPROVED`.
- Boundary: `review-to-delivery`, submitted by `code-chief`, revision 7.
- Evidence: all six keys resolve. `executed_probes` and `rendered_verification` name hashed artifacts, and `rendered_verification`'s `inputs` bind by sha256 to the rendered source, so no input-hash drift is present. `review_verdict` is APPROVED with no challenge record attached.
- Open risks: `residual_risk` records one deferred Major with `design-qa` as owner and a reopen trigger, which the finding policy admits.
- Next action: hand off to delivery; the cross-stage record lands beside the phase record as `review/verdict_review-to-delivery.cross-stage.json`.
- Revision: 7. Reuse this verdict only while the package fingerprint holds.

## Example 4 — `design-to-build`, `APPROVED` on a shadcn/ui design package

**Submission:** `admiral` routes the design package after `gatekeeper-design`
approved it. Save Context: run `r-2301`, phase `design`, submission `r-2301-d3`,
revision 3, owner `commander`.

**Output:**
- Verdict: `APPROVED`.
- Boundary: `design-to-build`, submitted by `commander`.
- Evidence map: `ui_evidence` (generated tokens in `globals.css`, components, `design-system.md`), the artifact-backed `decisions`, `architecture`, `plan`, and `taste_snapshot`, plus `interfaces`, `acceptance`, `security_seed`, and `stack_lock` all point to the same revision, and the active Save Context matches it. `stack_lock`'s `overlay_sha256` validates against `../../tech-stacks/registry.yaml`.
- Open risks: none recorded beyond the two open questions the packet already assigns to `planner` with a decision point at build entry.
- Next action: build may consume the package at revision 3.
- Revision: 3. If the UI evidence, tokens, or any hashed design artifact changes, generate a new submission id before reusing this verdict.

## Example 5 — `redesign-review`, `REVISE` on a refused waiver, with a sanctioned one accepted alongside

**Submission:** `admiral` routes the redesign package. Save Context: run `r-2301`,
phase `redesign`, submission `r-2301-rd2`, revision 2, owner `redesign`.

**Output:**
- Verdict: `REVISE`.
- Boundary: `redesign-review`, submitted by `redesign`.
- Evidence, and the waiver that is *not* a failure:
  - `mock_rendering` carries the applicability record "no visible surface changed". `../../gates.yaml` lists that key under this boundary's `no_fallback`, so the waiver is rejected — the four directions are mocks, a mock that was never rendered is not evidence, and a boundary-level `no_fallback` beats the global fallback.
  - `rendered_verification`, `selected_variant`, `parity_evidence`, and `accessibility_evidence` each carry the record `selection deferred - no variant built`, and `selection.decision` is `deferred`. That reason is sanctioned at this boundary by its own `fallback_values`, so all four pass. Refusing them would route a `REVISE` to `design-qa` for a render of a variant this run never built.
- Next action: route to `design-qa`, the owner of `mock_rendering`, for hashed captures of the four mocks across the required breakpoints and themes, bound by `inputs` to each mock. The other nine keys are unchanged and carry their prior judgment.
- Revision: 2.

## Example 6 — `taste-review`, `REVISE` split between two owners

**Submission:** `admiral` routes the Taste package. Save Context: run `taste-42`,
phase `taste`, submission `taste-42-r3`, revision 3, owner `taste`.

**Validators:**
- Boundary validator, `--boundary taste-review`: exit 1. `confirmation` carries an applicability record; `taste_review_record` names a path that is not in `artifact_hashes`.

**Output:**
- Verdict: `REVISE`.
- Boundary: `taste-review`, submitted by `taste`, revision 3.
- Evidence, grouped by owner:
  - `taste` — `confirmation` was waived. It appears in no fallback list at all, so the failure reads *evidence not waivable*, not *bad reason*. The promotion of `pref-new` from project to global is exactly the operation that requires the explicit record, with `candidate_ids` equal to the changed id set.
  - `taste-review` — `taste_review_record` is referenced but unhashed, so the record behind the eleventh of the boundary's twelve required keys cannot be verified.
- Open risks: `residual_uncertainty` carries an applicability record whose `reason` is "none observed", the sanctioned wording at this boundary; the record form is what makes it acceptable, since this schema-2 package would fail on the bare string.
- Next action: both owners fix in parallel; `taste` resubmits at revision 4.
- Revision: 3.

## Example 7 — `deploy-readiness`, `ESCALATE` on an unresolved go decision

**Submission:** `admiral` routes the release package. Save Context: run `r-2214`,
phase `delivery`, submission `r-2214-s1`, revision 9, owner `ship`.

**Output:**
- Verdict: `ESCALATE`.
- Boundary: `deploy-readiness`, submitted by `ship`, revision 9.
- Conflict: `approved_delivery` names revision 7, the review verdict this gate approved in Example 3. That verdict carries a deferred Major owned by `design-qa` whose reopen trigger is "any change to the checkout surface", and `deploy_config` changes the checkout surface. Meanwhile `human_go_required` is recorded as satisfied.
- Evidence: the contradiction is preserved rather than normalized — both statements are in the package, and neither is wrong on its own.
- Next action: the release owner or the user resolves the risk-acceptance question. Reopening the deferred Major would rewind to `review-to-delivery`; accepting it is a decision this gate does not own.
- Revision: 9.
