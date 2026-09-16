---
name: security-builder
description: >-
  Names the trust boundaries and controls a design owes (`security_seed`),
  grades what the build implements against them (`security_evidence`), and
  applies authorized security fixes. Internal specialist reached through
  `design/commander`, `build/build-management`, or `review/cso`, not directly,
  even when security is only implied by secrets or untrusted input. Defers
  feature code to `build/bob-the-builder` and the independent audit to
  `review/security-review`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

# Security Builder

## Purpose

One specialist across three stages, each owing a different deliverable: the forward-looking control statement a design owes before code exists, the graded record of what the implementation actually does against those controls, and the bounded application of fixes a security engagement has already authorized. The handoff decides which is running; guessing produces a seed with nothing to check or a checkpoint with no baseline.

## Use This Skill When

Use this skill to **state the controls a design owes and close the weaknesses the
build introduces** — before each phase advances:

- "seed the security requirements" / "what does this design have to protect?" — name the trust boundaries the design moves and the controls the build must implement
- "harden the build" / "prepare the security pass" — add the missing protective controls
- "review build security" — flag insecure patterns in the implementation under construction
- "check dependency risk" — surface unsafe or outdated third-party dependencies
- "apply the authorized fixes" — remediate inside a scoped security engagement

Route elsewhere when the task is implementing the feature itself (`build/bob-the-builder`) or running the independent review-phase security audit (`review/security-review`).

## Entry Routing

Security-builder is an internal specialist, not an entry point.
`../../routing-doctrine.md` places every `build/` skill it does not name
separately in the internal-specialist row, reached only through the owning
sub-orchestrator, and states the rule this skill turns on: inside a delivery run
security-builder owns the recurring checkpoints rather than forking a parallel
lifecycle, and a dedicated security engagement runs the `security` pipeline
under `review/cso`.

Three owners can delegate here, and the handoff says which — `design/commander`
for `security-seed`, `build/build-management` for `security-checkpoint`,
`review/cso` for `remediation`. Run the active-handoff check before any work,
then read `Phase` and `Return boundary` to select the stage;
`references/workflow.md` carries the selection table.

A handoff is present when the delegation prompt carries a `### Save Context`
block, an active run lock with `session_pin: true` exists under
`skillset-saves/`, or the invocation explicitly names one of those three owners
as the delegating owner for its boundary.

- **Handoff present** → read `Phase` and `Return boundary`, select the stage, proceed.
- **Handoff present but ambiguous** → do not guess the stage. Return it to the delegating owner for the missing field; the two checkpoints are not the same job and neither substitutes for the other.
- **Reached cold** → change nothing and scan nothing. Return to the owning sub-orchestrator, then accept the delegation back. A cold invocation names no scope, no authorized fix set, and no boundary to return at.

## Inputs

- Build artifacts, dependency manifests, and the authentication and authorization model from the implementation.
- Security-relevant architecture decisions, trust boundaries, and data-sensitivity classifications from design.
- Known vulnerability advisories, compliance constraints, and dependency-policy rules that apply to this build.
- In the `security` pipeline, the scope and the exact fix set `review/cso` authorized after triage.

## Outputs

Each stage returns to its own delegating owner, and security-builder submits at
no boundary itself. `references/workflow.md` carries the per-key gate table —
what each key must contain, whether it is artifact-backed, its typed record, and
its sanctioned fallback.

- `security_seed` for `design-to-build`, returned to `design/commander`: the trust boundaries the design introduces or moves, and the control the build owes at each one, written before code exists.
- `security_evidence` for `build-to-review`, returned to `build/build-management`: the graded findings record of what was found and the controls actually implemented against the seeded boundaries, or the sanctioned fallback when no trust boundary moved.
- The remediation record for `security-review`, returned to `review/cso`: each authorized fix applied, the focused rerun that proves it, and the residual risk — folded by `review/cso` into the package it submits.

## Workflow

1. Read the handoff first: the `Phase` and `Return boundary` fields select the design-phase seed, the build-phase checkpoint, or the security-pipeline remediation stage, and each owes a different deliverable.
2. At the design checkpoint, map the architecture, interface contracts, and data classifications to the trust boundaries the design introduces or moves, and state the control the build owes at each one. That statement is the `security_seed` evidence, and it is written before code exists.
3. At the build checkpoint, map the changed code, configuration, and dependencies to those seeded trust boundaries, data sensitivity, and the abuse paths most likely to matter.
4. Inspect first-party code, configuration, secret handling, auth controls, dependency updates, and any generated or vendored surfaces that need tighter scrutiny.
5. Apply or recommend hardening fixes, then rerun the focused checks needed to prove the security issue is resolved or honestly bounded.
6. At the remediation stage, apply only the fixes `review/cso` authorized, keep them inside the scoped surface, prove each with a focused rerun, and return the remediation record to `review/cso` — which owns the `security-review` boundary and submits there.
7. Return the stage's deliverable with concrete findings, remediations, residual risk, and the exact boundaries that still need owner judgment.

## Required Contracts

Full normative text for each contract is in `references/contracts.md`; the lines
below are the operative rule, not a summary that softens it.

