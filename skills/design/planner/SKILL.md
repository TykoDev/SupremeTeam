---
name: planner
description: >-
  Turns the approved architecture into the build plan, before any code is written:
  milestones, workstream order and dependencies, decision gates, per-slice acceptance,
  and risk handling. Use when asked to plan this project, sequence the implementation
  work, define build milestones, or decide what gets built in what order — even when
  the ask is only "what's our plan here?". Planning the work is this skill; performing
  the release itself belongs to `ship`. Defers requirements to
  `design/researcher`, architecture to `design/architect`, and the spec to
  `design/engineer`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

# Planner

## Purpose

Decide the order in which an approved design becomes real, and what makes each
step done. `../../pipelines.yaml` places `plan` after `architecture` and before
`implementation-spec`, so the sequence is derived from component boundaries that
are already fixed rather than proposed alongside them — sequencing against an
unfixed boundary is a guess that later invalidates itself. `../../gates.yaml`
gives this skill two of the nine `design-to-build` keys, `plan` and `acceptance`,
and the second is the one a plan can look complete without: a milestone with no
stated acceptance condition is a date, not a commitment.

## Use This Skill When

Use this skill for the **high-level delivery plan** — how the work ships, not how it is built:

- "plan this project" / "what gets built in what order" — set milestones, workstream order, and decision gates
- "sequence the implementation work" — order the major workstreams and their dependencies
- "define build milestones" — make risk handling and gate criteria explicit

Route elsewhere when the need is gathering requirements (`design/researcher`), the architecture and interface contracts the plan sequences against (`design/architect`), or the detailed implementation spec and delivery slices (`design/engineer`).

## Entry Routing

Planner is an internal design specialist, not an entry point.
`../../routing-doctrine.md` places every `design/` skill it does not name
separately in the internal-specialist row, reached only through the owning
sub-orchestrator, and `../../pipelines.yaml` names `commander` the owner of the
`design` pipeline this skill's `plan` stage belongs to. Run the active-handoff
check before writing a plan: the approved architecture the sequence rests on, the
requirements evidence behind it, the `security-seed` whose control work is
sequenced, the revision the plan belongs to, and the save path all arrive with the
handoff, and none of them can be reconstructed cold.

A handoff is present when the delegation prompt carries a `### Save Context`
block, an active run lock with `session_pin: true` exists under
`skillset-saves/`, or the invocation explicitly names `design/commander` as the
delegating owner for the design boundary.

- **Handoff present** → proceed; this is a delegated `plan` assignment.
- **Reached cold** → write no plan. Return to `design/commander`, which owns stage
  sequencing and package assembly, then accept the delegation back. A bare "plan
  this project" is exactly the cold path this check closes: sequencing against
  boundaries nobody has fixed produces milestones that invalidate themselves when
  the architecture lands, and `plan` and `acceptance` produced outside a run carry
  no revision and no registered hash, so neither reaches `design-to-build` as
  evidence.

## Inputs

- The approved `architecture` from `design/architect`: component boundaries, data flow, invariants, failure behavior, trust boundaries, and interface contracts the delivery sequence has to respect.
- Requirements evidence, stakeholder goals, success measures, and constraints approved by `design/researcher` and carried forward through the architecture phase.
- The `security-seed` from `build/security-builder` when the design crosses a trust boundary, so control work is sequenced rather than assumed.
- Business or technology choices already locked by intake or prior gates, plus resource and sequencing constraints.
- Decisions that still affect milestones, staffing, release slices, dependency order, or rollout risk.
- Migration, deprecation, replacement, or legacy-support context when the plan changes an existing system, API, dependency, feature, or operational workflow.

## Outputs

- Delivery plan with milestones, decision gates, dependency map, and rollout strategy.
- Acceptance criteria per delivery slice: the observable condition, the check that proves it, and the named acceptor.
- Decision Register capturing open choices, recommended defaults, owners, and escalation timing.
- Migration/deprecation path when applicable, including replacement readiness, consumer/usage discovery, advisory vs compulsory posture, and removal criteria.
- Planning packet for `design/commander` and `design/engineer` that names the delivery slices, their dependency order, and the decision gates the implementation spec must satisfy — that spec is `design/engineer`'s artifact and is never authored here.

