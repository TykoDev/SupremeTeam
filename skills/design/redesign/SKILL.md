---
name: redesign
description: >-
  Admiral-pipeline redesign sub-orchestrator for a user-facing surface that
  already exists: maps the current design, grills project taste, commissions four
  distinct design systems as static mocks, puts the choice to the user, and builds
  the living prototype for the selected direction only, gated at `redesign-review`.
  Use to redesign the UI, refresh the look and feel, explore design directions,
  compare four redesigns, or ask for alternative design systems — even when Admiral
  is never named. Defers to `admiral` when reached cold; a first-time design belongs
  to `design/commander`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

# Redesign

## Purpose

Redesign commissions and compares; it builds nothing the project ships. Its
boundary is a *choice made on evidence* — four genuinely different design systems
measured against one parity contract, so the decision rests on what each
direction actually covers rather than on which picture looked better.

The principle that shapes every stage: **drafts are mocks, implementation follows
selection.** The four things the user compares are static — drawn screens, real
tokens, a real component catalog, no behaviour. Only after a direction has been
chosen does anything become a living prototype, and then only for that one
direction. Four living prototypes built before a choice is three implementations
made to be thrown away, and preventing exactly that is why this pipeline is
ordered the way it is.

Two other things are most often got wrong. Differentiation is judged after the
drafts exist, when it is expensive to fix; it is decided at the directions stage,
from prose, before anything is drawn. And parity is read as visual similarity; it
is mechanical — `check_parity.py` reporting full coverage of the ids its level
scores — so a prettier mock that drops a route is not a mock at all.

The chosen variant leaves here as an input to `design/commander`, which
implements it in the project's real stack; the prototype stays reference
behaviour.

## Entry Routing

This skill is a component of the **Admiral** delivery pipeline; `admiral` is the primary entry orchestrator (see `../../routing-doctrine.md`). Before doing any work, run the **active-handoff check** — a handoff is present when the prompt carries a `### Save Context` block, an active run lock / `session_pin: true` exists under `skillset-saves/`, or the invocation explicitly names this skill as the owning sub-orchestrator for the redesign boundary.

- **Handoff present** → proceed; the run is active inside an Admiral run.
- **No handoff (cold/direct invocation)** → do not run standalone. Start `admiral` first and let it run intake, persistence, and gatekeeping, then accept the delegation back. This is the loop guard: Admiral's own delegations always carry the handoff signal, so a delegated call proceeds immediately and never re-bootstraps Admiral.

## Use This Skill When

- redesign this existing surface
- explore design directions for this app
- give me alternative design systems for the current interface
- compare four redesigns before we commit
- commission four distinct design systems at functional parity

A surface that does not exist yet has no parity contract to measure against, so
a first-time design starts at `design/commander` instead. The chosen variant from
this pipeline enters there as the `design-system` input. The bare lifecycle
phrasings — `redesign the UI`, `refresh the look and feel` — are advertised by
the front door `admiral`, which runs intake and delegates here.

### Scoping a surface too large to inventory exhaustively

Parity is scored at coverage 1.0 against the inventory, so the inventory — not
the application — is what the run commits to. Above roughly 25 routes, an
exhaustive inventory and its twelve-capture-per-route baseline stop being
affordable, and the answer is to **narrow the declared surface, never to accept
partial coverage inside it**.

At intake, before delegating stage 2, fix one of these and record which:

- **Route-count ceiling.** Take the parity-defining flows named in the request and the routes they traverse, plus every route reachable in one step from them. Everything else is an explicit non-goal of this revision, listed by id in the inventory's scope note.
- **Template sampling.** Where a surface repeats a template across many records (a detail page per entity, a settings pane per section), scope one representative per template and name the rest as covered-by-template.
- **Phased redesign.** Split into two runs with their own inventories and gates, and say which routes belong to which. A second run's inventory is written against the surface as the first run left it.

Whichever is chosen, the inventory is the contract: coverage 1.0 against a
declared subset is a pass, and coverage 0.7 against the whole application is a
`REVISE`. Never let a large surface turn into a short parity report; turn it into
a smaller declared one. `design/design-mapper`'s Workflow step 7 carries the
matching sampling rule for baseline captures inside whatever scope this fixes.

