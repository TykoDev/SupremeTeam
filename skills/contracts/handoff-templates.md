# Handoff Templates

## Contents

- Responsibility
- Save Context
- Editing the Save Context block
- Request fields
- Response fields
- Gate submission (manifest schema 2)
- Taste package example
- Delegate obligations
- Enforcement
- Failure paths

## Responsibility

This contract standardizes the record passed between owners. It makes context,
identity, evidence, and the return boundary explicit; it does not decide which
owner is selected.

## Save Context

Include this block verbatim in every governed delegation. Replace every value
before sending it.

```markdown
### Save Context
- Run ID: {run-id}
- Phase: {phase}
- Save path: skillset-saves/runs/{run-id}/{phase}/
- Persistence active: {yes|no}
- Persistence probe result: {ok|reason}
- Context tier: {1|2|3}
- Preamble tier: {0|1|2|3} + rationale
- Artifact mode: {inline|file|reference}
- Session pin: {true|false}
- Execution mode: {agent|skill}
- Submission ID: {id}
- Revision: {revision}
- Owner: {owner}
- Expected artifact: {artifact}
- Evidence paths: {relative paths}
- Artifact hashes: {path: sha256|none yet}
- Risks: {known risks|none declared}
- Return boundary: {gate boundary for the returned package}
```

The two tier fields are different scales, and neither substitutes for the
other. `Context tier` feeds artifact-mode decisions: it grades how much context
the delegation must carry and selects `Artifact mode` as `inline`, `file`, or
`reference`. `Preamble tier` is the execution-contract blast-radius tier
required by clause 1 of [`../execution-contract.md`](../execution-contract.md),
recorded with the rationale that placed this run at that tier; it starts at 0
because the Tier 0 fast path is a real selection, not an absent one.

The block is a routing signal only when its run, owner, phase, revision, and
expected artifact are present and internally consistent. This template and the
copy in [`../save-protocol.md`](../save-protocol.md) carry the same field set;
neither may drop a field the other carries.

## Editing the Save Context block

That last rule is enforced, not asserted. The block above is the canonical copy,
and `SaveContextParityTests` in
[`../validation/test_catalog_contracts.py`](../validation/test_catalog_contracts.py)
compares against it every copy in the catalog that it recognizes — which is far
fewer files than mention the block, for the reason the next paragraph gives.

The comparator discovers copies by scanning: it reads every `*.md` file under
`skills/`, treats any file containing the words that title this block as a
candidate, parses field names from either a bulleted list or a table, and counts
a file as a real copy when it carries the anchor field naming the run. A
hardcoded list of copies was tried first and missed one — a normative field
table that dropped a field on the line after asserting that none may be dropped
— which is why discovery is by scan. At this revision 91 Markdown files under
`skills/` contain the words that title this block and the scan parses 10 of them:
this one and nine copies. The other 81 name the block in prose without carrying it, do not
reach the anchor, and are skipped — a real copy added without a `Run ID` line
would be skipped the same way. The canonical set is seventeen fields plus the
anchor.

Two consequences for an editor:

- Adding a field here makes every discovered copy fail until each carries it.
  Add the field to this block last, after the copies, or expect a red suite in
  between.
- Removing a field here removes it from the compared set and silently permits
  every copy to drop it. A field is removed from this block only as a deliberate
  contract change.

The comparator also asserts by name that the block carries the anchor field and
the execution-contract blast-radius tier field, so neither can be dropped even
if every copy dropped it at the same time. It compares field names only. No
value, no ordering, and no formatting is checked, and a copy that adds an extra
field of its own passes.

## Request fields

```yaml
request:
  goal: [one outcome]
  scope: [included work]
  non_goals: [explicit exclusions]
  inputs: [paths, decisions, and prior evidence]
  constraints: [runtime, security, timing, and format limits]
  acceptance: [observable conditions]
  return_boundary: [what the delegate may write and return]
```

## Response fields

