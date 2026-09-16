# Boundary Evidence Reference

Read this when a build submission is in hand and the question is *what a specific
key must be* — a hashed artifact or a claim, which typed record shape, and
whether a waiver is admissible. `../SKILL.md` carries the boundary table, the
owner table, and the two key spaces; this file carries the per-key detail.
`../../../gates.yaml` is the authority: where this file and the spec disagree,
the spec wins and this file is the defect.

## Contents

1. `build-to-review`, key by key
2. What a `probe` record must contain
3. The one sanctioned waiver, verbatim
4. Reading the untyped keys

## 1. `build-to-review`, key by key

Submitter `build-management`. Six required keys; two artifact-backed.

The "Record type" column is the shape `../../../gates.yaml` `evidence_types`
assigns the key. The boundary validator `../../../harness/gatekeeper/check.py`
enforces that shape **only when the manifest declares `schema_version: 2`**; on a
legacy manifest with no `schema_version` the typed column is advisory. The two
columns are split accordingly. (`../scripts/check.py` is a different file and
checks none of this — it looks at filenames in the package directory.)

| Key | Backing | Record type | Enforced at every schema | Additionally enforced at schema 2 | Owner |
| --- | --- | --- | --- | --- | --- |
| `tests` | artifact | `probe` | present, and names a correctly hashed path in `artifact_hashes`, else `evidence not artifact-backed: tests` | a `probe` record at `result.status: pass`, else `tests must be a typed probe record at schema 2`, `tests record declares no artifacts`, or `tests result not passing: <status>`. The artifact is the test-runner log itself, a hashed file under `build/evidence/` | test-builder |
| `runtime` | artifact | `probe` | the same, with `runtime` substituted in each string | the same, for the startup / entry-point smoke log. The key most often absent | health-check |
| `approved_design_revision` | claim | `revision_ref` | present and non-falsy, so the empty string reads `missing evidence: approved_design_revision` | a non-empty, non-boolean scalar, else `approved_design_revision must name an approved upstream revision`. Whitespace-only is truthy, so it fails here, not as missing | build-management |
| `security_evidence` | claim | `findings` | presence only — any non-empty string passes | `{items: [{id, severity, status, owner?, reopen_trigger?, reason?}]}` with each `severity` in Critical / Major / Minor / Info, or the one sanctioned applicability record. See §3 | security-builder |
| `implementation` | claim | untyped | present and non-falsy | nothing further — `evidence_types` has no rule for this key | bob-the-builder |
| `traceability` | claim | untyped | present and non-falsy. This is what maps each change back to the approved design item it satisfies | nothing further — `evidence_types` has no rule for this key | build-management |

Three of the six — `approved_design_revision`, `implementation`, `traceability` —
accept any non-empty string at either schema version. "Accepts no fallback" on
those keys means an `{applicable: false, …}` record is refused as
`evidence not waivable: <key>`; it does not mean prose is refused. Reading them
is §4's job, not the validator's.

## 2. What a `probe` record must contain

`../../../gates.yaml` `evidence_type_rules` defines `probe` as a record with
hashed artifacts and `result.status: pass`, where the executed logs are the
artifacts. At this boundary it adds the specific reading:

- `tests` is the test-runner log.
- `runtime` is the startup / entry-point smoke log.
- Each is a hashed file under `build/evidence/`.
- A bare count or claim is not evidence.

That last line is the whole point of making the pair artifact-backed. A summary
can be written without running anything; a log cannot. At manifest schema 2 the
rule widens further — every path-shaped string in an evidence value must be a
correctly hashed artifact — so a `tests` value that merely mentions a log path is
checked as though it named one, and fails if the hash is absent or stale.

A record whose `result.status` is `fail`, `error`, `not-run`, or `unavailable`
does not satisfy the key. An unavailable check is a data gap, never a pass.

## 3. The one sanctioned waiver, verbatim

Only `security_evidence` is waivable at this boundary, and only as a typed
applicability record — `{applicable: false, reason, scope, decided_by}` — whose
reason is exactly:

```text
no trust-boundary change - security-builder not engaged
```

`security_evidence` is not in this boundary's `artifact_evidence`, so no
artifact-backing check ever runs on it. What rejects a bare string is the typed
check, and that runs at `schema_version: 2` only:

| Value at this key | schema 1 | schema 2 |
| --- | --- | --- |
| the applicability record above | passes | passes |
| the sanctioned wording as a bare string | passes | `bare fallback string not accepted at schema 2: security_evidence (use an applicability record)` |
| any other explanatory string | passes | `security_evidence must be a findings record with an items list at schema 2` |
| a `{items: [...]}` findings record | passes | passes, each item's `severity` checked against `['Critical', 'Info', 'Major', 'Minor']` |

Two consequences worth holding separately. At schema 2 the sanctioned wording is
not a password: it fails as a bare string and passes only inside the record. At
schema 1 nothing at this key fails, so a schema-1 package leaves the entire
security question to judgment — which is why `../SKILL.md` returns `REVISE` on a
manifest that omits `schema_version`.

A waiver on any of the other five keys fails as `evidence not waivable: <key>` at
both schema versions, rather than as a bad reason. The distinction matters when
routing the `REVISE`: the first is `security-builder` supplying a record, the
second is a key that simply has to be produced.

## 4. Reading the untyped keys

`implementation` and `traceability` are checked only for presence and
non-falsiness, at every schema version — `evidence_types` assigns neither a
record shape. `approved_design_revision` is barely stronger: at schema 2 it must
be a non-empty scalar, which any sentence satisfies. The validator cannot tell an
adequate traceability map from a paragraph that uses the word "traceability", and
cannot tell an approved design revision from the words "the approved one".

That gap is the judgment half of this gate:

- For `implementation`, ask whether the described change set matches the code surface the package actually carries — every changed module accounted for, nothing in the diff that the summary omits.
- For `traceability`, ask whether each change maps to an approved design item, and treat an unmapped change as scope the design never authorised.
- For `approved_design_revision`, ask whether the named revision has an approval record — the sibling `design/verdict_design-to-build.json` under the same `skillset-saves/runs/{run-id}/`, at that revision. The validator checks that the field is a non-empty scalar and nothing more; whether anyone approved it is entirely this gate's read.
- Treat a value that only restates the key name as absent.

## Cross-references

- `../../../gates.yaml` — the authority for everything on this page.
- `../SKILL.md` — boundary table, owner routing, key-space collisions, failure modes.
- `workflow.md` — the order these checks run in.
- `examples.md` — worked submissions applying them.
