# Taste workflow reference

## Record model

Taste maintains a global record and a project record. Each is schema-versioned,
revisioned, and contains uniquely identified entries with a value, kind
(`preference` or `anti-preference`), source (`explicit` or `inferred`), examples,
and counterexamples. The default global path is
`~/.agents/preferences/taste.json`; the default project path is
`skillset-saves/preferences/taste.md`. Despite the compatibility filename, the
project record contains JSON. Callers may override both paths for controlled
hosts and tests.

## Mutation sequence

1. Inspect and validate before proposing a mutation.
2. Preserve the user's language in evidence; normalize only the candidate.
3. Compare IDs and meanings across both scopes. Surface contradictions,
   duplicates, accessibility risks, and unclear target scope.
4. Render a before/after diff and resolve an effective preview.
5. Ask for confirmation when the candidate is inferred, widens scope, removes
   data, or affects a batch.
6. Persist with the writer, reload, resolve, and package the handoff.

Project entries override global entries with the same stable ID. They do not
silently erase global state. Specialization writes a project override; promotion
copies a confirmed project entry to global while leaving the project record
intact until separately revoked.

## Operations

- **inspect:** show one or both source records; read-only.
- **resolve:** show the effective merged profile; read-only.
- **specialize/upsert:** add or replace one scoped entry after preview. Inferred
  content requires confirmation.
- **promote:** copy project to global; always requires confirmation.
- **revoke:** remove a named entry. Confirm whenever destructive intent or scope
  is unclear; bulk revocation always requires explicit batch confirmation.
- **reset:** replace a scope with an empty revision. Global reset always requires
  confirmation.
- **import:** validate and replace a scoped record; always a confirmed bulk action.
- **export:** serialize a source or effective record without mutation.

## Gate package and handoff

The Taste owner submits `scope`, `intake`, `preference_diff`,
`effective_profile`, `policy_check`, `confirmation`, and `consumer_handoff` to
`taste-review`. The handoff identifies source revisions, stable IDs, intended
consumers, precedence, unresolved ambiguity, and accessibility constraints.
Downstream pipelines consume it as immutable input; they return requested
semantic changes to Taste rather than editing the record.
