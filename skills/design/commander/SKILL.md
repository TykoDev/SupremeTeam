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

- **Handoff present** → proceed; you are running inside an Admiral run.
- **No handoff (cold/direct invocation)** → do not run standalone. Start `admiral` first and let it run intake, persistence, and gatekeeping, then accept the delegation back. This is the loop guard: Admiral's own delegations always carry the handoff signal, so a delegated call proceeds immediately and never re-bootstraps Admiral.

## Use This Skill When

- design this system
- create the design package
- start the design pipeline
- plan and architect this project

## Inputs

- Admiral-normalized design request with product goals, users, constraints, technology preferences, and explicit non-goals.
- Active design save context, prior phase verdicts, and revision lineage when resuming an interrupted design run.
- Intake decisions, escalations, or skip requests that affect research, planning, architecture, API/UI handoff, or implementation guidance.

## Outputs

- Design package combining research evidence, delivery plan, architecture/API/UI contracts, implementation spec, and Decision Register.
- `design/gatekeeper-design` submission record with phase approvals, revision id, skip justifications, and unresolved design risks.
- Design escalation packet naming the conflicting requirement, blocked decision, owner, and recommended default.

## Workflow

1. Confirm the product goal, constraints, and technology preferences before assigning specialist work by running the `../../grill-me-doctrine.md` intake interview to a shared understanding — one question at a time, always recommending an answer.
2. Move through research, planning, architecture, API endpoint design, interface design, and implementation guidance in dependency order.
3. Own the design gate cycle so no phase advances without a recorded approval or explicit skip rule.
4. Publish one consolidated design package that downstream build work can use without reinterpreting the design intent.

## Required Contracts

- **Grill-Me Intake**: Before assigning any specialist work, run the intake interview in `../../grill-me-doctrine.md` — resolve every load-bearing branch one question at a time, use the planning-mode decision prompt contract for unresolved design/configuration choices, always recommend an answer, and explore the codebase instead of asking when the answer is discoverable. Record resolved, deferred, and rejected material options in the Decision Register.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from admiral, persist every phase state transition, gatekeeper capture, and consolidated package to the save path. Include a `### Save Context` block in every specialist delegation. Saving is mandatory, not optional.

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
| A requested skip would leave a required frontend, architecture, or implementation artifact absent from the design package | Reject the skip, name the missing boundary, and require an explicit scoped exception before proceeding. |
| A requested skip would leave an API endpoint contract absent for a surface the build must implement | Reject the skip, require `design/architect` to produce the endpoint inventory and contracts, or record a scoped backend-only/no-endpoint exception. |

## Save Protocol

When admiral delegates with `Persistence active: yes`, commander owns these files within `skillset-saves/runs/{run-id}/design/`. When persistence is inactive or read-only resume is in effect, commander keeps the same phase sequencing but returns artifacts inline and propagates `Persistence active: no` to specialists.

| Trigger | What Commander Writes |
|---------|----------------------|
| Phase start | `phase-{N}_{skill}/_phase-state.md` (state: ACTIVE) |
| Specialist delegation | Include `### Save Context` block with phase save path |
| Gate verdict capture | `phase-{N}_{skill}/gatekeeper-verdict.md` + `_phase-state.md` update |
| Package consolidation | `design-package.md` + `delegation-log.md` |

Save Context block for specialist delegations:

```markdown
### Save Context
- **Run ID**: {run-id}
- **Save path**: skillset-saves/runs/{run-id}/design/phase-{N}_{skill}/
- **Persistence active**: {yes|no — copied from current run state}
- **Persistence probe result**: {ok|failed|skipped}
- **Context tier**: {1|2|3|4}
- **Artifact mode**: {inline|reference|best-effort-inline}
- **Standalone fallback ref**: {path or "none"}
- **Skipped upstream stages**: {none or list}
- **Session pin**: {true|false}
- **Execution mode**: {agent|skill}
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
