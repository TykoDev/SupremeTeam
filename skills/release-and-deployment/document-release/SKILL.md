---
name: document-release
description: >-
  Updates release notes, operational follow-up, and product documentation so the
  release leaves a usable paper trail. Use when the user asks to document the
  release, update the launch notes, write the release follow-up, or capture what
  shipped — even when they only say "write up what we just released". Produces the
  release paper trail; defers the actual merge-and-rollout to
  `release-and-deployment/land-and-deploy`, end-to-end release orchestration to
  `release-and-deployment/ship`, and durable deploy configuration to
  `release-and-deployment/setup-deploy`.
version: 1.0.0
---


# Document Release

## Purpose

Updates release notes, operational follow-up, and product documentation so the release leaves a usable paper trail.

## Use This Skill When

Use this skill to **leave a usable record of what shipped** — after the rollout, not during it:

- "document the release" / "capture what shipped" — record scope, changes, and impact
- "update the launch notes" — produce user- and operator-facing release notes
- "write the release follow-up" — capture operational follow-up and known issues

Route elsewhere to perform the merge and rollout (`release-and-deployment/land-and-deploy`), orchestrate the whole release (`release-and-deployment/ship`), or set up durable deploy configuration (`release-and-deployment/setup-deploy`).

## Inputs

- Release scope, shipped revision, deployment outcome, and the audiences who need post-release documentation.
- Supporting material such as change summaries, rollout notes, verification results, known issues, screenshots, and operator follow-up items.
- Constraints such as regulated communications, customer commitments, embargoes, or incomplete rollout status.

## Outputs

- Release notes package tailored to the target audiences, with shipped changes, behavior differences, and known issues.
- Operational follow-up record covering rollout status, verification evidence, owner assignments, and support/monitoring notes.
- Documentation gap list for missing screenshots, customer commitments, regulatory language, or incomplete release facts.

## Workflow

1. Reconcile the intended release with the revision and rollout result that actually shipped so the documentation follows reality rather than plan.
2. Record user-facing changes, operational consequences, rollback notes, known issues, and any follow-up work that the release leaves behind.
3. Shape the release write-up for its consumers, including product, support, operators, and downstream teams who need a usable paper trail.
4. Return a release documentation package with ship summary, open risks, owners, and the next communication or remediation action.

## Required Contracts

- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- None required beyond the active task surface.

## Review Expectations

- Reconcile every public or operator-facing claim against the shipped revision and rollout evidence.
- Separate customer-facing notes, operator runbook updates, and internal follow-up so each audience gets the right detail.
- Flag unknown rollout state or missing verification as documentation blockers instead of filling gaps with planned behavior.

## Skip Rule

Skip only when the requested surface, tool, or environment does not exist and a safe fallback is unavailable.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The release notes describe planned features or fixes that are not present in the revision that actually shipped | Rewrite the documentation around the shipped evidence and explicitly drop claims that outrun the release. |
| User-facing notes omit one breaking change, migration step, or operator action that downstream teams must know to use the release safely | Treat the release documentation as incomplete until the operational consequence is documented. |
| Known issues exist at ship time, but the documentation hides them or leaves ownership vague | Preserve the issue, assign an owner, and avoid presenting the release as cleaner than it is. |
| The rollout stopped partway through and the package mixes documentation for shipped and unshipped environments | Narrow the release record to the actual deployment state and call out version skew explicitly. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Do not create or manage `_phase-state.md` — that is the delegating orchestrator's responsibility.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed release-documentation sequence and decision rules.
- `references/examples.md` for concrete release-note and follow-up outputs.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