## Inputs

- Admiral-normalized redesign request: the surface in scope (routes, screens, or the whole application), constraints, non-goals, brand inputs, and the flows that define functional parity.
- The current application source, a running instance, or captures of it, plus the locked stack (`stack_lock`) when one exists.
- The effective Taste snapshot from Admiral/Taste when a profile already exists; the grilled profile once the taste grilling has run.
- Active redesign save context, prior verdicts, and revision lineage when resuming.

## Outputs

- `redesign-package` at `redesign/reports/redesign-package.md`: the comparison matrix across the four mocks (mock parity, tiers and themes captured, Taste conformance, differentiators), the recommendation with rationale, the selected variant's parity, rendering, and accessibility results, and the handoff brief for `design/commander`.
- `redesign/reports/selection.md`: the user's decision recorded verbatim — one mock, a merge brief, or a deferral with owner and reopen trigger — backed by the typed `selection` record in the manifest.
- `redesign/manifest.json` (schema 2, `boundary: redesign-review`, `owner: redesign`) carrying every evidence key `../../gates.yaml` requires at `redesign-review`.
- Redesign escalation packet naming the blocked decision, conflicting evidence, owner, and recommended default.

### Gate evidence owned at `redesign-review`

Redesign is the only submitter at `redesign-review`, so it assembles all fourteen
required keys into `redesign/manifest.json` and authors three of them itself:
`selection`, `recommendation`, and `residual_risk`. The other eleven belong to
stage owners — `design_inventory`, `mock_parity`, and `parity_evidence` to
`design/design-mapper`, `taste_grilling` and `taste_snapshot` to `taste`,
`design_directions` to `design/architect`, `mock_set` and `selected_variant` to
`design/prototyper`, `mock_rendering` and `rendered_verification` to
`review/design-qa`, `accessibility_evidence` to `review/frontier` — and a gap
routes to that owner through the REVISE packet.

Four decisions live here; `references/gate-evidence.md` carries the full per-key
table with the must-contain, artifact-backing, and typed-record columns.

- **What redesign authors**: `selection` — the typed record and the hashed `reports/selection.md` behind it, carrying the decision, the chosen id or `null`, the recommended id, who decided and when, and the one-line basis; `recommendation` — the comparison matrix, the named direction with the reason it best satisfies the effective Taste profile inside the mandatory requirements; and `residual_risk`, which names each open item, who carries it, and the observation or decision that closes it. An empty `residual_risk` is a claim that nothing is open.
- **Which keys are hashed files**: eleven of the fourteen. Only `accessibility_evidence`, `recommendation`, and `residual_risk` are unbacked statements; everything else must reference a path in `artifact_hashes`.
- **Which keys depend on the decision**: `selected_variant`, `parity_evidence`, `rendered_verification`, and `accessibility_evidence`. When `selection.decision` is `variant` they carry real evidence and `selected_variant.variants[0].id` equals `selection.chosen`; when it is `merge` or `deferred` all four carry the matching sanctioned string, `selection deferred - no variant built` or `merge brief recorded - implemented as a fifth direction in the design pipeline`. Mixing the two — a fallback beside a built variant, or a built variant with no selection — fails mechanically.
- **Which key may be waived, and which may never be**: `taste_snapshot` alone is waivable, through `no saved Taste profile available`, and only when the user declines preference capture. `mock_rendering` is listed under `no_fallback` here, so it accepts neither a fallback string nor an applicability record — the four mocks are always built, so a browserless host returns an `inferred` render record instead.

## Execution Contract

Canonical source: `../../execution-contract.md`. Stated locally because that file
requires every orchestrator and gatekeeper to carry the clauses verbatim; a
paraphrase is drift.

1. Select the preamble tier before acting: Tier 0 for minor, understood, reversible tasks under
   the Tier 0 fast path in `skills/routing-doctrine.md`; Tier 1 for bounded read-only work beyond Tier 0;
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

