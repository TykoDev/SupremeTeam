---
name: investigate
description: >-
  Admiral-pipeline investigation component, normally invoked by `admiral`; if
  reached directly for lifecycle work without an active Admiral handoff, hand off
  to `admiral` first (see routing-doctrine.md). Runs disciplined root-cause
  analysis across code, logs, runtime clues, and environmental evidence when the
  failure shape is still unclear. Use when `admiral` delegates an investigation, or
  the user asks to investigate this issue, find the root cause, explain why this
  broke, trace the failure, or narrow a messy incident down to one credible
  explanation.
version: 1.0.0
---

# Investigate

## Purpose

Run disciplined root-cause analysis across code, logs, runtime clues, and environmental evidence when the failure shape is still unclear.

## Entry Routing

This skill is a component of the **Admiral** delivery pipeline; `admiral` is the primary entry orchestrator (see `../routing-doctrine.md`). Before doing any work, run the **active-handoff check** — a handoff is present when the prompt carries a `### Save Context` block, an active run lock / `session_pin: true` exists under `skillset-saves/`, or the invocation explicitly frames this skill as the owning component for an Admiral boundary.

- **Handoff present** → proceed; you are running inside an Admiral run.
- **No handoff (cold/direct invocation)** → do not run standalone. Start `admiral` first and let it run intake, persistence, and gatekeeping, then accept the delegation back. This is the loop guard: Admiral's own delegations always carry the handoff signal, so a delegated call proceeds immediately and never re-bootstraps Admiral.

## Use This Skill When

- investigate this issue
- find the root cause
- explain why this broke
- trace the failure

## Inputs

- Incident, defect, or unexplained behavior to investigate, plus current project/environment context and expected healthy behavior.
- Relevant logs, runtime observations, screenshots, traces, or configuration snapshots.
- Known constraints, such as protected environments, missing access, or evidence-retention limits.

## Outputs

- Root-cause investigation report with timeline, competing hypotheses, dismissed paths, and confidence level.
- Evidence bundle linking logs, traces, screenshots, config diffs, and code references to each conclusion.
- Next-step decision record listing confirmed fix path, missing access/evidence, or escalation owner when root cause remains unproven.

## Workflow

1. Build a failure timeline from symptoms, recent changes, logs, and environment clues before committing to a root-cause theory.
2. Reproduce or narrow the issue with targeted checks, keeping observed facts separate from hypotheses so the investigation does not silently drift into storytelling.
3. Test competing explanations until one survives the evidence or the remaining ambiguity is explicit and bounded.
4. Return an investigation report with the root cause or bounded suspect set, reproduction notes, and the next fix or data request.

## Required Contracts

- **Before/After Evidence**: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- None required beyond the active task surface.

## Review Expectations

- Show the causal chain from first observed symptom to likely source of failure, including hypotheses ruled out.
- Keep raw observations separate from inference so callers can challenge weak links in the investigation.
- End with a bounded fix or escalation path that names what evidence would change the conclusion.

## Skip Rule

Skip only when the requested surface, tool, or environment does not exist and a safe fallback is unavailable.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The incident cannot be reproduced and key logs or traces have already aged out | Bound the uncertainty explicitly, preserve the evidence that still exists, and request the next capture opportunity instead of inventing certainty. |
| Several failures begin at the same time after both code and environment changes | Track competing hypotheses in parallel and avoid collapsing the incident onto the first plausible narrative. |
| A candidate fix removes the symptom but leaves the causal chain unproven | Report the mitigation as provisional and do not overclaim root-cause confidence. |
| Access limitations hide one critical evidence source, such as production logs or a managed service metric stream | Escalate the missing evidence boundary and keep the conclusion scoped to what can actually be observed. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Do not create or manage `_phase-state.md` — that is the delegating orchestrator's responsibility.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed investigation sequence and decision rules.
- `references/examples.md` for concrete investigation examples.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
