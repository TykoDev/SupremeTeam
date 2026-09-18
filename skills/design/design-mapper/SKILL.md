---
name: design-mapper
description: >-
  Records an existing UI as a stable-id design inventory with baseline captures,
  then verifies the redesign mocks and the selected variant against it. Use when
  `design/redesign` delegates the inventory, the mock-parity stage, or the full
  parity stage, or the user asks to map the current UI, document what the
  interface does today, inventory the screens and components, or check that a mock
  or a prototype reproduces the existing app — even when the ask is just "what
  does this app do now?". Defers directions to `design/architect` and mocks and
  prototypes to `design/prototyper`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

# Design Mapper

## Purpose

Record the current design of an existing surface as evidence, not impression: a
stable-id inventory of every route, state, component, interaction, and flow, the
tokens actually in use, the accessibility baseline, and captures of the surface
as it renders today. The inventory is the parity contract every redesign draft
must satisfy, and the mapper is the owner who verifies that parity — twice, at
two different levels: across the four static mocks before the user chooses, and
against the living prototype built for the one direction they chose.

## Entry Routing

Design-mapper is an internal redesign specialist, not an entry point.
`../../routing-doctrine.md` places every `design/` skill it does not name
separately in the internal-specialist row, reached only through the owning
sub-orchestrator. `design/redesign` owns all three stages this skill runs —
`design-inventory`, `mock-parity`, and `parity-verification` — and the last two
are meaningless without the first, because parity is scored against the inventory
the same run produced.

A handoff is present when the delegation prompt carries a `### Save Context`
block, an active run lock with `session_pin: true` exists under
`skillset-saves/`, or the invocation explicitly names `design/redesign` as the
delegating owner.

Reached cold — "inventory this design" with no handoff — inventory nothing.
A parity score computed against an inventory from outside the run compares two
unrelated things and reports a number for it. Route the user to `admiral`, which
runs intake and persistence before any specialist is delegated.

## Use This Skill When

Use this skill to **record what the interface does today** before anyone changes it:

- "map the current UI" / "inventory the screens and components" — produce the stable-id inventory
- "document what the interface does today" — write the inventory report with captures
- "check that these mocks cover the existing app" — run the mock-level parity check across the four mocks
- "check that this prototype reproduces the existing app" — run the full-level parity check against the inventory

Route elsewhere to propose directions (`design/architect`) or draw a mock and build the selected variant (`design/prototyper`).

## Inputs

- The surface in scope from `design/redesign`: routes, screens, or the whole application, plus the flows that define functional parity.
- Application source (router configuration, page and component modules, stylesheets, token files, `components.json`), a running instance reachable through `browse`, or supplied captures.
- For mock parity: the hashed inventory and each mock's `mock.html` and `components.html`.
- For full parity verification: the hashed inventory, the `selection` record naming the chosen id, and that variant's `app.html` and `components.html`.

## Outputs

- `design-inventory` at `redesign/artifacts/inventory/design-inventory.json` (schema in `references/workflow.md`) and `design-inventory.md` (the human report: what exists, what is inconsistent, what the baseline captures show).
- Baseline captures under `redesign/evidence/baseline/` at the six responsive tiers in both themes per route, or an INFERRED record with a stated limitation when no browser is available.
- `mock-parity-evidence`: one `check_parity.py --level mock` record per mock at `redesign/evidence/mock-parity-<id>.json`, plus one aggregated typed probe record whose `artifacts` list names the four per-mock records. This aggregated record is what `design/redesign` packages as `mock_parity`.
- `parity-evidence` for the selected variant at `redesign/evidence/parity-<variant>.json`, a typed probe record written by `python skills/scripts/check_parity.py --level full` and bound by sha256 to the inventory and the prototype files.

### Gate evidence owned

`../../gates.yaml` `evidence_owners` assigns three keys to design-mapper; `design/redesign` packages them under the manifest's top-level `evidence` object at `redesign-review`.

| Key | Must contain, in one line | Fallback |
| --- | --- | --- |
| `design_inventory` | The stable-id inventory plus the six-tier, two-theme baseline (or an INFERRED record naming its limitation) | None sanctioned |
| `mock_parity` | The aggregated `--level mock` probe record naming the four per-mock records, at full route and component coverage | None sanctioned |
| `parity_evidence` | The `--level full` probe record for the selected variant, bound by sha256 to the inventory and the prototype | Two sanctioned strings, and `design/redesign` writes them — never this skill |

