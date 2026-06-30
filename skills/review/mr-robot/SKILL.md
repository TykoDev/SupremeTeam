---
name: mr-robot
description: >-
  Pressure-tests the scoped surface from an adversarial viewpoint by tracing
  exploit paths, abuse cases, and chaining conditions. Use when the user asks to
  run adversarial review, pressure-test this code, think like an attacker, or look
  for exploit chains — even when they only ask "how would someone break this?".
  Focuses on chained, attacker-driven scenarios; hands single defensive flaws with
  no abuse sequencing to `review/security-review` and security-governance decisions
  to `review/cso`.
version: 1.0.0
---


# Mr Robot

## Purpose

Pressure-tests the scoped surface from an adversarial viewpoint by tracing exploit paths, abuse cases, and chaining conditions.

## Use This Skill When

This lens **thinks like an attacker** — chaining weak checks, unsafe defaults, and race windows into a concrete abuse narrative:

- "run adversarial review" / "think like an attacker" — start from attacker entry points and trust boundaries
- "pressure-test this code" — probe what breaks under hostile, not merely unexpected, input
- "look for exploit chains" — sequence individual weaknesses into a reachable exploit

Route elsewhere when the item is a standalone defensive flaw with no meaningful chaining (`review/security-review`) or a governance / accepted-risk decision (`review/cso`).

## Inputs

- Code surface under review with its attack surface, entry points, and trust-boundary topology.
- Security-review findings and dependency advisories that identify candidate exploit primitives.
- Operational context such as deployment model, exposed services, and external dependency trust levels.
- Adversarial-review priorities such as high-value assets, attacker profiles, excluded abuse cases, or accepted-risk boundaries.
- Abuse-case seeds from design or security review, including LLM prompt-injection paths, SSRF candidates, privilege transitions, rate-limit gaps, and supply-chain trust assumptions.

## Outputs

- Adversarial assessment with traced exploit paths, abuse cases, and chaining conditions.
- Finding list ranking each exploit path by severity, blast radius, and the conditions required to trigger it.
- Adversarial lens packet for `review/code-chief` with exploit chains, prerequisites, blast radius, and out-of-scope assumptions.

## Workflow

1. Identify plausible attacker starting points, trust boundaries, high-value state changes, and abuse goals inside the scoped surface before proposing any exploit path.
2. Chain weak checks, unsafe defaults, race windows, privilege transitions, prompt/data poisoning, and supply-chain assumptions into concrete abuse narratives instead of listing isolated smells.
3. Distinguish confirmed exploit chains from speculative attack ideas, then record preconditions, blast radius, containment options, and the smallest non-destructive proof that makes the chain concrete.
4. Deliver an adversarial packet to `review/code-chief` with exploit narratives, required hardening, and any follow-up that `review/security-review` should validate further.

## Required Contracts

- **Before/After Evidence**: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- review/code-chief
- review/gatekeeper-code

## Review Expectations

- Trace every exploit path through concrete code, configuration, and dependency evidence — not through theoretical risk categories.
- Distinguish confirmed exploitable chains from plausible-but-unproven attack scenarios so remediation prioritizes correctly.
- Default to a standard external-attacker model only when the real profile is absent; state the assumption and reopen it when the system exposes privileged users, multi-tenant data, agents/tools, or internal network reachability.
- Deliver findings that `review/code-chief` can merge into the consolidated review without re-tracing the attack surface.

## Skip Rule

Skip only when the surface required by the review lens does not exist, such as a change with no attack surface or executable behavior to probe (docs-only or comment-only changes).

## Failure Modes

| Scenario | Response |
| --- | --- |
| A candidate exploit chain depends on trust boundaries, rate limits, or runtime controls that are not present in the supplied artifacts | State the missing defensive boundary explicitly and keep the chain conditional instead of pretending the missing controls do not exist. |
| Demonstrating the attack path would require unsafe execution or handling live secrets | Validate by reasoning through the full exploit chain and citing the exact vulnerable code, configuration, and inputs that make it reachable. Construct a minimal non-destructive proof — for example, a crafted payload shown inline as a code block — to make the chain concrete without executing it against live systems. Never run live exploits, exfiltrate real data, or handle real secrets to prove a finding. Describe the risk and recommend a contained validation environment (e.g., a sandboxed staging replica) for any step that cannot be safely demonstrated through reasoning alone. |
| Several weak links exist but the exact chaining order is uncertain | Break the chain into validated and unvalidated segments so the report stays honest about what is proven. |
| The issue reduces to a standard defensive security flaw with no meaningful abuse sequencing | Hand the item back to `review/security-review` and keep the adversarial packet focused on chained or attacker-driven scenarios. |
| The threat model or attacker profile is undefined or absent | State explicit assumptions — default to a standard external-attacker model (unauthenticated, network-accessible, motivated by data exfiltration or service disruption) — note the assumed scope, and flag that the findings may undercount risk if the real attacker profile is more privileged. |

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
