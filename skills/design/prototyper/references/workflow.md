# Workflow Reference

Read this when building a variant: it carries the build order, the prototype
architecture, the inventory fields the build reads, the marker placement rules,
the self-check command, and the acceptance checklist.

## Contents

1. Build order
2. Inventory fields this build reads
3. Prototype architecture
4. Marker placement
5. Self-check command
6. Decision rules
7. Acceptance checklist
8. Collaboration notes

## Build Order

1. Tokens (`tokens.css`): light and dark values for every shadcn token, the type scale, the spacing scale, radius, shadow, and motion durations. Verify contrast before moving on.
2. Component library (`components.css`, `components.js`): base styles per primitive, variant and size classes, state styles, and the behaviours that need script (dialog open and close with focus trap, menus, tabs, toasts, tooltips).
3. Catalog (`components.html`): every primitive, every variant, size, and state, light and dark side by side.
4. Prototype (`app.html`): shell, router, views, state switcher, mocked data, interactions, flows.
5. Specification (`variant.md`): the doctrine §5 templates, token table, differentiation statement, Taste traceability, state coverage matrix, and any recorded deviations.
6. Self-check with `check_parity.py`, then return.

## Inventory Fields This Build Reads

`design-inventory.json` is `design/design-mapper`'s artifact and its authoritative
schema lives with that skill. These are the fields a variant build consumes; they
are restated here so the packaged skill stands alone.

| Path in the inventory | What the build does with it |
| --- | --- |
| `routes[].id` | One view in `app.html`, marked `data-route` |
| `routes[].path` | The hash route that renders the view (`/orders` → `#/orders`) |
| `routes[].purpose`, `routes[].primary_action` | The view's heading and its primary control |
| `routes[].states[]` | One reachable rendering per state, marked `data-state` or `data-route-state` |
| `routes[].components[]` | The catalog primitives the view composes |
| `components[].id`, `.name`, `.shadcn` | The catalog entry, its name, and the shadcn primitive it maps to (`null` means the variant names it itself) |
| `components[].variants[]`, `.sizes[]`, `.states[]` | The axes `components.html` must show in full |
| `interactions[].id`, `.keyboard`, `.confirmation` | A working control, its keyboard path, and its confirmation step |
| `flows[].steps[]` | An end-to-end traversal, each step referencing an existing route, state, and interaction |
| `tokens.*` | The current values a direction departs from — read for contrast, never copied |
| `accessibility_baseline[]` | Findings the variant must not reproduce |
| `limitations[]` | Rows marked `inferred`; a state marked unreachable is still rendered |

Ids are lowercase and dot-separated, unique within their list, and never renamed.
A variant never invents an id and never drops one.

## Prototype Architecture

- One file, `app.html`, linking `tokens.css`, `components.css`, and
  `components.js` by relative path; nothing fetched over the network.
- Hash routing: `#/dashboard` renders the `route.dashboard` view; unknown hashes
  render the inventory's error route or a marked `permission-denied` view.
- A state switcher (a small control in the shell, keyboard reachable) that
  re-renders the current route in any declared state: loading, empty, error,
  success, permission-denied, disabled, optimistic.
- Mocked data lives in one in-memory object; interactions mutate it so flows
  behave (adding an item changes the list, submitting a form shows the success
  state, a confirmation dialog blocks a destructive action until confirmed).
- Focus management: route changes move focus to the view heading; dialogs trap
  focus and restore it on close; every interactive element is reachable with
  Tab and operable with Enter or Space.
- Dark mode through a `.dark` class on the root and a shell toggle; motion
  disabled under `prefers-reduced-motion`.

## Marker Placement

| Inventory id | Marker | Placement |
| --- | --- | --- |
| route | `data-route="route.x"` | the view container for that route |
| state | `data-state="empty"` inside the view, or `data-route-state="route.x:empty"` on any element that renders that state | one element per declared state per route |
| component | `data-component="component.x"` | every instance in `components.html`; at least one instance in `app.html` |
| interaction | `data-interaction="interaction.x"` | the control that triggers it |
| flow | `data-flow="flow.x"` | the entry control or the container of the first step |

Markers are attributes on rendered elements. A marker inside a comment, a
template string that never renders, or a script constant does not count; the
checker scans markup, and the mapper's rendered check would catch the gap.

## Self-Check Command

Two commands, in this order. The first resolves a governed scratch destination;
the second runs the check against it.

```bash
python skills/scripts/output_paths.py --kind test_work --name parity-selfcheck-v2.json
# -> {"ok": true, "kind": "test_work", "path": "...", "relative": ".harness-state/test-work/parity-selfcheck-v2.json"}

python skills/scripts/check_parity.py \
  --inventory redesign/artifacts/inventory/design-inventory.json \
  --app redesign/artifacts/variants/v2/app.html \
  --components redesign/artifacts/variants/v2/components.html \
  --out .harness-state/test-work/parity-selfcheck-v2.json \
  --project-root .
```

- Pass the resolver's `relative` value to `--out`. The resolver rejects an
  absolute or traversing name with a non-zero exit, which is why the scratch path
  is never composed by hand.
- Exit 0 is full coverage, 1 is missing ids with the exact ids in the record, 2 is
  an input or engine error with no record written. Only 0 permits returning.
- `--min-coverage` stays at its default `1.0`. Lowering it converts a defect into
  a pass and the mapper's authoritative run would catch it anyway.
- The scratch record is not gate evidence and never ships beside the variant;
  `design/design-mapper` runs the authoritative check and owns its record.

## Decision Rules

- The direction decides every aesthetic choice; the inventory decides every
  functional one. When they conflict, function wins and the conflict is
  recorded in `variant.md`.
- Prefer composition over configuration: build screens from the catalog's
  primitives rather than one-off elements.
- Keep the shell honest: the same navigation, the same primary action per
  route, the same confirmations as the inventory records.
- Never borrow from a sibling variant; the four are compared for
  differentiation and cross-pollination defeats the comparison.

## Acceptance Checklist

- `tokens.css` covers the full shadcn token set in both themes and passes WCAG 2.2 AA for body and large text.
- `components.html` shows every primitive in every variant, size, and state, marked `data-component`.
- `app.html` renders every route and every declared state, wires every interaction and flow, and opens offline with no console errors.
- Keyboard paths, focus management, dark mode, and reduced motion work.
- `variant.md` fills the doctrine §5 Component Template and UI/UX Handoff concretely, lists the differentiators, and traces decisions to the direction's Taste rows.
- `check_parity.py` reports full coverage before the variant is returned.

## Collaboration Notes

- `design/redesign` delegates one direction per build and receives the six files with hashes.
- `design/design-mapper` runs the authoritative parity check and returns missing ids in one batch.
- `review/design-qa` captures the prototype across the six tiers and two themes; `review/frontier` grades accessibility and interaction resilience.
- `design/architect` implements the chosen variant in the production stack after the redesign gate.
