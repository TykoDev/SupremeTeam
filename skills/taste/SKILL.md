---
name: taste
description: >-
  Owns the SupremeTeam preference lifecycle: normalize, confirm, persist, and resolve
  Taste preferences through taste_prefs.py, and runs the redesign taste-grilling
  stage when delegated. Preferences are design and product taste only — visual,
  interaction, tone, product shape — not coding or tool settings. Use when a user
  explicitly asks to remember, inspect, specialize, promote, revoke, reset, import,
  export, or show effective preferences — “remember that I prefer,” “save this
  globally,” “only in this project” — even phrased casually. Ordinary design
  feedback is not a preference change.
version: 1.1.2
allowed-tools: Read, Grep, Glob, Bash, Write, Agent, Task
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

## Use This Skill When

Use this skill to **change what is remembered** — an explicit lifecycle operation on the preference store, never ordinary design feedback:

- "remember that I prefer" / "save this globally" — capture a preference and choose its scope
- "only in this project" — specialize an existing preference down to the project scope
- "show my effective preferences" — resolve project over global and report what actually applies
- "revoke this preference" / "reset my preferences" — retire or clear records through the writer
- "export my preferences" — move canonical records out of a scope, with provenance intact

Route elsewhere for the read-only check of a package already assembled (`taste/taste-review`). Consuming a resolved profile during design or build opens no mutation pipeline, and a comment on one mockup is feedback, not a preference change.

## Entry and confirmation policy

Reached cold for an explicit Taste-management request, defer to Admiral. Preserve
routing precedence from `../routing-doctrine.md`. Read-only inspect, resolve, and
export operations do not need mutation confirmation. Obtain explicit confirmation
before every inferred preference or scope-widening change and before destructive
or bulk work. Promotion to global scope, global reset, bulk import, and bulk
revocation are never inferred from casual feedback and always require a fresh,
operation-specific confirmation.

## Execution Contract

Canonical source: `../execution-contract.md`. Stated locally because that file
requires every orchestrator and gatekeeper to carry the clauses verbatim; a paraphrase
is drift, and `skills/validation/test_catalog_contracts.py` compares them exactly.

1. Select the preamble tier before acting: Tier 0 for minor, understood, reversible tasks under the Tier 0 fast path in `skills/routing-doctrine.md`; Tier 1 for bounded read-only work beyond Tier 0; Tier 2 for multi-step edits, delegation, or external coordination beyond Tier 0; Tier 3 for destructive, security-sensitive, production, or irreversible work. Record the tier and rationale in the handoff, or the brief completion note for Tier 0. Tier 0 skips pipeline ceremony and full security audits, but retains focused verification and applicable guardrails; escalate when its eligibility no longer holds.
2. Trigger proactively when the task matches the skill's declared scope, even when the request uses different words; decline adjacent work and route end-to-end or specialist ownership explicitly. Offer a next safe action only after the current step, scope, and approval lineage are resolved; suppress that offer while any is unresolved.
3. Use Critical | Major | Minor | Info for findings. Block on Critical, resolve Major before a gate, record Minor, and preserve Info as context. Use APPROVED | REVISE | ESCALATE for gate verdicts.
4. Validate paths, inputs, revisions, and handoff fields before acting. Keep file operations inside the workspace, use read-only or dry-run probes first, and require explicit owner intent for destructive or externally visible actions.
5. Handle missing or malformed input, conflicting evidence, unsupported hosts or tools, empty results, and unavailable checks explicitly: preserve evidence, do not fabricate, return REVISE or ESCALATE, and state the next safe action.
6. Return Outcome, Evidence, Open risks, Next action, Revision, and Verdict when the skill owns a gate. A concise result without evidence is incomplete.

## Workflow

