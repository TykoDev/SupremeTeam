---
name: code-chief
description: >-
  Admiral-pipeline review sub-orchestrator: scopes and schedules the correctness,
  merge-readiness, and maintainability lenses plus the conditional security,
  adversarial, frontend, visual, and devex ones, then merges their packets into
  one package at `review-to-delivery`. It receives the bare, unscoped review
  request and bounds it before any lens runs. Use to run the full
  review flow, review this codebase comprehensively, audit this change before
  merge, or pressure-test this project — even when the user only says review the
  code. Defers to `admiral` when cold; security governance to
  `review/cso`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---


# Code Chief

## Purpose

Code-chief schedules lenses and merges what they find; the specialists do the
reviewing. Its boundary is one consolidated recommendation with its
disagreements intact — a package that says what was examined, what was not, and
where two lenses still disagree — because a review that averages a security
finding against a maintainability finding hides exactly the signal a delivery
decision needs.

Two things are most often got wrong. Conditional lenses are run as though they
were mandatory, which buries the real coverage question: `../../pipelines.yaml`
conditions `security-review`, `mr-robot`, `frontier`, `design-qa`, and
`devex-review` on a surface being present, so running one without its surface is
noise and skipping one with its surface is a gap. And security *governance* —
accepted risk, release posture, operating-model controls — is signed here
instead of escalated; the review pipeline has no cso stage, and code-chief never
owns that judgment.

## Entry Routing

This skill is a component of the **Admiral** delivery pipeline; `admiral` is the primary entry orchestrator (see `../../routing-doctrine.md`). Before doing any work, run the **active-handoff check** — a handoff is present when the prompt carries a `### Save Context` block, an active run lock / `session_pin: true` exists under `skillset-saves/`, or the invocation explicitly names this skill as the owning sub-orchestrator for the review boundary.

- **Handoff present** → proceed; this is a delegated Admiral run.
- **No handoff (cold/direct invocation)** → do not run standalone. Start `admiral` first and let it run intake, persistence, and gatekeeping, then accept the delegation back. This is the loop guard: Admiral's own delegations always carry the handoff signal, so a delegated call proceeds immediately and never re-bootstraps Admiral.

## Use This Skill When

- run the full review flow
- run the review pipeline
- review the code
- review this codebase comprehensively
- audit this change before merge
- pressure-test this project

A request for one lens — "check this for bugs", "is this accessible" — goes to
that specialist reviewer directly. The merge gate itself is
`review/gatekeeper-code`, and security governance is `review/cso` through
`admiral`.

## Inputs

- Build package from `build/build-management` with implementation revision, test evidence, hardening notes, completeness certification, and unresolved build risks.
- Active review save context, prior lens verdicts, and revision lineage when resuming an interrupted review run.
- Scope classification for optional review surfaces: frontend presence, visible-surface change, developer-facing surface, and any security governance or accepted-risk claim that must be escalated rather than reviewed here.
- Review constraints from the design/build packages: YAGNI decisions, migration/deprecation plan, performance budgets, threat model, and verification expectations.

## Outputs

- Review package combining bug, code, quality, security, adversarial, and optional frontend, visual, and developer-experience findings with conflict notes.
- `review/gatekeeper-code` submission record with lens coverage, skip justifications, build revision, and unresolved severity disputes.
- Remediation plan mapping each blocker to owning build/design/release surface, severity, and required evidence before delivery.

### Gate evidence owned at `review-to-delivery`

Code-chief is the `review-to-delivery` submitter (`../../gates.yaml`,
`boundaries`), so it assembles all six required keys into `review/manifest.json`
and authors five of them itself: `review_verdict`, `findings`,
`executed_probes`, `residual_risk`, and `revision_lineage`. The sixth,
`rendered_verification`, belongs to `review/design-qa` and is carried in
unchanged.

Three decisions live here; `references/gate-evidence.md` carries the full per-key
table with the must-contain, artifact-backing, typed-record, and fallback
columns.

- **Which key is a hashed file**: `executed_probes`, plus `rendered_verification` when a visible surface changed. A count of probes, or a claim that they passed, is not evidence for either.
- **What `review_verdict` may say**: APPROVED, or REVISE/ESCALATE with a challenge record `{by, reason}` the gate preserves as a disputed recommendation. It covers the change under review and nothing broader — a security-governance judgment is escalated, never signed here.
- **Which key may be waived**: `rendered_verification` alone, through `no visible surface changed - rendered verification not applicable` carried as the `reason` of an applicability record `{applicable: false, reason, scope, decided_by}` — at schema 2 a bare string is refused — and only when no visible surface changed. When one did change but this host has no browser, the answer is an `inferred` render record labelled `INFERRED - no browser available`, not that fallback.