### Gate evidence owned

`../../gates.yaml` assigns this skill two of the nine `design-to-build` keys. `design/commander`
submits the boundary, but neither key can be assembled unless it is produced here:

| Key | Content | Backing | Fallback |
|-----|---------|---------|----------|
| `plan` | The delivery plan: milestones and delivery slices, rollout and rollback shape, and risk handling — the three evidence lines `../../ownership.yaml` requires of the `plan` artifact. | **Artifact-backed** — a hashed plan report, not a summary in the manifest | None sanctioned; a design package without a plan cannot pass |
| `acceptance` | The acceptance criteria each delivery slice is judged against: the observable condition that makes a slice done, the check that proves it, and who accepts it. Written per slice so the build phase inherits a testable target rather than an intention. | Narrative | None sanctioned |

`acceptance` is the key most often missed, because a plan reads complete without
it. Workflow step 4 exists to produce it, and the acceptance table in
`references/workflow.md` is the shape it takes.

## Workflow

1. Convert the approved architecture and its requirements evidence into delivery tracks, milestones, and decision gates tied to user value instead of generic phase labels; derive the dependency order from the component boundaries and interface contracts rather than restating the architecture. Run the `../../grill-me-doctrine.md` intake interview first to confirm a shared understanding of scope and priorities — one design/configuration decision at a time, using the host-native planning prompt when available, always recommending an answer.
2. Apply YAGNI to sequencing: commit only to the release slices and decision gates needed for the current objective; record reversible defaults and reopen triggers for future-scale or speculative branches.
3. Sequence the implementation work around dependencies, risky integrations, release slices, migration/deprecation steps, and the points where leadership must choose between options.
4. Write the acceptance criteria for every delivery slice before the plan is packaged: the observable condition that makes the slice done, the check that proves that condition, and the named person or role who accepts it. This step produces the `acceptance` evidence key; a slice that reaches it without all three fields is not yet planned, because the build phase would inherit an intention instead of a target.
5. Stress-test the plan against staffing, environment setup, launch timing, replacement readiness, rollback/fallback constraints, and consumer migration cost so downstream phases do not inherit an impossible schedule.
6. Return a project plan that names the milestone path, critical risks, migration/deprecation posture when relevant, the Decision Register (resolved, deferred, rejected, YAGNI-deferred options), and the acceptance criteria per slice. The detailed spec that follows belongs to `design/engineer` and is not authored here.

## Required Contracts

