---
name: commander
description: >-
  Design sub-orchestrator of the Admiral pipeline: carries design from scope to
  an approved package — requirements, architecture, interfaces, delivery plan,
  implementation guidance — at the `design-to-build` gate. Use when `admiral`
  delegates design, or a user asks to design this system, create the design
  package, generate the full specification, start the design pipeline, or plan
  and architect this project, even when Admiral is never named. Defers to
  `admiral` when reached cold; reworking an existing UI starts at
  `design/redesign`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

# Commander

## Purpose

Commander sequences and assembles; the specialists author. Its boundary is the
design package as a *single coherent revision* — one stack decision, one
architecture, one plan sequenced against that architecture, one Taste snapshot —
because `build/build-management` implements the package as given and cannot
reconcile phases that disagree with each other.

Two things are most often got wrong. The plan is assembled beside the
architecture rather than after it, which inverts the dependency
`../../pipelines.yaml` fixes: `design/planner` sequences delivery against the
component boundaries `design/architect` sets, so a plan written first is drift
and returns to the earliest invalid boundary. And the Taste snapshot is
reconstructed from the mutable preference stores instead of requested from
Admiral/Taste, which produces a digest nothing can be revalidated against at the
gate.

## Entry Routing

This skill is a component of the **Admiral** delivery pipeline; `admiral` is the primary entry orchestrator (see `../../routing-doctrine.md`). Before doing any work, run the **active-handoff check** — a handoff is present when the prompt carries a `### Save Context` block, an active run lock / `session_pin: true` exists under `skillset-saves/`, or the invocation explicitly names this skill as the owning sub-orchestrator for the design boundary.

- **Handoff present** → proceed; the run is active inside an Admiral run.
- **No handoff (cold/direct invocation)** → do not run standalone. Start `admiral` first and let it run intake, persistence, and gatekeeping, then accept the delegation back. This is the loop guard: Admiral's own delegations always carry the handoff signal, so a delegated call proceeds immediately and never re-bootstraps Admiral.

## Use This Skill When

- design this system
- create the design package
- generate the full specification
- start the design pipeline
- plan and architect this project

A user-facing surface that already exists and is being reworked enters
`design/redesign` first. That pipeline compares four mocks, records the user's
choice, and builds one living prototype for the chosen direction; that variant's
`variant.md`, `tokens.css`, and `components.html` return here as the
`design-system` input and are locked at `design-to-build`. A merge choice arrives
as a brief to implement rather than a prototype, and a deferral hands nothing
over at all.

## Inputs

- Admiral-normalized design request with product goals, users, constraints, technology preferences, explicit non-goals, and YAGNI deferrals from intake.
- Active design save context, prior phase verdicts, and revision lineage when resuming an interrupted design run.
- Intake decisions, escalations, or skip requests that affect research, architecture, API/UI handoff, the security seed, planning, or implementation guidance.
- An effective-profile snapshot requested from Admiral/Taste whenever project or global Taste storage exists. It must carry the canonical digest, project and global source revisions, resolved entries, shadowed entries, unresolved conflicts, and applicability decision.

## Outputs

- Design package combining research evidence, architecture/API/UI contracts, the security seed or the recorded no-trust-boundary determination, the delivery plan, implementation spec, Decision Register, and `taste_snapshot` (or its sanctioned no-profile applicability record).
- `design/gatekeeper-design` submission record with phase approvals, revision id, skip justifications, and unresolved design risks.
- Design escalation packet naming the conflicting requirement, blocked decision, owner, and recommended default.

### Gate evidence owned

Commander is the `design-to-build` submitter, so it assembles all nine keys
`../../gates.yaml` requires at that boundary and authors exactly one of them:
`stack_lock`. Every other key belongs to a stage owner — `decisions` to
`admiral`, `architecture`, `interfaces`, and `ui_evidence` to `design/architect`,
`security_seed` to `build/security-builder`, `plan` and `acceptance` to
`design/planner`, `taste_snapshot` to `taste` — and a gap routes to that owner
through the REVISE packet rather than being filled in locally.

Three decisions live here; `references/gate-evidence.md` carries the full
per-key table with the must-contain, artifact-backing, typed-record, and fallback
columns.

- **What Commander authors**: `stack_lock` only — the `tech-stacks/registry.yaml` slug, the locked versions, and the overlay sha256, validated so the slug exists, the overlay digest matches both registry and file, and the versions intersect. Its one sanctioned fallback is `no new runtime or framework - existing stack unchanged`.
- **Which keys may be waived**: exactly three — `stack_lock`, `taste_snapshot` (`no saved Taste profile available`), and `ui_evidence` (`no user-facing surface - design system not engaged`). Each waiver is an applicability record at manifest schema 2 naming reason, scope, and decider, never a bare string.
- **Which may not**: `decisions`, `architecture`, `interfaces`, `plan`, `acceptance`, and `security_seed`. `../../gates.yaml` `fallback_values` carries no entry for `security_seed`, so a design with no trust boundary states the recorded determination rather than waiving the key.

