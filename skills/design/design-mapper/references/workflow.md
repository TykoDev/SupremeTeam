# Workflow Reference

Read this when producing a `design-inventory` or a `parity-evidence` record: it
carries the mapping sequence, the inventory JSON schema, the parity-marker
contract, the checker's exit contract, the report structure, and the acceptance
checklist.

## Contents

1. Mapping sequence
2. Inventory schema
3. Parity-marker contract
4. Checker contract
5. Report structure (`design-inventory.md`)
6. Decision rules
7. Acceptance checklist
8. Collaboration notes
9. Gate evidence owned

## Mapping Sequence

1. Enumerate routes from the router before reading screens; a screen that is not routed is recorded under the route that hosts it.
2. For each route, read the page module and its children to list the states the code can render and the components it composes.
3. Walk the component tree once, bottom-up, so every component gets one id and one usage count.
4. Read the stylesheet and token sources (`globals.css`, `app.css`, theme files, `components.json`) and record every declared token and every hard-coded value that bypasses one.
5. Record interactions from event handlers, keyboard handlers, and confirmation dialogs; record flows from the parity-defining journeys agreed at intake.
6. Grade the accessibility baseline from rendered evidence where a browser exists, otherwise from source with `inferred` marked.
7. Capture the baseline and write the inventory files.

## Inventory Schema

`design-inventory.json`, `schema_version: 1`. Every id is lowercase,
dot-separated, and unique in its list.

```json
{
  "schema_version": 1,
  "surface": "inventory dashboard",
  "captured_at": "2026-09-16T10:00:00Z",
  "source": {"paths": ["src/app", "src/components", "src/styles"], "revision": "git:3f9a1c2"},
  "routes": [
    {"id": "route.dashboard", "path": "/dashboard", "purpose": "stock overview",
     "primary_action": "interaction.receive-stock",
     "states": ["loading", "empty", "error", "success"],
     "components": ["component.button", "component.table"],
     "source": "src/app/dashboard/page.tsx"}
  ],
  "components": [
    {"id": "component.button", "name": "Button", "shadcn": "Button",
     "variants": ["default", "outline", "ghost"], "sizes": ["sm", "md"],
     "states": ["default", "hover", "focus", "disabled", "loading"],
     "source": "src/components/ui/button.tsx", "usage_count": 41}
  ],
  "interactions": [
    {"id": "interaction.receive-stock", "route": "route.dashboard",
     "description": "opens the receive dialog", "keyboard": "Enter on the primary button",
     "confirmation": false}
  ],
  "flows": [
    {"id": "flow.receive", "steps": [
      {"route": "route.dashboard", "state": "success", "interaction": "interaction.receive-stock"},
      {"route": "route.receive", "state": "success", "interaction": "interaction.submit-receipt"}
    ]}
  ],
  "tokens": {
    "colors": {"--primary": "oklch(0.52 0.2 262)", "--background": "#ffffff"},
    "typography": {"family": "Inter", "scale": [12, 14, 16, 20, 24, 32]},
    "spacing": [4, 8, 12, 16, 24, 32],
    "radius": ["0.5rem"],
    "motion": {"duration": "150ms", "reduced_motion": false},
    "off_scale": [{"value": "13px", "location": "src/components/Badge.tsx:12"}]
  },
  "accessibility_baseline": [
    {"id": "a11y.contrast.muted", "severity": "Major", "location": "src/styles/globals.css:40",
     "description": "muted foreground on background measures 3.9:1"}
  ],
  "limitations": []
}
```

`routes`, `components`, `interactions`, and `flows` are the parity lists;
`tokens`, `accessibility_baseline`, and `limitations` are context for the
directions and the report.

## Parity-Marker Contract

`skills/scripts/check_parity.py` reads the inventory and scans the draft's
markup — `mock.html` at mock level, `app.html` at full level — together with
`components.html`, for these attributes. The last column says which markers a
mock owes and which belong to the living prototype alone.

