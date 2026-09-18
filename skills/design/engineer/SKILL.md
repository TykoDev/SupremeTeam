---
name: engineer
description: >-
  Turns an approved design package into the implementation spec: ordered delivery
  slices with migrations, contract tests, and rollback. Use when asked to prepare
  the implementation spec, translate design into delivery slices, write the
  engineering plan, or sequence implementation details — even when the ask is just
  "cut this into slices". Milestone order is `design/planner`'s; this skill writes
  the per-slice spec inside it. Returns to `design/commander`; defers architecture to
  `design/architect`, milestones to `design/planner`, code to
  `build/bob-the-builder`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

# Engineer

## Purpose

Hold the seam where an unresolved design question stops being a discussion and
becomes an implementation guess. `../../pipelines.yaml` puts `implementation-spec`
after `plan` and before `stack-lock` and `phase-gate`, so the spec is written
against boundaries `design/architect` already fixed and a sequence `design/planner`
already committed to, and it goes back to `design/commander` for those two
remaining stages rather than to the build phase directly. `../../ownership.yaml`
makes `implementation-spec` the single artifact engineer writes and judges it on
two evidence lines: delivery slices in dependency order, and operational
constraints.

## Use This Skill When

Use this skill to **make the approved design buildable** — slice it into ordered, constraint-aware work:

- "prepare the implementation spec" / "write the engineering plan" — specify what to build and in what order
- "translate design into delivery slices" — break the approved architecture into independently shippable slices
- "sequence the implementation details" — resolve dependency order and operational constraints

Route elsewhere when the need is system architecture and interface contracts (`design/architect`), the high-level delivery plan and milestones (`design/planner`), or actually writing the code (`build/bob-the-builder`).

## Entry Routing

Engineer is an internal design specialist, not an entry point.
`../../routing-doctrine.md` places every `design/` skill it does not name
separately in the internal-specialist row, reached only through the owning
sub-orchestrator. Run the active-handoff check before writing a spec, because the
approved design package, the locked stack, the revision the spec is written
against, and the save path all arrive with the handoff, and none of them can be
reconstructed cold.

A handoff is present when the delegation prompt carries a `### Save Context`
block, an active run lock with `session_pin: true` exists under
`skillset-saves/`, or the invocation explicitly names `design/commander` as the
delegating owner for the design boundary.

- **Handoff present** → proceed; this is a delegated implementation-spec assignment.
- **Reached cold** → write no spec. Return to `design/commander`, which owns
  stage sequencing and package assembly, then accept the delegation back.
  Slicing against an unapproved architecture manufactures a sequence no gate can
  validate and no owner approved.

## Inputs

- The approved `architecture` and `interface-contract` from `design/architect`: component boundaries, data flow, invariants, failure behavior, trust boundaries, and the endpoint contracts a slice has to satisfy.
- The approved `plan` from `design/planner`: milestones, delivery slices, rollout and rollback shape, risk handling, and the per-slice acceptance conditions the spec turns into checks.
- The locked stack, runtime targets, migration constraints, and operational commitments carried in by `design/commander`.
- Test strategy expectations from the design package: reproduction tests for bug fixes, contract tests for endpoints, runtime verification for UI or operational flows.
- Questions that still affect module boundaries, migrations, rollout safety, or operational readiness.

## Outputs

- `implementation-spec`, returned to `design/commander`: every delivery slice as the record below, in dependency order, carrying the operational constraints that govern safe delivery and the technical decisions that still block execution.
- The dependency graph over those slices, with migration order, contract-test mapping, and rollback notes attached to the slices they belong to.
- Non-goals and unresolved build risks, named against the slice that carries them, so `design/commander` can package them and the build phase inherits no silent scope.

### Delivery-slice record

Every slice fills these eight fields. The document template that holds them, a
worked example, and the endpoint fields a slice must carry are in
`references/workflow.md`.