1. **Scope and parity contract.** Run the `../../grill-me-doctrine.md` intake interview to confirm the surface, the flows that define functional parity, constraints, and non-goals; explore the codebase before asking anything discoverable. Checkpoint through `session-memory` before the first delegation.
2. **Map the current design.** Delegate the inventory stage to `design/design-mapper`; the inventory is owned by that specialist and never assembled here. The stage comes back as `redesign/artifacts/inventory/design-inventory.json`, `design-inventory.md`, and the baseline captures under `redesign/evidence/baseline/`. The inventory is the parity contract every draft must satisfy; nothing downstream starts until it exists and is hashed.
3. **Project taste grilling.** Delegate `taste` (through Admiral, because it mutates the preference store) to run the taste grilling in `../../grill-me-doctrine.md` § Taste grilling against the inventory: one Taste category at a time, each question anchored to what the current design does, a recommended answer every time. Taste writes `taste-grilling-log`, runs its own pipeline (confirmation, project-scope persistence, `taste-review`), and returns the immutable effective-profile snapshot. Package it as `taste_snapshot`; when the user declines to persist preferences, carry the sanctioned applicability record and treat the grilling log's answers as current-run instructions.
4. **Four directions.** Delegate `design/architect` to write `redesign/reports/design-directions.md`: four directions that differ in at least three Taste categories, each tracing every effective preference or explicit instruction to a concrete token, layout, or component decision. A set whose directions are variations of one theme is returned to `architect`.
5. **Draw the four mocks.** Delegate `design/prototyper` once per direction (fan out four ways in parallel in agent mode) with the inventory, the direction, and the snapshot digest. Each returns `redesign/artifacts/mocks/<id>/{variant.md,tokens.css,components.css,components.html,mock.html}`: a framework-free, offline, shadcn-shaped component catalog and a static `mock.html` that draws one screen per inventory route with `data-route` markers, carries every inventory component with `data-component` markers, and declares itself with `data-mock="true"`. No router, no state, no wired interactions or flows, no `components.js`. Nothing is implemented at this stage.
6. **Verify the mocks.** Delegate `design/design-mapper` to run `python skills/scripts/check_parity.py --level mock` per mock — routes and components only, with interactions, flows, and states reported informationally — and to return one record per mock plus one aggregated probe record as `mock_parity`. A mock short of full route or component coverage goes back to `design/prototyper` with the exact missing ids; it never reaches the comparison.
7. **Capture the mocks.** Delegate `review/design-qa` to render every mock screen at the six responsive tiers in both themes, returning the typed `render` record as `mock_rendering`. On a browserless host the record is `inferred` with the stated limitation; this key accepts no fallback string, because the mocks always exist.
8. **Compare and decide.** Assemble the comparison matrix across the four mocks and a recommendation, then put the choice to the user through the decision prompt contract: one mock, a merge brief naming which mock supplies which decision, or a deferral with owner and reopen trigger. Write the answer verbatim to `redesign/reports/selection.md` and record the typed `selection` record. This is the hinge of the pipeline: nothing is implemented before it.
9. **Build the selected variant.** This stage runs only when a variant was selected. Delegate `design/prototyper` once, for the id `selection.chosen` names, to build `redesign/artifacts/variants/<id>/{variant.md,tokens.css,components.css,components.js,components.html,app.html}` — the living single-page prototype, derived from that mock's tokens and catalog, reproducing every inventory route, state, component, interaction, and flow with `data-*` parity markers.
10. **Verify the selected variant.** These stages run only when a variant was selected: `design/design-mapper` runs `check_parity.py --level full` against `app.html` for `parity_evidence`, `review/design-qa` captures every route in every declared state at the six tiers in both themes for `rendered_verification`, and `review/frontier` grades accessibility and interaction findings for `accessibility_evidence`. When the decision was a merge or a deferral, no build was commissioned and these four keys carry the matching sanctioned string instead: `selection deferred - no variant built`, or `merge brief recorded - implemented as a fifth direction in the design pipeline`.
11. **Recommend and package.** Write `redesign/reports/redesign-package.md`: the comparison matrix across the four mocks, the recommendation and its rationale, the recorded decision, the selected variant's parity, rendering, and accessibility results when one was built, and `residual_risk`.
12. **Gate.** Write `redesign/manifest.json` and submit it to `design/gatekeeper-design` (`../gatekeeper-design/scripts/check_redesign.py` then the boundary validator); Admiral routes the approved package through `gatekeeper-admiral`. The chosen variant then enters the design pipeline as the `design-system` input: `design/commander` and `design/architect` implement it in the project's real stack and lock it at `design-to-build`.

