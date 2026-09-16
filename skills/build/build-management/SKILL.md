---
name: build-management
description: >-
  Build sub-orchestrator of the Admiral pipeline: turns an approved design into
  a build package with implementation, tests, runtime-health, security, and
  completeness evidence at the `build-to-review` gate. Use when `admiral`
  delegates the build, or a user asks to implement this design, start the build
  pipeline, build this project, execute the implementation plan, or turn a
  specification into code — even when Admiral is never named. Defers to
  `admiral` when reached cold; reviewing the finished code belongs to
  `review/code-chief`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

# Build Management

## Purpose

Build-management sequences and assembles; the specialists write the code. Its
boundary is the build package as *one revision with coherent evidence* — code,
tests, runtime health, hardening, and completeness certification that all
describe the same commit — because `review/code-chief` reviews what the package
claims, and evidence gathered before the last change silently reviews something
that no longer exists.

Two things are most often got wrong. The `runtime-health` stage is treated as
optional and its smoke log replaced by a passing test suite; `runtime` is a
separate unwaivable key with a separate owner, and a suite passing in a harness
is not the shipped entry point starting. And a late security or bug fix lands
after tests have already run, leaving the package coherent in appearance and
stale in fact.

## Entry Routing

This skill is a component of the **Admiral** delivery pipeline; `admiral` is the primary entry orchestrator (see `../../routing-doctrine.md`). Before doing any work, run the **active-handoff check** — a handoff is present when the prompt carries a `### Save Context` block, an active run lock / `session_pin: true` exists under `skillset-saves/`, or the invocation explicitly names this skill as the owning sub-orchestrator for the build boundary.

- **Handoff present** → proceed; the run is active inside an Admiral run.
- **No handoff (cold/direct invocation)** → do not run standalone. Start `admiral` first and let it run intake, persistence, and gatekeeping, then accept the delegation back. This is the loop guard: Admiral's own delegations always carry the handoff signal, so a delegated call proceeds immediately and never re-bootstraps Admiral.

## Use This Skill When

- implement this design
- start the build pipeline
- build this project
- execute the implementation plan
- turn the specification into code

A failure discovered mid-build routes by what is known about it: a reproduced
failure with a known mechanism goes to `build/debugger`, and an unknown mechanism
goes to `investigate`, which returns a bounded fix path rather than a second
build.

## Inputs

- Gate-approved design package with implementation specification, delivery slices, interface contracts, and acceptance evidence expectations.
- Active build save context, prior build-phase verdicts, and revision lineage when resuming an interrupted build run.
- Upstream decisions, design-gate conditions, or review findings that constrain implementation, testing, hardening, or completeness scope.

## Outputs

- Build package combining implemented slices, diff summary, test evidence, security hardening, health/completeness certification, and dependency notes.
- `build/gatekeeper-build` submission record with implementation revision, evidence timestamps, phase lineage, and unresolved blockers.
- Build escalation packet naming missing design input, environment blocker, vendored-surface decision, or validation gap.

### Gate evidence owned at `build-to-review`

Build-management is the `build-to-review` submitter (`../../gates.yaml`,
`boundaries`), so it assembles all six required keys into `build/manifest.json`
and authors two of them itself: `approved_design_revision` and `traceability`.
The other four are authored by their owners and carried in unchanged —
`implementation` from `build/bob-the-builder`, `tests` from
`build/test-builder`, `runtime` from `build/health-check`, `security_evidence`
from `build/security-builder`.

Three decisions live here; `references/gate-evidence.md` carries the full per-key
table with the must-contain, artifact-backing, typed-record, and fallback
columns.

- **What build-management authors**: `approved_design_revision`, read from the `design-to-build` verdict rather than restated from memory, and `traceability`, the design-decision-to-changed-artifact mapping with proven or unproven status per row. A gap in either is its own to close, not a specialist's.
- **Which keys are hashed files**: `tests` and `runtime` only. Both are typed `probe` records whose executed logs live under `build/evidence/`; a count or a claim of passing is not evidence for either.
- **Which key may be waived**: `security_evidence` alone, and only when no trust boundary moved, carried as an applicability record for the sanctioned value `no trust-boundary change - security-builder not engaged`. `approved_design_revision`, `implementation`, `tests`, `runtime`, and `traceability` accept nothing but their evidence.

## Execution Contract

Canonical source: `../../execution-contract.md`. Stated locally because that file requires every
orchestrator and gatekeeper to carry the clauses verbatim; a paraphrase is drift.