1. **Scope and intake:** select `global`, `project`, or `both`; capture the intended consumer and whether the request is read-only or mutating.
2. **Load current preferences:** use `taste_prefs.py status` and `taste_prefs.py list`, validate both records, and stop rather than overwriting malformed state. When one scope is corrupt but the other is intact — a damaged global record with a readable project record, or the reverse — the writer refuses the corrupt scope with `corrupt_record` and preserves its bytes; continue read-only work against the intact scope, surface the corrupt scope as a blocker for its owner to repair or move the file explicitly, and never resolve an effective profile that silently drops the unreadable side.
3. **Elicit evidence:** gather explicit examples, counterexamples, and anti-preferences; label any interpretation as inferred.
4. **Normalize:** make candidates concise and consistently identified without changing intent.
5. **Check:** detect conflicts, duplicate identifiers or meanings, accessibility problems, and ambiguous scope. Accessibility constraints override aesthetic preferences that would exclude users. An **equal-precedence contradiction that cannot be resolved** — two entries at the same scope that disagree, per `../taste-doctrine.md` §7 — is never broken by timestamp, input order, strength, or any tie-break: record the conflict, surface it, and obtain a fresh user decision before persisting either side. A project entry lawfully shadowing a global one is a resolution, not a conflict; only same-scope ties are unresolvable.
6. **Preview:** show the record diff plus the effective project-over-global preference preview before writing.
7. **Confirm:** obtain confirmation for inferred, scope-widening, destructive, or bulk changes under the policy above.
8. **Persist:** invoke `taste_prefs.py`; never edit canonical preference files directly. Its atomic replacement is the only write path.
9. **Resolve:** run `taste_prefs.py effective` to calculate the effective merged profile, where project entries override global entries only when their stable IDs match.
10. **Hand off:** emit a consumption handoff containing profile revision(s), scopes, effective entries, conflicts resolved, accessibility constraints, provenance, and the intended downstream pipelines.
11. **Gate:** submit the package as Taste, the canonical submitter, to `taste-review`. Self-check the schema-2 manifest first, per `../gates.yaml` `revise_policy.self_check`, and fix every mechanical failure before submitting — run it without `--verdict-out`:

    ```bash
    python skills/harness/gatekeeper/check.py --boundary taste-review --package skillset-saves/runs/<run-id>/taste/manifest.json
    ```

    `references/workflow.md` § Gate package and handoff lists the twelve evidence keys the boundary requires, which of them `taste-review` writes rather than Taste, and the manifest path the command above points at.
12. **Maintain:** later requests may inspect, specialize a global entry for one project, promote a project entry, revoke one entry, reset a scope, or import/export records. Apply the same preview and confirmation rules.

## Taste grilling

When `design/redesign` delegates the taste-grilling stage (through Admiral),
run the protocol in `../grill-me-doctrine.md` § Taste grilling against the design
inventory: one Taste category per prompt, each question anchored to what the
current surface does, a recommended answer every time. Write the
`taste-grilling-log` at the destination the delegation names
(`redesign/reports/taste-grilling.md`), then continue with steps 4 to 11 above
for the candidate set: normalize, check, preview, confirm, persist to project
scope (global only on a separate explicit confirmation), resolve, and hand the
immutable effective-profile snapshot back to `redesign`. When the user declines
to persist, return the log and the applicability record for the sanctioned
no-profile fallback; the answers remain current-run instructions for
`architect` and `prototyper`.

## Gate evidence this skill owns

Taste is the declared owner of three evidence keys in `../gates.yaml`, at two
boundaries it does not itself submit. Each is produced here and handed to the
submitting pipeline, so naming them is what makes them assemblable:

`references/workflow.md` § Gate package and handoff is authoritative for the full
`taste-review` evidence set; the three rows below are the keys this skill authors
at the two *design* boundaries, summarized so the submitting pipeline can name
them.

| Key | Boundary | Content | Artifact-backed | Fallback |
|-----|----------|---------|-----------------|----------|
| `taste_snapshot` | `design-to-build` | The immutable effective-profile snapshot and its digest, resolved at the moment the design package was assembled. | Yes — `artifact_evidence` at `design-to-build` names this key, so its value must reference a path present in the submitting manifest's `artifact_hashes` map | `no saved Taste profile available`, carried as the `reason` of an applicability record `{applicable: false, reason, scope, decided_by}`; at schema 2 the bare string is refused |
| `taste_snapshot` | `redesign-review` | The same snapshot for the redesign run, so variants are judged against the profile in force when they were built. | Yes — `artifact_evidence` at `redesign-review` names it here too | The same wording in the same applicability record; a snapshot that exists is shipped as a hashed file, never summarized |
| `taste_grilling` | `redesign-review` | The `taste-grilling-log`: one category per prompt, the recommended answer, and what the user actually confirmed. | Yes — `artifact_evidence` at `redesign-review` names it, so the log ships as a hashed file | None — `../gates.yaml` lists no fallback for this key, and only keys in `fallback_values` are waivable, so a redesign records the grilling or the boundary does not close |

