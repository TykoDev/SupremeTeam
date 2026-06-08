---
name: setup-deploy
description: >-
  Defines durable deployment settings and environment conventions so later rollout
  flows can reuse proven configuration safely. Use when the user asks to set up
  deployment config, prepare the release settings, persist the deployment details,
  or configure the deploy flow — even when they only say "get deploys set up".
  Establishes reusable configuration; defers executing an actual rollout to
  `release-and-deployment/land-and-deploy`, release orchestration to
  `release-and-deployment/ship`, and release notes to
  `release-and-deployment/document-release`.
version: 1.0.0
---


# Setup Deploy

## Purpose

Defines durable deployment settings and environment conventions so later rollout flows can reuse proven configuration safely.

## Use This Skill When

Use this skill to **establish durable deploy configuration** that later rollouts reuse — setup, not execution:

- "set up deployment config" / "configure the deploy flow" — define environments and conventions once
- "prepare the release settings" — capture the settings a rollout will depend on
- "persist the deployment details" — store proven configuration for safe reuse

Route elsewhere to run an actual rollout (`release-and-deployment/land-and-deploy`), orchestrate a full release (`release-and-deployment/ship`), or write release notes (`release-and-deployment/document-release`).

## Inputs

- Release targets, deployment environments, build artifact shape, and the current project or pipeline context.
- Existing configuration material such as pipeline vars, environment files, secrets references, DNS or certificate settings, and rollout notes.
- Constraints such as protected environments, secret-handling rules, promotion model, or rollback expectations.

## Outputs

- Deployment configuration package covering environments, artifact flow, variables/secret references, domains, and promotion rules.
- Durable deploy settings with rollback command/path, health probes, ownership, and environment-specific guardrails.
- Readiness gap list for missing credentials, protected-environment approvals, DNS/cert work, or automation prerequisites.

## Workflow

1. Map the deployment path across environments, artifacts, secrets, variables, domains, and promotion boundaries before writing any durable config.
2. Define how deploy settings are stored, injected, versioned, and reused so the release flow does not depend on hidden terminal history or tribal knowledge.
3. **Never persist secret values inline in config files, templates, or any durable artifact** — store only references or pointers to a secrets manager (e.g., `${{ secrets.MY_KEY }}`, ARN, Vault path). If a secret value is encountered during setup, redact it immediately and replace it with the appropriate reference. Storing actual credentials inline creates exfiltration risk and defeats secret rotation.
4. Check the configuration model against rollback needs, environment drift, secret rotation, and manual intervention boundaries.
5. Return a deployment configuration package with persisted settings, environment deltas, and the unresolved release blockers that still prevent safe rollout.

## Required Contracts

- **Deploy config persistence**: Store verified deployment configuration in a durable project location so later release flows can reuse it safely.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- None required beyond the active task surface.

## Review Expectations

- Verify each persisted setting maps to a real environment, secret source, artifact, or promotion rule.
- Separate reusable deployment convention from one-off rollout decisions so future releases do not inherit accidental choices.
- Surface credential, DNS, certificate, or protected-environment blockers before `ship` or `land-and-deploy` consumes the config.

## Skip Rule

Skip only when the requested surface, tool, or environment does not exist and a safe fallback is unavailable.

## Failure Modes

| Scenario | Response |
| --- | --- |
| Deployment settings are scattered across CI variables, local shells, wikis, and manual memory with no durable source of truth | Consolidate the deploy config into one reusable project-level contract before trusting the release path. |
| A secret value would be written inline into a config file or template | Stop immediately; do not write the value. Replace it with a reference to the appropriate secrets manager entry. Surface the gap as a release blocker and do not advance setup until every inline secret is converted to a reference. |
| Promotion assumes one artifact behaves identically in every environment, but environment-specific variables, domains, or secrets are still implicit | Make the environment deltas explicit and block rollout until the config model reflects them honestly. |
| The release path depends on a manual portal edit, ad hoc DNS change, or undocumented certificate step that cannot be replayed | Record the manual dependency and do not describe the deploy setup as reliable until the step is captured or removed. |
| Rollback is claimed, but the configuration surface does not preserve the previous artifact, secret version, or routing state needed to undo the rollout | Reopen the deploy setup boundary and require a real rollback path before downstream release work advances. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Do not create or manage `_phase-state.md` — that is the delegating orchestrator's responsibility.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed deployment-config setup sequence and decision rules.
- `references/examples.md` for concrete deploy-configuration outputs.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
