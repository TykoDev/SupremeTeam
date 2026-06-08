---
name: quality-review
description: >-
  Assesses maintainability, architecture drift, standards compliance, and
  technical debt pressure across the scoped surface. Use when the user asks to
  review code quality, check maintainability, measure technical debt, or look for
  architecture drift — even when they only say the code "feels hard to work in".
  Takes the long-horizon health view; defers merge-gating of a single diff to
  `review/code-review`, concrete correctness defects to `review/bug-review`, and
  security exposure to `review/security-review`.
version: 1.0.0
---


# Quality Review

## Purpose

Assesses maintainability, architecture drift, standards compliance, and technical debt pressure across the scoped surface.

## Use This Skill When

Use this lens for **long-horizon health** — how maintainable the surface stays as it grows, independent of any single merge:

- "review code quality" / "check maintainability" — assess structure, naming, and coupling
- "measure technical debt" — name the debt and the pressure it puts on future change
- "look for architecture drift" — flag where the implementation diverges from intended boundaries

Route elsewhere when the concern is gating one diff for merge (`review/code-review`), a concrete crash or wrong-output defect (`review/bug-review`), or a security weakness (`review/security-review`).

## Inputs

- Code surface under review with its module boundaries, dependency graph, and architecture constraints.
- Standards baseline such as naming conventions, layering rules, and technical-debt indicators.
- Prior quality findings or architecture-drift notes from earlier review rounds.
- Maintainability priorities such as architecture layers to inspect, standards exceptions, legacy areas accepted as-is, or debt categories to ignore.

## Outputs

- Maintainability assessment covering architecture drift, standards compliance, and technical-debt pressure.
- Finding list with each quality issue tied to a specific module, pattern, or dependency boundary.
- Quality lens packet for `review/code-chief` with module/coupling evidence, standards impact, refactor urgency, and excluded legacy debt.

## Workflow

1. Map the module boundaries, ownership seams, and architectural commitments touched by the scoped surface before naming maintainability issues.
2. Examine duplication, abstraction pressure, dependency direction, configuration sprawl, and long-term change cost against the current architecture rather than an idealized rewrite.
3. Separate local cleanup from structural drift, then explain how each major issue increases future delivery cost, fragility, or cognitive load.
4. Deliver a maintainability packet to `review/code-chief` with architecture drift, debt hotspots, and a pragmatic remediation order.

## Required Contracts

- **Before/After Evidence**: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- review/code-chief
- review/gatekeeper-code

## Review Expectations

- Ground every quality finding in a concrete module, coupling pattern, or standards violation — not in subjective preference.
- Distinguish systemic architecture drift from isolated code-quality issues so remediation routes correctly.
- Deliver findings that `review/code-chief` can merge into the consolidated review without re-analyzing the module graph.

## Skip Rule

Skip only when the surface required by the review lens does not exist, such as a change with no structural or maintainability surface to assess — a copy-only, comment-only, or single-constant change with no logic, dependency, abstraction, or design impact.

## Blocker vs. Debt Decision Rule

Escalate a finding as a BLOCKER when it raises change-cost on the critical path or risks the correctness, security, or maintainability of shipping code. Record it as tracked DEBT — with a note — when the issue is real but does not create immediate delivery risk. When in doubt, prefer the lower classification and state the reason; blockers that turn out to be debt erode trust faster than debt that turns out to be a blocker.

## Absent or Outdated Architecture Documentation

When architecture documentation is missing, incomplete, or clearly stale, do not halt the review. Infer the current architecture from the code, module boundaries, and dependency graph, state those inferences explicitly in the findings, and flag that the architecture documentation needs updating as a tracked DEBT item.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The scope only exposes a local slice of a broader dependency or ownership problem | State the visible architectural pressure, identify the hidden boundary, and avoid overstating a system-wide conclusion without the missing modules. |
| A cleanup suggestion conflicts with established platform conventions or shared abstractions | Flag the tension explicitly and recommend the narrowest change that improves maintainability without inventing a new platform direction. |
| A suspected debt hotspot is real but the package lacks evidence that it affects current delivery cost | Keep the issue in the report as a lower-confidence debt note instead of inflating it into a blocker. |
| Multiple symptoms point to the same abstraction or layering flaw | Collapse them into one structural finding so the remediation plan targets the root cause rather than the surface manifestations. |

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
