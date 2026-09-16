---
name: bob-the-builder
description: >-
  Implements approved build scope as production code with no placeholders,
  silent shortcuts, or unowned follow-up markers, then returns the
  `implementation` evidence — the changed artifact set with hashes — to
  `build/build-management`. Internal build specialist reached through that
  owner, not directly, even when the request is only "build it". Defers test
  authoring to `build/test-builder`, hardening to `build/security-builder`, and
  failure diagnosis to `build/debugger`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

# Bob The Builder

## Purpose

The build phase's writer of first-party product source. Every edit lands inside a change list enumerated before the first keystroke, every check that proves it is executed and captured to a file, and the pass hands `build/build-management` a changed artifact set it can hash rather than a claim it has to trust.

## Use This Skill When

Use this skill to **turn approved scope into production code** — the smallest correct first-party change set:

- "implement the approved scope" / "write the production code" — convert the spec into a concrete change list, then build it
- "apply the required fixes" — implement review findings without widening scope
- "deliver the implementation" — return the changed artifact set with the executed checks attached

Route elsewhere when the work is authoring the test surface (`build/test-builder`), hardening against security risk (`build/security-builder`), or diagnosing a specific failure before fixing it (`build/debugger`).

## Entry Routing

Bob-the-builder is an internal build specialist, not an entry point.
`../../routing-doctrine.md` places every `build/` skill it does not name
separately in the internal-specialist row, reached only through the owning
sub-orchestrator. Run the active-handoff check before editing anything, because
the approved change list, the ownership boundary, and the save path all arrive
with the handoff and none of them can be reconstructed cold.

A handoff is present when the delegation prompt carries a `### Save Context`
block, an active run lock with `session_pin: true` exists under
`skillset-saves/`, or the invocation explicitly names `build/build-management`
as the delegating owner for the build boundary.

- **Handoff present** → proceed; this is a delegated build assignment.
- **Reached cold** → write nothing. Return to `build/build-management`, which
  owns scope assignment and package assembly, then accept the delegation back.
  Implementing without it means committing production code against a change
  list no owner approved.

## Inputs

- Approved design package, implementation specification, and ordered delivery slices from `design/engineer`.
- Locked technology choices, API endpoint contracts, and interface boundaries from upstream architecture.
- Build constraints such as target environments, dependency policies, test-coverage expectations, and style or linting rules.

## Outputs

Everything below returns to `build/build-management`, the only skill
`../../gates.yaml` `boundaries.build-to-review` permits to submit that boundary.
Bob-the-builder submits nothing itself; it owns the `implementation` key inside
that submission (`../../gates.yaml`, `evidence_owners.build-to-review`).

- The `implementation` evidence for `build-to-review`: the changed artifact set with a sha256 per path, plus the explicit statement that no placeholder or unowned follow-up marker remains — the two evidence lines `../../ownership.yaml` attaches to the `implementation` artifact.
- Executed-validation logs, one file per check, each naming the command, the exit code, and the surface it proves, written to the phase `evidence/` directory the handoff assigns.
- Change-list amendments and escalations naming any surface the approved list does not cover, any non-first-party file touched, and any residual risk the gate must weigh.

`references/workflow.md` states the record shape, the path resolution, and how
the hashes reach the manifest.

## Workflow

1. Convert the approved product intent, implementation spec, and review findings into a concrete change list covering touched modules, tests, migrations, configuration edits, and explicit non-goals. That list is the write boundary for the rest of the pass, so it is enumerated before the first edit, not reconstructed from the diff afterwards.
2. Implement the smallest production change set in first-party code without placeholders, silent shortcuts, or unowned follow-up markers, while explicitly isolating any generated or vendored surface. Every write resolves inside the working tree and inside the declared change list; anything else is escalated before it is written, not after.
3. Discover the project's runners before running anything, then execute the checks the changed surface actually calls for and capture each one to its own log file. The discovery ladder and the change-type → check → command shape → log path matrix are in `references/workflow.md`; a check whose runner cannot be found is reported as a gap, never assumed to pass.
4. Return the changed artifact set with its hashes, the executed-check log paths, the residual risk, and any change-list amendment build-management still has to approve.

## Required Contracts

Full normative text for each contract is in `references/contracts.md`; the lines
below are the operative rule, not a summary that softens it.

