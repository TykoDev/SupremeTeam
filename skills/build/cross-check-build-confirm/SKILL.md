---
name: cross-check-build-confirm
description: >-
  Confirms that the build package is complete, internally consistent, and ready
  for downstream review without missing critical evidence. Use when the user asks
  to confirm build completeness, cross-check the build package, verify the
  implementation is complete, or prepare the build confirmation — even when they
  only ask "did we finish everything?". Performs the internal completeness
  cross-check; defers the formal advance/revise verdict to `build/gatekeeper-build`
  and runtime/startup health to `build/health-check`.
version: 1.0.0
---


# Cross Check Build Confirm

## Purpose

Confirms that the build package is complete, internally consistent, and ready for downstream review without missing critical evidence.

## Use This Skill When

Use this skill to **prove the build package is whole** before it leaves the build phase:

- "confirm build completeness" / "verify the implementation is complete" — check every approved item is built and evidenced
- "cross-check the build package" — reconcile implementation, tests, and security evidence for internal consistency
- "prepare the build confirmation" — assemble the completeness summary the gate will consume

Route elsewhere for the formal advance/revise gate verdict (`build/gatekeeper-build`) or runtime, startup, and environment health (`build/health-check`).

## Inputs

- Build package including implementation code, test results, security hardening evidence, and health-check report.
- Design-phase artifacts (delivery slices, interface contracts) that the build claims to satisfy.
- Prior completeness findings or gate verdicts when the package is being resubmitted.

## Outputs

- Build completeness confirmation mapping every delivery slice to its implementation, test, and security evidence.
- Gap list identifying missing artifacts, untested slices, or inconsistent claims that block the review handoff.
- Gate-ready summary for `build/gatekeeper-build` with the completeness verdict and any remaining blockers.

## Workflow

1. Inventory the build package deliverables, declared scope, and upstream approvals before calling the build complete.
2. Cross-check code output, test evidence, security findings, and packaging metadata so missing artifacts or contradictions are caught before the gate sees them.
3. Record the completeness decision with explicit proof for each required deliverable and with any unresolved build risks called out directly.
4. Return a gate-ready build confirmation packet that names what is present, what is missing, and what still blocks downstream review.

## Required Contracts

- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Before/After Evidence**: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- build/build-management
- build/gatekeeper-build

## Review Expectations

- Confirm completeness by cross-referencing the build artifacts against the design specification, not by summarizing intent.
- Call out every missing or inconsistent evidence element before the package reaches the build gate.
- Produce a traceability matrix the gatekeeper can audit without re-reading the full build output.

## Skip Rule

Do not skip a mandatory build activity inside the canonical path; route scope changes through the build owner instead.

## Failure Modes

| Scenario | Response |
| --- | --- |
| A required build artifact, test result, or security output is missing from the package | Mark the package incomplete and name the missing deliverable instead of inferring readiness. |
| Two build artifacts disagree about version, scope, or evidence lineage | Preserve the contradiction and return a narrower completeness statement until the package is reconciled. |
| The build appears complete locally but lacks proof for downstream review consumption | Treat the missing proof as a blocker and require explicit evidence for the gate-facing deliverable. |
| A remediation step would change the approved build scope rather than confirm it | Escalate the scope drift to the build owner instead of hiding it inside the completeness check. |

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
