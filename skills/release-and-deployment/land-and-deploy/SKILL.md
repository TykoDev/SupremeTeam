---
name: land-and-deploy
description: >-
  Combines merge, rollout, verification, and post-release checks into one controlled
  flow with rollback awareness. Use when the user asks to land and deploy this, merge
  and release it, ship the branch, merge then verify the rollout, or take an approved
  change all the way into a real environment — even when they just say "get this
  live". Executes the merge-to-environment flow; defers broader release
  orchestration and sequencing to `release-and-deployment/ship`, first-time deploy
  configuration to `release-and-deployment/setup-deploy`, and release notes to
  `release-and-deployment/document-release`.
version: 1.0.0
---

# Land And Deploy

## Purpose

Combine merge, rollout, verification, and post-release checks into one controlled flow with rollback awareness.

## Use This Skill When

Use this skill to **take one approved change from merge into a real environment** in a single controlled flow:

- "land and deploy this" / "merge and release it" — merge, roll out, then verify
- "ship the branch" / "merge then verify the rollout" — run the rollout with post-release checks
- "take an approved change all the way into a real environment" — keep rollback awareness throughout

Route elsewhere for multi-step release orchestration and sequencing (`release-and-deployment/ship`), first-time deploy configuration (`release-and-deployment/setup-deploy`), or release documentation (`release-and-deployment/document-release`).

## Inputs

- Merge target, deployable revision, release environment, and current repository/pipeline state.
- Deployment target, branch or release identifier, and verification expectations.
- Known constraints, such as protected environments, release windows, or rollback requirements.

## Outputs

- Land-and-deploy execution record with merge command/result, deployment id, target environment, rollout window, and rollback checkpoint.
- Rollout evidence bundle with build output, deployment logs, health checks, smoke tests, and post-deploy observations.
- Go/no-go follow-up list for failed checks, rollback triggers, partial rollout holds, or documentation handoff.

## Workflow

1. Verify the merge target, deployment target, rollout window, deploy configuration, rollback path, and health signals before landing anything.
2. **Require explicit authorization before proceeding**: confirm a named approver has reviewed the exact revision being merged, obtain the approval reference (review link, sign-off record, or equivalent), and verify it is current — CI/CD artifact checks alone are not sufficient authorization. Do not merge or deploy without this gate.
3. Land the approved change set in a reversible way, capture before and after state, and keep the release narrative tied to the exact shipped revision.
4. Execute the rollout and post-deploy verification against live health signals, smoke paths, logs, and user-visible checks before declaring success.
5. Return a deployment record with merge outcome, environment evidence, rollback status, and any follow-up tasks that still need owner attention.

## Required Contracts

- **Deploy config persistence**: Store verified deployment configuration in a durable project location so later release flows can reuse it safely.
- **Before/After Evidence**: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- None required beyond the active task surface.

## Review Expectations

- Tie every merge and deployment step to the requested revision and target environment before declaring the release landed.
- Record live verification evidence and rollback readiness at each gate, not only command success.
- Distinguish failed deployment, failed verification, and blocked environment access so the next action is unambiguous.

## Skip Rule

Skip only when the requested surface, tool, or environment does not exist and a safe fallback is unavailable.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The reviewed revision is approved, but the release branch has drifted since that approval | Stop before merge, name the drift boundary, and require a fresh review or a narrowed release target. |
| No verifiable authorization is present — named approver or approval reference is missing | Stop immediately; do not merge or deploy until a named, verifiable approval with current review evidence is provided. Artifact and CI checks do not substitute for an identified approver. |
| The rollout depends on configuration that is not stored durably with the project or environment | Capture the missing configuration as a release blocker and do not trust one-off terminal history as deploy evidence. |
| Health probes are green after deployment, but a critical user flow fails during smoke verification | Treat the release as incomplete, preserve the conflicting evidence, and decide between rollback or controlled hold before declaring success. |
| The rollout succeeds in one environment but fails in the next, leaving version skew across the release path | Return a partial deployment state explicitly and avoid describing the release as fully shipped until the skew is resolved. |
| The rollback itself fails or leaves the environment in an inconsistent state | Do not declare the rollback complete; escalate to the named approver immediately, freeze forward progress, and hold the environment until a human-verified recovery path is confirmed. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Do not create or manage `_phase-state.md` — that is the delegating orchestrator's responsibility.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed land-and-deploy sequence and decision rules.
- `references/examples.md` for concrete release and rollout examples.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