`references/workflow.md` §9 carries the full cell-by-cell requirement for all
three, including exactly what a short-coverage report must name and the typed
applicability-record shape a fallback takes at schema 2. Read it before packaging
or judging any of the three; do not work from the summary above.

## Workflow

1. Establish scope from the request and the codebase: read the router, navigation, page modules, and templates; enumerate routes before reading any screen. Ask only for what the code cannot answer (which flows define parity, which routes are out of scope).
2. Inventory routes and screens: stable id, path, purpose, entry points, primary action, the states the code can render (loading, empty, error, success, permission-denied, disabled, optimistic where present), and data dependencies.
3. Inventory components: stable id, name, the shadcn primitive it corresponds to when one exists, variants, sizes, states, source path, usage count; record duplicates and one-off equivalents as inconsistencies.
4. Extract tokens as used: colors, typography, spacing, radius, shadows, motion; map them to shadcn token names where they fit and list off-scale or hard-coded values.
5. Record interactions and flows: keyboard paths, focus management, confirmations, undo and retry, and the ordered steps (route, state, interaction) of each parity-defining flow.
6. Record the accessibility baseline with the shared severities: contrast failures, missing focus indicators, missing accessible names, reduced-motion gaps.
7. Capture the baseline through `browse` when a running surface is available: every route at 320, 375, 640, 1024, 1440, and 1920 px in light and dark themes, saved under `redesign/evidence/baseline/`. Without a browser, write an INFERRED baseline record with the limitation stated.

   Every route × six tiers × two themes is twelve captures per route, so past roughly 25 routes (300 captures) the exhaustive sweep stops being affordable. Above that ceiling, sample instead of skipping, and record the sampling rule in the baseline record so the parity check is judged against what was actually captured:

   - **Every route keeps two captures** — the narrowest tier (320) and the widest (1920), in the default theme. Route coverage never drops below 1.0; it is the *tier* grid that thins.
   - **The full twelve go to a named subset**: every route the delegation lists as parity-defining, every route with a layout breakpoint of its own, and one representative per repeated template (a list, a detail, a form, an empty state).
   - **Both themes stay mandatory** wherever a route resolves a theme-dependent token, since a theme bug is invisible in a single-theme capture.
   - Name the ceiling used, the sampled route ids, and the rule that selected them in the baseline record. A sampled baseline is a stated scope, not a short one; an unrecorded sample is a coverage gap wearing a full baseline's label.
8. Write `design-inventory.json` and `design-inventory.md`, return their paths and sha256 digests, and stop; the mapper never proposes a new design.
9. When delegated **mock parity**, run `python skills/scripts/check_parity.py --level mock --inventory <inventory.json> --app <mock.html> --components <components.html> --out redesign/evidence/mock-parity-<id>.json --project-root .` once per mock. Mock level scores routes and components only; interactions, flows, and states come back as informational counts and never fail the level. Then write one aggregated probe record — the same shape as a full-level record — whose `artifacts` list names the four per-mock records, and return it with each mock's coverage and its exact missing ids.
10. When delegated **full parity verification**, confirm the `selection` record names `decision: variant` and take its `chosen` id, then run `python skills/scripts/check_parity.py --level full --inventory <inventory.json> --app <app.html> --components <components.html> --out redesign/evidence/parity-<variant>.json --project-root .` for that one variant, return the record path, coverage, and the exact missing ids, and never edit the prototype. This stage runs only when a variant was selected; with no selection, or with a decision of `merge` or `deferred`, there is no prototype to check and the key is `design/redesign`'s sanctioned string, not a record this skill writes.

## Required Contracts

- **Evidence over impression**: Every inventory row names its source path or capture; a row without a source is marked `inferred` and listed in the report's limitations.
- **Stable ids**: Ids are lowercase, dot-separated, unique within the inventory, and never renamed across revisions; a renamed id is a new id with the old one retired in the report.
- **Read-only**: The mapper writes only its inventory, report, captures, and parity records; it never changes application source, a mock, or a prototype.
- **Level discipline**: The level follows the stage, never the artifact's apparent completeness. A mock is scored at `--level mock` even when its builder drew extra states; the selected variant is scored at `--level full` even when the run is short of time. Scoring a mock at full level manufactures a failure, and scoring a prototype at mock level manufactures a pass.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../../execution-contract.md` defines, so upstream and downstream packages read risk identically.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- `design/redesign`
- `browse` (baseline captures)
- `design/prototyper` (receives missing ids from mock parity and from full parity verification)

