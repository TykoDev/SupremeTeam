# Taste workflow reference

## Record model

Taste maintains a global record and a project record. Each is schema-versioned,
revisioned, and contains uniquely identified entries with a value, kind
(`preference` or `anti-preference`), source (`explicit` or `inferred`), examples,
and counterexamples. The global record lives outside every checkout, under `preferences/` in the
deterministic user-data root that `taste_prefs.py` resolves (`SUPREMETEAM_HOME`,
then `CODEX_HOME` or `AGENTS_HOME` plus `supremeteam`, then the platform data
directory); the project record lives at `skillset-saves/preferences/`. Each
scope holds a canonical `taste.json`, a rendered `taste.md`, `_history/`,
`taste.journal.jsonl`, and `taste.lock`, written only by `taste_prefs.py`
(`../../save-ownership.yaml`, class `project-taste-preferences`). Callers may
override both roots for controlled hosts and tests.

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

Each semantic operation maps to a concrete `taste_prefs.py` subcommand. Every
mutating subcommand requires `--scope` (`global`, `project`, or `both`); run
`--help` on a subcommand before composing a call rather than assuming a flag. The
read subcommands (`status`, `list`, `diff`, `effective`, `export`) do not mutate
and need no confirmation.

- **inspect:** `status` (record path, revision, digest, existence) and `list`
  (entries per scope); read-only.
- **resolve:** `effective` — the merged profile, project entries overriding global
  by matching stable id; read-only.
- **diff:** `diff` — entries that differ between scopes; read-only.
- **propose:** `propose` — create a `proposed` candidate awaiting a decision;
  inference records its confidence and never activates without `confirm`.
- **confirm:** `confirm` — move a `proposed` entry to `active`; only a `proposed`
  entry can be confirmed.
- **set / upsert:** `set` — create or supersede one user-authored entry as
  `active` after preview. Inferred content is proposed and confirmed, not set
  directly.
- **specialize:** `specialize` (writes project, or `both`) — copy a global entry
  into a project override; the source global entry is untouched.
- **promote:** `promote` (writes global, or `both`) — copy a confirmed project
  entry to global; always requires confirmation and leaves the project record
  intact until separately revoked.
- **deprecate:** `deprecate` — retain an entry for history while excluding it from
  resolution.
- **revoke:** `revoke` — tombstone a named entry. Confirm whenever destructive
  intent or scope is unclear; bulk revocation always requires explicit batch
  confirmation and is decomposed into a preview plus a confirmed operation.
- **reset:** `reset` — tombstone every entry in a scope, replacing it with an empty
  revision. Global reset always requires confirmation.
- **import:** `import` (`--input <file>`) — validate and merge external entries;
  always a confirmed bulk action, and an unknown `schema_version` or an invalid id
  is rejected rather than coerced.
- **export:** `export` (`--output <file>`) — serialize a source or effective
  record without mutation. **Redaction is always on.** The `--redact` flag exists
  but is declared `default=True`, so passing it changes nothing and there is no
  way to export unredacted; treat an export as redacted whether or not the flag
  appears in the command.

A mutating subcommand against an existing store requires `--expect-revision` to
guard against a concurrent write, and refuses with `revision_required` without it.
Pass one shared value (`--expect-revision 2`) for a single scope, or one flag per
scope for `--scope both` (`--expect-revision project=2 --expect-revision
global=0` — repeated flags, not a single slash-joined value). A mismatch exits
`stale_revision` and changes nothing, so reload with `status` and re-preview
before retrying.

## Gate package and handoff

`../SKILL.md` § Gate evidence summarizes the three keys this skill authors at the
two design boundaries; this section is the authoritative one for the full
`taste-review` set. The Taste owner submits the evidence set declared in
`../../gates.yaml`: `scope`, `intent`, `before_revision`, `preference_diff`,
`confirmation`, `conflict_analysis`, `policy_check`, `persistence_result`,
`effective_profile`, `consumer_handoff`, `taste_review_record` (written by
`taste-review`), and `residual_uncertainty`, as a schema-2 manifest at
`skillset-saves/runs/{run-id}/taste/manifest.json`. The handoff identifies source revisions, stable IDs, intended
consumers, precedence, unresolved ambiguity, and accessibility constraints.
Downstream pipelines consume it as immutable input; they return requested
semantic changes to Taste rather than editing the record.