1. Select the preamble tier before acting: Tier 0 for minor, understood, reversible tasks under the Tier 0 fast path in routing-doctrine.md; Tier 1 for bounded read-only work beyond Tier 0; Tier 2 for multi-step edits, delegation, or external coordination beyond Tier 0; Tier 3 for destructive, security-sensitive, production, or irreversible work. Record the tier and rationale in the handoff, or the brief completion note for Tier 0. Tier 0 skips pipeline ceremony and full security audits, but retains focused verification and applicable guardrails; escalate when its eligibility no longer holds.
2. Trigger proactively when the task matches the skill's declared scope, even when the request uses different words; decline adjacent work and route end-to-end or specialist ownership explicitly. Offer a next safe action only after the current step, scope, and approval lineage are resolved; suppress that offer while any is unresolved.
3. Use Critical | Major | Minor | Info for findings. Block on Critical, resolve Major before a gate, record Minor, and preserve Info as context. Use APPROVED | REVISE | ESCALATE for gate verdicts.
4. Validate paths, inputs, revisions, and handoff fields before acting. Keep file operations inside the workspace, use read-only or dry-run probes first, and require explicit owner intent for destructive or externally visible actions.
5. Handle missing or malformed input, conflicting evidence, unsupported hosts or tools, empty results, and unavailable checks explicitly: preserve evidence, do not fabricate, return REVISE or ESCALATE, and state the next safe action.
6. Return Outcome, Evidence, Open risks, Next action, Revision, and Verdict when the skill owns a gate. A concise result without evidence is incomplete.

## Workflow

1. Validate the implementation scope and identify any design gaps before code work starts.
2. Run the ordered stages `../../pipelines.yaml` defines for the `build` pipeline as separate controlled phases: implementation through `build/bob-the-builder`, the test surface through `build/test-builder`, then the security checkpoint through `build/security-builder` when a trust boundary is in scope.
3. Run the `runtime-health` stage through `build/health-check` on every build. `../../pipelines.yaml` attaches no condition to that stage, and its startup and entry-point smoke log is the `runtime` evidence `build-to-review` requires, so a passing test suite never stands in for it.
4. Engage `build/debugger` for the `debugging` stage when a reproduced build-phase failure exists, and `investigate` for the `investigation` stage when the failure mechanism is unknown. Investigation runs its own pipeline gated at `investigation-review` and returns a bounded fix path to the build phase; it never becomes a second build.
5. Confirm completeness through `build/cross-check-build-confirm`, route every finding back to the owning build specialist, and re-run the affected phases before the build package advances.
6. Publish one build package with enough evidence for review work to trust the code, tests, runtime health, and remediation history, then submit it at `build-to-review` through `build/gatekeeper-build`.

## Required Contracts

Two contracts bind the build phase. The decision each one forces is stated here;
`references/contracts.md` carries their full normative text, and neither document
paraphrases the other.

- **Vendoring detection**: classify every changed path as first-party or not before any completeness claim is made, using the mechanical rule in the reference — a vendor or generated root, a generator marker in the name or header, or an entry that arrived through a package manager or codegen step rather than an authored edit. A non-first-party path is inventoried with its upstream source, version, accepting owner, and scan note; it is excluded from first-party coverage rather than counted toward it; and it is never hand-edited, because an edit the next regeneration erases is not a fix.
- **Save-Protocol Adherence**: persist every phase transition, gatekeeper capture, and consolidated package when admiral sends a Save Context block, and carry a `### Save Context` block into every specialist delegation.

## Delegation Surface

The `build` pipeline stages in `../../pipelines.yaml` and their owners, in order.
A stage with a condition runs only when that condition holds; the rest are
unconditional.

- `build/bob-the-builder` for `implementation`
- `build/test-builder` for `test-surface`
- `build/security-builder` for `security-checkpoint`, when a trust boundary is in scope
- `build/health-check` for `runtime-health`, which produces the `runtime` evidence the build manifest requires
- `build/debugger` for `debugging`, when a reproduced build-phase failure exists
- `investigate` for `investigation`, when the failure mechanism is unknown; it owns the investigation pipeline gated at `investigation-review` and returns a bounded fix path
- `build/cross-check-build-confirm` for `completeness-cross-check`
- `build/gatekeeper-build` for `phase-gate`

## Boundary Rules

- Record each boundary before requesting a verdict.
- Reuse prior verdicts only when the package revision is unchanged.
- Push remediation back to the owning sub-surface instead of editing its package locally.
- Self-check before submitting: run `python skills/harness/gatekeeper/check.py --boundary build-to-review --package build/manifest.json` (no `--verdict-out`) and fix every mechanical failure first; a package that fails the machine is never submitted (`../../gates.yaml` `revise_policy.self_check`).
- Treat a `REVISE` as one packet: delegate each owner group in `revise_packet.by_owner` in parallel, batching every finding for a specialist into a single revision delegation, and resubmit once with `--prior` so the gate re-judges only `changed_evidence`.

