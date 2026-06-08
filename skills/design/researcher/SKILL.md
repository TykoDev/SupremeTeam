---
name: researcher
description: >-
  Researches stakeholder goals, domain constraints, and requirement evidence so
  the design pipeline starts from a grounded problem statement. Use when the user
  asks to research this problem space, gather requirement evidence, analyze
  stakeholder needs, map the domain context, or turn a fuzzy request into evidence
  the design team can actually build from — even when they only hand over a vague
  idea. Establishes the grounded problem statement; defers turning requirements
  into a plan to `design/planner` and system architecture to `design/architect`.
version: 1.0.0
---

# Researcher

## Purpose

Research stakeholder goals, domain constraints, and requirement evidence so the design pipeline starts from a grounded problem statement.

## Use This Skill When

Use this skill to **ground the problem before any design work** — turn a fuzzy request into evidence:

- "research this problem space" / "map the domain context" — surface domain constraints and prior art
- "gather requirement evidence" — collect the evidence behind each requirement
- "analyze stakeholder needs" — convert stakeholder goals into a defensible problem statement

Route elsewhere once the problem is grounded and the work shifts to a delivery plan (`design/planner`) or system architecture (`design/architect`).

## Inputs

- Stakeholder questions, product or domain background, current design constraints, and existing artifacts that can be mined for evidence.
- Known actors, success criteria, compliance or domain constraints, and assumptions that need confirmation before planning starts.
- Decisions the planner or architect cannot make until research clarifies priority, risk, or feasibility.

## Outputs

- Requirements evidence package mapping each proposed requirement to source, confidence, and unresolved assumptions.
- Stakeholder and job-to-be-done summary with domain constraints, comparable patterns, and priority rationale.
- Design-intake packet for `design/commander` and `design/planner` that names decisions still blocked by missing evidence.

## Workflow

1. Frame the research question in terms of actors, jobs to be done, constraints, success criteria, and the decisions the next design phase must make. Run the `../../grill-me-doctrine.md` intake interview first to reach a shared understanding of intent and priorities — one question at a time, always recommending an answer.
2. Gather evidence from user input, existing artifacts, domain sources, and comparable flows while separating confirmed facts from assumptions or analogies.
3. Synthesize the evidence into requirements, constraints, risks, and open questions that downstream planner and architect phases can directly consume.
4. Return a concise review packet with evidence anchors, recommended priorities, and explicit unknowns that still need resolution.

## Required Contracts

- **Grill-Me Intake**: Before producing the research packet, run the intake interview in `../../grill-me-doctrine.md` — resolve every load-bearing branch one question at a time, always recommend an answer, and explore the codebase, configs, and existing artifacts instead of asking when the answer is discoverable.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- `design/commander`
- `design/gatekeeper-design`

## Review Expectations

- Cite the source, confidence level, and affected downstream decision for each material requirement or constraint.
- Separate verified facts from assumptions, analogies, and stakeholder preferences so the planner does not inherit false certainty.
- Hand off unresolved research gaps with an owner and decision deadline instead of burying them in narrative.

## Skip Rule

Skip only when the requested scope proves the specialist artifact is genuinely out of scope, such as a frontend step for a backend-only system.

## Failure Modes

| Scenario | Response |
| --- | --- |
| Stakeholder goals conflict or are underspecified, so different actors are optimizing for different outcomes | Surface the conflict explicitly and avoid collapsing it into one false set of requirements. |
| Evidence sources disagree on compliance, operational, or domain constraints | Preserve the disagreement, rank the confidence of each source, and flag the unresolved decision for the next gate. |
| Available research is mostly anecdotal and lacks reliable usage data | Mark the requirement confidence accordingly and avoid presenting assumptions as proven demand. |
| The prompt tries to force an implementation or technology decision that research should only inform, not pre-approve | Reframe the output as evidence and tradeoffs, then leave the actual design commitment to later phases. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Do not create or manage `_phase-state.md` — that is the delegating orchestrator's responsibility.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `../../grill-me-doctrine.md` for the binding intake interview protocol run before producing the research packet.
- `references/workflow.md` for the detailed research sequence and decision rules.
- `references/examples.md` for concrete research examples.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
