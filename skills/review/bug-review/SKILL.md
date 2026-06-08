---
name: bug-review
description: >-
  Finds correctness defects, broken invariants, crash paths, and data corruption
  risks in the scoped code surface. Use when the user asks to find the bugs,
  review correctness, check failure paths, or look for broken assumptions — even
  when they only say "something is wrong here" and point at code. Focuses on
  deterministic correctness, not attacker-driven exploit chains (route to
  `review/mr-robot`), defensive-security posture (`review/security-review`), or
  maintainability and tech-debt pressure (`review/quality-review`).
version: 1.0.0
---


# Bug Review

## Purpose

Finds correctness defects, broken invariants, crash paths, and data corruption risks in the scoped code surface.

## Use This Skill When

Use this lens for **deterministic correctness** — defects that yield wrong output, crashes, or corrupted state on a reachable path:

- "find the bugs" / "review correctness" — trace the logic for broken invariants
- "check failure paths" — exercise error, retry, and recovery branches
- "look for broken assumptions" — surface unstated preconditions callers can violate

Route elsewhere when the real concern is attacker-driven chaining (`review/mr-robot`), defensive-security exposure (`review/security-review`), maintainability or architecture drift (`review/quality-review`), or merge-readiness of a specific diff (`review/code-review`).

## Inputs

- Code surface under review, including changed files, modules, and the implementation diff.
- Test results, crash logs, and any prior defect reports that narrow the suspect surface.
- Interface contracts and invariants the code is expected to preserve.
- Bug-priority guidance, known flaky areas, excluded modules, or pipeline-specific invariants that constrain the defect hunt.

## Outputs

- Correctness defect report with each bug tied to a specific file, line, or observable behavior.
- Severity-ranked finding list distinguishing crash paths and data-corruption risks from minor logic errors.
- Bug-review lens packet for `review/code-chief` with defect ids, affected invariants, reproduction evidence, and any scoped exclusions.

## Workflow

1. Trace the scoped code paths, mutable state, and invariants before naming any correctness defect.
2. Probe crash paths, stale-state updates, ordering mistakes, retry hazards, and persistence corruption risks, and anchor each suspected bug to visible evidence.
3. Separate deterministic correctness failures from speculative concerns, then document trigger condition, user impact, and smallest credible fix path for every major finding.
4. Deliver a correctness packet to `review/code-chief` with repro notes, blocking defects, and any handoffs required for security, UX, or performance follow-up.

## Required Contracts

- **Before/After Evidence**: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- review/code-chief
- review/gatekeeper-code

## Review Expectations

- Anchor every defect to a concrete code path, test failure, or invariant violation — not to a category label.
- Distinguish confirmed bugs from suspicious patterns that need further investigation.
- Shape the defect report so `review/code-chief` can merge it into the consolidated review without re-reading the implementation.

## Skip Rule

Skip only when the surface required by the review lens does not exist, such as a change with no behavioral or logical surface to exercise (pure formatting, comment-only, or asset-only changes).

## Failure Modes

| Scenario | Response |
| --- | --- |
| The supplied artifacts do not expose enough runtime behavior to reproduce a suspected crash or invariant break | Mark the issue as unverified, name the missing logs, test case, or repro steps, and request the minimum evidence needed to confirm the defect. |
| The suspected bug crosses async, distributed, or persistence boundaries outside the provided scope | Trace the visible boundary, describe the missing dependency chain, and stop short of inventing behavior that is not in evidence. |
| Multiple symptoms appear to stem from the same broken invariant | Merge them under one root-cause finding so the remediation path stays coherent instead of fragmented. |
| A discovered issue belongs primarily to security, UX, or performance rather than correctness | Record the correctness impact if any, then hand the item to the appropriate specialist instead of diluting the bug report. |

## Save Protocol

See `references/workflow.md` for the full save-path conventions and filename rules.

## References

- `references/workflow.md` for the detailed operating sequence and decision rules.
- `references/examples.md` for concrete request patterns and response shapes.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