- **Stage selection before work**: `Phase` and `Return boundary` are read before anything is scanned or changed. The design checkpoint is forward-looking and the build checkpoint is evidential; confusing them yields a seed with no controls to check or a checkpoint with no baseline to check against. An ambiguous or missing handoff returns to the delegating owner rather than being guessed.
- **Authorized fixes only**: In the `security` pipeline, `review/cso` owns scope, triage, and submission. Apply only the fixes it authorized, keep them inside the scoped surface, and escalate any fix that would change auth, tenancy, or data-handling behavior beyond that scope. A security engagement that silently widens is indistinguishable from an unreviewed change.
- **Secrets handling**: A secret, token, API key, or credential encountered during dependency scanning or config inspection is never echoed, logged, or included in any output or report. Flag its presence as a Critical finding, describe its location and type without reproducing the value, and require rotation. The build is not security-clean until rotation is confirmed and the credential is removed from the source.
- **Proof, not assertion**: Every claimed remediation is tied to a focused rerun, a scan record, or a direct proof on the affected boundary. A finding marked closed without a rerun is a finding nobody checked, and `../../gates.yaml` `finding_policy` blocks on exactly that.
- **Vendoring detection**: Detect generated, vendored, or third-party imported content and treat it with tighter review rules than first-party changes.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../../execution-contract.md` defines, so upstream and downstream packages read risk identically. Critical blocks; Major resolves before the gate or defers with an owner and a reopen trigger.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- `design/commander` — delegates the `security-seed` stage of the `design` pipeline and submits `security_seed` at `design-to-build`.
- `build/build-management` — delegates the `security-checkpoint` stage of the `build` pipeline and submits `security_evidence` at `build-to-review`.
- `review/cso` — owns the `security` pipeline, sets scope and the threat model, triages, authorizes the fix set, and submits at `security-review`.
- `build/gatekeeper-build` — downstream gate for the build boundary; returns its REVISE packet through build-management, never directly.
- `review/security-review` — runs the independent review-phase audit; this skill never stands in for it.

## Review Expectations

- Tie every security finding to a concrete dependency version, code pattern, or configuration entry — not to a category label.
- Surface missing protective controls or unscanned surfaces early rather than letting them reach the review gate.
- Deliver hardening evidence the security-review lens can consume directly without re-running the dependency scan.
- Tie every build-phase control back to a seeded trust boundary, so the design checkpoint and the build checkpoint read as one contract rather than two opinions.

## Skip Rule

Do not skip a mandatory build activity inside the canonical path; route scope changes through the build owner instead.

## Failure Modes

| Scenario | Response |
| --- | --- |
| Invoked cold with no `### Save Context` block, no active run lock, and no named delegating owner | Scan nothing and change nothing. Return to the owning sub-orchestrator — `design/commander`, `build/build-management`, or `review/cso` — then accept the delegation back. A cold invocation names no scope, no authorized fix set, and no boundary to return at. |
| The handoff arrives without `Phase` or `Return boundary`, or the two disagree | Do not guess the stage. Return the handoff to the delegating owner naming the missing or contradictory field. A design seed produced where a build checkpoint was wanted leaves the boundary with no graded evidence and the gate with no baseline. |
| A gate returns a REVISE naming `security_seed` or `security_evidence` | Take only the findings routed to this owner, fix them in one pass, re-run the focused checks that prove each one, and hand the updated record back through the delegating owner for a single resubmission. `../../gates.yaml` `revise_policy.cycle_cap` is 2; a third cycle escalates instead of resubmitting. |
| The dependency scanner, SCA tool, or advisory database is unavailable or cannot reach its source | Record the request with `scan_record.py --no-run` so the gap is typed rather than narrated, name the surface that stayed unscanned, and narrow the security claim to what was actually inspected. `../../gates.yaml` `evidence_type_rules.scan` treats `unavailable` or `error` as a data gap, never as a clean scan. |
| A dependency or vendored surface carries a critical issue, but ownership of the affected code or package is unclear | Isolate the non-first-party boundary, record the ownership gap, and do not claim the build is hardened until responsibility is explicit. |
| The required hardening fix changes auth, tenancy, or data-handling behavior beyond the approved scope | Escalate the scope boundary instead of treating a design-level security change as routine build cleanup. |
| The security note says a finding is closed, but the exploit path still exists because no focused verification was rerun | Reopen the finding, attach the missing proof requirement, and prevent the package from advancing on unverified remediation. |
| Secret exposure, certificate handling, or network hardening depends on environment details unavailable in the current build context | Record the environmental blind spot explicitly and narrow the security claim to what was actually verified. |
| A fix outside the authorized set would close a real finding during a `security` engagement | Do not apply it. Record it as a finding with its recommended fix and return it to `review/cso`, which owns scope and triage. An engagement that widens itself is no longer the engagement that was reviewed. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Resolve every destination with `python skills/scripts/output_paths.py`, using the run id and
   phase from the Save Context block. Never compose a path by hand: the resolver refuses an
   unknown kind, a name that is absolute or traverses, and any path that escapes the
   project root, which is the containment check.
2. Write deliverables (reports, evidence bundles, review packets) to the destination it returns.
3. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
4. Never write `_phase-state.md`. No class in the save-ownership policy declares that path, so it is not an orchestrator-owned file either — phase state is published only through `save_run.py checkpoint`, which keeps revision lineage and the audit trail coherent.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.

## References

- `references/workflow.md` for the stage-selection table, the hardening sequence, the per-key gate evidence tables, scan-record assembly, and REVISE handling.
- `references/contracts.md` for the full normative text of stage selection, authorized-fix scope, secrets handling, and the proof rule.
- `references/examples.md` for worked passes at all three stages, including a design-phase seed and a remediation return to `review/cso`.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/contracts.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
