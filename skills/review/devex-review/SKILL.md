---
name: devex-review
description: >-
  Assesses onboarding, tool ergonomics, documentation clarity, and integration
  friction for developer-facing surfaces. Use when the user asks to review the
  developer experience, audit onboarding, check the docs and tooling, or look for
  integration friction — even when they only say the API or SDK is "hard to get
  started with". Focuses on the experience of developers consuming the surface;
  defers end-user visual quality to `review/design-qa` and runtime frontend
  behavior to `review/frontier`.
version: 1.0.0
---


# DevEx Review

## Purpose

Assesses onboarding, tool ergonomics, documentation clarity, and integration friction for developer-facing surfaces.

## Use This Skill When

Use this lens for **developer experience** — how easily a developer adopts and integrates the surface:

- "review the developer experience" / "audit onboarding" — walk the first-run path and find the friction
- "check the docs and tooling" — judge documentation clarity and tool ergonomics against real tasks
- "look for integration friction" — flag where integrating the surface costs avoidable effort

Route elsewhere when the concern is end-user visual quality (`review/design-qa`) or runtime frontend behavior, accessibility, and performance (`review/frontier`).

## Inputs

- Developer-facing surface including CLI tools, SDK interfaces, API documentation, and onboarding materials.
- Integration examples, error messages, and any developer-feedback history from prior usage.
- Ergonomic expectations such as setup time targets, documentation-coverage standards, and supported integration paths.
- Developer-journey priorities such as first-run scenario, supported SDK/CLI paths, docs sections to exclude, or known onboarding pain points.

## Outputs

- Developer-experience assessment covering onboarding friction, tool ergonomics, documentation clarity, and integration pain points.
- Finding list with each issue tied to a specific CLI command, API surface, or documentation gap.
- DevEx lens packet for `review/code-chief` with friction points, affected commands/docs, severity, and integration-path exclusions.

## Workflow

1. Walk the first-run developer journey for the scoped surface: install, configure, run, test, or integrate it as the published docs describe.
2. Inspect documentation accuracy, CLI or SDK ergonomics, setup friction, error clarity, and sample quality across the actual toolchain boundary.
3. Separate release-blocking onboarding failures from minor paper cuts, then explain who is affected and the smallest fix that removes the friction.
4. Deliver a developer-experience packet to `review/code-chief` with repro steps, environment notes, and the integration gaps that still need attention.

## Required Contracts

- **Before/After Evidence**: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- review/code-chief
- review/gatekeeper-code

## Review Expectations

- Ground every developer-experience finding in an observable friction point — a broken command, missing doc, or confusing error — not in opinion.
- Separate onboarding-blocking issues from polish improvements so remediation prioritizes correctly.
- Deliver findings that `review/code-chief` can merge into the consolidated review without re-walking the integration path.

## Skip Rule

Skip only when the surface required by the review lens does not exist, such as a change that touches no developer-facing surface — no CLI, SDK or library API, public API, docs, config, or error/log output.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The package lacks setup steps, sample integrations, or environment details needed to follow the developer journey | Record the missing onboarding artifact and narrow the report to the friction that can actually be reproduced. |
| Tooling behavior depends on OS, shell, or language-runtime details that are not specified | Name the missing environment boundary and avoid claiming the issue reproduces across every supported setup. |
| The docs and shipped behavior appear out of sync but the version or release target is unclear | Treat the mismatch as a documentation-version gap until the intended release boundary is confirmed. |
| A setup or integration failure depends on external credentials or services that are not supplied | Preserve the reproduction gap, note the missing secret or service boundary, and stop short of inventing a full failure narrative. |

## Save Protocol

See `references/workflow.md` for the full save-path conventions and filename rules.

## References

- `references/workflow.md` for the detailed operating sequence and decision rules.
- `references/examples.md` for concrete request patterns and response shapes.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
