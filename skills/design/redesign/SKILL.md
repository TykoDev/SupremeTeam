---
name: redesign
description: >-
  Admiral-pipeline redesign sub-orchestrator, normally invoked by `admiral`; if
  reached directly for lifecycle work without an active Admiral handoff, hand off
  to `admiral` first (see routing-doctrine.md). Runs the redesign pipeline for an
  existing user-facing surface: records and maps the current design, runs a
  project taste grilling, commissions four distinct design systems, each with a
  living single-page HTML prototype at functional parity and a UI component
  library, verifies parity, rendering, and accessibility, and hands the chosen
  variant to the design pipeline. Use when `admiral` delegates the redesign
  boundary, or the user asks to redesign the UI, refresh the look and feel,
  explore design directions, or compare alternative design systems for an app
  that already exists.
version: 1.0.0
---

# Redesign

## Purpose

Run the redesign pipeline from an existing user-facing surface to a gate-approved
redesign package: a recorded map of the current design, a grilled and confirmed
project Taste profile, four genuinely different design systems with living
prototypes and component libraries at functional parity, comparable evidence for
each, and a recorded choice the design pipeline can build from.

## Entry Routing

This skill is a component of the **Admiral** delivery pipeline; `admiral` is the primary entry orchestrator (see `../../routing-doctrine.md`). Before doing any work, run the **active-handoff check** — a handoff is present when the prompt carries a `### Save Context` block, an active run lock / `session_pin: true` exists under `skillset-saves/`, or the invocation explicitly names this skill as the owning sub-orchestrator for the redesign boundary.

- **Handoff present** → proceed; the run is active inside an Admiral run.
- **No handoff (cold/direct invocation)** → do not run standalone. Start `admiral` first and let it run intake, persistence, and gatekeeping, then accept the delegation back. This is the loop guard: Admiral's own delegations always carry the handoff signal, so a delegated call proceeds immediately and never re-bootstraps Admiral.

## Use This Skill When

- redesign the UI or refresh the look and feel
- explore design directions for this app
- give me alternative design systems for the current interface
- compare four redesigns before we commit

## Inputs

- Admiral-normalized redesign request: the surface in scope (routes, screens, or the whole application), constraints, non-goals, brand inputs, and the flows that define functional parity.
- The current application source, a running instance, or captures of it, plus the locked stack (`stack_lock`) when one exists.
- The effective Taste snapshot from Admiral/Taste when a profile already exists; the grilled profile once the taste grilling has run.
- Active redesign save context, prior verdicts, and revision lineage when resuming.

## Outputs

- `redesign-package` at `redesign/reports/redesign-package.md`: the comparison matrix across the four variants (parity coverage, rendered evidence, accessibility findings, Taste conformance, differentiation), the recommendation with rationale, the user's decision or a recorded deferral with reopen trigger, and the handoff brief for `design/commander`.
- `redesign/manifest.json` (schema 2, `boundary: redesign-review`, `owner: redesign`) carrying every evidence key `../../gates.yaml` requires at `redesign-review`.
- Redesign escalation packet naming the blocked decision, conflicting evidence, owner, and recommended default.

## Workflow

