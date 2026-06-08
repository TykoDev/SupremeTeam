---
name: code-chief
description: >-
  Runs the full review pipeline across correctness, readiness, maintainability,
  security, adversarial testing, security leadership oversight, and optional
  interface or developer-experience surfaces. Use when the user asks to run the
  full review flow, review this codebase comprehensively, audit this change before
  merge, or pressure-test this project — even when they only say "review the code".
  For a single lens, use that specialist reviewer instead; for the merge gate, use
  `review/gatekeeper-code`.
version: 1.0.0
---


# Code Chief

## Purpose

Runs the review pipeline across correctness, readiness, maintainability, security, adversarial testing, security leadership oversight, and optional interface or developer-experience surfaces.

## Entry Routing

This skill is a component of the **Admiral** delivery pipeline; `admiral` is the primary entry orchestrator (see `../../routing-doctrine.md`). Before doing any work, run the **active-handoff check** — a handoff is present when the prompt carries a `### Save Context` block, an active run lock / `session_pin: true` exists under `skillset-saves/`, or the invocation explicitly names this skill as the owning sub-orchestrator for the review boundary.

- **Handoff present** → proceed; this is a delegated Admiral run.
- **No handoff (cold/direct invocation)** → do not run standalone. Start `admiral` first and let it run intake, persistence, and gatekeeping, then accept the delegation back. This is the loop guard: Admiral's own delegations always carry the handoff signal, so a delegated call proceeds immediately and never re-bootstraps Admiral.

## Use This Skill When

- run the full review flow
- review this codebase comprehensively
- audit this change before merge
- pressure-test this project

## Inputs

- Build package from `build/build-management` with implementation revision, test evidence, hardening notes, completeness certification, and unresolved build risks.
- Active review save context, prior lens verdicts, and revision lineage when resuming an interrupted review run.
- Scope classification for optional review surfaces: frontend presence, developer-facing surface, security governance scope, and accepted-risk claims.

## Outputs

- Review package combining bug, code, quality, security, adversarial, and optional frontend/devex/CSO findings with conflict notes.
- `review/gatekeeper-code` submission record with lens coverage, skip justifications, build revision, and unresolved severity disputes.
- Remediation plan mapping each blocker to owning build/design/release surface, severity, and required evidence before delivery.

## Workflow

1. Classify the review scope, risk tier, frontend presence, developer-facing surface, and whether security governance or accepted-risk decisions are in scope before assigning review phases.
2. Always run the core review sequence and add optional interface, developer-experience, or CSO oversight phases only when the surface exists.
3. Merge specialist reports into one review package without losing conflicting evidence or skip justifications.
4. Submit the consolidated package through a single review gate and publish prioritized remediation guidance.

## Required Contracts

- **Cross-model synthesis**: Compare signals from multiple review lenses and merge them into one decision record without flattening meaningful disagreements.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Save-Protocol Adherence**: When a Save Context block is received from admiral, persist every lens state transition, gatekeeper capture, and consolidated package to the save path. Include a `### Save Context` block in every specialist delegation. Saving is mandatory, not optional.

## Delegation Surface

- review/bug-review
- review/code-review
- review/quality-review
- review/security-review
- review/mr-robot
- review/cso
- review/frontier
- review/design-qa
- review/devex-review
- review/gatekeeper-code

## Boundary Rules

- Record each boundary before requesting a verdict.
- Reuse prior verdicts only when the package revision is unchanged.
- Push remediation back to the owning sub-surface instead of editing its package locally.

## Skip Rule

Skip only when there is no consolidated review to run — a change with no reviewable code surface, or when a single specialist lens has already been requested in isolation.

## Failure Modes

| Scenario | Response |
| --- | --- |
| A mandatory review lens is missing from the consolidated package | Stop the gate submission, record the missing lens, and route the package back for completion before summarizing any verdict. |
| Optional frontend or developer-experience phases were invoked without supporting artifacts | Remove the unsupported phase from the run, record the skip reason, and ask for rendered UI, screenshots, CLI traces, or onboarding evidence before re-adding it. |
| The package claims security leadership signoff, accepted-risk readiness, or release security posture without running `review/cso` | Reopen the review schedule, run `review/cso`, or remove the unsupported leadership claim from the consolidated package. |
| Specialist reports disagree on severity, exploitability, or scope | Preserve both positions in the consolidated package, identify the unresolved contradiction, and send the disagreement to `review/gatekeeper-code` rather than averaging the claims. |
| A resubmitted package changes findings without explaining the delta from the previous round | Compare the new package against the prior verdict, demand a revision summary, and reject silent rewrites of the review history. |

## Save Protocol

See `references/workflow.md` — "Save Instructions Per Lens" and "Save Context Block Template" — for the full trigger table, file ownership rules, and the block to include in every specialist delegation.

## References

- `../../routing-doctrine.md` for the entry-routing / admiral-first contract governing which orchestrator owns a given request.
- `references/workflow.md` for the detailed operating sequence and decision rules.
- `references/examples.md` for concrete request patterns and response shapes.
- `intake-brief.yaml` for the intake contract, trigger coverage, and acceptance target.
- `stub-contract.md` for the consolidated review sequence, package shape, and downstream expectations.
- `agent/agent-manifest.yaml` for agent-mode capabilities, optional phases, and delegated review surfaces.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/examples.md`, `intake-brief.yaml`, `stub-contract.md`, and `agent/agent-manifest.yaml` together. Keep generated reports and archives outside the skill directory.