## Execution Contract

Canonical source: `../../execution-contract.md`. Stated locally because that file
requires every orchestrator and gatekeeper to carry the clauses verbatim; a
paraphrase is drift.

1. Select the preamble tier before acting: Tier 0 for minor, understood, reversible tasks under
   the Tier 0 fast path in routing-doctrine.md; Tier 1 for bounded read-only work beyond Tier 0;
   Tier 2 for multi-step edits, delegation, or external coordination beyond Tier 0; Tier 3 for
   destructive, security-sensitive, production, or irreversible work. Record the tier and
   rationale in the handoff, or the brief completion note for Tier 0. Tier 0 skips pipeline
   ceremony and full security audits, but retains focused verification and applicable
   guardrails; escalate when its eligibility no longer holds.
2. Trigger proactively when the task matches the skill's declared scope, even when the request
   uses different words; decline adjacent work and route end-to-end or specialist ownership
   explicitly. Offer a next safe action only after the current step, scope, and approval lineage
   are resolved; suppress that offer while any is unresolved.
3. Use Critical | Major | Minor | Info for findings. Block on Critical, resolve Major before a
   gate, record Minor, and preserve Info as context. Use APPROVED | REVISE | ESCALATE for gate
   verdicts.
4. Validate paths, inputs, revisions, and handoff fields before acting. Keep file operations
   inside the workspace, use read-only or dry-run probes first, and require explicit owner
   intent for destructive or externally visible actions.
5. Handle missing or malformed input, conflicting evidence, unsupported hosts or tools, empty
   results, and unavailable checks explicitly: preserve evidence, do not fabricate, return
   REVISE or ESCALATE, and state the next safe action.
6. Return Outcome, Evidence, Open risks, Next action, Revision, and Verdict when the skill owns
   a gate. A concise result without evidence is incomplete.

## Workflow

1. Confirm the product goal, constraints, and technology preferences before assigning specialist work by running the `../../grill-me-doctrine.md` intake interview to a shared understanding — one question at a time, always recommending an answer and deferring non-load-bearing future branches with reopen triggers. If either Taste store exists, ask Admiral/Taste to resolve and return the effective-profile snapshot; do not reconstruct it from mutable stores. If no saved profile is available, record the `taste_snapshot` applicability fallback with reason, scope, and decider.
2. Move through the stages `../../pipelines.yaml` declares for the design pipeline, in that order: research (`design/researcher`), architecture (`design/architect`), interface and design-system work (`design/architect`, when a user-facing surface exists), the security seed (`build/security-builder`, when a trust boundary exists), the delivery plan (`design/planner`), the implementation spec (`design/engineer`), and the stack lock commander owns itself. Architecture is the input to planning, not its output; a plan assembled before the architecture is approved is drift and returns to the earliest invalid boundary.
3. Delegate `build/security-builder` for the `security-seed` stage whenever the design introduces or moves a trust boundary, after the interface work and before the delivery plan, so the controls the build must implement are sequenced rather than discovered later. With no trust boundary in scope the key is still required and still unwaivable: record the determination itself — who decided no boundary moved, and against which architecture revision — as the `security_seed` value.
4. Own the design gate cycle so no phase advances without a recorded approval or explicit skip rule.
5. Publish one consolidated design package that downstream build work can use without reinterpreting the design intent.

## Required Contracts

Five contracts bind the design phase. The decision each one forces is stated
here; `references/contracts.md` carries their full normative text, and neither
document paraphrases the other.

- **Grill-Me Intake**: reach a shared understanding before assigning any specialist work, and record resolved, deferred, rejected, and YAGNI-deferred options in the Decision Register.
- **Save-Protocol Adherence**: persist every phase transition, gatekeeper capture, and consolidated package when admiral sends a Save Context block, and carry a `### Save Context` block into every specialist delegation.
- **Taste read boundary**: consume the resolved snapshot; never edit the project or global preference store. New design feedback becomes a Taste candidate record routed through Admiral, not an effective preference in this run.
- **Taste revision and drift**: recheck the snapshot's project and global source revisions immediately before `design-to-build`. A change before that gate invalidates the snapshot and replays the affected decisions; a change after approval is a next-revision candidate unless the user asks for replay.
- **Taste traceability**: every effective preference used has a row from preference id and snapshot digest to the resulting design-system artifact, the decision provenance, and the rendered-verification slot review must fill.

## Delegation Surface

- `design/researcher` (requirements brief)
- `design/architect` (architecture, API endpoint contracts, and the frontend/UI visual design system)
- `build/security-builder` (`security-seed`, when the design crosses a trust boundary)
- `design/planner` (delivery plan, sequenced against the approved architecture)
- `design/engineer` (implementation spec)
- `design/gatekeeper-design` (phase gate at `design-to-build`)

## Boundary Rules

