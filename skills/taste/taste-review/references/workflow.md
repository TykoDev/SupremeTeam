# Workflow Reference

Read this when a Taste package is in hand and the question is *how to run a
check* — which file to open, what to compare it against, and how the result is
graded. `../SKILL.md` states the eight-step order and the evidence set; this file
states the procedure inside each step.

`../../../taste-doctrine.md` is the semantic authority and `../../../gates.yaml` is the
evidence authority. Where either disagrees with this file, they win and this file
is the defect.

## Contents

1. Before starting — what to open
2. The eight checks, procedurally
3. Grading a finding
4. Recommendation rules
5. Acceptance checklist
6. Collaboration notes
7. Cross-references

## 1. Before starting — what to open

The package under review is a schema-2 manifest at
`skillset-saves/runs/{run-id}/taste/manifest.json` with its evidence files
alongside. Open, in this order:

1. The Save Context block, for the run id, revision, submission id, and the destination the review record is owed at.
2. `taste/manifest.json`, for the twelve evidence keys and the `artifact_hashes` map.
3. The five artifact-backed evidence files `taste` submits — `preference_diff`, `confirmation`, `conflict_analysis`, `persistence_result`, `effective_profile` — plus the intake report behind them, which is context rather than an artifact-backed key. The sixth `artifact_evidence` key `../../../gates.yaml` lists at `taste-review` is `taste_review_record`, and this stage writes it rather than reading it: `../../../pipelines.yaml` gives the `review` stage to `taste-review` with `taste-review-record` as its artifact.
4. The before and after canonical records — `taste_prefs.py status` and `taste_prefs.py list` output for every scope named in `scope`.

Read-only throughout. A mutating `taste_prefs.py` operation is never run from
this stage, and no package artifact is edited: a needed change is a REVISE
finding for `taste`.

If any of the four cannot be read, or a hash cannot be verified against the file
on disk, stop and record the gap. An unreadable package is an ESCALATE, never an
inferred clean result.

## 2. The eight checks, procedurally

### Step 1 — scope, intent, and provenance

- Confirm `scope` names the exact scopes the diff touches: a diff that writes global while `scope` says project is a scope-widening change, and step 2 then requires confirmation for it.
- Confirm `intent` is non-falsy and describes the change rather than the mechanism.
- For every id in `preference_diff.added` and `.updated`, open its entry and confirm all seven provenance fields (doctrine §4): `preference_id`, `scope`, registry `category`, `source`, `strength`, `state`, timestamps.
- For an imported entry, confirm the original provenance survived the import rather than being rewritten to the importing run.
- Read each entry against doctrine §1: an entry that decides what is *correct*, *secure*, *accessible*, or which *stack* to use is outside Taste, regardless of how it is phrased.

### Step 2 — confirmation

- List the operations the diff implies: inferred candidates, scope-widening changes, promotions, global resets, bulk imports, bulk revocations.
- For each, confirm a `confirmation` record exists and that `candidate_ids` equals the changed id set exactly — not a superset, not a prefix.
- Confirm no id moved from `proposed` to `active` without appearing in a confirmation (§5).
- `confirmation` appears in no fallback list in `../../../gates.yaml`, so an applicability record here is *evidence not waivable*. Grade it Critical and name the operation that required the record.

### Step 3 — conflicts

- Open `conflict_analysis` and check `conflicting_ids` against the resolution order in doctrine §7.
- Every equal-precedence contradiction belongs in `unresolved_conflicts`. A `precedence_decision` that resolves one is tie-breaking, which the doctrine forbids.
- Every collision with a mandatory accessibility, safety, security, legal, or gate requirement belongs in `accessibility_policy_collisions`, surfaced rather than normalized (§1).

### Step 4 — policy check

- `policy_check` records the doctrine-boundary and registry-category screen. Confirm it is present, non-falsy, and consistent with what steps 1 and 3 found: a `passed` value beside a §1 boundary violation found in step 1 is itself a finding.
- The key accepts no fallback, so an absent or explanatory value cannot be recorded as a gap and waved through.

### Step 5 — redaction

