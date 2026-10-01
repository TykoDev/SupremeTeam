# Taste workflow reference

## Record model

Taste maintains a global record and a project record. Each is schema-versioned,
revisioned, and holds uniquely identified entries. The writer stores an entry as
`state`, `value`, and `updated_at`; the fields that describe the preference sit
inside `value` and are defined by `../../taste-doctrine.md` §4, which is
canonical: `category` (one of the eleven §3 identifiers, `anti-preference` among
them), `normalized_rule`, `strength` (`hard`, `strong`, or `soft`), `source`
(`explicit`, `imported`, or `confirmed-inference`), and, when they apply,
`rationale`, `source_run`, `confidence` for an inference candidate,
`applicability_selectors`, `conflicts`, and `supersedes` / `superseded_by`. The
user's own examples and counterexamples are evidence for the run, kept in the
intake and diff artifacts and summarised in `rationale`; they are not entry
fields. `propose` refuses a value that lacks `category`, `normalized_rule`,
`strength`, or `source`, or that uses an identifier outside the doctrine
(`invalid_entry`). `set` and `import` accept any JSON value, so the same fields
are the contract on Taste there, and entries stored in another shape are read
and resolved unchanged.

The global record lives outside every checkout, under `preferences/` in the
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
- **diff:** `diff` — entries whose `state` or `value` differs between the project
  and global stores; read-only. `updated_at` is not compared, so a preference
  written to both scopes reads as the same, and only `--scope both` is accepted.
- **propose:** `propose` — create a `proposed` candidate awaiting a decision;
  inference records its confidence and never activates without `confirm`. The
  value is a JSON object with the doctrine §4 fields, for example
  `{"category":"density","normalized_rule":"Prefer compact table rows","strength":"soft","source":"explicit"}`.
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
  always a confirmed bulk action. A file that declares a `schema` must name
  `supremeteam-taste-preferences` or `supremeteam-taste-export` at
  `schema_version` 1, or it is rejected as `invalid_schema` rather than coerced;
  an invalid id is `invalid_id`. Every imported entry becomes `active`.
- **export:** `export` (`--output <file>`) — serialize a source or effective
  record without mutation. **Redaction is always on.** The command replaces
  secret-shaped values, drops fields named for a credential or personal datum,
  truncates text over 1000 characters, and lists each one as `redactions` in its
  result (`path` and `action`: `dropped`, `redacted`, or `truncated`, never the
  content), so nothing leaves the export silently. The `--redact` flag is
  accepted and does nothing, because redaction is a safety property that must not
  be switchable; the flag stays so callers that already pass it keep working.
  Treat an export as redacted whether or not the flag appears in the command.

A mutating subcommand against an existing store requires `--expect-revision` to
guard against a concurrent write, and refuses with `revision_required` without it.
Pass one shared value (`--expect-revision 2`) for a single scope, or one flag per
scope for `--scope both` (`--expect-revision project=2 --expect-revision
global=0` — repeated flags, not a single slash-joined value). A mismatch exits
`stale_revision` and changes nothing, so reload with `status` and re-preview
before retrying.

## Ids and values

An id is a stable lowercase label (`[a-z0-9][a-z0-9._-]{0,127}`) fixed when an
entry is created by `propose`, `set`, `import`, `promote`, or `specialize`. It may
not embed a secret, and it follows the same rule as a field name inside a value:
a credential word anywhere in it (`password`, `secret`, `credential`,
`authorization`, `ssn`, `api-key`, `private-key`, `social-security`, `full-name`,
`user-name`), or a personal-data word at its end (`token`, `cookie`, `prompt`,
`conversation`, `email`, `phone`, `address`, with or without a number, id, or
value qualifier), is refused as `sensitive_input`, and `--redact` does not waive
it. The words match whole words, so design vocabulary that reuses them as
qualifiers passes: `design-tokens`, `phone-layout`, `email-density`,
`cookie-banner`, `address-bar`, and `prompt-style` are ordinary ids and field
names. Say what the preference is about (`cli.prompt-style`, not `cli.prompt`).