1. **Scope and parity contract.** Run the `../../grill-me-doctrine.md` intake interview to confirm the surface, the flows that define functional parity, constraints, and non-goals; explore the codebase before asking anything discoverable. Checkpoint through `session-memory` before the first delegation.
2. **Map the current design.** Delegate `design/design-mapper` to produce `redesign/artifacts/inventory/design-inventory.json`, `design-inventory.md`, and the baseline captures under `redesign/evidence/baseline/`. The inventory is the parity contract every variant must satisfy; nothing downstream starts until it exists and is hashed.
3. **Project taste grilling.** Delegate `taste` (through Admiral, because it mutates the preference store) to run the taste grilling in `../../grill-me-doctrine.md` § Taste grilling against the inventory: one Taste category at a time, each question anchored to what the current design does, a recommended answer every time. Taste writes `taste-grilling-log`, runs its own pipeline (confirmation, project-scope persistence, `taste-review`), and returns the immutable effective-profile snapshot. Package it as `taste_snapshot`; when the user declines to persist preferences, carry the sanctioned applicability record and treat the grilling log's answers as current-run instructions.
4. **Four directions.** Delegate `design/architect` to write `redesign/reports/design-directions.md`: four directions that differ in at least three Taste categories, each tracing every effective preference or explicit instruction to a concrete token, layout, or component decision. A set whose directions are variations of one theme is returned to `architect`.
5. **Build the variants.** Delegate `design/prototyper` once per direction (fan out in parallel in agent mode) with the inventory, the direction, and the snapshot digest. Each returns `redesign/artifacts/variants/<id>/{variant.md,tokens.css,components.css,components.js,components.html,app.html}`: a framework-free, offline, shadcn-shaped component library and a living single-page prototype that reproduces every inventory route, state, component, interaction, and flow with `data-*` parity markers.
6. **Verify.** Delegate `design/design-mapper` to run `python skills/scripts/check_parity.py` per variant (typed probe records under `redesign/evidence/` bound to the inventory and prototype hashes), `review/design-qa` for rendered verification of every variant across the six responsive tiers and both themes, and `review/frontier` for accessibility and interaction findings per variant. A variant that fails parity goes back to `design/prototyper` with the exact missing ids; it never reaches the comparison.
7. **Compare and decide.** Assemble the comparison matrix and a recommendation, then put the choice to the user through the decision prompt contract: one variant, a merge brief naming which variant supplies which decision, or a deferral with owner and reopen trigger. Record the answer in the package.
8. **Gate.** Write `redesign/manifest.json` and submit it to `design/gatekeeper-design` (`scripts/check_redesign.py` then the boundary validator); Admiral routes the approved package through `gatekeeper-admiral`. The chosen variant then enters the design pipeline as the `design-system` input: `design/commander` and `design/architect` implement it in the project's real stack and lock it at `design-to-build`.

## Required Contracts

- **Grill-Me Intake**: Before delegating any stage, run the intake interview in `../../grill-me-doctrine.md` — one load-bearing question at a time, always with a recommendation, exploring the codebase instead of asking when the answer is discoverable. Record resolved, deferred, and rejected decisions.
- **Four distinct variants**: Exactly four, differentiated across at least three Taste categories from `../../taste-doctrine.md` §3. Differentiation is judged from `design-directions.md` before any prototype is built.
- **Functional parity**: Parity is mechanical (`check_parity.py` reports full coverage of every inventory id) and rendered (`design-qa` captures every declared state at the six tiers). Pixel similarity is never the criterion; a prototype missing an inventory id is not a variant.
- **Framework-free prototypes**: No build step, no network access, shadcn-shaped component names and token names, so the chosen variant maps one-to-one onto the production design system per `../../design-doctrine.md` §9.
- **Taste read boundary**: Consume the snapshot read-only. Feedback that surfaces during comparison becomes Taste candidate records routed through Admiral to `taste`; it never becomes a silent edit or an effective preference in this run.
- **Design doctrine**: Every direction and variant honours `../../design-doctrine.md` §0 to §6 and §9; a doctrine violation is a `REVISE` to the variant's builder.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Save-Protocol Adherence**: When a Save Context block is received from admiral, persist every phase artifact to the save path through the classes below and checkpoint through `session-memory` at every delegation and return. Saving is mandatory, not optional.

## Delegation Surface

- `design/design-mapper` (inventory, baseline, parity evidence)
- `taste` through Admiral (taste grilling, confirmation, persistence, effective profile)
- `design/architect` (four design directions)
- `design/prototyper` (one delegation per direction, fanned out)
- `review/design-qa` (rendered verification per variant)
- `review/frontier` (accessibility and interaction findings per variant)
- `design/gatekeeper-design` (phase gate at `redesign-review`)

## Boundary Rules

- Record each boundary before requesting a verdict.
- Reuse prior verdicts only when the package revision is unchanged.
- Push remediation back to the owning specialist instead of editing its artifact locally; batch every finding for one specialist into a single revision delegation and fan independent owners out in parallel.

## Skip Rule