- Scan every entry, example, and rationale for derivation from protected or personal characteristics.
- Scan the record and its evidence for secrets, tokens, and personal data. Nothing of that kind is persisted, in the package or in the review record this stage writes.

### Step 6 — persistence safety and the before revision

- `persistence_result.requested_destinations` covers every scope the diff touches, and `committed_revisions` and `hashes` match the files on disk.
- `atomicity_status` is `committed`; a partial write with `rollback_result` other than `not-required` is a Major finding even when the surviving state looks correct.
- Global state stayed outside the checkout.
- `before_revision` equals the store's prior revision and agrees with `preference_diff.before_digest`. As a schema-2 waiver it arrives as the `reason` of an applicability record `{applicable: false, reason, scope, decided_by}`. The sanctioned "new store - no prior revision" is admissible only when the scope genuinely had none — verify against `taste_prefs.py status`, not against the package's own claim.

### Step 7 — digest integrity and handoff

- Recompute `effective_profile.digest` against its `entries` and confirm they match.
- Confirm every entry carries `source_scope` and `source_id`.
- Confirm `consumer_handoff.effective_profile_digest` is that same digest. A mismatch means the consuming pipeline would apply a profile nobody approved.
- As a schema-2 waiver it arrives as the `reason` of an applicability record `{applicable: false, reason, scope, decided_by}`. The sanctioned "preference management only - no downstream consumer" is admissible only when the run has no consuming pipeline; a package whose intent names a consumer cannot carry it.

### Step 8 — record and return

- Write one finding per check, each naming the artifact and field it rests on.
- State `residual_uncertainty` explicitly. "none observed" is a claim about the review itself, so it is admissible only when every scope and every key was examined; an unexamined scope goes here in words.
- Return the graded findings and the recommendation to `taste`.

## 3. Grading a finding

| Severity | When | Effect |
| --- | --- | --- |
| Critical | A missing or waived `confirmation`; an entry that encodes a correctness, security, accessibility, or stack decision; unreadable evidence with a boundary implication | Blocks until verified or marked not-applicable with a reason |
| Major | Digest or hash mismatch; a tie-broken equal-precedence conflict; an absent `policy_check`; a non-atomic persistence result | Blocks unless verified, not-applicable with reason, or deferred with a named owner and a reopen trigger |
| Minor | A provenance field present but imprecise; an `intent` that describes the mechanism rather than the change | Recorded |
| Info | Context the next reader needs and nothing more | Preserved |

## 4. Recommendation rules

This stage recommends; the `taste-review` gate decides.

- **APPROVED** — every check passed, every waiver used is sanctioned *and* true, and `residual_uncertainty` is genuinely empty.
- **REVISE** — `taste` can repair the package: capture the confirmation, re-persist, surface the conflict, re-run the policy screen. Never repair it here.
- **ESCALATE** — the package collides with a mandatory requirement, or the evidence cannot be read or hashed. Both are decisions above this stage.

## 5. Acceptance checklist

- All twelve `taste-review` evidence keys were examined, including `scope`, `intent`, `policy_check`, and `residual_uncertainty`.
- Every waiver used is one of the three sanctioned at this boundary, carried as the `reason` of an applicability record `{applicable: false, reason, scope, decided_by}`, and the statement it makes is true of the package.
- `confirmation` is present, and its `candidate_ids` equal the changed id set.
- No equal-precedence conflict was tie-broken.
- `effective_profile` and `consumer_handoff` carry the same digest.
- Every Critical and Major finding names an artifact and a field.
- No package artifact was edited and no mutating operation was run.

## 6. Collaboration notes

- `taste` owns every key at this boundary except `taste_review_record`, assembles the package, and resubmits after a REVISE.
- `gatekeeper-admiral` validates the `taste-review` boundary itself and consumes the record this stage writes as the `taste_review_record` evidence key.

## Cross-references

- `examples.md` — a full worked record and the REVISE it produced.
- `../../../taste-doctrine.md` — §1 boundary, §2 scopes, §4 provenance, §5 lifecycle, §7 resolution order.
- `../../../gates.yaml` — the twelve keys, their typed shapes, and the three sanctioned waivers.
