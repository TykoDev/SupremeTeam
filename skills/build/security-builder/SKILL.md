---
name: security-builder
description: >-
  Hardens the implementation by checking unsafe dependencies, insecure patterns,
  and missing protective controls before the build advances. Use when the user asks
  to harden the build, review build security, check dependency risk, or prepare the
  security pass — even when security is only implied by handling secrets or
  untrusted input. Hardens code during the build phase; defers feature
  implementation to `build/bob-the-builder` and the independent review-phase
  security audit to `review/security-review`.
version: 1.0.0
---

# Security Builder

## Purpose

Harden the implementation by checking unsafe dependencies, insecure patterns, and missing protective controls before the build advances.

## Use This Skill When

Use this skill to **harden code as it is built** — close weaknesses before the build advances:

- "harden the build" / "prepare the security pass" — add the missing protective controls
- "review build security" — flag insecure patterns in the implementation under construction
- "check dependency risk" — surface unsafe or outdated third-party dependencies

Route elsewhere when the task is implementing the feature itself (`build/bob-the-builder`) or running the independent review-phase security audit (`review/security-review`).

## Inputs

- Build artifacts, dependency manifests, and the authentication/authorization model from the implementation.
- Security-relevant architecture decisions, trust boundaries, and data-sensitivity classifications from design.
- Known vulnerability advisories, compliance constraints, and dependency-policy rules that apply to this build.

## Outputs

- Security hardening report with dependency audit results, unsafe-pattern findings, and applied protective controls.
- Remediation record listing each addressed vulnerability, the fix applied, and the residual risk if any.
- Gate-ready security evidence for `build/gatekeeper-build` with scan results, advisory matches, and unresolved blockers.

## Workflow

1. Map the changed code, configuration, and dependencies to trust boundaries, data sensitivity, and the abuse paths most likely to matter.
2. Inspect first-party code, configuration, secret handling, auth controls, dependency updates, and any generated or vendored surfaces that need tighter scrutiny.
3. Apply or recommend hardening fixes, then rerun the focused checks needed to prove the security issue is resolved or honestly bounded.
4. Return a gate-ready security package with concrete findings, remediations, residual risk, and the exact boundaries that still need owner judgment.

## Required Contracts

- **Vendoring detection**: Detect generated, vendored, or third-party imported content and treat it with tighter review rules than first-party changes.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Secrets handling**: If a secret, token, API key, or credential is encountered during dependency scanning or config inspection — for example, a token embedded in a lockfile, a credential in a committed config, or a key in a generated file — do not echo, log, or include it in any output or report. Flag its presence as a Critical finding, describe its location and type without reproducing the value, and recommend immediate rotation. Treat the build as not security-clean until rotation is confirmed and the credential is removed from the source.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- `build/build-management`
- `build/gatekeeper-build`

## Review Expectations

- Tie every security finding to a concrete dependency version, code pattern, or configuration entry — not to a category label.
- Surface missing protective controls or unscanned surfaces early rather than letting them reach the review gate.
- Deliver hardening evidence that the security-review lens can consume directly without re-running the dependency scan.

## Skip Rule

Do not skip a mandatory build activity inside the canonical path; route scope changes through the build owner instead.

## Failure Modes

| Scenario | Response |
| --- | --- |
| A dependency or vendored surface carries a critical issue, but ownership of the affected code or package is unclear | Isolate the non-first-party boundary, record the ownership gap, and do not claim the build is hardened until responsibility is explicit. |
| The required hardening fix changes auth, tenancy, or data-handling behavior beyond the approved build scope | Escalate the scope boundary instead of treating a design-level security change as routine build cleanup. |
| The security note says a finding is closed, but the exploit path still exists because no focused verification was rerun | Reopen the finding, attach the missing proof requirement, and prevent the package from advancing on unverified remediation. |
| Secret exposure, certificate handling, or network hardening depends on environment details that are unavailable in the current build context | Record the environmental blind spot explicitly and narrow the security claim to what was actually verified. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Do not create or manage `_phase-state.md` — that is the delegating orchestrator's responsibility.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed hardening sequence, dependency scrutiny rules, and acceptance checks.
- `references/examples.md` for concrete security-pass outputs and remediation examples.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