The design pipeline's unconditional `taste-snapshot` stage delegates here, even
without a preference mutation. Resolve the effective profile through `taste_prefs.py`
and return a hashed immutable snapshot containing canonical digest, source revisions,
resolved entries and applicability to `design/commander`, under the active run's
design artifact destination. Both stores absent permits the sanctioned no-profile
record. An existing unreadable or corrupt store blocks resolution, not absence.
No mutation or new confirmation is inferred from ordinary consumption; preference
changes return through Admiral into the Taste lifecycle before a new snapshot.

A snapshot is immutable once handed over. When the profile changes mid-run, issue a new
snapshot with a new digest rather than editing the one already submitted — a consumer that
cited the old digest must be able to detect the drift.

## Writer commands

`taste_prefs.py` exposes `status`, `list`, `effective`, `diff`, `export`, `confirm`,
`deprecate`, `import`, `promote`, `propose`, `reset`, `revoke`, `set`, and `specialize`.
Every mutating subcommand requires `--scope`; run `--help` on any of them before composing
a call rather than assuming a flag.

```bash
# read (no --scope confirmation needed)
python skills/taste/taste_prefs.py status --scope project
python skills/taste/taste_prefs.py list --scope project
python skills/taste/taste_prefs.py effective --scope both

# first write into an empty scope (revision 0 -> 1)
python skills/taste/taste_prefs.py set --scope project --id density --value '{"category":"density","normalized_rule":"Prefer compact layouts","strength":"strong","source":"explicit"}'

# any later write requires --expect-revision (else the writer refuses with revision_required)
python skills/taste/taste_prefs.py set --scope project --expect-revision 1 --id spacing --value '{"category":"layout","normalized_rule":"Prefer tight spacing","strength":"soft","source":"explicit"}'

# promote writes global scope (or both) — never --scope project — with a revision per scope
python skills/taste/taste_prefs.py promote --scope both --expect-revision project=2 --expect-revision global=0 --id density

# a candidate is proposed with the doctrine fields, then confirmed on the user's explicit decision
python skills/taste/taste_prefs.py propose --scope project --expect-revision 3 --id tables.density --value '{"category":"density","normalized_rule":"Prefer compact table rows","strength":"soft","source":"confirmed-inference","confidence":0.6}'
python skills/taste/taste_prefs.py confirm --scope project --expect-revision 4 --id tables.density
```

`status`, `list`, `diff`, and `effective` read without mutating; `effective` resolves the
merged project-over-global profile. `diff` compares the two stores by `state` and `value`
(not `updated_at`) and takes only `--scope both`. `set` creates or supersedes a user-authored
entry, and every mutating subcommand (`set`, `confirm`, `deprecate`, `import`, `promote`,
`propose`, `reset`, `revoke`, `specialize`) writes only through the module's atomic
replacement — an edit tool never touches the canonical files. `pre_tool_use.py` (Rule C,
single writers) denies a direct write to the project store under
`skillset-saves/preferences/` by an edit tool or by a shell command, a redirect included.
The global store lives outside the checkout, where the guard reads no record, so a direct
write to it is not denied: there the single-writer rule is this skill's own discipline.

`propose` refuses a value that is not an object carrying `category`, `normalized_rule`,
`strength`, and `source` from `../taste-doctrine.md` §3 and §4. `set` and `import` accept any
JSON value, so record the same fields there yourself; `references/workflow.md` § Record
model states them. `export` is always redacted and lists what it removed as `redactions`;
`--redact` is accepted and does nothing. An id follows the field-name rule in
`references/workflow.md` § Ids and values: name what the preference is about, not a
credential or a personal datum.

A `confirm` on one operation is never permission for another: confirmation is per-operation,
so a fresh explicit decision is required for each inferred, scope-widening, destructive, or
bulk change. Bulk revocation must be decomposed into a preview and an explicitly confirmed
operation; repeated single-entry calls are not a way to evade that rule.

## Failure Modes

