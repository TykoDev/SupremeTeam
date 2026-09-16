---
name: design-mapper
description: >-
  Records an existing UI as a stable-id design inventory with baseline captures,
  then verifies each redesign variant against it. Use when
  `design/redesign` delegates the inventory or parity stage, or the user asks to
  map the current UI, document what the interface does today, inventory the
  screens and components, or check that a prototype reproduces the existing app —
  even when the ask is just "what does this app do now?". Defers directions to
  `design/architect` and prototypes to `design/prototyper`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

# Design Mapper

## Purpose

Record the current design of an existing surface as evidence, not impression: a
stable-id inventory of every route, state, component, interaction, and flow, the
tokens actually in use, the accessibility baseline, and captures of the surface
as it renders today. The inventory is the parity contract every redesign variant
must satisfy, and the mapper is the owner who verifies that parity.

## Entry Routing

Design-mapper is an internal redesign specialist, not an entry point.
`../../routing-doctrine.md` places every `design/` skill it does not name
separately in the internal-specialist row, reached only through the owning
sub-orchestrator. `design/redesign` owns both stages this skill runs —
`design-inventory` and `parity-verification` — and the second is meaningless
without the first, because parity is scored against the inventory the same run
produced.

A handoff is present when the delegation prompt carries a `### Save Context`
block, an active run lock with `session_pin: true` exists under
`skillset-saves/`, or the invocation explicitly names `design/redesign` as the
delegating owner.

Reached cold — "inventory this design" with no handoff — inventory nothing.
A parity score computed against an inventory from outside the run compares two
unrelated things and reports a number for it. Route the user to `fabled`, which
runs intake and persistence before any specialist is delegated.

## Use This Skill When

Use this skill to **record what the interface does today** before anyone changes it:

- "map the current UI" / "inventory the screens and components" — produce the stable-id inventory
- "document what the interface does today" — write the inventory report with captures
- "check that this prototype reproduces the existing app" — run the parity check against the inventory

Route elsewhere to propose directions (`design/architect`) or build a variant (`design/prototyper`).

## Inputs

- The surface in scope from `design/redesign`: routes, screens, or the whole application, plus the flows that define functional parity.
- Application source (router configuration, page and component modules, stylesheets, token files, `components.json`), a running instance reachable through `browse`, or supplied captures.
- For parity verification: the hashed inventory and one variant's `app.html` and `components.html`.

## Outputs

- `design-inventory` at `redesign/artifacts/inventory/design-inventory.json` (schema in `references/workflow.md`) and `design-inventory.md` (the human report: what exists, what is inconsistent, what the baseline captures show).
- Baseline captures under `redesign/evidence/baseline/` at the six responsive tiers in both themes per route, or an INFERRED record with a stated limitation when no browser is available.
- `parity-evidence` per variant at `redesign/evidence/parity-<variant>.json`, a typed probe record written by `python skills/scripts/check_parity.py` and bound by sha256 to the inventory and the prototype files.

### Gate evidence owned

`../../gates.yaml` `evidence_owners` assigns both keys to design-mapper; `design/redesign` packages them under the manifest's top-level `evidence` object at `redesign-review`.

| Key | Boundary | Must contain | Artifact-backed | Fallback |
| --- | --- | --- | --- | --- |
| `design_inventory` | `redesign-review` | Stable-id routes, states, components, interactions, and flows with their sources; the tokens in use and the off-scale values with their locations; baseline captures across the six tiers and both themes, or an INFERRED record stating its limitation | Yes — the value references the hashed inventory files in `artifact_hashes` | None sanctioned; the inventory is never waived in a redesign run |
| `parity_evidence` | `redesign-review` | One `check_parity.py` probe record per variant, `result.status` pass, `inputs` bound by sha256 to the inventory and the prototype files, coverage per list, and the exact missing ids when coverage is short | Yes — the probe records are hashed artifacts in the package | None sanctioned; a short coverage report is a `REVISE` to the builder, not a waiver |

## Workflow

1. Establish scope from the request and the codebase: read the router, navigation, page modules, and templates; enumerate routes before reading any screen. Ask only for what the code cannot answer (which flows define parity, which routes are out of scope).
2. Inventory routes and screens: stable id, path, purpose, entry points, primary action, the states the code can render (loading, empty, error, success, permission-denied, disabled, optimistic where present), and data dependencies.
3. Inventory components: stable id, name, the shadcn primitive it corresponds to when one exists, variants, sizes, states, source path, usage count; record duplicates and one-off equivalents as inconsistencies.
4. Extract tokens as used: colors, typography, spacing, radius, shadows, motion; map them to shadcn token names where they fit and list off-scale or hard-coded values.
5. Record interactions and flows: keyboard paths, focus management, confirmations, undo and retry, and the ordered steps (route, state, interaction) of each parity-defining flow.
6. Record the accessibility baseline with the shared severities: contrast failures, missing focus indicators, missing accessible names, reduced-motion gaps.
7. Capture the baseline through `browse` when a running surface is available: every route at 320, 375, 640, 1024, 1440, and 1920 px in light and dark themes, saved under `redesign/evidence/baseline/`. Without a browser, write an INFERRED baseline record with the limitation stated.
8. Write `design-inventory.json` and `design-inventory.md`, return their paths and sha256 digests, and stop; the mapper never proposes a new design.
9. When delegated parity verification, run `python skills/scripts/check_parity.py --inventory <inventory.json> --app <app.html> --components <components.html> --out redesign/evidence/parity-<variant>.json --project-root .` for the variant, return the record path, coverage, and the exact missing ids, and never edit the prototype.

