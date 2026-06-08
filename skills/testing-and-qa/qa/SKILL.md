---
name: qa
description: >-
  Runs systematic product testing, records evidence, applies scoped fixes, and
  reruns checks until the requested surface stabilizes. Use when the user asks to
  run QA, test this product thoroughly, find and fix the issues, or verify the
  workflow end to end — even when they only say "make sure it works". Tests and
  fixes in one loop; defers test-and-report-only with no fixes to
  `testing-and-qa/qa-only` and quantitative performance measurement to
  `testing-and-qa/benchmark`.
version: 1.0.0
---


# QA

## Purpose

Runs systematic product testing, records evidence, applies scoped fixes, and reruns checks until the requested surface stabilizes.

## Use This Skill When

Use this skill to **test, fix, and re-verify** until the surface stabilizes — the close-the-loop QA mode:

- "run QA" / "test this product thoroughly" — exercise the surface systematically and record evidence
- "find and fix the issues" — apply scoped fixes, then rerun the failing checks
- "verify the workflow end to end" — confirm the full path stabilizes after fixes

Route elsewhere when fixes must NOT be applied and a defect report is sufficient (`testing-and-qa/qa-only`), or when the goal is performance measurement (`testing-and-qa/benchmark`).

## Inputs

- Product surface under test, including critical user flows, supported environments, and pass/fail checkpoints.
- Known defects, prior QA findings, and any test-scope limitations such as environment restrictions or data constraints.
- Acceptance criteria defining when the surface is considered stable enough to stop testing.

## Outputs

- QA execution record with findings, applied fixes, rerun results, and residual risks.
- Before/after evidence for each fix so improvements are verifiable, not just asserted.
- Stabilization summary stating whether the surface passed, what remains blocked, and what follow-up is needed.

## Workflow

1. Map the critical user flows, supported environments, and pass or fail checkpoints for the requested surface before testing starts. Design test cases explicitly: each case must cover a happy path, at least one boundary condition, and at least one negative/error scenario.
2. Execute the test sweep. For each defect, capture: reproduction steps, expected vs. actual behavior, environment details, and relevant logs. Isolate the defect to a minimal reproduction before applying a fix — bisect or narrow the trigger condition so the fix is targeted, not speculative.
3. Apply one atomic fix at a time. Re-test the affected path plus its closest risk neighbors. The surface is considered stabilized when all targeted defects no longer reproduce across at least 3 consecutive runs and no new regressions have been introduced. Document the before/after evidence for each fix.
4. Return a QA execution record with findings, fixes applied, rerun results, and any residual risks that still block completion. See `references/workflow.md` for full decision rules and `references/examples.md` for a sample execution record.

## Required Contracts

- **Before/After Evidence**: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- **Atomic commit per fix**: Keep each fix isolated, explain what changed, and preserve easy rollback boundaries even when several issues are found.
- **Safe defaults and scope limits**: Fixes must be atomic and reversible. Never perform destructive operations (dropping tables, deleting data, mutating production data) or touch production environments without explicit owner approval. If a proposed fix would exceed QA scope — e.g., schema migrations, infrastructure changes, or irreversible deletions — stop, report the finding, and hand it to the appropriate owner instead of proceeding.
- **Input validation**: Validate that the product surface, acceptance criteria, and environment specification are present and coherent before starting the test sweep. Refuse to proceed if scope is ambiguous.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- None required beyond the active task surface.

## Review Expectations

- Back every fix with before/after evidence so the improvement is verifiable by any downstream consumer.
- Distinguish stabilized flows from residual defects so the caller knows exactly what passed and what remains at risk.
- Shape the QA record so downstream pipelines can consume it without re-running the test sweep.

## Skip Rule

Skip only when the requested surface, tool, or environment does not exist and a safe fallback is unavailable.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The environment, test data, or account setup is incomplete for a critical workflow | Stop the affected test path, record the missing prerequisite, and continue only with the flows that can still be tested honestly. |
| A defect reproduces intermittently and cannot yet be tied to one trigger | Record the unstable reproduction boundary, preserve the evidence gathered so far, and avoid claiming the fix is verified. |
| Several failing tests appear to share one root cause | Collapse them into one blocker and rerun the dependent paths after the first credible fix instead of applying scattered changes. |
| A scoped fix destabilizes a neighboring path during retest | Keep the atomic fix boundary explicit, record the regression, and decide whether to continue or escalate before more changes stack up. |

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
