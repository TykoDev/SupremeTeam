# Worked Design-Gate Submissions

Every example below is a **routed submission**, not a cold request.
`design/commander` or `design/redesign` reached this gate with an active handoff —
a `### Save Context` block naming run, phase, submission id, revision, and owner —
because `../SKILL.md` Entry Routing forbids running standalone: with no
submission there is no packet, no evidence bundle, and no approval lineage to
judge. A prompt that arrives as a bare "validate the design deliverable" with
none of that is answered by routing to `admiral`, not by returning a verdict.

Six submissions, three at each boundary.

## Contents

1. `design-to-build` — `REVISE` on an unbacked architecture
2. `design-to-build` — `APPROVED` with two sanctioned waivers
3. `design-to-build` — `ESCALATE` on a compliance contradiction
4. `redesign-review` — `REVISE` on three variants and an unbound parity probe
5. `redesign-review` — `REVISE` on a refused `rendered_verification` waiver
6. `redesign-review` — `APPROVED` with the chosen variant

## Example 1 — `design-to-build`, `REVISE` on an unbacked architecture

**Submission:** `design/commander` submits the design packet. Save Context: run
`r-3108`, phase `design`, submission `r-3108-d2`, revision 2, owner `commander`,
return boundary `design-to-build`.

**Validators:**
- `../scripts/check.py skillset-saves/runs/r-3108/design`: `NEEDS_JUDGMENT`. Research, plan, architecture, stack-lock, taste-snapshot, and spec files all present; `api_contracts` and `ui_handoff` reported `UNCHECKED`.
- Boundary validator `--boundary design-to-build`: exit 1. `architecture` names `reports/adr-event-bus.md`, which is absent from `artifact_hashes`; `security_seed` is empty.

**Output:**
- Verdict: `REVISE`.
- Boundary: `design-to-build`, submitted by `commander`, revision 2.
- Evidence, batched and grouped by `../../../gates.yaml` `evidence_owners`:
  - `architect` — `architecture` is artifact-backed and its path is unhashed, so the ADR set cannot be verified as the one the packet describes. The same ADRs introduce an event bus that `interfaces` and the implementation spec still model as direct request-response; that contradiction is the judgment finding behind the same key.
  - `security-builder` — `security_seed` is present but falsy. It is not waivable at this boundary; the threat-model seed is what `security-builder` answers at build.
- Open risks: the two `UNCHECKED` conditional artifacts are resolved as in scope — the packet describes four HTTP endpoints — so the API endpoint contract is required and currently absent, which is part of the `architect` group.
- Next action: both owners fix in parallel; `commander` resubmits once at revision 3.
- Revision: 2.

## Example 2 — `design-to-build`, `APPROVED` with two sanctioned waivers

**Submission:** `design/commander` resubmits at revision 3, a background job
change with no user-facing surface and no new runtime. Save Context: run `r-3108`,
submission `r-3108-d3`, owner `commander`; `--prior design/verdict_design-to-build.json`.

**Validators:**
- `../scripts/check.py`: `STRUCTURE_OK`.
- Boundary validator: exit 0. `changed_evidence` names `architecture`, `security_seed`, and `interfaces`; the rest carry their prior judgment.

**Output:**
- Verdict: `APPROVED`.
- Boundary: `design-to-build`, submitted by `commander`, revision 3.
- Evidence: `decisions`, `architecture`, `plan`, and `taste_snapshot` all resolve to hashed paths in `artifact_hashes`. `stack_lock` carries the applicability record "no new runtime or framework - existing stack unchanged" with scope and decided_by, and `ui_evidence` carries "no user-facing surface - design system not engaged"; both are the exact sanctioned strings for their keys, and both statements are true of a background job. `interfaces`, `acceptance`, and `security_seed` are non-falsy and specific enough that build can act on them.
- Open risks: one open question about retry limits, assigned to `planner` with a decision point at build entry.
- Next action: build may consume the packet at revision 3.
- Revision: 3. A new submission id is required before this verdict is reused against any changed artifact.

## Example 3 — `design-to-build`, `ESCALATE` on a compliance contradiction

**Submission:** `design/commander` submits a packet for a patient-messaging
feature. Save Context: run `r-3210`, phase `design`, submission `r-3210-d1`,
revision 1, owner `commander`.

**Validators:** both pass mechanically — all nine keys resolve, four hashed.

**Output:**
- Verdict: `ESCALATE`.
- Boundary: `design-to-build`, submitted by `commander`, revision 1.
- Conflict: `decisions` commits to HIPAA-bound storage with no third-party processor, while `stack_lock` and `architecture` both lock a hosted analytics SDK that ships event payloads off-platform. Each is internally coherent; together they cannot both hold.
- Evidence: the contradiction is preserved rather than normalized — both statements are in the packet, and this gate does not get to choose which one the product meant.
- Next action: the user or the product owner resolves the compliance-versus-analytics tradeoff. A `REVISE` would be the wrong verdict: no design owner can fix this by editing the packet.
- Revision: 1.