```yaml
response:
  outcome: [completed, revised, blocked, or escalated]
  artifacts: [workspace-relative paths]
  artifact_hashes: [path=sha256 digest]  # from `python skills/scripts/content_hash.py <path>`: text folded to LF, binary byte-for-byte, so LF and CRLF checkouts agree
  evidence_paths: [workspace-relative paths]
  risks: [known residual risks]
  disputes: [unresolved decisions or none]
  next_action: [single safe next action]
  revision: [revision produced]
  return_boundary: [what was returned and what was not changed]
```

## Gate submission (manifest schema 2)

```yaml
schema_version: 2
run_id: [run id]                      # required inside skillset-saves/runs/<run>/<phase>/
boundary: [gate boundary]             # must equal the boundary being checked
owner: [submitter from gates.yaml]
submission_id: [id]
revision: [revision]                  # equals the single value in revisions
revisions: [revision]
evidence:
  [plain key]: [statement]
  [artifact key]: [manifest-relative hashed path, e.g. ../intake/report_grilling.md]
  [typed key]: {artifacts: [...], inputs: [{path, sha256}], result: {status: pass}}
  [waivable key]: {applicable: false, reason: ..., scope: ..., decided_by: ...}
artifact_hashes:
  [manifest-relative path]: [sha256]
```

Typed records (`scan`, `render`, `probe`, `audit`, `findings`, `verdict`,
`stack_lock`, `revision_ref`, and the Taste records `preference_diff`,
`confirmation`, `conflict_analysis`, `persistence_result`, `effective_profile`,
`consumer_handoff`, `variant_set`, and `selection`) and the finding policy are defined in
[`../gates.yaml`](../gates.yaml); destinations for reports, artifacts, evidence,
and packages in [`../save-ownership.yaml`](../save-ownership.yaml). Resolve every
destination with `python skills/scripts/output_paths.py` rather than composing
paths by hand.

Unlike the block above, this schema sketch is illustration. The authority for a
submission is `gates.yaml`, and the authority for whether one passes is the
checker below: a submission that satisfies this sketch and not the boundary
contract is rejected by the checker, not by this file.

Validate a submission with:

```text
python skills/harness/gatekeeper/check.py \
  --boundary <boundary> --package <manifest.json> \
  [--prior <previous verdict>] [--verdict-out <phase>/verdict_<boundary>.json]
```

Exit 0 is a mechanical fact, not approval. The gatekeeper maps the result to
`APPROVED`, `REVISE`, or `ESCALATE`. Exit 1 is a failed package; exit 2 is an
engine error — an unknown boundary or an unreadable gate spec — and an engine
error is never a verdict of any kind.

## Taste package example

This schema-2 package uses the shared checker at `taste-review`. Artifact-backed
records include their report path in `artifacts`; the abbreviated digests below
must be replaced by full SHA-256 values in a real package. The scope vocabulary
is the one `skills/taste/taste_prefs.py` accepts: `global`, `project`, or
`both`. Its twelve evidence keys are the twelve `taste-review` requires in
`gates.yaml`, in the order the spec lists them; six of those keys are
artifact-backed and appear in `artifact_hashes`.

```yaml
schema_version: 2
run_id: taste-42
boundary: taste-review
owner: taste
submission_id: taste-42-r3
revision: 3
revisions: [3]
evidence:
  scope: project preferences
  intent: revoke pref-old and promote pref-new
  before_revision: 2
  preference_diff: {artifacts: [evidence/preference-diff.json], added: [pref-new], updated: [], deprecated: [], revoked: [pref-old], unchanged: [pref-a], before_digest: "<sha256>", after_digest: "<sha256>"}
  confirmation: {artifacts: [evidence/confirmation.json], actor: user, timestamp: "2026-09-11T12:00:00Z", confirmed_scope: project, candidate_ids: [pref-new, pref-old], source_run: taste-42}
  conflict_analysis: {artifacts: [evidence/conflicts.json], conflicting_ids: [], precedence_decision: project-over-global, unresolved_conflicts: [], accessibility_policy_collisions: []}
  policy_check: passed
  persistence_result: {artifacts: [evidence/persistence.json], requested_destinations: [skillset-saves/preferences/taste.md], committed_revisions: [3], hashes: {skillset-saves/preferences/taste.md: "<sha256>"}, atomicity_status: committed, rollback_result: not-required}
  effective_profile: {artifacts: [evidence/effective-profile.json], entries: [{id: pref-new, source_scope: project, source_id: taste-42}], digest: "<sha256>"}
  consumer_handoff: {consuming_pipeline: design, effective_profile_digest: "<sha256>", applicability_summary: applies to UI design decisions}
  taste_review_record: {artifacts: [evidence/taste-review-record.md], findings: [], recommendation: APPROVED}
  residual_uncertainty: none observed
artifact_hashes:
  evidence/preference-diff.json: "<sha256>"
  evidence/confirmation.json: "<sha256>"
  evidence/conflicts.json: "<sha256>"
  evidence/persistence.json: "<sha256>"
  evidence/effective-profile.json: "<sha256>"
  evidence/taste-review-record.md: "<sha256>"
```

