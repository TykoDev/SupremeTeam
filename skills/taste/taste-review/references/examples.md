# Worked Taste-Review Record

This file carries one full instance of the `taste-review-record` — the single
artifact this skill owns — and the REVISE it produced, followed by the two
shorter shapes a review takes when the package is clean or unreadable.

Every example is a **routed submission**. `taste` reached this stage with an
active handoff: a `### Save Context` block naming run, phase, submission id,
revision, owner, and the destination the record is owed at. `../SKILL.md` Entry
Routing forbids running cold — without a delegation there is no package, no
before-and-after pair, and nothing to review. A bare "double-check this
preference change" with no package is answered by handing off to `admiral`, which
routes preference management through `taste`.

## Contents

1. The submission under review
2. The full record — one Critical, one Major, and the REVISE
3. The resubmission — a clean record and an APPROVED recommendation
4. An unreadable package — ESCALATE

## 1. The submission under review

**Save Context:** run `taste-42`, phase `taste`, save path
`skillset-saves/runs/taste-42/taste/`, persistence active, submission
`taste-42-r3`, revision 3, owner `taste`, expected artifact
`taste-review-record`, return boundary `taste-review`.

**Package:** `skillset-saves/runs/taste-42/taste/manifest.json`, schema 2, twelve
evidence keys. `intent` reads "revoke pref-old and promote pref-new to global".
`scope` names project and global. The diff records `pref-new` added at global,
`pref-old` revoked at project, `pref-a` unchanged.

Two facts from the canonical records matter below:

- `taste_prefs.py status` reports the project store at revision 2 before the change and 3 after.
- The promotion of `pref-new` from project to global is both a scope-widening change and a promotion — two of the operations doctrine §5 requires confirmation for.

## 2. The full record — one Critical, one Major, and the REVISE

Written to
`skillset-saves/runs/taste-42/taste/reports/taste-review-record.md`, path and
sha256 returned to `taste` so it can register the file as `taste_review_record`
in `taste/manifest.json`.

```markdown
# Taste Review Record

- Run: taste-42
- Submission: taste-42-r3
- Revision: 3
- Package: skillset-saves/runs/taste-42/taste/manifest.json
- Reviewer: taste-review
- Recommendation: REVISE

## Findings

### F-01 — Critical — confirmation absent for a promotion

- Check: step 2, confirmation (taste-doctrine.md section 5)
- Evidence: evidence/confirmation.json, field `candidate_ids`
- Observed: `candidate_ids` is `[pref-old]`. The diff changes two ids —
  `pref-new` added at global, `pref-old` revoked at project — so the record
  covers the revocation and not the promotion. `pref-new` reaches `state:
  active` at global scope with no confirmation naming it.
- Why it blocks: a promotion and a scope-widening write each require the
  explicit record on their own, and `candidate_ids` must equal the exact
  changed id set rather than a subset of it. `confirmation` appears in no
  fallback list in gates.yaml, so this is evidence not waivable: no
  applicability record, and no reason, would be admissible in its place.
- Required: a confirmation record whose `candidate_ids` is `[pref-new,
  pref-old]`, with `confirmed_scope` covering global, actor, timestamp, and
  `source_run: taste-42`.
- Owner: taste

### F-02 — Major — effective-profile digest does not match its entries

- Check: step 7, digest integrity
- Evidence: evidence/effective-profile.json field `digest`;
  evidence/consumer-handoff field `effective_profile_digest`
- Observed: the recorded `digest` was computed over an entry list that still
  contained `pref-old`. Recomputing over the two entries actually present
  yields a different sha256. `consumer_handoff` carries the recorded value, so
  the design pipeline named as the consuming pipeline would apply a profile
  that no longer matches the store.
- Why it blocks: the digest is the immutable handle a consumer resolves
  against. A stale one is not a cosmetic mismatch — it hands the consumer a
  profile nobody approved at this revision.
- Required: recompute the digest over the committed entries and carry the same
  value into `consumer_handoff`.
- Owner: taste

### F-03 — Info — before_revision is correct and matches the store

- Check: step 6, persistence safety and the before revision
- Evidence: evidence/preference-diff.json `before_digest`; `taste_prefs.py
  status` output for the project scope
- Observed: `before_revision` is 2, matching both the store's prior revision
  and the diff's before digest. `persistence_result` shows
  `atomicity_status: committed` and `rollback_result: not-required`, with
  hashes matching the files on disk, and global state outside the checkout.
- Recorded as Info: nothing to fix; noted so the next reader does not re-derive
  it.

## Keys examined

scope, intent, before_revision, preference_diff, confirmation,
conflict_analysis, policy_check, persistence_result, effective_profile,
consumer_handoff, taste_review_record, residual_uncertainty. `policy_check` reads `passed` and
agrees with steps 1 and 3: no entry encodes a correctness, security,
accessibility, architecture, or stack decision, and `conflict_analysis` lists
no equal-precedence contradiction and no accessibility or policy collision.

## Residual uncertainty

None. Both scopes named in `scope` were read against their canonical records,
and every one of the twelve evidence keys was examined.
```

**Returned to `taste`:**

- Recommendation: `REVISE` — one Critical and one Major, both repairable by the owner of the keys.
- Routing: both findings are `taste`'s. F-01 is not a wording problem, so no waiver will clear it; F-02 is arithmetic, not judgment.
- Not done here: neither the confirmation nor the digest was repaired. This stage is read-only, so a needed change is a finding, never an edit.
- Next: `taste` resubmits at revision 4.

## 3. The resubmission — a clean record and an APPROVED recommendation

**Save Context:** run `taste-42`, submission `taste-42-r4`, revision 4.

`taste` captured the confirmation naming both ids and recomputed the digest. The
record written at revision 4 carries:

- F-01 — Info — confirmation now covers both ids. `candidate_ids` is `[pref-new, pref-old]`, `confirmed_scope` covers global, actor and timestamp present, `source_run: taste-42`. The revision-3 Critical is cleared by evidence rather than by argument.
- F-02 — Info — the `effective_profile` digest recomputes correctly over its two entries, and `consumer_handoff` carries the same value.
- F-03 — Info — `before_revision` is 3 and matches the store's prior revision, which advanced with the revision-3 write.
- Recommendation: `APPROVED`.
- Residual uncertainty: none — every key and both scopes examined.

One note on the waivers this package did *not* use. All three sanctioned at this
boundary were available and none was admissible: `before_revision` had a real
prior revision, `consumer_handoff` names the design pipeline as a downstream
consumer, and `residual_uncertainty` is empty as a finding rather than as a
default. A waiver is a statement of fact, and this stage checks whether the fact
holds — not only whether the string matches.

## 4. An unreadable package — ESCALATE

**Save Context:** run `taste-51`, submission `taste-51-r1`, revision 1.

`evidence/persistence.json` is named in `artifact_hashes` but its recorded
sha256 does not match the file on disk, and `evidence/conflicts.json` cannot be
opened at all.

The record carries one finding and stops:

- F-01 — Critical — the package cannot be verified. Two of the six artifact-backed keys are unreadable or unhashable, so `persistence_result` and `conflict_analysis` are unexamined and steps 3 and 6 did not run.
- Recommendation: `ESCALATE`.
- Residual uncertainty: stated in full — the two unexamined keys are named, and "none observed" is not used. An unreadable artifact is a data gap, and a data gap is never a clean result inferred from the keys that did read cleanly.
