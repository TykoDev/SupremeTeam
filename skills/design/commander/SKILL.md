---
name: commander
description: >-
  Admiral-pipeline design sub-orchestrator, normally invoked by `admiral`; if
  reached directly for lifecycle work without an active Admiral handoff, hand off
  to `admiral` first (see routing-doctrine.md). Runs the design pipeline from
  initial scope to an approved design package with requirements, plans,
  architecture, interface contracts, and implementation guidance. Use when
  `admiral` delegates the design boundary, or the user asks to design this system,
  create the design package, start the design pipeline, or plan and architect this
  project.
version: 1.0.0
---

# Commander

## Purpose

Run the design pipeline from initial scope to an approved design package with requirements, plans, architecture, interface contracts, and implementation guidance.

## Entry Routing

This skill is a component of the **Admiral** delivery pipeline; `admiral` is the primary entry orchestrator (see `../../routing-doctrine.md`). Before doing any work, run the **active-handoff check** — a handoff is present when the prompt carries a `### Save Context` block, an active run lock / `session_pin: true` exists under `skillset-saves/`, or the invocation explicitly names this skill as the owning sub-orchestrator for the design boundary.

- **Handoff present** → proceed; the run is active inside an Admiral run.
- **No handoff (cold/direct invocation)** → do not run standalone. Start `admiral` first and let it run intake, persistence, and gatekeeping, then accept the delegation back. This is the loop guard: Admiral's own delegations always carry the handoff signal, so a delegated call proceeds immediately and never re-bootstraps Admiral.

## Use This Skill When

- design this system
- create the design package
- start the design pipeline
- plan and architect this project

## Inputs

- Admiral-normalized design request with product goals, users, constraints, technology preferences, explicit non-goals, and YAGNI deferrals from intake.
- Active design save context, prior phase verdicts, and revision lineage when resuming an interrupted design run.
- Intake decisions, escalations, or skip requests that affect research, planning, architecture, API/UI handoff, or implementation guidance.
- An effective-profile snapshot requested from Admiral/Taste whenever project or global Taste storage exists. It must carry the canonical digest, project and global source revisions, resolved entries, shadowed entries, unresolved conflicts, and applicability decision.

## Outputs

- Design package combining research evidence, delivery plan, architecture/API/UI contracts, implementation spec, Decision Register, and `taste_snapshot` (or its sanctioned no-profile applicability record).
- `design/gatekeeper-design` submission record with phase approvals, revision id, skip justifications, and unresolved design risks.
- Design escalation packet naming the conflicting requirement, blocked decision, owner, and recommended default.

## Workflow

1. Confirm the product goal, constraints, and technology preferences before assigning specialist work by running the `../../grill-me-doctrine.md` intake interview to a shared understanding — one question at a time, always recommending an answer and deferring non-load-bearing future branches with reopen triggers. If either Taste store exists, ask Admiral/Taste to resolve and return the effective-profile snapshot; do not reconstruct it from mutable stores. If no saved profile is available, record the `taste_snapshot` applicability fallback with reason, scope, and decider.
2. Move through research, planning, architecture, API endpoint design, interface design, and implementation guidance in dependency order.
3. Own the design gate cycle so no phase advances without a recorded approval or explicit skip rule.
4. Publish one consolidated design package that downstream build work can use without reinterpreting the design intent.

## Required Contracts

- **Grill-Me Intake**: Before assigning any specialist work, run the intake interview in `../../grill-me-doctrine.md` — resolve every load-bearing branch one question at a time, use the planning-mode decision prompt contract for unresolved design/configuration choices, always recommend an answer, explore the codebase instead of asking when the answer is discoverable, and apply YAGNI to avoid speculative commitments. Record resolved, deferred, rejected, and YAGNI-deferred material options in the Decision Register.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from admiral, persist every phase state transition, gatekeeper capture, and consolidated package to the save path. Include a `### Save Context` block in every specialist delegation. Saving is mandatory, not optional.
- **Taste read boundary**: Commander and Architect may consume the resolved snapshot but must not edit the project or global preference store. New design feedback is emitted as Taste candidate records (source context, proposed preference, rationale, and affected artifacts) and routed through Admiral to the Taste pipeline for user confirmation; it is not treated as an effective preference in the current run unless Taste confirms it and Commander re-resolves before the gate.
- **Taste revision and drift**: Recheck the snapshot's project and global source revisions immediately before `design-to-build`. A changed revision before that gate invalidates the snapshot and requires Admiral/Taste re-resolution plus replay of affected design decisions. A change after approval is a next-revision candidate unless the user explicitly requests replay. Report a project preference that conflicts with an approved project design rather than applying it retroactively. Surface revocation of a preference used by an active design as drift and obtain a user decision.
- **Taste traceability**: For each effective preference used, record a row from preference id and snapshot digest to the resulting design-system artifact(s), decision provenance, and the rendered-verification evidence slot that review must fill. Explicit run instructions, existing project conventions, and documented architect judgment use the same table with their provenance kind but no invented Taste id.

## Delegation Surface

- `design/researcher`
- `design/planner`
- `design/architect` (architecture + frontend/UI visual design system)
- `design/engineer`
- `design/gatekeeper-design`

## Boundary Rules