## Execution Contract

Canonical source: `../../execution-contract.md`. Stated locally because that file requires every
orchestrator and gatekeeper to carry the clauses verbatim; a paraphrase is drift.

1. Select the preamble tier before acting: Tier 0 for minor, understood, reversible tasks under the Tier 0 fast path in `skills/routing-doctrine.md`; Tier 1 for bounded read-only work beyond Tier 0; Tier 2 for multi-step edits, delegation, or external coordination beyond Tier 0; Tier 3 for destructive, security-sensitive, production, or irreversible work. Record the tier and rationale in the handoff, or the brief completion note for Tier 0. Tier 0 skips pipeline ceremony and full security audits, but retains focused verification and applicable guardrails; escalate when its eligibility no longer holds.
2. Trigger proactively when the task matches the skill's declared scope, even when the request uses different words; decline adjacent work and route end-to-end or specialist ownership explicitly. Offer a next safe action only after the current step, scope, and approval lineage are resolved; suppress that offer while any is unresolved.
3. Use Critical | Major | Minor | Info for findings. Block on Critical, resolve Major before a gate, record Minor, and preserve Info as context. Use APPROVED | REVISE | ESCALATE for gate verdicts.
4. Validate paths, inputs, revisions, and handoff fields before acting. Keep file operations inside the workspace, use read-only or dry-run probes first, and require explicit owner intent for destructive or externally visible actions.
5. Handle missing or malformed input, conflicting evidence, unsupported hosts or tools, empty results, and unavailable checks explicitly: preserve evidence, do not fabricate, return REVISE or ESCALATE, and state the next safe action.
6. Return Outcome, Evidence, Open risks, Next action, Revision, and Verdict when the skill owns a gate. A concise result without evidence is incomplete.

## Workflow

1. Classify the review scope and risk tier, then answer each condition `../../pipelines.yaml` attaches to a stage as a yes or no before assigning any phase: did a trust boundary change, is there an exploitable surface, did visible behavior change, did a visible surface change, did a developer-facing surface change. Also record the migration/deprecation surface, performance budget, and threat model the design and build packages carry.
2. Run the three unconditional lenses on every review — `review/bug-review` (correctness), `review/code-review` (merge readiness), `review/quality-review` (maintainability) — then add each conditional lens whose answer in step 1 was yes: `review/security-review` when a trust boundary changed, `review/mr-robot` when an exploitable surface exists, `review/frontier` when visible behavior changed, `review/design-qa` when a visible surface changed, `review/devex-review` when a developer-facing surface changed. Record each no with its reason; an unrun lens whose condition held is a coverage gap, and a lens run without its surface is noise that dilutes the package.
3. Escalate to `admiral` the moment security governance, accepted-risk decisions, or release security posture enter scope. Those judgments belong to the `security` pipeline under `cso`, gated at `security-review`, and `../../pipelines.yaml` gives the `review` pipeline no cso stage, so there is no lens here to schedule for them.
4. Require each lens to separate blockers from optional cleanup, and to distinguish behavior-preserving simplification from speculative refactoring.
5. Merge specialist reports into one review package without losing conflicting evidence, and carry the execution manifest that records every conditional lens that did not run together with the condition that was false.
6. Submit the consolidated package through a single review gate at `review-to-delivery` and publish prioritized remediation guidance.

## Required Contracts

- **Cross-model synthesis**: Compare signals from multiple review lenses and merge them into one decision record without flattening meaningful disagreements.
- **Save-Protocol Adherence**: When a Save Context block is received from admiral, persist every lens state transition, gatekeeper capture, and consolidated package to the save path. Include a `### Save Context` block in every specialist delegation. Saving is mandatory, not optional.

## Delegation Surface

The `review` pipeline stages in `../../pipelines.yaml` and their owners, in
order. A stage with a condition runs only when that condition holds; the rest are
unconditional.

- `review/bug-review` for `correctness-review`, producing `bug-findings`
- `review/code-review` for `merge-readiness-review`
- `review/quality-review` for `maintainability-review`
- `review/security-review` for `security-review`, when a trust boundary changed
- `review/mr-robot` for `penetration-review`, when an exploitable surface exists
- `review/frontier` for `frontend-review`, when visible behavior changed
- `review/design-qa` for `visual-qa`, when a visible surface changed; it produces the `rendered-verification` record code-chief carries to the gate
- `review/devex-review` for `developer-experience-review`, when a developer-facing surface changed
- code-chief itself for `finding-triage`, producing the `review-verdict`
- `review/gatekeeper-code` for `phase-gate` at `review-to-delivery`

