---
name: frontier
description: >-
  Assesses interface performance, accessibility, frontend robustness, and
  component behavior across the visible product surface. Use when the user asks to
  review the frontend, check accessibility and performance, audit the interface
  behavior, or look at the component surface — even when they only say the UI
  "feels janky" or slow. Focuses on how the frontend behaves and performs; defers
  pure visual hierarchy, token adherence, and polish to `review/design-qa` and
  developer-facing onboarding and tooling to `review/devex-review`.
version: 1.0.0
---


# Frontier

## Purpose

Assesses interface performance, accessibility, frontend robustness, and component behavior across the visible product surface.

## Use This Skill When

Use this lens for **frontend behavior and performance** — how the interface holds up at runtime for real users:

- "review the frontend" / "audit the interface behavior" — exercise component state, edge inputs, and error states
- "check accessibility and performance" — verify a11y semantics, keyboard paths, and render/interaction cost
- "look at the component surface" — flag fragile or non-resilient component contracts

Route elsewhere when the concern is purely visual hierarchy, tokens, and polish (`review/design-qa`) or developer-facing onboarding and tooling (`review/devex-review`).

## Inputs

- Rendered UI surface, component tree, and the design-system specification the interface should follow.
- Accessibility requirements, responsive breakpoints, and performance budgets for the target viewports.
- Browser screenshots, Lighthouse reports, or console/network evidence when already captured.
- Interface-review priorities such as required viewports, accessibility targets, performance budgets, or interactions explicitly out of scope.
- Performance baselines or budgets when performance is claimed, including Core Web Vitals, bundle-size, interaction latency, or endpoint timing evidence where applicable.

## Outputs

- Frontend assessment covering interface performance, accessibility compliance, and component behavior.
- Finding list with each issue tied to a specific component, viewport, or interaction path.
- Frontend lens packet for `review/code-chief` with component/viewport evidence, accessibility or performance blockers, and skipped flows.

## Workflow

1. Map the rendered flows, components, states, and viewports actually in scope before judging the interface behavior.
2. Inspect accessibility, interaction resilience, loading and error states, and component behavior with concrete viewport or runtime evidence.
3. For performance claims, measure before recommending optimization: capture baseline symptom, identify the bottleneck, and verify improvement evidence instead of approving speculative micro-optimizations.
4. Separate release-blocking UI failures from polish issues, then explain user impact, affected devices, and the most likely root cause for each major item.
5. Deliver a frontend packet to `review/code-chief` with reproduction notes, affected breakpoints, performance evidence, and any handoff needed from design or engineering lenses.

## Required Contracts

- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- review/code-chief
- review/gatekeeper-code
- review/design-qa

## Review Expectations

- Ground every interface finding in an observable behavior — screenshot, Lighthouse metric, or console error — not in design opinion.
- Separate accessibility blockers from visual-polish issues so remediation routes to the right priority.
- Reject performance work that adds complexity without baseline and after-measurement evidence; obvious anti-patterns such as unbounded rendering, missing pagination, missing image dimensions, and N+1 fetches can be flagged directly with the affected path.
- Deliver findings that `review/code-chief` can merge into the consolidated review without re-rendering the interface.

## Skip Rule

Skip only when the surface required by the review lens does not exist, such as a change with no performance- or accessibility-relevant surface (no user-facing rendering and no perf-sensitive path).

## Failure Modes

| Scenario | Response |
| --- | --- |
| The package lacks rendered UI, viewport captures, or runtime traces for the surface being reviewed | Narrow the review to what is actually observable and ask for screenshots, recordings, or performance evidence before asserting user-facing failures. |
| A responsive, keyboard, or assistive-technology issue appears plausible but the relevant state or breakpoint is missing | Record the incomplete evidence boundary and stop short of calling the issue confirmed across all devices or interaction modes. |
| Component behavior depends on shared design-system code or feature flags outside the provided scope | Name the external dependency and keep the finding focused on the visible impact instead of inventing the hidden implementation. |
| The observed defect is purely visual-fidelity drift rather than runtime behavior or accessibility | Hand the item to `review/design-qa` while keeping only the user-facing behavior risk in the frontier report. |

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