A text value is refused when it holds a secret shape (an email address, a private
key block, a `Bearer` credential, or an `sk-`, `sk_live_`, `ghp_`, `github_pat_`,
or `xox` key with a token-shaped tail). Words such as `skeleton-loading-states` or
`skeuomorphic-glass-theme` are not secrets: an `sk-` tail must be at least 16
characters and carry a digit, which real keys do and these words do not. Text over
1000 characters and lists over 100 items are refused. `--redact` replaces a secret
value with `[REDACTED]`, drops a sensitive field, and truncates long text after
scanning it, so nothing it replaces is stored.

## Lock and recovery

A mutation takes `taste.lock` in each scope it writes with `O_CREAT | O_EXCL` and
records its `pid`, an opaque `host` hash, `created_at`, and a random `token` in
it. It releases a lock only while the token is still its own, and it checks the
token again immediately before committing, refusing with `lock_lost` when another
writer reclaimed the lock in between.

A killed writer does not wedge the store. Before it refuses with `locked`, the
writer reclaims a lock that is provably abandoned: the holder was recorded on
this host and that process no longer exists (`holder-dead`), or the lock is older
than ten minutes (`expired`), because a mutation holds it for milliseconds. A lock
file with no readable content is judged by its modification time, and Windows
cannot probe a process, so only the age applies there. A reclaim appends a
`lock_reclaimed` note to the store journal (`event`, `at`, `scope`, `reason`, and
the prior `pid` and `created_at`) and is reported as `lock_reclaimed` in the
result, including on a write that is then refused. Never delete `taste.lock` by
hand or with an edit tool. A `locked` refusal that survives this means a live
writer holds the lock, so wait for it; the error names the holder's pid, the
lock's age, and the ten-minute bound.

## Error codes

A refusal the writer reports is a JSON `error` with a `code` and exit status 1,
and it leaves the prior record intact unless `write_failed` lists `unrestored`
files; a usage error is argparse's, exit status 2 with no JSON. `SKILL.md`
§ Failure Modes says what to do about the refusals that need a decision; this
table names them all.

| Code | Raised when |
| --- | --- |
| `missing_value` | `set` or `propose` without `--value` |
| `invalid_id` | the id is absent or not a stable lowercase identifier, or an imported id is not |
| `sensitive_input` | a value holds a secret shape, a field name or an id names a credential or personal datum |
| `unbounded_input` | text over 1000 characters or a list over 100 items, unless `--redact` truncates the text |
| `invalid_input` | a value that is not JSON data reaches the validator (a guard for in-process callers; the command line always parses JSON) |
| `invalid_entry` | a `propose` value lacks `category`, `normalized_rule`, `strength`, or `source`, or names an identifier outside the doctrine; `field` and `allowed` say which |
| `not_found` | `confirm`, `deprecate`, or `revoke` names an absent id, or `promote` or `specialize` finds no such id in its source |
| `invalid_state` | `confirm` on an entry that is not `proposed` |
| `invalid_scope` | `promote` without `global` or `both`, `specialize` without `project` or `both`, or `diff` without `both` |
| `invalid_revision` | a malformed `--expect-revision` |
| `revision_required` | a write to an existing store without `--expect-revision` |
| `stale_revision` | the expected revision differs from the store's; `scope`, `expected`, and `actual_revision` say how |
| `locked` | a live writer holds the lock; `holder_pid`, `age_seconds`, and `stale_after_seconds` say who and how long |
| `lock_lost` | the lock was reclaimed while this writer held it; nothing was written |
| `write_failed` | the atomic write failed and was rolled back; `reason` says why, and `unrestored` lists any file that could not be restored with the backup that keeps its prior bytes |
| `corrupt_record` | a store is unreadable, or parses but fails validation; a validation failure adds `reason` (`invalid_schema`, `invalid_record`, or `digest_mismatch`) and `detail`, and the original bytes are preserved |
| `unsafe_global_path` | the global root resolves inside the checkout |
| `invalid_import` | the import file is unreadable, is not a map of entries, or holds more than 1000 |
| `invalid_schema` | an import declares a schema or version the writer does not recognise |

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
