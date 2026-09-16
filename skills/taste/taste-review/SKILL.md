---
name: taste-review
description: >-
  Read-only reviewer for the Taste preference pipeline: checks a preference
  package's provenance, conflicts, redaction, confirmation, and persistence
  safety, then writes the taste-review record for the `taste-review` gate. Use
  when `taste` hands a package to the review stage, or the user asks to review,
  audit, or double-check a preference change before it is saved — even when they
  only ask "is this safe to save?". Never mutates a preference store; defers
  preference decisions to `taste`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---

# Taste Review

## Purpose

Be the reader who did not make the change.

`taste` gathers the preference, resolves the conflict, and commits the write, so
by the time a package exists every judgment in it has already been made once by
the same owner. This stage re-reads those judgments against
`../../taste-doctrine.md` before the `taste-review` gate sees them, looking for
the three failures a self-check is least likely to catch:

- a preference that became `active` without the explicit confirmation its lifecycle requires
- a contradiction that was tie-broken rather than surfaced as unresolved
- an entry that encodes a correctness, security, accessibility, or stack decision as taste

Taste Review owns exactly one artifact, the `taste-review-record`
(`../../ownership.yaml`), holds no write access to either durable preference
store, and issues a recommendation rather than the gate verdict.

## Use This Skill When

Use this reviewer to **re-read a preference package before it is persisted** — it recommends, and never writes to a store:

- "review this preference change" — check provenance, confirmation, and lifecycle against the doctrine
- "is this safe to save?" — say whether the package can be persisted as it stands
- "double-check a preference change before it is saved" — look for a contradiction that was tie-broken instead of surfaced
- "audit this preference package before saving" — grade every gate evidence key, not only the changed entry

Route elsewhere to make the preference decision or write the record (`taste`), which owns every mutation phrasing; this stage only issues a recommendation.

## Entry Routing

This skill is the review stage of the `taste` pipeline (`../../pipelines.yaml`)
and runs only inside a Taste delegation: the prompt carries a `### Save Context`
block from `taste`, or an active run with `session_pin: true` exists under
`skillset-saves/`. Reached cold for a preference request, hand off to `admiral`
(see `../../routing-doctrine.md`), which routes explicit preference management
through `taste`. Without a delegation there is no package, no before-and-after
pair, and nothing to review.

## Inputs

- The Taste package under review: `taste-intake`, `preference-diff`, `taste-confirmation`, `taste-conflict-analysis`, `taste-persistence-result`, `effective-taste-profile`, and `taste-consumer-handoff`, with their hashes.
- The before and after canonical records (`taste_prefs.py status` and `list` output) for each scope the package touches.
- `../../taste-doctrine.md` for the boundary of Taste (§1), scopes (§2), provenance fields (§4), lifecycle (§5), and the resolution order (§7).

## Outputs

- `taste-review-record`: findings graded Critical | Major | Minor | Info, one per check below, each with the evidence path it rests on, and a recommendation of APPROVED, REVISE, or ESCALATE for the `taste-review` gate. It is the hashed artifact behind the `taste_review_record` evidence key in `../../gates.yaml`.

## The Gate Evidence Set

`../../gates.yaml` requires twelve keys at the `taste-review` boundary, submitted
by `taste`. Eleven belong to `taste`; the twelfth, `taste_review_record`, is this
skill's only artifact (`../../gates.yaml` `evidence_owners`). Review every key —
a package is judged whole, and a key this stage never looks at is a key the gate
inherits unexamined.

| Evidence key | Backing | Waivable | Checked by |
| --- | --- | --- | --- |
| `scope` | claim | no | step 1 |
| `intent` | claim | no | step 1 |
| `before_revision` | claim | yes — "new store - no prior revision" | step 6 |
| `preference_diff` | artifact | no | steps 1, 6 |
| `confirmation` | artifact | **never** | step 2 |
| `conflict_analysis` | artifact | no | step 3 |
| `policy_check` | claim | no | step 4 |
| `persistence_result` | artifact | no | step 6 |
| `effective_profile` | artifact | no | step 7 |
| `consumer_handoff` | claim | yes — "preference management only - no downstream consumer" | step 7 |
| `taste_review_record` | artifact | no | step 8 |
| `residual_uncertainty` | claim | yes — "none observed" | step 8 |

Every "yes" in the Waivable column means the wording travels as the `reason` of an
applicability record `{applicable: false, reason, scope, decided_by}`, never as a bare
string: this package is `schema_version: 2`, where `check.py` fails a bare fallback
with `bare fallback string not accepted at schema 2`.

Two properties of that table decide most findings:

- **`confirmation` appears in no fallback list at all.** A waiver on it fails as *evidence not waivable* rather than as a bad reason, which is why a missing confirmation is a Critical finding and never a negotiation.
- **`policy_check` has no fallback either**, so a package that omits it or fills it with an explanatory string cannot reach APPROVED, however clean the rest of the set looks.

## Workflow