`references/workflow.md` carries the full fourteen-stage table with each stage's
owner, artifact, condition, and fan-out.

## Required Contracts

Eight contracts bind the redesign phase. The decision each one forces is stated
here; `references/contracts.md` carries their full normative text, and neither
document paraphrases the other.

- **Grill-Me Intake**: confirm the surface, the flows that define parity, constraints, and non-goals before delegating any stage; explore the codebase before asking anything discoverable.
- **Four distinct mocks**: exactly four, differentiated across at least three Taste categories, judged from `design-directions.md` before any mock is commissioned — because a near-duplicate found after the drawing wastes four of them.
- **Mocks before implementation**: the four drafts are static. Nothing gains a router, a state machine, or a wired interaction until the selection record names a chosen id, and then only for that id.
- **Functional parity**: mechanical at two levels — `--level mock` scores routes and components across the four mocks, `--level full` scores every inventory id on the selected variant — and rendered (`design-qa` captures the mocks, and every declared state of the selected variant, at the six tiers). Pixel similarity is never the criterion.
- **Framework-free drafts**: no build step, no network access, shadcn-shaped component and token names, so the chosen direction maps one-to-one onto the production design system.
- **Taste read boundary**: consume the snapshot read-only. Feedback that surfaces during comparison becomes a Taste candidate routed through Admiral, never a silent edit or an effective preference in this run.
- **Design doctrine**: every direction, mock, and variant honours `../../design-doctrine.md` §0 to §6 and §9; a doctrine violation is a `REVISE` to the builder, not a note in the comparison.
- **Save-Protocol Adherence**: persist every stage artifact to the save path when admiral sends a Save Context block, and checkpoint through `session-memory` at every delegation and return.

## Delegation Surface

- `admiral` (intake grilling, and the route through which `taste` is delegated)
- `design/design-mapper` (inventory, baseline, mock parity, full parity evidence)
- `taste` through Admiral (taste grilling, confirmation, persistence, effective profile)
- `design/architect` (four design directions)
- `design/prototyper` (one delegation per direction at `mock-build`, fanned out four ways; one delegation at `selected-build` when a variant was selected)
- `review/design-qa` (mock rendering across the four mocks; rendered verification of the selected variant)
- `review/frontier` (accessibility and interaction findings on the selected variant)
- `design/gatekeeper-design` (phase gate at `redesign-review`)

The `selection` stage is redesign's own: no specialist owns the user's decision.

## Boundary Rules

- Record each boundary before requesting a verdict.
- Reuse prior verdicts only when the package revision is unchanged.
- Push remediation back to the owning specialist instead of editing its artifact locally; batch every finding for one specialist into a single revision delegation and fan independent owners out in parallel.
- Self-check before submitting: run `python skills/harness/gatekeeper/check.py --boundary redesign-review --package redesign/manifest.json` (no `--verdict-out`) and fix every mechanical failure first; a package that fails the machine is never submitted (`../../gates.yaml` `revise_policy.self_check`).
- Treat a `REVISE` as one packet: delegate each owner group in `revise_packet.by_owner` in parallel, batching every finding for a specialist into a single revision delegation, and resubmit once with `--prior` so the gate re-judges only `changed_evidence` and carries its prior judgment on `unchanged_evidence`.

## Skip Rule

Never skip the inventory, the mock parity check, or the selection stage. A
package that reports a built variant with no recorded decision behind it has
skipped the one stage this pipeline exists to protect. The taste grilling may be
skipped only when the user explicitly declines preference capture; record the
decision, carry the applicability record, and treat the interview answers as
current-run instructions.

## Failure Modes

These six change what Redesign does next. The differentiation, parity, conflict,
and decision failures whose handling is procedural rather than routing are in
`references/failure-modes.md`, which repeats none of these rows.

