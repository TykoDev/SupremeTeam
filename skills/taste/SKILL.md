---
name: taste
description: >-
  Owns the SupremeTeam preference lifecycle. Use when a user explicitly asks to
  remember, inspect, specialize, promote, revoke, reset, import, export, or show
  effective Taste preferences, including “remember that I prefer,” “save this
  style globally,” and “only use this preference in this project.”
version: 1.0.0
---

# Taste

## Purpose and ownership

Taste is the pipeline owner and **sole semantic owner** of preference-lifecycle
decisions. It may delegate evidence gathering or analysis, but it alone decides
the normalized preference meaning, writes canonical records through
`taste_prefs.py`, writes the consumer handoff, and submits the package to the
`taste-review` gate. Delegates never mutate preference records.

Ordinary design and build work consumes the resolved Taste profile without
opening this mutation pipeline. A standalone utility invocation also cannot
mutate Taste unless the user explicitly invokes preference management.

## Entry and confirmation policy

Reached cold for an explicit Taste-management request, defer to Admiral. Preserve
routing precedence from `../routing-doctrine.md`. Read-only inspect, resolve, and
export operations do not need mutation confirmation. Obtain explicit confirmation
before every inferred preference or scope-widening change and before destructive
or bulk work. Promotion to global scope, global reset, bulk import, and bulk
revocation are never inferred from casual feedback and always require a fresh,
operation-specific confirmation.

## Workflow

1. **Scope and intake:** select `global`, `project`, or `both`; capture the intended consumer and whether the request is read-only or mutating.
2. **Load current preferences:** use `taste_prefs.py inspect`, validate both records, and stop rather than overwriting malformed state.
3. **Elicit evidence:** gather explicit examples, counterexamples, and anti-preferences; label any interpretation as inferred.
4. **Normalize:** make candidates concise and consistently identified without changing intent.
5. **Check:** detect conflicts, duplicate identifiers or meanings, accessibility problems, and ambiguous scope. Accessibility constraints override aesthetic preferences that would exclude users.
6. **Preview:** show the record diff plus the effective project-over-global preference preview before writing.
7. **Confirm:** obtain confirmation for inferred, scope-widening, destructive, or bulk changes under the policy above.
8. **Persist:** invoke `taste_prefs.py`; never edit canonical preference files directly. Its atomic replacement is the only write path.
9. **Resolve:** run `taste_prefs.py resolve` to calculate the effective merged profile, where project entries override global entries only when their stable IDs match.
10. **Hand off:** emit a consumption handoff containing profile revision(s), scopes, effective entries, conflicts resolved, accessibility constraints, provenance, and the intended downstream pipelines.
11. **Gate:** submit the package as Taste, the canonical submitter, to `taste-review` using `../harness/gatekeeper/check.py`.
12. **Maintain:** later requests may inspect, specialize a global entry for one project, promote a project entry, revoke one entry, reset a scope, or import/export records. Apply the same preview and confirmation rules.

See [references/workflow.md](references/workflow.md) for operation details and
[references/examples.md](references/examples.md) for routing and confirmation
examples. `intake-brief.yaml` defines intake and `stub-contract.md` defines the
handoff and writer boundary.

## Writer commands

```bash
python skills/taste/taste_prefs.py inspect --scope project
python skills/taste/taste_prefs.py upsert --scope project --id density --value "Prefer compact layouts"
python skills/taste/taste_prefs.py resolve
python skills/taste/taste_prefs.py promote --id density --confirm
```

Never treat `--confirm` as permission carried over from an unrelated action.
Bulk revocation must be decomposed into a preview and an explicitly confirmed
operation; repeated single-entry calls are not a way to evade that rule.
