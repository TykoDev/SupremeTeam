# Example Invocations

## Example 1 — pipeline mode, both preconditions on file

**User request:** (delegated with a Save Context block, run `2026-04-19-web`) land and deploy this

**Output:**
- Mode: pipeline — the go decision comes from `ship`'s approved deploy-readiness package for run `2026-04-19-web`.
- Go decision: `human_go_required` in that package names approver `release-owner`, reference `GO-2026-04-19-01`, revision `rev-8f21c0a`, decided at `2026-04-19T20:05:00Z` — the exact revision about to merge.
- Review approval: checked separately and additionally — reviewer `payments-lead` approved `rev-8f21c0a` at review `PR-4412`, still current for it. Two independent checks, both present.
- Merge target: `release/2026-04-19`, landing `rev-8f21c0a` and nothing else; the package names `deploy-config` revision 4 and rollback build 2026.04.12, and the live environment matches both.
- Verification: pre-release health captured, then checkout and sign-in smoke paths rerun against the live target after the rollout.
- Result: release record with the shipped revision, rollout start/finish/checkpoint timestamps, the observed values for each post-release check against its pass condition, rollback status, and both precondition references.

## Example 2 — drift between the approved and the merging revision

**User request:** merge and release it

**Output:**
- Release blocker: the branch carries one extra commit beyond the approved review packet, and the recorded go decision names the earlier revision.
- Action: stop before merge. Two separate repairs are required, because the two preconditions failed independently — a fresh review boundary for the drifted revision, and a new go decision for that revision at this time from a named owner. Re-dating the old decision is not a decision.
- Evidence: the exact divergence, the last approved commit, and which precondition each extra commit invalidates.

## Example 3 — standalone mode, no package exists

**User request:** ship the branch

**Output:**
- Mode: standalone — no Save Context block, no run lock, and nothing from `ship`, so no deploy-readiness package and no gate verdict stand behind this release. Stated before anything is landed.
- Go decision obtained first: approver `service-owner`, reference `#ops-releases permalink`, revision `rev-2a71f4d`, decided at `2026-04-19T14:02:00Z`, quoted back against the exact revision and confirmed explicitly before the merge.
- Review approval: `rev-2a71f4d` approved at `PR-4418` by `frontend-lead`, still current; checked separately from the go decision.
- Configuration: the persisted `deploy-config` and rollback path read directly from `setup-deploy` at revision 3, since no package names them here; the live staging and production settings match.
- Deployment note: the rollout completed in staging, but production verification shows error rates on the primary user flow at 2.4% against a 0.5% pass condition.
- Status: partial deployment with hold. Next move is a decision between rollback and targeted remediation before the release is called complete, and the record says the release ran on a recorded owner decision with no gate assurance behind it.

## Example 4 — rollback that does not complete cleanly

**User request:** get this live, and roll it back if the error rate spikes

**Output:**
- Go decision and review approval recorded for `rev-9d40c1e` before the merge; the rollback trigger from `setup-deploy`'s plan is the error rate above 2% for five minutes.
- Trigger fired 11 minutes after rollout; the rollback restored the previous artifact but left one queue consumer on the new message schema.
- Response: the rollback is **not** declared complete. Forward progress is frozen, the named approver is escalated to immediately, and the environment is held until a human-verified recovery path is confirmed.
- Record: the inconsistent state, its exact boundary, the timestamps of trigger and attempted rollback, and the compensating action named in the rollback plan's data considerations.