## Skip Rule

Skip only when an upstream artifact is fully approved, structurally complete, and valid for the next boundary.

## Failure Modes

These six change what Build-Management does next. The revision-coherence,
phase-skip, and vendored-surface failures whose handling is procedural rather
than routing are in `references/failure-modes.md`, which repeats none of these
rows.

| Scenario | Response |
| --- | --- |
| The build is a library, SDK, or package with no startable entry point, so `build/health-check` has nothing to boot | `runtime` still has no fallback and the test suite may not stand in for it, because `tests` and `runtime` are separate keys with separate owners. Have `build/health-check` smoke the real consumption path the package declares — import the built artifact from a clean environment, resolve its entry points, and exercise the documented public surface once — and hash that executed log as `runtime`. If even that cannot run on this host, submit nothing: escalate to Admiral naming the missing capability, because a `build-to-review` package without `runtime` fails mechanically and a claimed pass would be fabricated evidence. |
| The design package is missing, carries no `design-to-build` approval, or its approval names a revision the build does not implement | Start no implementation. `approved_design_revision` has no fallback, so a build begun here cannot reach the gate whatever it produces. Return the gap to Admiral naming which of the three it is — absent, unapproved, or mismatched — and let Admiral rewind to the design boundary rather than reconstructing intent from the code. |
| The design input parses but is incoherent: acceptance criteria contradict the implementation spec, or slices reference interfaces the package does not contain | Treat it as malformed rather than as a puzzle to solve. Name the two artifacts that disagree and the exact contradiction, and route it back through Admiral to `design/commander`, which owns design-stage revisions. Choosing one side silently is how a build implements a design nobody approved. |
| `investigate` returns from the `investigation` stage without a bounded fix path — the mechanism is still open, or the path it names is larger than the build phase owns | Do not implement a guess. An investigation that returns `ESCALATE` or a fix path outside this phase stops the build phase: record the open mechanism and the residual uncertainty in the package, and hand the decision to Admiral, which routes the path to the phase that owns it. A fix applied without a mechanism produces exactly the stale, unexplained evidence the gate exists to catch. |
| `build-to-review` returns `REVISE` twice, exhausting `../../gates.yaml` `revise_policy.cycle_cap` of 2 | Stop resubmitting and escalate to Admiral with both revise packets, both verdicts, and the unclosed keys named with their owners. Two failed cycles on the same keys mean the disagreement is about the requirement, not the artifact, and a third submission spends the gatekeeper's judgment on the same dispute. |
| A required capability is unavailable: no sub-agent delegation, no command execution for the test or smoke run, or no Python for the gate self-check | Run what the host allows and report the rest as unproven by name. A probe that could not execute is `result.status: unavailable`, which is a data gap and never a pass — `tests` and `runtime` both fail the gate on it, which is the correct outcome. Without Python the self-check did not run, so the package is submitted as unverified rather than described as passing. |

## Save Protocol

See `references/workflow.md` — "Save Instructions Per Phase" — for the full
write-trigger table, the path classes a phase lead may create, and the
`### Save Context` block to include in every specialist delegation. Two rules
decide the rest: resolve every destination with
`python skills/scripts/output_paths.py --run-id {run-id} --phase build --kind <reports|artifacts|evidence|manifest> --name <file>`
rather than composing a path, because nested per-specialist directories and
phase-state files belong to no class `../../save-ownership.yaml` declares; and
when persistence is inactive or read-only resume is in effect, keep the same
phase sequencing but return artifacts inline and propagate
`Persistence active: no` to every specialist.

## References

- `references/failure-modes.md` for the revision-coherence, phase-skip, and vendored-surface failures the SKILL.md table does not carry.
- `references/contracts.md` for the full normative text of the vendoring-detection and save contracts the Required Contracts section names.
- `references/gate-evidence.md` for the six `build-to-review` keys with their owners, must-contain, artifact-backing, typed records, and sanctioned fallbacks.
- `references/workflow.md` for the detailed phase-order, revision-loop, package-assembly, and save rules, including the `### Save Context` block template.
- `references/examples.md` for concrete build-pipeline outputs and handoff examples.
- `intake-brief.yaml` for the trigger set, input and output contract, and packaging expectations.
- `stub-contract.md` for the mandatory phase order, package shape, and downstream review expectations.
- `agent/agent-manifest.yaml` for agent-mode delegation capabilities and fallback behavior.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/contracts.md`, `references/failure-modes.md`, `references/gate-evidence.md`, `references/examples.md`, `intake-brief.yaml`, `stub-contract.md`, and `agent/agent-manifest.yaml` together. Keep generated reports and archives outside the skill directory.