| Inventory list | Marker | Where it must appear | Required in a mock |
| --- | --- | --- | --- |
| `routes[].id` | `data-route="<id>"` | on the screen element of that route in `mock.html`, or on the view element in `app.html` | Yes — scored at mock level |
| `components[].id` | `data-component="<id>"` | at least once in `components.html` (the catalog) and at least once in the screens file | Yes — scored at mock level |
| `routes[].states[]` | `data-state="<state>"` inside that route's view, or `data-route-state="<route id>:<state>"` anywhere | `app.html`; every declared state of every route | No — a mock may draw a state as an extra static screen, and the count is informational |
| `interactions[].id` | `data-interaction="<id>"` | on the control that triggers it in `app.html` | No — a mock wires nothing |
| `flows[].id` | `data-flow="<id>"` | on the flow's entry control or container in `app.html` | No — a mock wires nothing |

One marker has no inventory id behind it: `data-mock="true"` on `mock.html`'s
root element. It is how the checker and the reviewers tell a mock from a living
prototype, and it never appears on `app.html`.

Coverage is the fraction of inventory ids found in the lists the level scores;
the record passes only at full coverage of those lists (`--min-coverage 1.0` is
the default at both levels). At `--level mock` that means routes and components
alone — states, interactions, and flows are reported as informational counts and
never fail the level. At `--level full` every list is scored. The record is a
typed probe: `artifacts` (the record itself), `inputs` (inventory, the screens
file, `components.html` with sha256), `coverage` per list, `missing` per list,
and `result.status`.

## Checker Contract

`skills/scripts/check_parity.py` is the only source of a `mock-parity-evidence`
or `parity-evidence` record. Its behaviour is part of the contract, not an
implementation detail.

```bash
# mock parity, once per mock
python skills/scripts/check_parity.py --level mock --inventory <design-inventory.json> --app <mock>/mock.html --components <mock>/components.html --out redesign/evidence/mock-parity-<id>.json --project-root .

# full parity, once, for the selected variant only
python skills/scripts/check_parity.py --level full --inventory <design-inventory.json> --app <variant>/app.html --components <variant>/components.html --out redesign/evidence/parity-<variant>.json --project-root .
```

The four mock-level records are then summarised into one aggregated probe record
of the same shape, whose `artifacts` list names them; that aggregate is what the
package carries as `mock_parity`. The full-level record stands alone as
`parity_evidence`.

| Exit | Meaning | Record written |
| --- | --- | --- |
| 0 | Coverage meets `--min-coverage` (default `1.0`) | Yes, `result.status: pass` |
| 1 | Inventory ids the level scores are missing from the draft | Yes, `result.status: fail`, with the exact ids per list |
| 2 | Input or engine error: unreadable file, wrong `schema_version`, a parity list that is not a list, an invalid or duplicate id | No — `engine_error` on stderr only |

- `--project-root .` makes every `inputs[].path` in the record project-relative.
  Without it the record can carry absolute paths, which the gate cannot bind to
  the package's hashed artifacts. Pass it on every run.
- `--level` follows the stage, not the artifact. `mock` for a `mock-build` output,
  `full` for the selected variant. Scoring a mock at full level manufactures a
  failure for behaviour the mock was never meant to have; scoring a prototype at
  mock level manufactures a pass.
- `--min-coverage` is not a dial. The default of `1.0` is the parity definition in
  `../../../design-doctrine.md` §9 and applies at both levels — to routes and
  components at mock level, to every list at full level; lowering it converts a
  defect into a pass.
- An inventory whose parity lists are all empty scores coverage `1.0`, because an
  empty expectation set is trivially met. A surface with no router therefore gets
  one implicit `route.root` row rather than an empty `routes` list, or the check
  certifies a prototype that renders nothing.
- Markers are read from rendered markup only. The scanner skips `script`, `style`,
  and `template` contents, so a marker in a template literal or a comment does not
  count.
- Exit 2 is never reported as a parity result. Fix the input and re-run; a
  hand-written record is not evidence.

## Report Structure (`design-inventory.md`)

The JSON is the contract; the report is what a person reads before deciding the
redesign's scope. Both are returned, and both are hashed.