- Record each boundary before requesting a verdict.
- Reuse prior verdicts only when the package revision is unchanged.
- Push remediation back to the owning sub-surface instead of editing its package locally.

## Skip Rule

Skip only when an upstream artifact is fully approved, structurally complete, and valid for the next boundary.

## Failure Modes

| Scenario | Response |
| --- | --- |
| Research, planning, architecture, or interface work disagree on target users, scope, or locked stack assumptions | Freeze package assembly, preserve the contradictory phase outputs, and route the mismatch back to the owning phase instead of normalizing it inside the final package. |
| A phase deliverable looks polished but lacks the gatekeeper-design approval record for the current revision | Keep the phase closed, record the missing approval lineage, and rerun the gate before any later phase advances. |
| An upstream design change invalidates downstream phase work already assembled into the package | Invalidate the affected downstream artifacts, log the drift explicitly, and replay the pipeline from the earliest changed boundary. |
| A Taste source revision differs from the snapshot before `design-to-build` | Invalidate `taste_snapshot`, request re-resolution from Admiral/Taste, and replay every affected design-system decision before resubmission. |
| A used Taste entry is revoked, or a project preference conflicts with an already approved project design | Surface drift and ask the user whether to replay; never mutate either store or retroactively rewrite the approved design. |
| A requested skip would leave a required frontend, architecture, or implementation artifact absent from the design package | Reject the skip, name the missing boundary, and require an explicit scoped exception before proceeding. |
| A requested skip would leave an API endpoint contract absent for a surface the build must implement | Reject the skip, require `design/architect` to produce the endpoint inventory and contracts, or record a scoped backend-only/no-endpoint exception. |

## Save Protocol

When admiral delegates with `Persistence active: yes`, commander is the phase lead
for `skillset-saves/runs/{run-id}/design/` and writes only the path classes
`../../save-ownership.yaml` grants a phase lead: `manifest.json`, `reports/`,
`artifacts/`, `evidence/`, and `packages/`. Resolve every destination with
`python skills/scripts/output_paths.py --run-id {run-id} --phase design --kind <reports|artifacts|evidence|manifest> --name <file>`;
never compose a path by hand, and never create nested per-specialist directories
or phase-state files, because no declared class covers them and phase state lives
in the run record. When persistence is inactive or read-only resume is in effect,
commander keeps the same phase sequencing but returns artifacts inline and
propagates `Persistence active: no` to specialists.

| Trigger | What Commander Writes |
|---------|----------------------|
| Phase start | Nothing on disk: the phase state is published through `session-memory` (`save_run.py checkpoint --expect-revision <n> --set active_owner=commander --set phase_state=DESIGN_ACTIVE`) before the first specialist delegation |
| Specialist delegation | The canonical `### Save Context` block (below) naming the specialist as `Owner`, the exact `reports/`, `artifacts/`, or `evidence/` destination as `Expected artifact`, and `design-to-build` as `Return boundary` |
| Specialist return | Verify the named artifact exists at its destination, then register its sha256 through a `session-memory` checkpoint (`--evidence <path>`) |
| Gate submission | `design/manifest.json` (schema 2: `boundary: design-to-build`, `owner: commander`), referencing `../intake/report_grilling.md` as `decisions`, the hashed architecture and plan reports, and the hashed `taste_snapshot` artifact (or its applicability record) |
| Phase-gate verdict | Nothing: `design/gatekeeper-design` writes `design/verdict_design-to-build.json` through `check.py --verdict-out`; commander records the semantic verdict in its next checkpoint |
| Package consolidation | `design/reports/design-package.md` plus the manifest revision admiral submits to `gatekeeper-admiral` |

Save Context block for specialist delegations (the canonical field set from
`../../contracts/handoff-templates.md`; neither file may drop a field the other
carries):

```markdown
### Save Context
- Run ID: {run-id}
- Phase: design
- Save path: skillset-saves/runs/{run-id}/design/
- Persistence active: {yes|no}
- Persistence probe result: {ok|reason}
- Context tier: {1|2|3}
- Artifact mode: {inline|file|reference}
- Session pin: {true|false}
- Execution mode: {agent|skill}
- Submission ID: {id}
- Revision: {revision}
- Owner: {specialist}
- Expected artifact: {reports/...|artifacts/...|evidence/...}
- Evidence paths: {relative paths}
- Artifact hashes: {path: sha256|none yet}
- Risks: {known risks|none declared}
- Return boundary: design-to-build
```

When Save Context is absent or `Persistence active: no`, skip all save operations and return the deliverable inline.

## References

- `../../grill-me-doctrine.md` for the binding intake interview protocol run before assigning specialist work.
- `references/workflow.md` for the detailed phase-order, gate-routing, and package-assembly rules.
- `references/examples.md` for concrete design-pipeline outputs and handoff examples.
- `intake-brief.yaml` for the trigger set, input and output contract, and packaging expectations.
- `stub-contract.md` for the required phase order, package shape, and downstream build expectations.
- `agent/agent-manifest.yaml` for agent-mode delegation capabilities and fallback behavior.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/examples.md`, `intake-brief.yaml`, `stub-contract.md`, and `agent/agent-manifest.yaml` together. Keep generated reports and archives outside the skill directory.