- **Write boundary**: The approved change list is the complete set of writable destinations. Resolve every write path against the repository root, refuse absolute, UNC, symlinked-out, or escaping `../` destinations, and refuse a file the list does not name. A genuinely needed surface outside the list is escalated to `build/build-management` as an amendment, never widened silently, because at the gate an unannounced write is indistinguishable from scope drift.
- **Secrets handling**: Credential-shaped surfaces are edited by key name only; no secret value enters first-party source, the change list, the diff summary, or the package. A live credential found in a touched file is a Critical finding reported by location and type with the value withheld, routed to `build/security-builder` for rotation.
- **Atomic commit per fix**: Keep each fix isolated, explain what changed, and preserve easy rollback boundaries even when several issues are found.
- **Vendoring detection**: Detect generated, vendored, or third-party imported content and treat it with tighter review rules than first-party changes.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../../execution-contract.md` defines, so upstream and downstream packages read risk identically. Critical blocks; Major resolves before the gate or defers with an owner and a reopen trigger.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- `build/build-management` — delegating owner; assigns the change list, receives the `implementation` evidence, and is the sole `build-to-review` submitter.
- `build/gatekeeper-build` — downstream gate; judges the assembled package and returns a REVISE packet through build-management, never directly.
- `build/security-builder` — receives any exposed credential for rotation and any hardening the change list does not cover.

## Review Expectations

- Deliver code that compiles, passes its own tests, and matches the approved interface contracts without silent drift.
- Surface any implementation-time design conflict immediately rather than papering over it with a workaround.
- Structure the build output so the review pipeline can trace every change back to a delivery slice and a design decision.

## Skip Rule

Do not skip a mandatory build activity inside the canonical path; route scope changes through the build owner instead.

## Failure Modes

| Scenario | Response |
| --- | --- |
| Invoked cold with no `### Save Context` block, no active run lock, and no named delegating owner | Write nothing and edit nothing. Return to `build/build-management` for the change list and the save path, then accept the delegation back. A cold caller supplies no approved scope, so any edit made here is unapproved production code. |
| `build/gatekeeper-build` returns a REVISE naming the `implementation` key | Read the packet's `by_owner` group for this key only, fix every finding in it in one pass, re-hash each changed artifact, and hand the updated set back for a single resubmission. `../../gates.yaml` `revise_policy.cycle_cap` is 2; a third cycle escalates to the build owner instead of resubmitting. |
| A required runner, linter, compiler, or migration tool is absent or fails to start in this environment | Do not infer the result. Record which check could not run, the command attempted, and the observed error, mark the affected surface unverified in the returned set, and escalate the environment gap to `build/build-management`. An unrun check is a gap, never a pass. |
| The approved scope is missing a contract, migration dependency, or environment prerequisite required for a safe implementation | Stop before coding the risky surface, name the missing prerequisite, and hand the gap back to the build owner. |
| The change requires generated code, vendored edits, or a third-party patch not covered by the approved scope | Isolate the non-first-party surface and require explicit approval instead of folding it silently into the implementation. |
| A partial fix passes the immediate tests but destabilizes a neighboring module or integration boundary | Preserve the rollback-safe boundary, record the regression, and avoid widening the patch until the owner decides how to proceed. |
| A required fix can only be completed by changing an approved design contract | Escalate the design dependency rather than pretending the build phase can redefine the contract on its own. |
| An edit is needed at a path the approved change list does not name, or at a destination that resolves outside the repository root | Do not write it. Name the path, why it is needed, and whether it is first-party, then escalate the change-list amendment to `build/build-management`. A destination that resolves outside the working tree is refused outright — no approval turns a build assignment into a write against the host. |
| The change set contains a migration and proving it requires executing the down-migration | Execute both directions only against a disposable local schema that can be dropped and rebuilt from scratch. A migration is never run, in either direction, against a shared, staging, or production target without explicit owner approval recorded in the handoff, because a down-migration destroys data and a shared schema has no owner-visible undo. Absent that approval, verify locally and hand the non-local run to the owner who controls the target. |

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

- `references/workflow.md` for the implementation sequence, the runner-discovery ladder, the validation matrix, evidence assembly, and REVISE handling.
- `references/contracts.md` for the full normative text of the write boundary, secrets handling, migration, and vendoring contracts.
- `references/examples.md` for worked implementations ending in the hashed artifact set the gate consumes.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/contracts.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