| Field | Content |
| --- | --- |
| `id` | `slice.<area>.<short-name>`, lowercase and unique within the spec |
| Modules owned | The exact paths or module names this slice may change; no sibling slice claims them |
| Depends on | Slice ids that must land first, each with its reason: schema, contract, data, or flag |
| Data / migration changes | Schema changes and backfills, ordered against the code that reads them |
| Contract tests | The endpoint or interface contracts this slice proves, and the cases that prove them |
| Proof plan | The failing test or reproduction first, the smallest green target, the refactor boundary |
| Rollback | How the slice is withdrawn once shipped: flag, revert, or compensating migration |
| Acceptance evidence | The command or observation that proves the slice done, and who accepts it |

### Artifact owned

`../../ownership.yaml` assigns engineer one artifact, `implementation-spec`, and
`../../gates.yaml` assigns it no evidence key: the spec reaches `design-to-build`
inside `design/commander`'s design package, never as a key of its own. A slice
list that loses its dependency order, or a spec that states no operational
constraint, drops one of the artifact's two required evidence lines and comes back
as a `REVISE`.

## Workflow

1. Confirm the package is sliceable before slicing it: architecture, interface contracts, and plan approved for the whole requested scope, and a stack lock naming the runtime the slices target. Run the `../../grill-me-doctrine.md` intake interview over the implementation branches only — slice boundaries, migration and cutover strategy, rollout mechanism, and the form acceptance evidence takes — one decision at a time, always recommending an answer, and reading the design package instead of asking whenever it already answers.
2. Break the approved design into delivery slices, each filling the eight fields above, mapped to modules, API endpoint contracts, data changes, jobs, integrations, and validation needs.
3. For every behavior-changing slice, define the proof-first test path: reproduction or failing test first, minimal implementation, then refactor with tests still passing. A docs-only or static-content slice records why TDD does not apply rather than leaving the field blank.
4. Order the slices by dependency, migration risk, rollout safety, and testability so build work proceeds incrementally without hidden prerequisites, and name the one command that becomes meaningful after each slice.
5. Attach the operational constraints that govern safe delivery — feature flags, cutovers, backfills, observability, support tasks, rollback steps, removal criteria — to the slices they constrain instead of collecting them in a trailing list nobody sequences.
6. Return the spec to `design/commander` with slice order, module ownership, contract-test mapping, migration and rollback notes, non-goals, and the blocking decisions that remain. `design/commander` runs the `stack-lock` stage and submits the package to `design/gatekeeper-design` at `design-to-build`.

## Required Contracts

