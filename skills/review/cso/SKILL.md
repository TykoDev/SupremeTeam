---
name: cso
description: >-
  Applies security-leadership scrutiny to the product, release, or operating model
  and surfaces the highest-value control gaps. Use when the review scope includes
  security governance, accepted risk, release posture, or executive control
  decisions, or when the user asks to run the security oversight pass, review this
  like a security chief, challenge the security posture, or stress-test the
  security decisions. Defers code-level vulnerability hunting to
  `review/security-review` and attacker-chaining to `review/mr-robot`.
version: 1.0.0
---


# CSO

## Purpose

Applies security leadership scrutiny inside the review pipeline to the product, release, or operating model and surfaces the highest-value control gaps.

## Use This Skill When

Use this lens for **security leadership** — governance, accepted risk, and release-posture judgment above the level of any single finding:

- "run the security oversight pass" / "review this like a security chief" — weigh the portfolio of risk, not one bug
- "challenge the product security posture" — test whether accepted risk is actually defensible
- "stress-test the security decisions" / "evaluate accepted security risk" / "review release security posture" — decide whether the release is governable

Route elsewhere when the work is finding code-level vulnerabilities (`review/security-review`) or chaining them into an exploit (`review/mr-robot`).

## Inputs

- Product scope, release posture, architecture or operating-model context, and the security decisions already on the table.
- Relevant security evidence such as data-flow notes, auth boundaries, dependency inventories, incident history, or control documentation.
- Known constraints such as regulated data, customer commitments, limited remediation windows, or missing observability.

## Outputs

- Security-leadership review mapping control gaps to business impact, decision owner, and required governance action.
- Accepted-risk register with compensating controls, expiration/review date, evidence strength, and unresolved leadership decisions.
- Escalation packet for `review/code-chief` covering release-posture blockers, missing control evidence, and risks that cannot be owned by code fixes.

## Workflow

1. Map the product, release, or operating model to the real trust boundaries, attacker leverage points, and business-critical assets before scoring risk.
2. Challenge authentication, authorization, secret handling, dependency exposure, operational controls, and blast-radius assumptions from a security leadership perspective.
3. Separate tactical bugs from strategic control gaps so the review distinguishes what engineering can fix immediately from what leadership must govern explicitly.
4. Return a security leadership packet to `review/code-chief` with prioritized control gaps, compensating-control analysis, accepted-risk candidates, and the decisions that still need executive or owner judgment.

## Required Contracts

- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- review/code-chief
- review/security-review
- review/mr-robot
- review/gatekeeper-code

## Review Expectations

- Tie each control gap to a trust boundary, asset, decision owner, and release consequence.
- Separate tactical vulnerabilities from governance or accepted-risk decisions so remediation lands with the right owner.
- Refuse to credit paper controls unless staffing, monitoring, escalation, and test evidence show they operate in practice.

## Skip Rule

Skip only when the surface required by the review lens does not exist, such as no security-leadership, accepted-risk, or release-posture decision being in scope.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The security review judges policy intent or diagrams instead of the controls that actually protect the live product or release surface | Narrow the verdict to the evidence that exists and call out the unverified control boundaries explicitly. |
| A critical trust boundary depends on vendored code, managed services, or third-party identity flows that were not included in the review package | Keep the external dependency in scope, elevate the missing evidence, and avoid pretending the first-party code alone defines the security posture. |
| The release relies on a compensating control, such as manual monitoring or after-hours approvals, that is not staffed or tested in the real operating model | Preserve the governance gap as a blocker instead of crediting a control that exists only on paper. |
| Strategic security issues are buried inside a flat finding list with no distinction between immediate exploit risk and longer-term control debt | Reframe the output by blast radius and decision owner so leadership can act on the highest-value gaps first. |

## Save Protocol

See `references/workflow.md` for the full save-path conventions and filename rules.

## References

- `references/workflow.md` for the detailed security-oversight sequence and decision rules.
- `references/examples.md` for concrete security-chief review outputs.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
