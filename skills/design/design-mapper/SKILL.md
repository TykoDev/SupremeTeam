---
name: design-mapper
description: >-
  Records and maps the current design of an existing user-facing surface into a
  machine-readable design inventory (routes, states, components, tokens,
  interactions, flows, accessibility baseline) with baseline captures, and later
  verifies each redesign variant against that inventory with the parity checker.
  Use when `design/redesign` delegates the inventory or parity stage, or the user
  asks to map the current UI, document what the interface does today, inventory
  the screens and components, or check that a prototype reproduces the existing
  app. Records what exists; defers proposing directions to `design/architect` and
  building prototypes to `design/prototyper`.
version: 1.0.0
---

# Design Mapper

## Purpose

Record the current design of an existing surface as evidence, not impression: a
stable-id inventory of every route, state, component, interaction, and flow, the
tokens actually in use, the accessibility baseline, and captures of the surface
as it renders today. The inventory is the parity contract every redesign variant
must satisfy, and the mapper is the owner who verifies that parity.

## Use This Skill When

Use this skill to **record what the interface does today** before anyone changes it:

- "map the current UI" / "inventory the screens and components" — produce the stable-id inventory
- "document what the interface does today" — write the inventory report with captures
- "check that this prototype reproduces the existing app" — run the parity check against the inventory

Route elsewhere to propose directions (`design/architect`) or build a variant (`design/prototyper`).

## Inputs

- The surface in scope from `design/redesign`: routes, screens, or the whole application, plus the flows that define functional parity.
- Application source (router configuration, page and component modules, stylesheets, token files, `components.json`), a running instance reachable through `browser-automation/browse`, or supplied captures.
- For parity verification: the hashed inventory and one variant's `app.html` and `components.html`.

## Outputs

- `design-inventory` at `redesign/artifacts/inventory/design-inventory.json` (schema in `references/workflow.md`) and `design-inventory.md` (the human report: what exists, what is inconsistent, what the baseline captures show).
- Baseline captures under `redesign/evidence/baseline/` at the six responsive tiers in both themes per route, or an INFERRED record with a stated limitation when no browser is available.
- `parity-evidence` per variant at `redesign/evidence/parity-<variant>.json`, a typed probe record written by `python skills/scripts/check_parity.py` and bound by sha256 to the inventory and the prototype files.

## Workflow

1. Establish scope from the request and the codebase: read the router, navigation, page modules, and templates; enumerate routes before reading any screen. Ask only for what the code cannot answer (which flows define parity, which routes are out of scope).
2. Inventory routes and screens: stable id, path, purpose, entry points, primary action, the states the code can render (loading, empty, error, success, permission-denied, disabled, optimistic where present), and data dependencies.
3. Inventory components: stable id, name, the shadcn primitive it corresponds to when one exists, variants, sizes, states, source path, usage count; record duplicates and one-off equivalents as inconsistencies.
4. Extract tokens as used: colors, typography, spacing, radius, shadows, motion; map them to shadcn token names where they fit and list off-scale or hard-coded values.
5. Record interactions and flows: keyboard paths, focus management, confirmations, undo and retry, and the ordered steps (route, state, interaction) of each parity-defining flow.
6. Record the accessibility baseline with the shared severities: contrast failures, missing focus indicators, missing accessible names, reduced-motion gaps.
7. Capture the baseline through `browser-automation/browse` when a running surface is available: every route at 320, 375, 640, 1024, 1440, and 1920 px in light and dark themes, saved under `redesign/evidence/baseline/`. Without a browser, write an INFERRED baseline record with the limitation stated.
8. Write `design-inventory.json` and `design-inventory.md`, return their paths and sha256 digests, and stop; the mapper never proposes a new design.
9. When delegated parity verification, run `python skills/scripts/check_parity.py --inventory <inventory.json> --app <app.html> --components <components.html> --out redesign/evidence/parity-<variant>.json --project-root .` for the variant, return the record path, coverage, and the exact missing ids, and never edit the prototype.

## Required Contracts

- **Evidence over impression**: Every inventory row names its source path or capture; a row without a source is marked `inferred` and listed in the report's limitations.
- **Stable ids**: Ids are lowercase, dot-separated, unique within the inventory, and never renamed across revisions; a renamed id is a new id with the old one retired in the report.
- **Read-only**: The mapper writes only its inventory, report, captures, and parity records; it never changes application source or a prototype.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- `design/redesign`
- `browser-automation/browse` (baseline captures)
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
| The router or page structure cannot be read (compiled bundle only, no source) | Map from the running surface through `browse`, mark structural rows `inferred`, and state the limitation in the report. |
| Two components render the same primitive with different names | Record both ids, flag the duplicate as an inconsistency, and let `architect` decide the merge; never silently unify them. |
| A state exists in code but cannot be reached in the running surface | Record it with `reachable: false` and its source; the prototype must still render it. |
| The parity checker reports missing ids | Return the exact ids to `design/redesign` for the builder; do not lower the coverage threshold. |
| The inventory changes after variants were built | Publish a new inventory revision and report which variants must be re-verified; stale parity records fail the gate as input hash drift. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write the inventory files to `redesign/artifacts/inventory/`, captures to `redesign/evidence/baseline/`, and parity records to `redesign/evidence/`, at the destinations the delegation names (resolved with `python skills/scripts/output_paths.py --phase redesign`).
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