## Example 4 — `redesign-review`, `REVISE` on three variants and an unbound parity probe

**Submission:** `design/redesign` submits the redesign package. Save Context: run
`r-3210`, phase `redesign`, submission `r-3210-rd1`, revision 1, owner `redesign`,
return boundary `redesign-review`.

**Validators:**
- `../scripts/check_redesign.py skillset-saves/runs/r-3210/redesign`: `NEEDS_JUDGMENT`. Inventory, grilling log, directions, three `variant.md` files, the redesign package, and one `parity.json` present; `rendered_verification` reported `UNCHECKED`.
- Boundary validator `--boundary redesign-review`: exit 1 on `variant_set` alone — three variants against a required count of four. `parity_evidence` is a single probe record with no `inputs`, which the validator accepts (`inputs` is required only for `scan` and `render` records), so that one arrives as judgment rather than as a mechanical failure.

**Output:**
- Verdict: `REVISE`.
- Boundary: `redesign-review`, submitted by `redesign`, revision 1.
- Evidence, grouped by owner:
  - `prototyper` — `variant_set` holds three variants. `../../../gates.yaml` `evidence_type_params` fixes the required count at four, and a field of three that already includes the recommendation is a comparison with a predetermined winner.
  - `design-mapper` — the single `parity_evidence` probe carries hashed artifacts and a passing status but no `inputs`, so nothing binds it to `design_inventory`. It proves that a probe ran, not that any variant matches the surface it claims parity with. The validator lets this through; the binding is what this verdict requires, added as `inputs` entries on that same record, which stays one mapping covering all four variants.
  - `design-qa` — the shape check's `UNCHECKED` on `rendered_verification` is unresolved, and the evidence key is absent. See Example 5 for the case where it is present but waived.
- Next action: three owners fix in parallel; `redesign` resubmits once at revision 2.
- Revision: 1.

## Example 5 — `redesign-review`, `REVISE` on a refused waiver

**Submission:** `design/redesign` resubmits at revision 2. Save Context: run
`r-3210`, submission `r-3210-rd2`, owner `redesign`; `--prior redesign/verdict_redesign-review.json`.

**Validators:**
- `../scripts/check_redesign.py`: `STRUCTURE_OK` on everything except `rendered_verification`, still `UNCHECKED` — no capture file was written.
- Boundary validator: exit 1. `rendered_verification` carries `{applicable: false, reason: "no visible surface changed - rendered verification not applicable", scope: "redesign", decided_by: "redesign"}`.

**Output:**
- Verdict: `REVISE`.
- Boundary: `redesign-review`, submitted by `redesign`, revision 2.
- Evidence: the waiver is rejected, and the reason is not that the record is malformed. `../../../gates.yaml` lists `rendered_verification` under this boundary's `no_fallback`, where the key accepts neither the sanctioned string nor an applicability record. A boundary-level `no_fallback` beats the global fallback, because a redesign always has a visible surface and the waiver's own reason therefore cannot be true here.
- The `UNCHECKED` from the shape check is recorded as an unresolved question, never as agreement with the waiver. The two validators ask different things about this key.
- Next action: route to `design-qa` for hashed captures across the required breakpoints and themes, with `inputs` bound by sha256 to the rendered variant. `variant_set` and `parity_evidence` are in `unchanged_evidence` and carry their revision-1 judgment; only this key is re-judged.
- Revision: 2.

## Example 6 — `redesign-review`, `APPROVED` with the chosen variant

**Submission:** `design/redesign` resubmits at revision 3. Save Context: run
`r-3210`, submission `r-3210-rd3`, owner `redesign`; `--prior` from revision 2.

**Validators:**
- `../scripts/check_redesign.py`: `STRUCTURE_OK`.
- Boundary validator: exit 0.

**Output:**
- Verdict: `APPROVED`.
- Boundary: `redesign-review`, submitted by `redesign`, revision 3.
- Evidence: `variant_set` holds four variants with unique ids, each with `spec`, `tokens`, `components`, and `app` correctly hashed; four `parity_evidence` probes, one per variant, each bound by `inputs` to `design_inventory` and the prototype files; `rendered_verification` carries hashed captures at all six responsive tiers in both themes, `inputs` bound to the rendered variant. `design_inventory`, `taste_grilling`, `taste_snapshot`, and `design_directions` all resolve to hashed paths.
- Judgment: the four directions are differentiated on more than palette — layout density, navigation model, and disclosure pattern each differ (`../../../design-doctrine.md` §9) — and `recommendation` names variant `v3` for a reason the comparison matrix actually supports.
- Open risks: `residual_risk` records one deferred Major owned by `frontier` with a reopen trigger on any change to the table component.
- Next action: DESIGN resumes with variant `v3`.
- Revision: 3. Any change to a variant artifact or capture requires a new submission id before this verdict is reused.