| Scenario | Response |
| --- | --- |
| `taste.lock` is held by another process — the writer exits with `locked` | Do not retry in a loop, and never delete the lock by hand or with an edit tool. The error names `holder_pid` and the lock's `age_seconds`. A lock whose holder is a process on this host that no longer exists, or that is older than ten minutes (`stale_after_seconds`), is not held: the next write removes it, appends a `lock_reclaimed` note to the store journal, and reports it as `lock_reclaimed` in the result, so a killed writer needs no manual recovery. On Windows only the age applies. A `locked` refusal that persists means a live writer started less than ten minutes ago holds the store; report that and re-run once it releases. |
| The writer exits `lock_lost` | Another writer reclaimed this writer's lock before it committed, so it had stalled for more than ten minutes, and nothing was written. Reload with `status`, re-resolve, re-preview against the new revision, and redo the change with the current `--expect-revision`. |
| The writer exits `write_failed` | The atomic write failed and both stores were rolled back to their prior bytes. Verify with `status`, then retry. If the error lists `unrestored` files, their prior bytes are in the named backups: stop and report them rather than retrying. |
| A revision conflict between the previewed state and the persist attempt — the writer exits `stale_revision`, or `revision_required` for an existing store | The record moved between preview and write. Reload with `status`, re-resolve, re-preview the diff against the new revision, obtain confirmation again if the change is still intended, and persist with the correct `--expect-revision`; never force the write. |
| The requested global root resolves inside the checkout — the writer exits `unsafe_global_path` | Global Taste may not live under the project tree, because a committed global record leaks one user's preferences into the repository. Point `SUPREMETEAM_HOME` (or `CODEX_HOME`/`AGENTS_HOME`) at a real user-data location outside the checkout, or record the preference at project scope instead. |
| A corrupt record in one scope with the other scope intact — the writer exits `corrupt_record` and preserves the bytes | Continue read-only against the intact scope, surface the corrupt scope for its owner to repair or move the file explicitly, and refuse to resolve an effective profile that would silently omit the unreadable side. When the record parsed but failed validation the error adds `reason` (`invalid_schema`, `invalid_record`, or `digest_mismatch`) and `detail`; report them with the path. |
| An import carries an unknown `schema` or `schema_version`, or entries that fail validation — the writer exits `invalid_schema`, `invalid_import`, `invalid_id`, or `sensitive_input` | Reject the import rather than coercing it; report the offending field or id. A schema the writer does not recognize is not silently upgraded, because a wrong assumption about shape would corrupt the store the import claims to populate. |
| A `propose` exits `invalid_entry` | The value lacks `category`, `normalized_rule`, `strength`, or `source`, or names an identifier outside `../taste-doctrine.md` §3 and §4. The error's `field` and `allowed` say what to fix; correct the candidate rather than weakening it to pass. |
| A value, field name, or id exits `sensitive_input` | Do not store it. A secret shape is refused, and so is a credential word in a field name or id, or a personal-data word ending one. Rename the id or field to say what the preference is about (`cli.prompt-style`, not `cli.prompt`). Use `--redact` only when the user agrees to lose the value, because it stores `[REDACTED]` in its place. |
| The writer exits non-zero for any reason (`emit(False)`, exit 1) | Treat the mutation as not applied — atomic replacement means a failed write left the prior record intact. Read the `error.code`, resolve it, and do not report a persistence result the writer did not return. |

## References

- `references/workflow.md` — the record model, mutation sequence, per-operation-to-subcommand mapping, id and value rules, lock recovery, the error-code table, and gate-package fields.
- `references/examples.md` — routing, confirmation, promotion, and accessibility-conflict examples.
- `taste_prefs.py` — the sole sanctioned writer for durable Taste records (standard-library only); every documented command invokes it, and `../harness/hooks/pre_tool_use.py` Rule C denies any other write to the project store — an edit-tool write or a shell redirect alike — while a write to the global store, outside the checkout, is not seen and so not denied.
- `test_taste_prefs.py` — the command-surface tests for `taste_prefs.py`: every subcommand and its refusals, scope and revision handling, the record's digest chain, history, journal, and rendered view, corrupt-record refusal, lock reclaim, and commit rollback.
- `test_taste_store.py` — the engine and safety unit tests: process probing and lock staleness, lock races, the commit helpers, global root resolution, owner identity, the secret and field-name validators, proposal validation, and the checks that keep the writer equal to `../taste-doctrine.md`. Run both suites (`python -m unittest discover -s skills/taste -p "test_*.py"`) after any change to the writer or its documented commands.
- `intake-brief.yaml` — the intake contract (scopes, inputs, confirmation triggers, outputs, acceptance).
- `stub-contract.md` — the ownership, persistence, confirmation, handoff, and gate boundary in brief.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/examples.md`, `intake-brief.yaml`, `stub-contract.md`, `taste_prefs.py`, `test_taste_prefs.py`, and `test_taste_store.py` together — the writer and its tests ship with the skill because the documented commands depend on them. `taste-review/` is a separate skill with its own owner and is not packaged here. Keep resolved snapshots, handoffs, and generated records under the run's save path, not inside the skill directory; durable Taste records live in the writer's own roots (`skillset-saves/preferences/` for project scope, the user-data root for global), never in the skill.
