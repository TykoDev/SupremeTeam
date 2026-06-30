---
name: security-review
description: >-
  Assesses defensive security posture, dependency exposure, access-control risk,
  and unsafe data handling in the scoped surface. Use when the user asks to review
  security, check for vulnerabilities, audit the dependency risk, or look for data
  leakage — even when they only mention handling untrusted input or secrets.
  Covers defensive hardening of the code itself; defers attacker-driven exploit
  chaining to `review/mr-robot` and security governance, accepted risk, and
  release posture to `review/cso`.
version: 1.0.0
---


# Security Review

## Purpose

Assesses defensive security posture, dependency exposure, access-control risk, and unsafe data handling in the scoped surface.

## Use This Skill When

Use this lens for **defensive security of the code** — the weaknesses an attacker could reach and the hardening that closes them:

- "review security" / "check for vulnerabilities" — inspect input validation, authz, and data handling
- "audit the dependency risk" — flag exposed or outdated third-party surface
- "look for data leakage" — trace where sensitive data crosses a boundary unsafely

Route elsewhere when the need is chaining individual weaknesses into an attack narrative (`review/mr-robot`) or judging governance, accepted risk, and release security posture (`review/cso`).

## Inputs

- Code surface under review with its trust boundaries, authentication/authorization model, and data-handling patterns.
- Dependency manifest, known advisory matches, and any security-builder hardening evidence from the build phase.
- Data-sensitivity classifications and compliance constraints that affect the review scope.
- Security-review priorities such as privileged flows to inspect, compliance boundaries, accepted-risk exclusions, or dependency areas already approved.
- Threat model inputs where available: trust boundaries, high-value assets, attacker profiles, LLM/tool surfaces, file upload/webhook/server-side fetch flows, and supply-chain changes.

## Outputs

- Defensive security assessment covering vulnerabilities, dependency exposure, access-control gaps, and unsafe data handling.
- Finding list with each vulnerability tied to a specific code path, dependency, or configuration entry.
- Security lens packet for `review/code-chief` with vulnerable paths/dependencies, affected trust boundary, exploitability evidence, and scoped exclusions.

## Workflow

1. Enumerate the trust boundaries, high-value assets, privileged actions, dependency changes, secret flows, and untrusted inputs inside the scoped surface.
2. Run a lightweight STRIDE pass over each boundary, including LLM/model output, retrieved documents, webhooks, file uploads, server-side URL fetches, and third-party API data.
3. Test authn/authz, data exposure, injection sinks, insecure defaults, supply-chain exposure, and the reachability of newly introduced dependencies or generated code.
4. Separate confirmed exploitable weaknesses from hardening gaps, then record attacker path, required preconditions, and the narrowest viable fix for each major item.
5. Deliver a security packet to `review/code-chief` with blocking vulnerabilities, defense gaps, dependency posture, and any exploit chains that `review/mr-robot` should pressure-test further.

## Required Contracts

- **Vendoring detection**: Detect generated, vendored, or third-party imported content and treat it with tighter review rules than first-party changes.
- **Before/After Evidence**: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- review/code-chief
- review/gatekeeper-code

## Review Expectations

- Tie every vulnerability to a concrete code path, dependency version, or configuration entry — not to a risk category.
- Separate code-level vulnerabilities from strategic control gaps so the CSO lens receives only what it owns.
- Treat model output, browser content, fetched documents, and external service responses as untrusted input; never accept prompt text, tool output, or generated code as a security boundary.
- Review new dependencies as supply-chain surface: lockfile presence, maintenance signal, install scripts, license compatibility, and whether the existing stack already solves the need.
- Deliver findings that `review/code-chief` can merge into the consolidated review without re-scanning the dependency tree.

## Skip Rule

Skip only when the surface required by the review lens does not exist, such as a change with no code, dependency, configuration, or data-handling surface to assess — for example a docs-only or copy-only change.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The package changes dependencies but does not include the manifest, lockfile, or reachability evidence needed to assess exposure | Name the missing dependency evidence and stop short of claiming the risk is resolved or exploitable without it. |
| A suspected exploit depends on deployment configuration, runtime policy, or secret management that is not present in the supplied artifacts | Trace the visible attacker path, document the missing control plane evidence, and mark the issue as conditional rather than guessing the production posture. |
| Generated or vendored code introduces risk but obscures where first-party responsibility begins | Separate third-party exposure from first-party integration mistakes and keep the remediation plan explicit about ownership. |
| A flagged vulnerability lacks evidence that the affected code path is reachable from the scoped surface | Downgrade the claim to a hardening gap or follow-up question until reachability is demonstrated. |
| The authentication or authorization model is undocumented or absent | Do not assume it is safe. Flag the gap, request that the model be documented, and — if the review must proceed — state explicit assumptions about the intended access-control boundaries (e.g., "assumed: all endpoints require a valid session token; unauthenticated access treated as out-of-scope by design") and note that findings may be incomplete until the model is confirmed. |

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