- **Grill-Me Intake**: Before producing the plan, run the intake interview in `../../grill-me-doctrine.md` — resolve every load-bearing branch one question at a time, use the planning-mode decision prompt contract for design/configuration choices, always recommend an answer, and explore the codebase and existing artifacts instead of asking when the answer is discoverable.
- **Acceptance per slice**: No slice ships without an observable condition, a check, and an acceptor. The gate reads `acceptance` as a required key with no sanctioned fallback, and a check nobody is named to run is not a check.
- **Architecture fidelity**: The sequence follows the approved component boundaries and interface contracts. A sequence that only works if a boundary moves is a boundary change, and it goes back to `design/architect` rather than being absorbed into the plan.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../../execution-contract.md` defines, so upstream and downstream packages interpret risk consistently.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- `design/commander` (delegates the plan stage and assembles the package)
- `design/gatekeeper-design` (judges the package at `design-to-build` and returns any `REVISE`)
- `design/architect` (owns the boundaries the sequence rests on; a needed boundary change goes back there)
- `design/engineer` (consumes the plan at the next stage; sequencing conflicts come back from there)
- `build/security-builder` (supplies the `security-seed` whose control work the plan sequences)

## Review Expectations

- Tie every milestone and dependency to a requirement, constraint, or architecture boundary so the implementation spec can see why the sequencing exists.
- Mark unresolved decisions with owners and latest safe decision points instead of turning uncertainty into hidden assumptions.
- Do not deprecate without a replacement path: plans that remove or replace behavior must identify active consumers, migration tooling/docs, advisory vs compulsory posture, and the evidence required before removal.
- Separate rollout risk, staffing risk, and technical dependency risk so the gate can challenge the right part of the plan.

## Skip Rule

Skip only when the requested scope proves a delivery plan is genuinely out of scope, such as a single reversible change that ships as one slice under an already-approved plan for the same revision. Record the skip with its justification and the plan it defers to; an unrecorded skip reads at the gate as a missing artifact, and `plan` has no sanctioned fallback.

## Failure Modes

| Scenario | Response |
| --- | --- |
| A plan is requested before `design/architect` has returned an approved architecture | Return to `design/commander` naming the missing upstream artifact; sequencing invented against an unfixed component boundary is a guess, not a plan. |
| The architecture is approved for only part of the requested scope | Plan the approved part and stop at its edge. Name the unapproved remainder as an explicit non-goal of this revision, record the boundary that has not been fixed and who owns it, and open a decision gate rather than extending the sequence past the approval. A plan that silently spans both halves makes the unapproved half look gated. |
| The architecture is present but malformed — a component with no owner, an interface with no error taxonomy, a non-functional target with no number | Quote the defective row, treat it as a blocker for the milestones that depend on it, and return it to `design/architect`. Sequencing around a hole reproduces it at the build boundary. |
| `design/gatekeeper-design` returns a `REVISE` naming `plan` or `acceptance` | Take the whole owner group in `revise_packet.by_owner` as one batch, fix every finding in a single revision, and return the changed artifact with its new sha256 so the gate re-judges only `changed_evidence`. Fixing the first finding alone burns a cycle against `revise_policy.cycle_cap`. |
| A tool or host capability the plan depends on is unavailable — no host planning prompt for the decision interview, no access to the issue tracker or the consumer inventory a deprecation needs | Ask the same decision as a concise plain-text question when the planning primitive is missing, and for missing data record the affected rows as unverified with the source named. A consumer list nobody could enumerate makes a deprecation advisory, never compulsory. |
| The milestone plan depends on a vendor approval, migration, or environment setup that lands after the proposed release date | Mark the rollout sequence as non-credible, surface the dependency explicitly, and require re-sequencing before downstream phases rely on the plan. |
| The plan hides major decisions behind generic buckets like "phase two" or "future optimization" without saying what must be chosen first | Replace the vague placeholder with an explicit decision gate so later phases do not mistake ambiguity for approval. |
| The plan assumes a design or configuration choice without a Decision Register entry | Reopen planning mode, prompt the user or record the codebase-derived answer, and do not advance until the decision source is explicit. |
| The rollout path assumes team capacity, support coverage, or operational readiness that the current constraints do not support | Narrow the plan to a defendable release slice and call out the missing capability instead of endorsing an impossible schedule. |
| The delivery sequence contradicts a locked product or architecture decision from an earlier phase | Freeze the contradiction, preserve the upstream decision record, and hand the conflict back to the design owner before the plan advances. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write the plan to the `Expected artifact` destination the block names, under the run's `design/reports/`. Resolve it with `python skills/scripts/output_paths.py --run-id {run-id} --phase design --kind reports --name delivery-plan.md`; `--kind` and `--run-id` are both required, and the resolver exits non-zero on a missing run id or a name that is absolute or traverses. That exit is the containment check — never compose a path by hand, and never write to a supplied path the resolver did not return.
2. Return the path with its sha256 so `design/commander` can register it; `plan` is artifact-backed, so an unhashed summary in the manifest fails the gate mechanically.
3. Write nothing else. Phase state lives in the run record and is published only through `save_run.py checkpoint`; `_phase-state.md` is declared by no save-ownership class, so it is not this skill's file nor the orchestrator's.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.

## References

- `../../grill-me-doctrine.md` for the binding intake interview protocol run before producing the plan.
- `references/workflow.md` for the planning sequence, the delivery-plan document template, the acceptance and Decision Register tables, the migration/deprecation template, and the acceptance checklist.
- `references/examples.md` for three complete outputs: a milestone path with acceptance rows, a Decision Register, and a migration/deprecation plan.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together — the three files this skill owns. Keep generated plans under the run's `skillset-saves/runs/{run-id}/design/reports/` directory, never inside the skill directory.
