---
name: design-qa
description: >-
  Assesses visual hierarchy, token adherence, responsive behavior, and
  interaction polish across the rendered interface. Use when the user asks to
  review the visual quality, audit the design implementation, check the interface
  polish, or validate the visual system — even when they only say the UI "looks
  off". Focuses on visual fidelity against the design system; defers runtime
  performance, accessibility, and component robustness to `review/frontier` and
  developer-facing ergonomics to `review/devex-review`.
version: 1.0.0
---


# Design QA

## Purpose

Assesses visual hierarchy, token adherence, responsive behavior, and interaction polish across the rendered interface.

## Use This Skill When

Use this lens for **visual fidelity** — whether the rendered interface matches the design system and reads cleanly:

- "review the visual quality" / "check the interface polish" — judge hierarchy, spacing, and interaction finish
- "audit the design implementation" — verify token adherence and responsive behavior against the spec
- "validate the visual system" — confirm the implemented UI honors the design system

Route elsewhere when the concern is runtime performance, accessibility, or component robustness (`review/frontier`) or developer-facing onboarding and tooling (`review/devex-review`).

## Inputs

- Rendered interface screenshots or live surface plus the design-token system the implementation should follow.
- Visual hierarchy spec, responsive layout targets, and interaction-polish expectations from the design package.
- Prior design-qa findings or design-review scorecards when the surface is being re-evaluated.
- Design-review priorities such as target breakpoints, brand-token exceptions, animation polish expectations, or excluded screens.

## Outputs

- Visual-quality assessment covering hierarchy adherence, token compliance, responsive behavior, and interaction polish.
- Finding list with each design issue tied to a specific component, breakpoint, or token violation.
- Design-QA lens packet for `review/code-chief` with screenshot anchors, token/breakpoint evidence, and any skipped surfaces.

## Workflow

1. Compare the rendered screens against the intended visual hierarchy, token usage, spacing rhythm, typography, responsive composition, and interaction polish.
2. Inspect alignment, contrast, component composition, motion, and breakpoint behavior using screenshots, recordings, or rendered UI evidence.
3. Separate fidelity breaks from intentional product tradeoffs, then explain which screen, state, or breakpoint is affected and why the deviation weakens the design system.
4. Deliver a visual QA packet to `review/code-chief` with evidence anchors, affected states, and any runtime-behavior handoff needed from `review/frontier`.

## Required Contracts

- **Before/After Evidence**: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- review/code-chief
- review/gatekeeper-code

## Review Expectations

- Anchor every visual finding to a screenshot, token value, or rendered measurement — not to subjective impression.
- Separate design-system violations from interaction-polish issues so remediation routes accurately.
- Deliver findings that `review/code-chief` can merge into the consolidated review without re-rendering the surface.

## Skip Rule

Skip only when the surface required by the review lens does not exist — for this visual lens that means a rendered interface, screenshots, or equivalent visual evidence must be absent for the skip to apply.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The design system, token set, or reference mocks have not been shared | Halt the fidelity assessment, name the missing design source, and request the relevant design system docs or Figma/mock exports before continuing. |
| The package lacks design mocks, token references, or rendered screenshots for the claimed surface | Limit the review to the visible evidence, state the missing design source, and avoid inventing the intended visual target. |
| The screenshots or recordings do not cover the breakpoint or state where the deviation is suspected | Mark the finding as partial, name the missing breakpoint or state, and request the additional evidence before broadening the claim. |
| Motion or interaction polish is mentioned but no recording captures the transition | Describe the gap, request motion evidence, and keep the report focused on the static fidelity issues that are actually visible. |
| A deviation may be intentional product direction rather than a design-system miss | Ask for the governing design decision or note the ambiguity instead of treating every difference as a defect. |

## Save Protocol

See `references/workflow.md` for the full save-path conventions and filename rules.

## References

- `references/workflow.md` for the detailed operating sequence and decision rules.
- `references/examples.md` for concrete request patterns and response shapes.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