- **Grill-Me Intake**: `../../grill-me-doctrine.md` names engineer a bound skill. Before the spec is written, resolve every load-bearing implementation branch one question at a time, use the planning-mode decision prompt contract for unresolved choices, always recommend an answer, and explore the design package, codebase, and prior artifacts instead of asking when the answer is discoverable. Scope the interview to decisions that change the spec, a migration path, a rollback commitment, or user-visible behavior; design intent is settled upstream and is not reopened here.
- **Proof-first delivery**: Each behavior-changing slice names the test that fails before the change and passes after it, because a proof written after the code proves the code rather than the behavior. Do not schedule repeated unchanged test runs as reassurance.
- **Design contract fidelity**: Implementation detail stays inside the approved architecture, interface contracts, and stack lock. A slice that needs a different contract is an escalation to the owning skill, not a local decision, because a silently reopened contract reaches build as an unapproved redesign.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../../execution-contract.md` defines, so upstream and downstream packages read risk identically.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- `design/commander` (delegates the stage, receives the spec, runs `stack-lock`, submits the package)
- `design/gatekeeper-design` (judges the package at `design-to-build` and returns any `REVISE`)
- `design/architect` (receives the endpoint or boundary changes a slice would otherwise make silently)
- `design/planner` (receives conflicts between the plan's sequence and the real dependency chain)

## Review Expectations

- Map every slice back to an architecture decision and a planner milestone so build work has traceable scope.
- Spell out dependency order, migration and rollback constraints, and contract-test obligations before handoff.
- Require tests to prove behavior, not implementation details, and state which command becomes meaningful after each slice.
- Escalate any design ambiguity that would otherwise force the builder to choose architecture during implementation.

## Skip Rule

Skip only when the requested scope proves an implementation spec is genuinely out of scope, such as a documentation-only or configuration-only change that adds no module, migration, endpoint, or job work. Record the skip with its justification and hand it to `design/commander`; an unrecorded skip reads at the gate as a missing artifact.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The delegation arrives with no approved design package — no architecture, no interface contracts, or no plan for the requested scope | Write no slices. Name the missing artifact and its owner, return to `design/commander`, and let the pipeline replay from the earliest invalid stage; slicing an unapproved design manufactures a sequence no gate can validate. |
| An upstream artifact is present but malformed — an architecture with no component boundaries, an endpoint named with no contract, a plan whose slices carry no acceptance condition | Quote the missing field, treat it as the blocker for the slices that depend on it, and return the gap to its owner. Do not infer the missing contract and do not spec around it. |
| `design/gatekeeper-design` returns a `REVISE` naming the implementation spec | Treat the whole owner group in `revise_packet.by_owner` as one batch, fix every finding in a single revision, and return the changed artifact with its new sha256 so the gate re-judges only `changed_evidence`. Returning the first fix alone burns a cycle against `revise_policy.cycle_cap`. |
| A tool or host capability the proof plan depends on is unavailable — no test runner, no migration harness, no environment for a cutover rehearsal | Record the verification as unavailable with its reason, name the command that would prove the slice, and mark that slice's acceptance evidence pending. Never report a check that did not run. |
| The slice order requires downstream modules, infrastructure, or schema changes before their prerequisites exist | Reorder the plan around the actual dependency chain and do not hand build work a sequence that only works by guesswork. |
| The implementation spec ignores migrations, backfills, feature-flag rollout, or observability even though the design clearly needs them | Treat the spec as operationally incomplete and add the missing delivery constraints before it advances. |
| A required non-functional target depends on implementation choices that the current slice plan does not actually support | Preserve the risk against the affected slice and require either a different approach or a narrower target promise. |
| A delivery slice changes endpoint behavior without a matching API contract update | Treat it as architecture drift and route the change back to `design/architect` before build begins. |
| The engineering plan quietly reopens an approved design contract or locked stack choice under the label of implementation detail | Escalate the contract change instead of letting build work inherit a silent redesign. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write the spec to the `Expected artifact` destination the block names, under the run's `design/reports/`. Resolve it with `python skills/scripts/output_paths.py --run-id {run-id} --phase design --kind reports --name implementation-spec.md`; `--kind` and `--run-id` are both required, and the resolver exits non-zero on a missing run id or on a name that is absolute or traverses. That exit is the containment check — never compose a path by hand, and never write to a supplied path the resolver did not return.
2. Return the path with its sha256 so `design/commander` can register it as a hashed artifact in the design package.
3. Write nothing else. Phase state lives in the run record and is published only through `save_run.py checkpoint`; `_phase-state.md` is declared by no save-ownership class, so it is not this skill's file nor the orchestrator's.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.

## References

- `../../grill-me-doctrine.md` for the binding intake interview protocol run before the spec is written.
- `references/workflow.md` for the implementation-spec document template, the filled delivery-slice record, the endpoint fields every slice carries, the dependency and ordering rules, and the acceptance checklist.
- `references/examples.md` for three complete outputs: a filled slice, a reordered dependency chain, and the response to a delegation with no approved design package.
- `../architect/references/api-endpoint-design.md` for the authoritative endpoint contract template. It resolves only inside the full catalog; `references/workflow.md` restates the subset a delivery slice must carry so the packaged skill never depends on it.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together — the three files this skill owns. Keep generated specs under the run's `skillset-saves/runs/{run-id}/design/reports/` directory, never inside the skill directory.
