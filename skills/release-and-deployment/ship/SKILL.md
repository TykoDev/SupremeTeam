---
name: ship
description: >-
  Orchestrates release readiness, launch sequencing, verification, and follow-up
  actions for a controlled product release. Use when the user asks to ship this
  release, prepare the launch, run the release flow, or coordinate the rollout —
  even when they only say "let's launch". Owns end-to-end release orchestration;
  defers the single merge-and-deploy execution to
  `release-and-deployment/land-and-deploy`, durable deploy configuration to
  `release-and-deployment/setup-deploy`, and release notes to
  `release-and-deployment/document-release`.
version: 1.0.0
---


# Ship

## Purpose

Orchestrates release readiness, launch sequencing, verification, and follow-up actions for a controlled product release.

## Use This Skill When

Use this skill to **orchestrate a full, multi-step release** — readiness, sequencing, verification, and follow-up:

- "ship this release" / "run the release flow" — drive the release from readiness to follow-up
- "prepare the launch" — confirm readiness and sequence the launch steps
- "coordinate the rollout" — manage verification and post-launch actions across the release

Route elsewhere for a single merge-and-deploy of one change (`release-and-deployment/land-and-deploy`), first-time deploy configuration (`release-and-deployment/setup-deploy`), or release documentation (`release-and-deployment/document-release`).

## Inputs

- Release candidate package with approved review evidence, deployment configuration, and rollback plan.
- Launch window, rollout sequence, and verification checkpoints from the release plan.
- Known constraints such as partial-rollout requirements, feature-flag dependencies, and communication obligations.

## Outputs

- Release record with launch evidence, live verification results, and rollout state.
- Post-ship checklist identifying remaining verification steps, rollback triggers, and follow-up actions.
- Escalation notes when a rollout gate fails and the release must be paused or rolled back.

## Workflow

1. Confirm the release candidate, launch window, rollback path, and verification checkpoints before the rollout starts.
2. Sequence the launch with explicit go or no-go checks so packaging, deployment, communication, and verification happen in the right order.
3. **Require an explicit owner go-decision before committing the production ship**: a named owner or approver must issue a clear "go" for this specific release at this specific time. Prerequisite checks, artifact validation, and CI status satisfy readiness but do not substitute for an explicit human go-decision. Record the approver identity and the go-decision reference in the release record.
4. Record the release state with launch evidence, live verification results, and any partial-rollout decision that affects downstream follow-up.
5. Return a release record with next launch actions, rollback triggers, and the post-ship checks still required for a controlled rollout.

## Required Contracts

- **Before/After Evidence**: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- None required beyond the active task surface.

## Review Expectations

- Base every launch decision on live verification evidence — health checks, smoke tests, rollout metrics — not on build-phase assertions.
- Surface rollback triggers and partial-rollout risks before the release advances past each gate.
- Shape the release record so post-ship follow-up and the `document-release` skill can consume it directly.

## Skip Rule

Skip only when the requested surface, tool, or environment does not exist and a safe fallback is unavailable.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The release candidate, launch window, or rollback plan is missing | Block the rollout and name the missing launch prerequisite explicitly. |
| No owner go-decision is present — prerequisites pass but no named approver has issued an explicit go | Hold the release; do not ship. Record the missing go-decision as a blocker and wait for a named owner to provide an explicit approval for this specific release. |
| Verification signals are incomplete or contradictory during rollout | Freeze the next launch step, preserve the current state, and decide whether to retry, pause, or roll back. |
| A required approval or external coordination step has not happened yet | Keep the release record in no-go state until the dependency is resolved instead of launching optimistically. |
| The rollout partially succeeds but leaves uncertainty about user impact | Record the partial state, define the rollback trigger, and keep follow-up actions explicit rather than implying a full ship. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Do not create or manage `_phase-state.md` — that is the delegating orchestrator's responsibility.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed operating sequence and decision rules.
- `references/examples.md` for concrete request patterns and response shapes.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