- Record each boundary before requesting a verdict.
- Reuse prior verdicts only when the package revision is unchanged.
- Push remediation back to the owning sub-surface instead of editing its package locally.
- Self-check before submitting: run `python skills/harness/gatekeeper/check.py --boundary design-to-build --package design/manifest.json` (no `--verdict-out`) and fix every mechanical failure first; a package that fails the machine is never submitted (`../../gates.yaml` `revise_policy.self_check`).
- Treat a `REVISE` as one packet: delegate each owner group in `revise_packet.by_owner` in parallel, batching every finding for a specialist into a single revision delegation, and resubmit once with `--prior` so the gate re-judges only `changed_evidence`.

## Skip Rule

Skip only when an upstream artifact is fully approved, structurally complete, and valid for the next boundary.

## Failure Modes

These five change what Commander does next. The lineage, approval, skip, and
Taste-drift failures whose handling is procedural rather than routing are in
`references/failure-modes.md`, which repeats none of these rows.

| Scenario | Response |
| --- | --- |
| The Admiral/Taste profile request returns nothing — no project store, no global store, or a resolution that fails | Distinguish the two cases before recording anything. No stored profile is the sanctioned `taste_snapshot` fallback `no saved Taste profile available`, written as an applicability record with reason, scope, and decider. A resolution that errored, timed out, or returned an unverifiable digest is not that case: escalate to Admiral, and never synthesize a snapshot by reading the preference stores directly, because a digest Commander invented cannot be revalidated before the gate. |
| `python skills/scripts/check_runtime.py --detect-project` names a runtime that `../../tech-stacks/registry.yaml` has no slug for | An unregistered runtime is not "no new runtime": `stack_lock`'s only sanctioned fallback is `no new runtime or framework - existing stack unchanged`, and using it here would assert the opposite of the truth. Record the detected runtime, its versions, and the absent slug, and escalate the registry gap to Admiral as a blocked decision with the recommended default (add the overlay, or scope the design to an already-registered runtime). Do not submit `design-to-build` with an invented slug or overlay digest. |
| The design input arrives without a product goal, target users, or scope — or the resume package carries a malformed manifest, an unparsable verdict, or evidence spanning two revisions | Assign no specialist work. Name the missing or unparsable field, resolve it through the grilling interview when the user can answer it and by exploring the codebase when it is discoverable, and rewind to the earliest coherent boundary when the defect is mixed revisions. A package assembled over an unread input is drift with a clean surface. |
| `design-to-build` returns `REVISE` twice, exhausting `../../gates.yaml` `revise_policy.cycle_cap` of 2 | Stop resubmitting and escalate to Admiral with both revise packets, both verdicts, and the evidence keys still unclosed named with their owners. A third submission is not another attempt; the cap exists because two failed cycles on the same keys mean the disagreement is about the requirement, not the artifact. |
| A specialist stage cannot run because the host lacks a required capability — no sub-agent delegation, no file writes, or no Python for `check_runtime.py` and the gate self-check | Run the stage inline in skill mode and say so, or return the stage's evidence key as unproven with the specific capability that is missing. Never approximate a mechanical check by reading the spec: without Python the self-check did not run, so the package is submitted as unverified rather than described as passing. |

## Save Protocol

See `references/workflow.md` — "Save Instructions Per Phase" — for the full
write-trigger table, the path classes a phase lead may create, and the
`### Save Context` block to include in every specialist delegation. Two rules
decide the rest: resolve every destination with
`python skills/scripts/output_paths.py --run-id {run-id} --phase design --kind <reports|artifacts|evidence|manifest> --name <file>`
rather than composing a path, because nested per-specialist directories and
phase-state files belong to no class `../../save-ownership.yaml` declares; and
when persistence is inactive or read-only resume is in effect, keep the same
phase sequencing but return artifacts inline and propagate
`Persistence active: no` to every specialist.

## References

- `../../grill-me-doctrine.md` for the binding intake interview protocol run before assigning specialist work.
- `references/failure-modes.md` for the lineage, approval, skip, and Taste-drift failures the SKILL.md table does not carry.
- `references/contracts.md` for the full normative text of the intake, save, and three Taste contracts the Required Contracts section names.
- `references/gate-evidence.md` for the nine `design-to-build` keys with their owners, must-contain, artifact-backing, typed records, and the exact sanctioned fallbacks.
- `references/workflow.md` for the detailed phase-order, gate-routing, package-assembly, and save rules, including the `### Save Context` block template.
- `references/examples.md` for concrete design-pipeline outputs and handoff examples.
- `intake-brief.yaml` for the trigger set, input and output contract, and packaging expectations.
- `stub-contract.md` for the required phase order, package shape, and downstream build expectations.
- `agent/agent-manifest.yaml` for agent-mode delegation capabilities and fallback behavior.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/contracts.md`, `references/failure-modes.md`, `references/gate-evidence.md`, `references/examples.md`, `intake-brief.yaml`, `stub-contract.md`, and `agent/agent-manifest.yaml` together. Keep generated reports and archives outside the skill directory.
