---
name: test-builder
description: >-
  Builds the automated test surface that proves the implementation behaves
  correctly across the intended scope and key failure paths. Use when the user asks
  to build the test suite, cover the implementation with tests, verify the changed
  behavior, or add regression protection — even when they only say "add some tests".
  Authors the test surface; defers feature implementation to `build/bob-the-builder`,
  diagnosing a specific failure to `build/debugger`, and runtime/startup health to
  `build/health-check`.
version: 1.0.0
---

# Test Builder

## Purpose

Build the automated test surface that proves the implementation behaves correctly across the intended scope and key failure paths.

## Use This Skill When

Use this skill to **author the automated test surface** — prove behavior across scope and the failure paths that matter:

- "build the test suite" / "cover the implementation with tests" — add coverage for the intended behavior
- "verify the changed behavior" — pin the new behavior with tests that would fail before the change
- "add regression protection" — lock down the paths most likely to break later

Route elsewhere when the task is writing the feature code (`build/bob-the-builder`), diagnosing a specific failure (`build/debugger`), or checking that the system runs (`build/health-check`).

## Inputs

- Implementation source code, delivery slices, and the interface contracts the tests must verify.
- Coverage targets, testing framework preferences, and any existing test infrastructure to extend.
- Known failure paths, edge cases, and regression risks identified during build or review.

## Outputs

- Automated test suite covering the intended scope, key failure paths, and contract boundaries.
- Coverage report mapping tests to delivery slices and identifying untested critical paths.
- Gate-ready test evidence for `build/gatekeeper-build` showing pass rates, flaky-test notes, and coverage gaps.

## Workflow

1. Derive a test matrix from the changed modules, promised behavior, and the failure paths most likely to regress.
2. Add or update the right mix of unit, integration, contract, or end-to-end coverage around the changed behavior instead of relying on one generic test layer.
3. Run the targeted suites and capture exactly what passed, failed, or remained out of scope, including the commands or environments needed to reproduce the result.
4. Return a gate-ready test package with coverage rationale, executed evidence, residual risk, and any blocked dependencies that still need owner input.

## Required Contracts

- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- `build/build-management`
- `build/gatekeeper-build`

## Review Expectations

- Prove that every critical delivery slice and failure path has at least one test with a clear pass/fail assertion.
- Flag untestable boundaries explicitly rather than pretending coverage is complete.
- Structure test output so the review pipeline can verify behavior without re-reading the implementation.

## Skip Rule

Do not skip a mandatory build activity inside the canonical path; route scope changes through the build owner instead.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The test package covers only the happy path even though the changed surface introduces obvious failure, retry, or permission behavior | Mark coverage as incomplete and add the missing regression paths before claiming build readiness. |
| A flaky or slow test is left as the primary proof for the change without a stable reproduction path | Keep the instability visible, narrow the readiness claim, and route the reliability issue back through the build owner instead of burying it. |
| Required coverage depends on an unavailable environment, dataset, or third-party service | Record the missing prerequisite explicitly and avoid claiming that the behavior is verified when only a subset could run. |
| Assertions are added at the wrong layer, so the changed behavior appears covered but the critical contract or integration boundary is never exercised | Rework the test plan around the correct boundary and stop the package from advancing on false coverage. |
| The test harness itself is broken — runner crashes, CI configuration is misconfigured, or test infrastructure is unavailable — making it impossible to determine whether tests pass or fail | Do not infer test health from absence of failures. Record the infrastructure failure explicitly, distinguish it from a genuine test failure, and return an infrastructure-gap report to the build owner. No test evidence is produced until the harness is restored and a clean run completes. |
| Tests produce non-deterministic results across identical runs (genuinely flaky) with no obvious environment cause | Quarantine the flaky tests so they do not contribute to the pass/fail verdict, document the instability with reproduction notes, and treat the affected paths as unverified until a stable run is achieved. Do not allow flaky tests to mask genuine failures or provide false confidence. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Do not create or manage `_phase-state.md` — that is the delegating orchestrator's responsibility.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed test-design sequence, evidence rules, and acceptance checks.
- `references/examples.md` for concrete testing outputs and regression-coverage examples.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