Never skip the inventory or the parity check. The taste grilling may be skipped only when the user explicitly declines preference capture; record the decision, carry the applicability record, and treat the interview answers as current-run instructions.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The current surface cannot be rendered or read (no source access, no running instance, no captures) | Stop before mapping, name the missing access, and return to Admiral; an inventory built from memory is not evidence. |
| The four directions differ only in palette or one category | Return `REVISE` to `design/architect` naming the categories that must diverge; do not commission prototypes for near-duplicates. |
| A prototype misses inventory ids or renders a state only in prose | Return the exact missing ids to `design/prototyper`; parity below full coverage keeps the variant out of the comparison. |
| The user's choice conflicts with a mandatory accessibility, security, or gate requirement | Surface the conflict, keep the requirement, and record the user's decision as a scoped exception only with explicit intent. |
| Taste source revisions change after the directions were written | Invalidate `taste_snapshot`, request re-resolution, and replay only the directions and variants that used the changed entries. |
| The user cannot decide between variants | Record a deferral with owner and reopen trigger, gate the package with `recommendation` stating the deferral, and hand nothing to the design pipeline. |

## Save Protocol

When admiral delegates with `Persistence active: yes`, redesign is the phase lead
for `skillset-saves/runs/{run-id}/redesign/` and writes only the path classes
`../../save-ownership.yaml` grants a phase lead: `manifest.json`, `reports/`,
`artifacts/`, `evidence/`, and `packages/`. Resolve every destination with
`python skills/scripts/output_paths.py --run-id {run-id} --phase redesign --kind <reports|artifacts|evidence|manifest> --name <file>`;
never compose a path by hand, and never create nested per-specialist directories
or phase-state files, because no declared class covers them and phase state lives
in the run record. When persistence is inactive or read-only resume is in effect,
redesign keeps the same stage sequencing but returns artifacts inline and
propagates `Persistence active: no` to specialists.

| Trigger | What Redesign Writes |
|---------|----------------------|
| Phase start | Nothing on disk: the phase state is published through `session-memory` (`save_run.py checkpoint --expect-revision <n> --set active_owner=redesign --set phase_state=REDESIGN_ACTIVE`) before the first specialist delegation |
| Specialist delegation | The canonical `### Save Context` block (below) naming the specialist as `Owner`, the exact `reports/`, `artifacts/`, or `evidence/` destination as `Expected artifact`, and `redesign-review` as `Return boundary` |
| Specialist return | Verify the named artifact exists at its destination, then register its sha256 through a `session-memory` checkpoint (`--evidence <path>`) |
| Gate submission | `redesign/manifest.json` (schema 2: `boundary: redesign-review`, `owner: redesign`), carrying the hashed inventory, taste grilling log, snapshot, directions, the `variant_set` record for the four variants, parity probe records, rendered verification, and accessibility findings |
| Phase-gate verdict | Nothing: `design/gatekeeper-design` writes `redesign/verdict_redesign-review.json` through `check.py --verdict-out`; redesign records the semantic verdict in its next checkpoint |
| Package consolidation | `redesign/reports/redesign-package.md` plus the manifest revision admiral submits to `gatekeeper-admiral` |

Save Context block for specialist delegations (the canonical field set from
`../../contracts/handoff-templates.md`; neither file may drop a field the other
carries):

```markdown
### Save Context
- Run ID: {run-id}
- Phase: redesign
- Save path: skillset-saves/runs/{run-id}/redesign/
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
- Return boundary: redesign-review
```

When Save Context is absent or `Persistence active: no`, skip all save operations and return the deliverable inline.

## References

- `../../grill-me-doctrine.md` for the intake interview and the taste grilling protocol.
- `../../design-doctrine.md` §9 for variant differentiation, prototype requirements, and the parity definition.
- `../../gates.yaml` for the `redesign-review` evidence set, the `variant_set` record, and the keys that accept no fallback.
- `references/workflow.md` for the detailed stage order, fan-out, verification, and decision rules.
- `references/examples.md` for concrete redesign requests and package shapes.
- `intake-brief.yaml` for the trigger set, input and output contract, and packaging expectations.
- `stub-contract.md` for the stage order, package shape, and the handoff into the design pipeline.
- `agent/agent-manifest.yaml` for agent-mode delegation capabilities and fan-out.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/examples.md`, `intake-brief.yaml`, `stub-contract.md`, and `agent/agent-manifest.yaml` together. Keep generated inventories, prototypes, and reports under the run's `redesign/` directory, never inside the skill directory.