## Required Contracts

- **Evidence over impression**: Every inventory row names its source path or capture; a row without a source is marked `inferred` and listed in the report's limitations.
- **Stable ids**: Ids are lowercase, dot-separated, unique within the inventory, and never renamed across revisions; a renamed id is a new id with the old one retired in the report.
- **Read-only**: The mapper writes only its inventory, report, captures, and parity records; it never changes application source or a prototype.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../../execution-contract.md` defines, so upstream and downstream packages read risk identically.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- `design/redesign`
- `browse` (baseline captures)
- `design/prototyper` (receives missing ids from parity verification)

## Review Expectations

- Every route, state, component, interaction, and flow in scope appears once with a stable id and a source.
- The token extraction distinguishes declared tokens from hard-coded values and lists inconsistencies with locations.
- The accessibility baseline is graded and located, not summarized.
- Parity records are the checker's output, bound by sha256 to the exact inventory and prototype files.

## Skip Rule

Never skip the inventory in a redesign run. Baseline captures may be replaced by an INFERRED record only when no running surface and no captures exist, and the limitation is stated.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The surface has no router — a single-page tool, an embedded widget, or a component library with no routes | Record one implicit route (`route.root`) with its states, components, interactions, and flows, and note the absent router under `limitations`. An empty `routes` list is not a valid inventory: `check_parity.py` scores an empty expectation set as coverage 1.0, so it would pass a variant that renders nothing. |
| The delegation names a surface that does not exist, or the inventory arrives malformed — wrong `schema_version`, a non-list parity list, a duplicate or non-conforming id | Stop before any parity run. `check_parity.py` exits 2 with an `engine_error` on stderr for exactly these; quote the error, return it to `design/redesign` with the offending id or field, and never hand-write a record the script did not produce. |
| `check_parity.py` exits 2 on a path — an inventory, `app.html`, or `components.html` that cannot be read | Treat the exit as the answer, not an obstacle: correct the path and re-run. Exit 0 is a pass, 1 is missing ids, 2 is an input or engine error, and only 0 or 1 produces a record. Report coverage only from a record the script wrote. |
| Python or `check_parity.py` is unavailable in the host | Report the parity stage as unverifiable, name the command that would have run, and return to `design/redesign`; a read-through of the markup is not a probe record and must never be labelled one. |
| `design/gatekeeper-design` returns a `REVISE` naming `design_inventory` or `parity_evidence` | Take the whole owner group in `revise_packet.by_owner` as one batch, fix every finding in a single revision, and return the changed files with new sha256 digests so the gate re-judges only `changed_evidence`. |
| The router or page structure cannot be read (compiled bundle only, no source) | Map from the running surface through `browse`, mark structural rows `inferred`, and state the limitation in the report. |
| Two components render the same primitive with different names | Record both ids, flag the duplicate as an inconsistency, and let `architect` decide the merge; never silently unify them. |
| A state exists in code but cannot be reached in the running surface | Record it with `reachable: false` and its source; the prototype must still render it. |
| The parity checker reports missing ids | Return the exact ids to `design/redesign` for the builder; do not lower the coverage threshold. |
| The inventory changes after variants were built | Publish a new inventory revision and report which variants must be re-verified; stale parity records fail the gate as input hash drift. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write the inventory files to `redesign/artifacts/inventory/`, captures to `redesign/evidence/baseline/`, and parity records to `redesign/evidence/`, at the destinations the delegation names. Resolve each one with `python skills/scripts/output_paths.py --run-id {run-id} --phase redesign --kind <artifacts|evidence> --name <file>`; both `--run-id` and `--kind` are required and the command exits non-zero without them.
2. Return each path with its sha256 so the phase lead can register it.
3. Write nothing else; phase state belongs to the run record.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.

## References

- `references/workflow.md` for the mapping sequence, the inventory JSON schema, the parity-marker contract, and the acceptance checklist.
- `references/examples.md` for concrete inventory and parity outputs.
- `../../design-doctrine.md` §4 for the six responsive tiers the baseline covers and §9 for the parity definition.
- `../../scripts/check_parity.py` for the mechanical parity check and its record shape.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep inventories, captures, and parity records under the run's `redesign/` directory, never inside the skill directory.
