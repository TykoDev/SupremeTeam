---
name: debugger
description: >-
  Isolates root causes, tests repair strategies, and returns a bounded fix path
  with proof that the failure mode changed. Use when the user asks to debug this
  failure, find the root cause, repair the broken path, or isolate the defect —
  even when they only paste an error and ask "why?". Targets a specific, reproduced
  failure inside the build phase; defers greenfield feature implementation to
  `build/bob-the-builder`, test authoring to `build/test-builder`, and broad
  multi-system incident analysis to `investigate`.
version: 1.0.0
---


# Debugger

## Purpose

Isolates root causes, tests repair strategies, and returns a bounded fix path with proof that the failure mode changed.

## Use This Skill When

Use this skill for **a specific, reproducible failure** — isolate the cause, then prove the fix changed it:

- "debug this failure" / "isolate the defect" — narrow to the smallest reproduction
- "find the root cause" — separate the true cause from the symptom
- "repair the broken path" — apply a bounded fix and show the before/after behavior change

Route elsewhere when the task is building new feature code (`build/bob-the-builder`), adding the test surface (`build/test-builder`), or untangling a broad cross-system incident (`investigate`).

## Inputs

- Failure description with symptoms, error messages, stack traces, or behavioral observations.
- Reproduction context including environment, configuration, recent changes, and affected code paths.
- Access constraints such as read-only environments, missing logs, or time-limited reproduction windows.

## Outputs

- Root-cause report identifying the defect, its causal chain, and the evidence that confirms the diagnosis.
- Bounded fix path with proof that the failure mode changed and no neighboring behavior regressed.
- Escalation notes when the root cause cannot be isolated within the available evidence or access boundary.

## Workflow

1. Build a failure timeline from the symptom, recent code or environment changes, and the exact boundary where the system first stops behaving correctly.
2. Reproduce or narrow the defect with targeted checks so the debug path stays anchored in observed evidence rather than guesswork.
3. Test candidate fixes against the actual failure mode and adjacent regression surface, keeping the remediation smaller than the original uncertainty.
4. Return a debug report and fix path with the root cause, verified repair boundary, remaining risk, and the next build-phase action.

## Required Contracts

- **Before/After Evidence**: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- **Atomic commit per fix**: Keep each fix isolated, explain what changed, and preserve easy rollback boundaries even when several issues are found.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- build/build-management
- build/gatekeeper-build

## Review Expectations

- Trace every fix back to a specific root cause with reproduction evidence, not just symptom disappearance.
- Distinguish confirmed root causes from provisional mitigations so downstream reviewers know what is proven.
- Deliver fix evidence that the build pipeline can consume directly without re-investigating the failure.

## Skip Rule

Do not skip a mandatory build activity inside the canonical path; route scope changes through the build owner instead.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The bug cannot be reproduced because the failing environment differs from the local or test environment in one material way, such as config, data, or feature flags | Preserve the environment mismatch as part of the root-cause boundary and do not claim a fix until the relevant conditions are reproduced or bounded. |
| A candidate fix makes one failing test pass but never proves the underlying defect chain or checks nearby regression paths | Treat the repair as provisional and extend the validation surface before calling the defect closed. |
| Instrumentation or temporary logging changes alter timing or behavior enough to hide the original failure | Record the observer effect explicitly and use a less invasive debug path rather than mistaking silence for resolution. |
| Multiple recent changes could explain the symptom, but the debug path collapses onto the first plausible culprit without falsifying alternatives | Keep competing explanations alive until one survives the evidence or the remaining ambiguity is narrow and documented. |
| The failure cannot be reproduced at all — no local, staging, or CI environment surfaces the defect and no reliable trigger is known | Do not apply a speculative fix. State explicitly that reproduction failed, gather whatever indirect evidence exists (logs, metrics, user reports, environment differences), record the assumptions required for each candidate theory, and return an evidence-gap report that the build owner can use to decide next steps. |
| The symptom data appears fabricated, self-contradictory, or inconsistent across sources — error messages that do not match the stated stack, timestamps that predate the claimed change, or behavior that contradicts the attached logs | Do not proceed as if the data is reliable. Call out the inconsistency explicitly, halt speculative diagnosis, and request a clean reproduction case or authoritative log source before forming a root-cause theory. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Do not create or manage `_phase-state.md` — that is the delegating orchestrator's responsibility.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed build-debugging sequence and decision rules.
- `references/examples.md` for concrete debug-report and fix-path outputs.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
