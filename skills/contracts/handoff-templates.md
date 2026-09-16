# Handoff Templates

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

The block is a routing signal only when its run, owner, phase, revision, and
expected artifact are present and internally consistent. This template and the
copy in [`../save-protocol.md`](../save-protocol.md) carry the same field set;
neither may drop a field the other carries.

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
  artifact_hashes: [path=sha256 digest]
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
`consumer_handoff`) and the finding policy are defined in
[`../gates.yaml`](../gates.yaml); destinations for reports, artifacts, evidence,
and packages in [`../save-ownership.yaml`](../save-ownership.yaml). Resolve every
destination with `python skills/scripts/output_paths.py` rather than composing
paths by hand.

Validate a submission with:

```text
python skills/harness/gatekeeper/check.py \
  --boundary <boundary> --package <manifest.json> \
  [--prior <previous verdict>] [--verdict-out <phase>/verdict_<boundary>.json]
```

Exit 0 is a mechanical fact, not approval. The gatekeeper maps the result to
`APPROVED`, `REVISE`, or `ESCALATE`.

## Taste package example

This schema-2 package uses the shared checker at `taste-review`. Artifact-backed
records include their report path in `artifacts`; the abbreviated digests below
must be replaced by full SHA-256 values in a real package.

```yaml
schema_version: 2
run_id: taste-42
boundary: taste-review
owner: taste
submission_id: taste-42-r3
revision: 3
revisions: [3]
evidence:
  scope: repository preferences
  intent: revoke pref-old and promote pref-new
  before_revision: 2
  preference_diff: {artifacts: [evidence/preference-diff.json], added: [pref-new], updated: [], deprecated: [], revoked: [pref-old], unchanged: [pref-a], before_digest: "<sha256>", after_digest: "<sha256>"}
  confirmation: {artifacts: [evidence/confirmation.json], actor: user, timestamp: "2026-09-11T12:00:00Z", confirmed_scope: repository, candidate_ids: [pref-new, pref-old], source_run: taste-42}
  conflict_analysis: {artifacts: [evidence/conflicts.json], conflicting_ids: [], precedence_decision: repository-over-user, unresolved_conflicts: [], accessibility_policy_collisions: []}
  policy_check: passed
  persistence_result: {artifacts: [evidence/persistence.json], requested_destinations: [skillset-saves/preferences/taste.md], committed_revisions: [3], hashes: {skillset-saves/preferences/taste.md: "<sha256>"}, atomicity_status: committed, rollback_result: not-required}
  effective_profile: {artifacts: [evidence/effective-profile.json], entries: [{id: pref-new, source_scope: repository, source_id: taste-42}], digest: "<sha256>"}
  consumer_handoff: {consuming_pipeline: design, effective_profile_digest: "<sha256>", applicability_summary: applies to UI design decisions}
  residual_uncertainty: none observed
artifact_hashes:
  evidence/preference-diff.json: "<sha256>"
  evidence/confirmation.json: "<sha256>"
  evidence/conflicts.json: "<sha256>"
  evidence/persistence.json: "<sha256>"
  evidence/effective-profile.json: "<sha256>"
```

## Delegate obligations

The delegate writes only the named artifact inside the supplied boundary. It
returns the response fields to the delegating owner and does not rewrite another
owner's state, handoff, or artifact. If persistence is inactive or the write
probe fails, it returns the same response inline and preserves the run and
revision.