`confirmation` is not waivable at this boundary: an applicability record in its
place fails with `evidence not waivable: confirmation`.

## Delegate obligations

The delegate writes only the named artifact inside the supplied boundary. It
returns the response fields to the delegating owner and does not rewrite another
owner's state, handoff, or artifact. If persistence is inactive or the write
probe fails, it returns the same response inline and preserves the run and
revision.

## Enforcement

| Part of this contract | Backing |
|-----------------------|---------|
| The canonical block's field set, and its presence in every *recognized* copy | Machine-checked by `SaveContextParityTests` in `../validation/test_catalog_contracts.py`. Names only, in both list and table form, and only for a file carrying the `Run ID` anchor: 91 Markdown files under `skills/` contain the words "Save Context" and 10 are parsed — this one and nine copies. The other 81 are skipped. |
| The run anchor field and the blast-radius tier field exist in the canonical block | Machine-checked: the same test asserts both by name. |
| A submission satisfies its boundary | Machine-checked by [`../harness/gatekeeper/check.py`](../harness/gatekeeper/check.py) against `../gates.yaml`, not by this file. |
| The boundary named in a submission matches the boundary being checked, and the owner is that boundary's submitter | Machine-checked by `check.py`: `boundary mismatch`, `submitter mismatch`, and at schema 2 `missing boundary` and `missing owner`. |
| Destinations resolve inside a generated root | Machine-checked by [`../scripts/output_paths.py`](../scripts/output_paths.py) and `../validation/test_save_contracts.py`. |
| Field values in any block here | Judgement. No comparator reads a filled value, so a block with a wrong phase or a stale revision passes every test and fails only at the gate, or not at all. |
| The request and response field sets | Judgement. Nothing compares them to anything, and no skill is required to carry them. |
| The schema-2 sketch in Gate submission | Judgement as written here; the real contract is `gates.yaml`. |
| The Taste package example | Judgement. Its twelve keys match `taste-review` as of this revision and no test keeps them matched. |
| Delegate obligations | Judgement, except the one-writer consequence, which is enforced in `../ownership.yaml` by `../scripts/validate_manifests.py`. |

## Failure paths

- Persistence is inactive or the write probe fails. The delegate returns the
  same response inline, preserves the run and revision, and records the probe
  result in the block rather than inventing a save path.
- A field cannot be filled. State the reason in place of the value. A dropped
  line is drift the parity test will catch in a copy and will not catch here.
- A copy and this file disagree. This file is canonical for the field set; the
  copy is corrected. The comparator enforces that direction and no other.
- The comparator cannot run. The block is unverified, not verified: treat a copy
  edit as unproven and re-run the suite before relying on it.
- A submission passes the checker but the gatekeeper sees a contradiction. Exit
  0 is a mechanical fact, not approval, and the gatekeeper returns `REVISE` or
  `ESCALATE` on its own judgement.
- The checker exits 2. There is no verdict. Report the engine error and enter
  `ESCALATE` under [workflow-protocol](workflow-protocol.md); an engine error is
  never read as a pass.
- A delegation needs an artifact another owner writes. The delegate returns a
  finding and the requested change, and the delegating owner opens a new handoff
  at a new revision. Writing it directly breaks the one-writer rule in
  [responsibility-matrix](responsibility-matrix.md).
