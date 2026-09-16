# Workflow Reference

## Contents

1. Mapping sequence
2. Inventory schema
3. Parity-marker contract
4. Decision rules
5. Acceptance checklist
6. Collaboration notes

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

`skills/scripts/check_parity.py` reads the inventory and scans a variant's
`app.html` and `components.html` for these attributes:

| Inventory list | Marker | Where it must appear |
| --- | --- | --- |
| `routes[].id` | `data-route="<id>"` | on the view element of that route in `app.html` |
| `routes[].states[]` | `data-state="<state>"` inside that route's view, or `data-route-state="<route id>:<state>"` anywhere | `app.html`; every declared state of every route |
| `components[].id` | `data-component="<id>"` | at least once in `components.html` (the catalog) and at least once in `app.html` |
| `interactions[].id` | `data-interaction="<id>"` | on the control that triggers it in `app.html` |
| `flows[].id` | `data-flow="<id>"` | on the flow's entry control or container in `app.html` |

Coverage is the fraction of inventory ids found; the record passes only at full
coverage (`--min-coverage 1.0` is the default). The record is a typed probe:
`artifacts` (the record itself), `inputs` (inventory, `app.html`,
`components.html` with sha256), `coverage` per list, `missing` per list, and
`result.status`.

## Decision Rules

- Record, do not judge: an ugly or inconsistent pattern is an inventory row with
  an `inconsistency` note, not an omission.
- Declared states beat reachable states: a state the code can render is in the
  inventory even when the running surface never showed it.
- One id per thing: duplicates are two ids plus an inconsistency, never one
  merged id.
- Parity is binary per variant: missing ids go back to the builder; the
  threshold does not move.

## Acceptance Checklist

- Every route in scope has a path, purpose, states, components, and source.
- Every component has a shadcn mapping or `null`, variants, states, and a usage count.
- Every parity-defining flow has ordered steps referencing inventory ids only.
- Tokens separate declared values from off-scale values with locations.
- Baseline captures exist for every route at the six tiers in both themes, or an INFERRED record states why not.
- The JSON validates against the schema fields above and every referenced id resolves within the inventory.

## Collaboration Notes

- `design/redesign` consumes the inventory as the parity contract and delegates parity verification per variant.
- `design/architect` reads the inventory and the taste grilling log to write the four directions.
- `design/prototyper` reads the inventory to place every parity marker and self-checks with the same script.
- `review/design-qa` reuses the baseline captures as the before-state for rendered verification.