1. **Scope, intent, and provenance**: `scope` names the exact scopes touched and `intent` states what the change is for, both non-falsy and both consistent with `preference_diff`. Every added or updated entry carries `preference_id`, `scope`, a registry `category`, `source`, `strength`, `state`, and timestamps (doctrine §4); an imported entry keeps its original provenance; no entry encodes correctness, security, accessibility, architecture, or stack selection (§1).
2. **Confirmation**: every inferred candidate, scope-widening change, promotion, global reset, bulk import, and bulk revocation has a `confirmation` record whose `candidate_ids` equal the exact changed id set; nothing moved from `proposed` to `active` without it (§5). Confirmation is never waivable.
3. **Conflicts**: the `conflict_analysis` names every equal-precedence contradiction as unresolved rather than tie-breaking it, and every collision with a mandatory accessibility, safety, security, legal, or gate requirement is surfaced, not normalized (§1, §7).
4. **Policy check**: `policy_check` records the result of the doctrine-boundary and registry-category screen, is present and non-falsy, and agrees with what steps 1 and 3 found. It accepts no fallback, so an absent or hand-waved value is a finding in its own right rather than a gap to note.
5. **Redaction**: no entry, example, or rationale derives from protected or personal characteristics, and no secret, token, or personal data is persisted in the record or its evidence.
6. **Persistence safety and the before revision**: `persistence_result` shows every requested destination committed atomically through `taste_prefs.py` with matching hashes, and global state stayed outside the checkout. `before_revision` equals the store's prior revision and matches `preference_diff`'s before digest — or carries "new store - no prior revision" as the `reason` of an applicability record `{applicable: false, reason, scope, decided_by}` when the scope genuinely had none.
7. **Digest integrity and handoff**: the `effective_profile` digest matches its entries, every entry carries its source scope and source id, and `consumer_handoff` carries that same digest — or "preference management only - no downstream consumer" as the `reason` of an applicability record `{applicable: false, reason, scope, decided_by}` when nothing downstream consumes the profile.
8. **Record and return**: write the review record to the destination named in the Save Context block, stating `residual_uncertainty` explicitly — the sanctioned "none observed" is a claim about the review, so use it only when the package left nothing unexamined, and it too arrives as the `reason` of an applicability record `{applicable: false, reason, scope, decided_by}`. Return the graded findings and the recommendation to `taste`. Do not edit any package artifact; return REVISE to `taste` instead.

## Required Contracts

- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../../execution-contract.md` defines, so upstream and downstream packages interpret risk consistently.
- **Read-only**: Never call a mutating `taste_prefs.py` operation and never edit `skillset-saves/preferences/` or the global store; a needed change is a REVISE finding for `taste`.
- **Evidence standard**: Apply `../../contracts/evidence-standards.md`; every Critical or Major finding names the artifact and the field it rests on.

## Failure Modes

| Scenario | Response |
| --- | --- |
| A `confirmation` record is missing for an inferred, promoted, reset, imported, or bulk-revoked entry, or its `candidate_ids` differ from the changed id set | Critical finding; recommend REVISE and name the ids that lack confirmation. |
| `confirmation` carries an applicability record instead of the confirmation itself | Critical finding. The key appears in no fallback list, so the failure is *evidence not waivable*, not a bad reason; recommend REVISE and name the operation that requires the explicit record. |
| `policy_check` is absent, empty, or replaced by an explanatory string | Major finding; the key accepts no fallback, so recommend REVISE rather than recording a gap. Escalate to Critical when the missing screen would have caught a §1 boundary violation. |
| The `preference_diff` before digest does not match the store's prior revision, `before_revision` disagrees with it, or `persistence_result` hashes differ from the files on disk | Major finding; recommend REVISE to `taste` for re-persistence, never repair the record. |
| Two entries of equal precedence contradict each other and the package records a winner | Major finding; the doctrine forbids tie-breaking, so the conflict must be surfaced as unresolved. |
| An entry encodes an accessibility, security, correctness, or stack decision as Taste | Critical finding; recommend ESCALATE with the mandatory requirement it collides with. |
| `effective_profile`'s digest does not match its entries, or `consumer_handoff` carries a different digest | Major finding; recommend REVISE. A consumer that reads a stale digest applies a profile nobody approved. |
| The package or its evidence cannot be read, or a hash cannot be verified | Do not infer a clean result; record the gap and recommend ESCALATE. |
| Every check passes but a scope of the package was never examined | Record it in `residual_uncertainty` rather than claiming "none observed", and grade the recommendation accordingly. An unexamined scope is a data gap, never approval. |

## Save Protocol

When the Save Context block carries `Persistence active: yes`, write the review
record to the destination it names (normally
`skillset-saves/runs/{run-id}/taste/reports/taste-review-record.md`, resolved
with `python skills/scripts/output_paths.py --phase taste --kind reports`) and
return its path and sha256 so `taste` can register it as `taste_review_record`
in `taste/manifest.json`. Write nothing else. When persistence is inactive,
return the record inline.

## References

- `references/workflow.md` for the per-check procedure: what to open, what to compare, and how each check is graded.
- `references/examples.md` for a full worked `taste-review-record` and the REVISE it produced.
- `../SKILL.md` for the Taste pipeline owner, its writer commands, and the confirmation policy.
- `../references/workflow.md` for the record model and operation semantics under review.
- `../../taste-doctrine.md` for the canonical semantic contract this review enforces.
- `../../gates.yaml` for the `taste-review` evidence set and the typed record shapes.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md`
together. This skill owns no scripts: it reads `taste_prefs.py` output that
`taste` produced and never invokes a mutating operation itself.

Two pointers leave this directory and must ship with it. `../SKILL.md` and
`../references/workflow.md` belong to the parent `taste` skill and carry the
operation semantics this review is checking against; `../../taste-doctrine.md`
and `../../gates.yaml` are catalog-level contracts. Shipping this skill alone
leaves those four pointers broken, so package it with the `taste` skill and the
catalog root rather than on its own. Keep generated records and run archives
outside the skill directory.
