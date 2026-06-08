---
name: qa-only
description: >-
  Runs systematic product testing without applying fixes so the team receives a
  clear evidence-backed defect report. Use when the user asks to run QA without
  fixing, test and report only, audit the workflow, gather product defects,
  perform a read-only audit, or says "don't touch anything, just tell me what's
  broken" — even when they only say "just tell me what's broken". Reports
  without changing code; defers test-and-fix QA to `testing-and-qa/qa` and
  performance measurement to `testing-and-qa/benchmark`.
version: 1.0.0
---


# QA Only

## Purpose

Runs systematic product testing without applying fixes so the team receives a clear evidence-backed defect report.

## Use This Skill When

Use this skill to **test and report only** — produce a defect report without touching the code:

- "run QA without fixing" / "test and report only" — exercise the surface and document what fails
- "audit the workflow" / "read-only audit" — assess the workflow and record evidence, not fixes
- "gather product defects" / "don't touch anything, just tell me what's broken" — deliver a clear, evidence-backed defect list

Route elsewhere when fixes should be applied in the same loop (`testing-and-qa/qa`) or when the goal is quantitative performance measurement (`testing-and-qa/benchmark`).

## Inputs

- Product surface under test, including critical workflows, supported environments, and expected behaviors.
- Known defects, prior QA findings, and any scope limitations such as environment access or data constraints.
- Test-scope boundaries defining what is in scope and what should be excluded from the report.

## Outputs

- QA-only defect report with reproducible issues, severity ratings, and reproduction steps for the remediation team.
- Evidence bundle with screenshots, logs, or recordings for each defect — no fixes applied.
- Blocked-environment summary listing any surfaces that could not be tested and why.

## Workflow

1. Map the critical workflows, supported environments, and failure checkpoints that must be tested before any report is written.
2. Execute the test sweep without mutating the product surface. For each defect, capture: (a) numbered reproduction steps, (b) observed vs. expected behavior, (c) environment details (OS, runtime, test data state), (d) relevant logs or screenshots. If environment access is partial, record what could and could not be verified — do not imply coverage for untested surfaces.
3. Re-run flaky or ambiguous paths only to tighten the evidence boundary, not to apply fixes. If a path cannot be reliably reproduced, record the unstable reproduction boundary and mark confidence accordingly.
4. Return a QA-only report with reproducible defects, severity ratings, blocked environments, and the clearest next action for the team that owns remediation. See `references/workflow.md` for full decision rules and `references/examples.md` for a sample defect report.

## Required Contracts

- **Reproduction Evidence**: For each defect, capture reproduction steps and observed-vs-expected state so the remediation team can act without re-investigating. No interventions or changes are made — this skill is strictly read-only.
- **Partial-access transparency**: When environment access is incomplete, explicitly list what was tested and what could not be reached. Never imply coverage for surfaces that were not exercised.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- None required beyond the active task surface.

## Review Expectations

- Report every defect with reproducible steps and evidence so the remediation team can act without re-investigating.
- Distinguish confirmed defects from flaky or environmental artifacts so severity ratings are trustworthy.
- Shape the report so the owning team can triage and assign defects directly from the output.

## Skip Rule

Skip only when the requested surface, tool, or environment does not exist and a safe fallback is unavailable.

## Failure Modes

| Scenario | Response |
| --- | --- |
| A required environment, account, or test fixture is missing for one of the target workflows | Mark the workflow as untested, keep the report honest about the gap, and continue only with the flows that can still be exercised. |
| A defect reproduces inconsistently across runs | Capture the unstable reproduction boundary and avoid overstating confidence in the failure narrative. |
| Someone requests a quick fix while the QA-only boundary is active | Refuse the mutation, keep the scope report-only, and hand the defect to the team that owns remediation. |
| Multiple failures collapse into one probable root cause | Group them under one evidence-backed defect chain so the report does not exaggerate the number of independent issues. |

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