There is no cso stage to add: `cso` owns the separate `security` pipeline, so
security-governance scope escalates to `admiral` rather than being delegated from
here. `references/workflow.md` states what counts as governance scope and what
the package records when it is present.

## Boundary Rules

- Record each boundary before requesting a verdict.
- Reuse prior verdicts only when the package revision is unchanged.
- Push remediation back to the owning sub-surface instead of editing its package locally.
- Self-check before submitting: run `python skills/harness/gatekeeper/check.py --boundary review-to-delivery --package review/manifest.json` (no `--verdict-out`) and fix every mechanical failure first; a package that fails the machine is never submitted (`../../gates.yaml` `revise_policy.self_check`).
- Treat a `REVISE` as one packet: delegate each owner group in `revise_packet.by_owner` in parallel, batching every finding for a specialist into a single revision delegation, and resubmit once with `--prior` so the gate re-judges only `changed_evidence`.

## Skip Rule

Skip only when there is no consolidated review to run — a change with no reviewable code surface, or when a single specialist lens has already been requested in isolation.

## Failure Modes

These five change what Code-Chief does next. The lens-coverage, disagreement,
and resubmission failures whose handling is procedural rather than routing are
in `references/failure-modes.md`, which repeats none of these rows.

| Scenario | Response |
| --- | --- |
| The package claims security leadership signoff, accepted-risk readiness, or release security posture | Remove the unsupported leadership claim and escalate to `admiral` to open the `security` pipeline under `cso`, gated at `security-review`; the review pipeline has no cso stage and code-chief never signs that judgment. |
| A visible surface changed but the host has no browser, so `review/design-qa` cannot capture it | Carry the record `design-qa` returns with `result.status: inferred`, its limitation statement, and the label `INFERRED - no browser available` that `../../gates.yaml` `evidence_type_rules.render` requires. State in `review_verdict` that rendering was not observed and carry the limitation into `residual_risk` with the condition that would close it. Never substitute `no visible surface changed - rendered verification not applicable`: that value asserts nothing visible changed, which is false here. |
| The build package is missing, unapproved, or malformed — no `build-to-review` verdict, evidence spanning two revisions, or a manifest that does not parse | Schedule no lenses. `revision_lineage` cannot be stated over an input whose revision is unknown, so name which of the three it is and return it to Admiral, which rewinds to the build boundary. Reviewing a package assembled from guesses produces findings against code nobody approved. |
| `review-to-delivery` returns `REVISE` twice, exhausting `../../gates.yaml` `revise_policy.cycle_cap` of 2 | Stop resubmitting and escalate to Admiral with both revise packets, both verdicts, and the unclosed keys named with their owners. Five of the six keys are code-chief's own, so a second failure on them is a disagreement about the standard rather than a defect in the artifact. |
| A required capability is unavailable: no sub-agent delegation for the lenses, no command execution for the probes, or no Python for the gate self-check | Run what the host allows and report the rest as unproven by name. A probe that could not execute is `result.status: unavailable`, which is a data gap and never a pass, so `executed_probes` fails the gate rather than carrying an inferred success. Without Python the self-check did not run, so the package is submitted as unverified rather than described as passing. |

## Save Protocol

See `references/workflow.md` — "Save Instructions Per Lens" and "Save Context Block Template" — for the full trigger table, file ownership rules, and the block to include in every specialist delegation.

## References

- `../../routing-doctrine.md` for the entry-routing / admiral-first contract governing which orchestrator owns a given request.
- `references/failure-modes.md` for the lens-coverage, disagreement, and resubmission failures the SKILL.md table does not carry.
- `references/gate-evidence.md` for the six `review-to-delivery` keys with their owners, must-contain, artifact-backing, typed records, sanctioned fallbacks, and the browserless-render branch.
- `references/workflow.md` for the detailed operating sequence and decision rules.
- `references/examples.md` for concrete request patterns and response shapes.
- `intake-brief.yaml` for the intake contract, trigger coverage, and acceptance target.
- `stub-contract.md` for the consolidated review sequence, package shape, and downstream expectations.
- `agent/agent-manifest.yaml` for agent-mode capabilities, optional phases, and delegated review surfaces.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/gate-evidence.md`, `references/failure-modes.md`, `references/examples.md`, `intake-brief.yaml`, `stub-contract.md`, and `agent/agent-manifest.yaml` together. Keep generated reports and archives outside the skill directory.
