---
name: health-check
description: >-
  Verifies runtime health signals, startup readiness, and environmental
  dependencies so deployment or review does not inherit avoidable runtime
  surprises. Use when the user asks to run the health check, verify runtime
  readiness, check startup health, or validate environment health — even when they
  only say "does it actually run?". Focuses on runtime and environment readiness;
  defers automated test authoring to `build/test-builder` and build-package
  completeness confirmation to `build/cross-check-build-confirm`.
version: 1.0.0
---


# Health Check

## Purpose

Verifies runtime health signals, startup readiness, and environmental dependencies so deployment or review does not inherit avoidable runtime surprises.

## Use This Skill When

Use this skill to **confirm the system actually comes up** — runtime and environment readiness, not static correctness:

- "run the health check" / "check startup health" — verify the app starts and reports healthy
- "verify runtime readiness" — exercise liveness/readiness signals and key dependencies
- "validate environment health" — confirm required environment and external dependencies are present

Route elsewhere when the work is authoring tests (`build/test-builder`) or confirming the build package is complete (`build/cross-check-build-confirm`).

## Inputs

- Runtime target, startup configuration, and the environmental dependencies the service requires.
- Health-probe endpoints, readiness checks, and expected startup sequence from the deployment spec.
- Known environmental constraints such as network isolation, missing credentials, or cold-start limitations.

## Outputs

- Health verification report covering startup readiness, probe responses, and dependency availability.
- Evidence bundle with probe results, startup logs, and environment-check outcomes.
- Escalation notes listing unresolvable environmental gaps that block deployment or review.

## Workflow

1. Define the runtime health contract for the assigned surface: boot behavior, dependency readiness, critical user path, and the environment conditions that must hold.
2. Execute the health checks that matter for the real target, including startup, readiness, smoke flows, external dependencies, and logs that expose degraded behavior.
3. Separate transient noise from structural health failures so the report does not confuse a momentary blip with a reliable runtime posture.
4. Return a health verification report with passed checks, degraded dependencies, blocked readiness claims, and the next remediation or release action.

## Required Contracts

- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- build/build-management
- build/gatekeeper-build

## Review Expectations

- Base every health claim on an observable signal — probe response, log entry, or dependency check — not on configuration intent.
- Surface environmental gaps and missing dependencies before deployment consumes the health report.
- Deliver startup-readiness evidence that the release pipeline can verify without re-running the health sweep.

## Skip Rule

Do not skip a mandatory build activity inside the canonical path; route scope changes through the build owner instead.

## Failure Modes

| Scenario | Response |
| --- | --- |
| Startup and liveness probes pass, but the critical dependency path fails once the application handles real traffic or authenticated flows | Treat the service as not ready and require proof for the real runtime boundary rather than trusting shallow green checks. |
| The health check package mixes evidence from a different environment, revision, or data state than the one being approved | Narrow the claim to the environment actually tested and block release language that outruns the evidence. |
| One transient spike or warm-up issue is mistaken for a permanent failure, or a recurring degradation is waved away as normal warm-up noise | Preserve the timing evidence and classify the issue based on repeatability instead of intuition. |
| The runtime looks healthy only because one failing dependency, queue, or feature flag path was never exercised during the health pass | Mark the missing path as unverified and do not let the report imply full readiness. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Do not create or manage `_phase-state.md` — that is the delegating orchestrator's responsibility.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed runtime-health verification sequence and decision rules.
- `references/examples.md` for concrete health-check outputs.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
