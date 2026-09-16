---
name: taste-review
description: >-
  Read-only reviewer for the Taste preference pipeline: checks a preference
  package's provenance, conflicts, redaction, confirmation, and persistence
  safety and writes the taste-review record. Use when `taste` hands a package to
  the review stage of the taste pipeline, or the user asks to review, audit, or
  double-check a preference change before it is saved. Never mutates a
  preference store; defers preference decisions and writes to `taste`.
version: 1.0.0
---

# Taste Review

## Purpose

Review a Taste package before the `taste-review` gate so every preference change
is traceable, confirmed where the doctrine requires it, free of sensitive
inference, and persisted safely. Taste Review owns exactly one artifact, the
`taste-review-record` (`../../ownership.yaml`), and does not mutate either
durable preference store.

## Entry Routing

This skill is the review stage of the `taste` pipeline (`../../pipelines.yaml`)
and runs only inside a Taste delegation: the prompt carries a `### Save Context`
block from `taste`, or an active run with `session_pin: true` exists under
`skillset-saves/`. Reached cold for a preference request, hand off to `admiral`
(see `../../routing-doctrine.md`), which routes explicit preference management
through `taste`.

## Inputs

- The Taste package under review: `taste-intake`, `preference-diff`, `taste-confirmation`, `taste-conflict-analysis`, `taste-persistence-result`, `effective-taste-profile`, and `taste-consumer-handoff`, with their hashes.
- The before and after canonical records (`taste_prefs.py inspect` output) for each scope the package touches.
- `../../taste-doctrine.md` for the boundary of Taste (§1), scopes (§2), provenance fields (§4), lifecycle (§5), and the resolution order (§7).

## Outputs

- `taste-review-record`: findings graded Critical | Major | Minor | Info, one per check below, each with the evidence path it rests on, and a recommendation of APPROVED, REVISE, or ESCALATE for the `taste-review` gate. It is the hashed artifact behind the `taste_review_record` evidence key in `../../gates.yaml`.

## Workflow

1. **Provenance**: every added or updated entry carries `preference_id`, `scope`, a registry `category`, `source`, `strength`, `state`, and timestamps (doctrine §4); an imported entry keeps its original provenance; no entry encodes correctness, security, accessibility, architecture, or stack selection (§1).
2. **Confirmation**: every inferred candidate, scope-widening change, promotion, global reset, bulk import, and bulk revocation has a `confirmation` record whose `candidate_ids` equal the exact changed id set; nothing moved from `proposed` to `active` without it (§5). Confirmation is never waivable.
3. **Conflicts**: the `conflict_analysis` names every equal-precedence contradiction as unresolved rather than tie-breaking it, and every collision with a mandatory accessibility, safety, security, legal, or gate requirement is surfaced, not normalized (§1, §7).
4. **Redaction**: no entry, example, or rationale derives from protected or personal characteristics, and no secret, token, or personal data is persisted in the record or its evidence.
5. **Persistence safety**: `persistence_result` shows every requested destination committed atomically through `taste_prefs.py` with matching hashes, the before digest equals the store's prior revision, and global state stayed outside the checkout.
6. **Digest integrity**: the `effective_profile` digest matches its entries, and the `consumer_handoff` carries that same digest.
7. Write the review record to the destination named in the Save Context block and return the graded findings and recommendation to `taste`. Do not edit any package artifact; return REVISE to `taste` instead.

## Required Contracts

- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Read-only**: Never call a mutating `taste_prefs.py` operation and never edit `skillset-saves/preferences/` or the global store; a needed change is a REVISE finding for `taste`.
- **Evidence standard**: Apply `../../contracts/evidence-standards.md`; every Critical or Major finding names the artifact and the field it rests on.

## Failure Modes

| Scenario | Response |
| --- | --- |
| A `confirmation` record is missing for an inferred, promoted, reset, imported, or bulk-revoked entry, or its `candidate_ids` differ from the changed id set | Critical finding; recommend REVISE and name the ids that lack confirmation. |
| The `preference_diff` before digest does not match the store's prior revision, or `persistence_result` hashes differ from the files on disk | Major finding; recommend REVISE to `taste` for re-persistence, never repair the record. |
| Two entries of equal precedence contradict each other and the package records a winner | Major finding; the doctrine forbids tie-breaking, so the conflict must be surfaced as unresolved. |
| An entry encodes an accessibility, security, correctness, or stack decision as Taste | Critical finding; recommend ESCALATE with the mandatory requirement it collides with. |
| The package or its evidence cannot be read, or a hash cannot be verified | Do not infer a clean result; record the gap and recommend ESCALATE. |

## Save Protocol

When the Save Context block carries `Persistence active: yes`, write the review
record to the destination it names (normally
`skillset-saves/runs/{run-id}/taste/reports/taste-review-record.md`, resolved
with `python skills/scripts/output_paths.py --phase taste --kind reports`) and
return its path and sha256 so `taste` can register it as `taste_review_record`
in `taste/manifest.json`. Write nothing else. When persistence is inactive,
return the record inline.

## References

- `../SKILL.md` for the Taste pipeline owner, its writer commands, and the confirmation policy.
- `../references/workflow.md` for the record model and operation semantics under review.
- `../../taste-doctrine.md` for the canonical semantic contract this review enforces.
- `../../gates.yaml` for the `taste-review` evidence set and the typed record shapes.