## Review Expectations

- Every route, state, component, interaction, and flow in scope appears once with a stable id and a source.
- The token extraction distinguishes declared tokens from hard-coded values and lists inconsistencies with locations.
- The accessibility baseline is graded and located, not summarized.
- Parity records are the checker's output, bound by sha256 to the exact inventory and the exact mock or prototype files, and run at the level the stage declares.

## Skip Rule

Never skip the inventory in a redesign run. Baseline captures may be replaced by an INFERRED record only when no running surface and no captures exist, and the limitation is stated.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The surface has no router — a single-page tool, an embedded widget, or a component library with no routes | Record one implicit route (`route.root`) with its states, components, interactions, and flows, and note the absent router under `limitations`. An empty `routes` list is not a valid inventory: `check_parity.py` scores an empty expectation set as coverage 1.0, so it would pass a variant that renders nothing. |
| The delegation names a surface that does not exist, or the inventory arrives malformed — wrong `schema_version`, a non-list parity list, a duplicate or non-conforming id | Stop before any parity run. `check_parity.py` exits 2 with an `engine_error` on stderr for exactly these; quote the error, return it to `design/redesign` with the offending id or field, and never hand-write a record the script did not produce. |
| `check_parity.py` exits 2 on a path — an inventory, `app.html`, or `components.html` that cannot be read | Treat the exit as the answer, not an obstacle: correct the path and re-run. Exit 0 is a pass, 1 is missing ids, 2 is an input or engine error, and only 0 or 1 produces a record. Report coverage only from a record the script wrote. |
| Python or `check_parity.py` is unavailable in the host | Report the parity stage as unverifiable, name the command that would have run, and return to `design/redesign`; a read-through of the markup is not a probe record and must never be labelled one. |
| `design/gatekeeper-design` returns a `REVISE` naming `design_inventory`, `mock_parity`, or `parity_evidence` | Take the whole owner group in `revise_packet.by_owner` as one batch, fix every finding in a single revision, and return the changed files with new sha256 digests so the gate re-judges only `changed_evidence`. |
| A full-parity run is delegated with no `selection` record, or the selection names a different id than the files supplied | Run nothing and return to `design/redesign`. Scoring an unchosen direction at full level measures an implementation the user did not ask for and binds the record to files the package will not carry. |
| A mock scored at `--level mock` reports missing states, interactions, or flows | Report them as informational counts and pass the mock. Those three lists are not scored at mock level; returning a mock for them asks its builder to implement before the selection, which is the sequencing this pipeline exists to prevent. |
| The router or page structure cannot be read (compiled bundle only, no source) | Map from the running surface through `browse`, mark structural rows `inferred`, and state the limitation in the report. |
| Two components render the same primitive with different names | Record both ids, flag the duplicate as an inconsistency, and let `architect` decide the merge; never silently unify them. |
| A state exists in code but cannot be reached in the running surface | Record it with `reachable: false` and its source; the prototype must still render it. |
| The parity checker reports missing ids | Return the exact ids to `design/redesign` for the builder; do not lower the coverage threshold. |
| The inventory changes after variants were built | Publish a new inventory revision and report which variants must be re-verified; stale parity records fail the gate as input hash drift. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write the inventory files to `redesign/artifacts/inventory/`, captures to `redesign/evidence/baseline/`, and parity records to `redesign/evidence/` — `mock-parity-<id>.json` per mock plus the aggregated record, and `parity-<variant>.json` for the selected variant — at the destinations the delegation names. Resolve each one with `python skills/scripts/output_paths.py --run-id {run-id} --phase redesign --kind <artifacts|evidence> --name <file>`; both `--run-id` and `--kind` are required and the command exits non-zero without them.
2. Return each path with its sha256 so the phase lead can register it.
3. Write nothing else; phase state belongs to the run record.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.

## References

- `references/workflow.md` for the mapping sequence, the inventory JSON schema, the parity-marker contract at both levels, the two checker commands, and the acceptance checklist.
- `references/examples.md` for concrete inventory and parity outputs.
- `../../design-doctrine.md` §4 for the six responsive tiers the baseline covers and §9 for the mock definition and the parity definition at each level.
- `../../scripts/check_parity.py` for the mechanical parity check, its `--level` contract, and its record shape.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep inventories, captures, and parity records under the run's `redesign/` directory, never inside the skill directory.
