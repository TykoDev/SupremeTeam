# Gate Submission Reference

Read this in pipeline mode, before assembling the `deploy-readiness` submission or responding
to a `REVISE`. SKILL.md carries the five evidence keys, their owners, and the self-check
command; this file carries the manifest shape, the packet routing across two owners, the
escalation cap, and the repeat-release rule.

## Contents

1. Manifest shape
2. Which keys `ship` may fill, and which it may not
3. Responding to a REVISE
4. Repeat releases: current-run snapshots
5. Standalone mode

## 1. Manifest Shape

One JSON file at the run's `release/` phase destination, resolved with
`python skills/scripts/output_paths.py --run-id <run> --phase release --kind manifest`:

```json
{
  "schema_version": 2,
  "boundary": "deploy-readiness",
  "owner": "ship",
  "run_id": "2026-04-19-web",
  "submission_id": "2026-04-19-web_deploy-readiness_attempt-1",
  "revisions": [2],
  "revision": 2,
  "evidence": {
    "approved_delivery": "rev-8f21c0a",
    "deploy_config": "artifacts/deploy-config.yaml",
    "verification_plan": "artifacts/verification-plan.md",
    "rollback_plan": "artifacts/rollback-plan.md",
    "human_go_required": {"decision": "go", "approver": "release-owner", "approval_reference": "GO-2026-04-19-01", "revision": "rev-8f21c0a", "decided_at": "2026-04-19T20:05:00Z"}
  },
  "artifact_hashes": {
    "artifacts/deploy-config.yaml": "<sha256>",
    "artifacts/verification-plan.md": "<sha256>",
    "artifacts/rollback-plan.md": "<sha256>"
  }
}
```

Three keys are artifact-backed and must name a path present in `artifact_hashes`, hashed to
match the file on disk. Paths are manifest-relative and stay inside the run's own directory;
`..` traversal, another run, and absolute, drive-qualified, or UNC paths are rejected, which is
why every destination is composed with `output_paths.py` rather than by hand.

`approved_delivery` is typed `revision_ref`: a non-empty approved upstream revision identifier,
not artifact-backed. `human_go_required` is typed `human_go`: decision `go`, non-blank
approver, approval_reference, revision and timezone-qualified ISO decided_at. Its revision
must equal approved_delivery. Identity and freshness are still verified by the owner. `../../gates.yaml` sanctions **no** fallback
value for any of the five, so no applicability record waives any of them — this boundary has no
waivable key at all, which is why a missing value is always a repair and never a note.

Every manifest, at any schema, needs `submission_id` and a `revision` matching the single
`revisions` value; the checker reports a missing one as `missing submission_id` or
`missing revision`. `schema_version: 2` adds `boundary`, `owner`, and `run_id` inside a run.
Advance both `submission_id` and `revision` on every resubmission.

## 2. Which Keys `ship` May Fill, and Which It May Not

Per-key detail, in the order the boundary lists them:

| Key | Type | Backing | Value shape the checker accepts |
| --- | --- | --- | --- |
| `approved_delivery` | `revision_ref` | none | A non-empty approved upstream revision identifier from the approved review or delivery package |
| `deploy_config` | plain | artifact | A path present in `artifact_hashes`, hashed to match the file |
| `verification_plan` | plain | artifact | A path present in `artifact_hashes`, hashed to match the file |
| `rollback_plan` | plain | artifact | A path present in `artifact_hashes`, hashed to match the file |
| `human_go_required` | `human_go` | none | `{decision: go, approver, approval_reference, revision, decided_at}`; exact revision match, timezone-qualified ISO timestamp |

A stale or missing `approved_delivery` is a blocker rather than a waiver, an artifact-backed key
stated in prose fails the artifact check, and `human_go_required` is never satisfied by
prerequisite checks, artifact validation, or CI status — those are readiness signals, and this
key records a decision.

`ship` submits the package and owns the mechanical result, but owns only three of the five keys.
`deploy_config` and `rollback_plan` belong to `setup-deploy` under `../../gates.yaml`
`evidence_owners`, and `../../ownership.yaml` lists `deploy-config` under `ship.does_not_write`.
A missing or stale value for either is requested from `setup-deploy`, never written here and
never approximated — one producer per key is what makes the next release reproducible.

## 3. Responding to a REVISE

A `REVISE` arrives as one packet carrying every mechanical failure and every judgment finding
from the whole pass, grouped by owner in `revise_packet.by_owner`. At this boundary the packet
routes across two owners at once:

| Owner group | Keys | Where the repair happens |
| --- | --- | --- |
| `setup-deploy` | `deploy_config`, `rollback_plan` | Reopen the `setup` stage for this release |
| `ship` | `approved_delivery`, `verification_plan`, `human_go_required` | Repaired here |

Delegate both groups in parallel — `revise_policy.parallel_fix` exists so independent owners do
not queue behind each other — then resubmit once with the prior verdict record:

```bash
python skills/harness/gatekeeper/check.py --boundary deploy-readiness --package <manifest.json> --prior <verdict.json>
```

`--prior` reports `changed_evidence` and `unchanged_evidence` from per-key digests, so the
gatekeeper re-judges only what moved. Raise the revision on every resubmission: a verdict is
reusable only for the same boundary, submission, revision, package fingerprint, and gate-spec
digest.

`revise_policy` sets `cycle_cap: 2`. A second `REVISE` ends the cycle: return `ESCALATE` with
both packets, the changed and unchanged evidence, and the owner of each key that did not
converge. Hold the release while either verdict stands — a gate that has not approved has not
approved slowly.

## 4. Repeat Releases: Current-Run Snapshots

`../../pipelines.yaml` runs `setup` on every release before the boundary. On a repeat
release, `setup-deploy` re-verifies the durable configuration and rollback source against
this environment and revision, then writes immutable current-run snapshots under
`release/artifacts/`, recording source run/revision and re-verification evidence. Ship
requests these artifacts and hashes the supplied snapshots; it never writes them itself.

The gate accepts the current-run paths exactly as on a first deployment. It still rejects
references into another run: durable reuse is not permission to widen evidence containment.
A failed re-verification is drift requiring repair by `setup-deploy`, never a waiver.
`land-and-deploy` and `document` are explicitly `after_boundary` and cannot run until the
cross-stage APPROVED record and the named owner's go decision are recorded.

## 5. Standalone Mode

None of the above applies without a run: no manifest, no `artifact_hashes`, no verdict, no
revise cycle. The readiness statement replaces the package, and the named owner's go decision is
the single element that is required identically in both modes, because it is an owner's judgment
rather than a mechanical check. The result says plainly that no `deploy-readiness` verdict
exists, so an unsubmitted release is never read downstream as an approved one.