```markdown
# Design Inventory — {surface}

**Source**: {paths} at {revision}   **Captured**: {timestamp}

## Scope
{routes and flows in scope, and what was deliberately excluded}

## Routes and states
{table: id, path, purpose, primary action, states, source}

## Components
{table: id, name, shadcn mapping or null, variants, sizes, states, source, usage count}

## Tokens in use
{declared tokens by group, then the off-scale table: value, location}

## Interactions and flows
{table per flow: ordered steps as route -> state -> interaction}

## Inconsistencies
{table: id, finding, location — duplicates, one-off equivalents, bypassed tokens}

## Accessibility baseline
{table: id, severity, finding, location — shared four-tier severities}

## Baseline captures
{route x tier x theme coverage, or the INFERRED record with its limitation}

## Limitations
{every row marked `inferred`, and why source or capture could not settle it}
```

Every section is filled from evidence. A section with nothing to report says so
explicitly; an omitted section reads at the gate as an unmapped area.

## Decision Rules

- Record, do not judge: an ugly or inconsistent pattern is an inventory row with
  an `inconsistency` note, not an omission.
- Declared states beat reachable states: a state the code can render is in the
  inventory even when the running surface never showed it.
- One id per thing: duplicates are two ids plus an inconsistency, never one
  merged id.
- Parity is binary per draft and per level: missing ids in a list the level
  scores go back to the builder; the threshold does not move, and neither does
  which lists the level scores.

## Acceptance Checklist

- Every route in scope has a path, purpose, states, components, and source.
- Every component has a shadcn mapping or `null`, variants, states, and a usage count.
- Every parity-defining flow has ordered steps referencing inventory ids only.
- Tokens separate declared values from off-scale values with locations.
- Baseline captures exist for every route at the six tiers in both themes, or an INFERRED record states why not.
- The JSON validates against the schema fields above and every referenced id resolves within the inventory.

## Collaboration Notes

- `design/redesign` consumes the inventory as the parity contract, delegates mock parity across the four mocks, and delegates full parity verification for the selected variant only.
- `design/architect` reads the inventory and the taste grilling log to write the four directions.
- `design/prototyper` reads the inventory to place every parity marker its level requires and self-checks with the same script at the same level.
- `review/design-qa` reuses the baseline captures as the before-state for the mock captures and for rendered verification.

## Gate Evidence Owned

`../../../gates.yaml` `evidence_owners` assigns three keys to design-mapper;
`design/redesign` packages them under the manifest's top-level `evidence` object
at `redesign-review`. `../SKILL.md` summarizes these three rows; this table is the
authoritative one.

| Key | Boundary | Must contain | Artifact-backed | Fallback |
| --- | --- | --- | --- | --- |
| `design_inventory` | `redesign-review` | Stable-id routes, states, components, interactions, and flows with their sources; the tokens in use and the off-scale values with their locations; baseline captures across the six tiers and both themes, or an INFERRED record stating its limitation | Yes — the value references the hashed inventory files in `artifact_hashes` | None sanctioned; the inventory is never waived in a redesign run |
| `mock_parity` | `redesign-review` | One aggregated `check_parity.py --level mock` probe record whose `artifacts` list names the four per-mock records, `result.status` pass, full coverage of routes and components across every mock, and the exact missing ids when coverage is short; interactions, flows, and states appear as informational counts and never fail the level | Yes — the aggregated record and the four per-mock records are hashed artifacts in the package | None sanctioned; a short coverage report is a `REVISE` to the builder, not a waiver |
| `parity_evidence` | `redesign-review` | The `check_parity.py --level full` probe record for the selected variant, `result.status` pass, `inputs` bound by sha256 to the inventory and the prototype files, coverage per list, and the exact missing ids when coverage is short | Yes — the probe record is a hashed artifact in the package | Only the sanctioned strings `selection deferred - no variant built` and `merge brief recorded - implemented as a fifth direction in the design pipeline`, carried at schema 2 as the `reason` of an applicability record `{applicable: false, reason, scope, decided_by}` and written by `design/redesign` when no variant was selected and therefore no prototype exists to check. This skill never writes one |
