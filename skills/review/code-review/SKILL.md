---
name: code-review
description: >-
  Evaluates merge readiness, local code quality, change risk, and clarity so the
  delivery decision rests on concrete evidence. Use when the user asks to review
  the code, check merge readiness, audit this change, or look for code quality
  issues — even when they just drop a diff and ask "is this good to merge?".
  Judges the change as submitted; defers exhaustive correctness hunting to
  `review/bug-review`, security exposure to `review/security-review`, and
  long-horizon maintainability to `review/quality-review`.
version: 1.0.0
---


# Code Review

## Purpose

Evaluates merge readiness, local code quality, change risk, and clarity so the delivery decision is based on concrete evidence.

## Use This Skill When

Use this lens to judge **a specific change for merge** — readability, change risk, test signal, and reviewer load on the diff in front of you:

- "review the code" / "check merge readiness" — weigh blockers against the merge decision
- "audit this change" — bound the review to the actual diff and touched interfaces
- "look for code quality issues" — flag clarity and maintainability costs in the change

Route elsewhere when the real need is exhaustive correctness or crash analysis (`review/bug-review`), defensive-security review (`review/security-review`), or whole-surface architecture drift rather than this diff (`review/quality-review`).

## Inputs

- Change diff, commit history, and the merge target branch or release context.
- Local code-quality signals such as linting results, style violations, and naming conventions.
- Change-risk indicators including affected module scope, breaking-change potential, and reviewer notes.
- Merge-decision guidance such as release urgency, style-policy exclusions, or areas already approved by earlier review.
- Verification story for the change: tests run, manual checks, build/lint output, and any intentionally skipped validation.

## Outputs

- Merge-readiness assessment with a clear go/no-go recommendation and supporting evidence.
- Finding list covering code quality, change risk, and clarity issues prioritized by merge impact.
- Merge-readiness lens packet for `review/code-chief` with go/no-go rationale, blocking issues, optional cleanup, and excluded diff regions.

## Workflow

1. Bound the review to the actual diff, touched interfaces, and merge context before commenting on code quality or readiness.
2. Review the test evidence first, then inspect correctness signals, readability/simplicity, architecture fit, security exposure, and performance risk in that order.
3. Apply YAGNI and dependency discipline: flag speculative abstractions, pass-through wrappers, future-proofing with no current use, unnecessary new dependencies, and refactors that relocate complexity instead of reducing it.
4. Separate merge blockers from optional cleanup, then explain how each major issue affects safety, maintainability, reviewer comprehension, or verification confidence.
5. Deliver a merge-readiness packet to `review/code-chief` with blockers, optional cleanups, rejected nits, and any follow-up lenses that should inspect the same surface.

## Required Contracts

- **Before/After Evidence**: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- review/code-chief
- review/gatekeeper-code

## Review Expectations

- Base every merge recommendation on observable code evidence — diffs, test results, linting output — not on intent.
- Flag change-risk concerns and breaking-change potential before the consolidated review reaches the gate.
- Use required vs optional language deliberately: correctness, security, contract, and verification gaps block; preference-only simplifications are optional unless the change actively worsens structure.
- Watch change size and file size: ask for a split when one logical review cannot be done confidently, and treat generated/vendor/mechanical churn as excluded evidence unless it changes first-party behavior.
- Deliver findings that `review/code-chief` can merge without re-diffing the change set.

## Skip Rule

Skip only when the surface required by the review lens does not exist, such as a change with no code diff to review (purely visual assets or documentation with no code paths affected).

## Failure Modes

| Scenario | Response |
| --- | --- |
| The diff arrives without a baseline, caller context, or the tests needed to judge merge impact | Record the missing review inputs, narrow the claim to what is visible, and request the smallest artifact set needed for a reliable merge decision. |
| Generated, vendored, or mechanical formatting changes obscure the first-party logic that actually needs review | Isolate the human-authored changes, document what was excluded, and keep style churn from hiding functional blockers. |
| A public interface changes but the affected callers, tests, or migration steps are outside the provided scope | Flag the interface risk explicitly and require the missing usage evidence before calling the change merge-ready. |
| Style or cleanup comments start to crowd out the real merge blockers | Re-rank the report so safety, correctness, and reviewer comprehension issues remain separate from optional cleanup. |

## Save Protocol

See `references/workflow.md` for the full save-path conventions and filename rules.

## References

- `references/workflow.md` for the detailed operating sequence and decision rules.
- `references/examples.md` for concrete request patterns and response shapes.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