| Scenario | Response |
| --- | --- |
| The current surface cannot be rendered or read (no source access, no running instance, no captures) | Stop before mapping, name the missing access, and return to Admiral; an inventory built from memory is not evidence. |
| The host has no browser, so `review/design-qa` cannot capture the mocks | `mock_rendering` is `no_fallback` at this boundary, so the key is still required and the sanctioned no-visible-surface string is rejected. Carry the record `design-qa` returns with `result.status: inferred`, its limitation statement, and the label `INFERRED - no browser available` that `../../gates.yaml` `evidence_type_rules.render` requires. Mark rendering unobserved for every mock in the comparison matrix and carry the gap into `residual_risk` with the condition that closes it — a capture run at the same mock hashes on a host with a browser. |
| The redesign request arrives without a surface in scope, without the flows that define parity, or with an unreadable inventory from a prior run | Delegate nothing. The inventory is the parity contract, so a missing or unparsable scope makes every downstream stage unmeasurable. Name the missing element, resolve it through the grilling interview when the user can answer it and by exploring the codebase when it is discoverable, and rebuild the inventory rather than reusing one whose ids cannot be read. |
| A specialist offers to build the living prototypes for all four directions, or a returned mock has a router and wired interactions | Refuse the offer, and return the mock to `design/prototyper` to be reduced to a draft. Implementation follows selection; four living prototypes is the failure this pipeline is ordered to prevent, and it is not made acceptable by being cheap to delegate. |
| `redesign-review` returns `REVISE` twice, exhausting `../../gates.yaml` `revise_policy.cycle_cap` of 2 | Stop resubmitting and escalate to Admiral with both revise packets, both verdicts, and the unclosed keys named with their owners. Two failed cycles on the same keys mean the disagreement is about the requirement — the differentiation bar, the parity contract, the accessibility floor — and a third submission spends the gatekeeper's judgment on the same dispute. |
| A required capability is unavailable: no parallel fan-out for the four mocks, no command execution for `check_parity.py`, or no Python for the gate self-check | Fan out serially when parallelism is missing; the four mocks are independently derived, so order does not change them. A parity check that cannot execute is `result.status: unavailable`, which is a data gap and never full coverage, so the mock stays out of the comparison rather than entering it unverified. Without Python the self-check did not run, so the package is submitted as unverified rather than described as passing. |

## Save Protocol

See `references/workflow.md` — "Save Instructions Per Stage" — for the full
write-trigger table, the path classes a phase lead may create, and the
`### Save Context` block to include in every specialist delegation. Two rules
decide the rest: resolve every destination with
`python skills/scripts/output_paths.py --run-id {run-id} --phase redesign --kind <reports|artifacts|evidence|manifest> --name <file>`
rather than composing a path, because nested per-specialist directories and
phase-state files belong to no class `../../save-ownership.yaml` declares; and
when persistence is inactive or read-only resume is in effect, keep the same
stage sequencing but return artifacts inline and propagate
`Persistence active: no` to every specialist.

## References

- `../../grill-me-doctrine.md` for the intake interview and the taste grilling protocol.
- `../../design-doctrine.md` §9 for direction differentiation, the mock definition, the selection rule, and the living-prototype requirements.
- `../../gates.yaml` for the `redesign-review` evidence set, the `mock_set` and `selected_variant` records, the sanctioned fallback strings, and the key that accepts no fallback.
- `references/failure-modes.md` for the differentiation, parity, conflict, and decision failures the SKILL.md table does not carry.
- `references/contracts.md` for the full normative text of the eight contracts the Required Contracts section names.
- `references/gate-evidence.md` for the fourteen `redesign-review` keys with their owners, must-contain, artifact-backing, and typed records, the selection record shape, the two sanctioned fallback strings, what `recommendation` and `residual_risk` must say, and the browserless-render branch.
- `references/workflow.md` for the fourteen-stage order, fan-out, verification, decision, and save rules, including the `### Save Context` block template.
- `references/examples.md` for concrete redesign requests and package shapes.
- `intake-brief.yaml` for the trigger set, input and output contract, and packaging expectations.
- `stub-contract.md` for the stage order, package shape, and the handoff into the design pipeline.
- `agent/agent-manifest.yaml` for agent-mode delegation capabilities and fan-out.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/contracts.md`, `references/failure-modes.md`, `references/gate-evidence.md`, `references/examples.md`, `intake-brief.yaml`, `stub-contract.md`, and `agent/agent-manifest.yaml` together. Keep generated inventories, mocks, prototypes, and reports under the run's `redesign/` directory, never inside the skill directory.
