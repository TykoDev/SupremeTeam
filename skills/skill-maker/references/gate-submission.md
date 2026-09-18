# Gate Submission Reference

Read this when assembling or repairing the `skill-maker-to-delivery` package.
`../SKILL.md` § Gate submission states the two rules that decide most
submissions; this file carries the mechanics behind them and the routing table
for a failed self-check.

## Contents

1. The self-check command
2. Artifact backing and the applicability record
3. Routing a failed self-check by owner

Run the self-check before submitting, so the boundary is judged deterministically:

```bash
python skills/harness/gatekeeper/check.py --boundary skill-maker-to-delivery --package <manifest.json>
```

`link_report` and `validation_report` must reference hashed files in the package's
`artifact_hashes` map. A bare claim that validation passed is not evidence. A
single-skill run carries the sanctioned `team_manifest` wording byte-for-byte as
the `reason` of an applicability record
`{applicable: false, reason, scope, decided_by}`, never as the key's own value:
the manifest is `schema_version: 2`, where `check.py` refuses a bare fallback
string outright. A paraphrase such as "no team was created" is not the sanctioned
wording and fails the mechanical check before any judgment is applied, and so
does the sanctioned wording written as a bare string.

**When the self-check fails**, do not submit. The checker groups every failure by
the evidence key it names and by that key's owner, so read the failure list as a
routing table:

| Failure | Response |
| --- | --- |
| A key is missing or falsy | Re-delegate to that key's owner: `link_report` to skill-reviewer, `validation_report` to skill-creator, `skills` and `team_manifest` to this orchestrator's own packaging step. Never fill another owner's key to make the check pass. |
| `link_report` or `validation_report` names a path absent from `artifact_hashes` | The file was described rather than shipped. Get the file written and hashed, then rebuild the manifest; hand-adding the hash of a file nobody produced is a fabricated artifact. |
| `team_manifest` carries a paraphrase, or a bare string — even the sanctioned one | Put the exact wording `single skill - no team manifest produced` in the `reason` field of an applicability record `{applicable: false, reason, scope, decided_by}`, or produce the real manifest for a team run. Re-spelling the value is not the fix; re-shaping it is. **Know which half the machine catches.** A bare string carrying the *sanctioned* wording is rejected outright: `bare fallback string not accepted at schema 2: team_manifest (use an applicability record)`. A **paraphrase passes the self-check silently** — `team_manifest` has no row in `../../gates.yaml` `evidence_types`, so no typed check runs on it, and a non-path string that does not match a sanctioned wording trips nothing in `check.py:400-425`. The perverse consequence is worth stating: being precise fails the machine and being vague does not. A paraphrase is caught downstream by gatekeeper judgment and returned as `REVISE`, never by the checker — so a green self-check is not evidence this key is well-formed. Read the value yourself before submitting. `references/examples.md` shows the record. |
| The checker itself errors, or the boundary spec cannot be loaded | Treat gate-engine failure as `ESCALATE`, never as approval. Report the error and the unjudged package rather than submitting on a machine that did not run. |
