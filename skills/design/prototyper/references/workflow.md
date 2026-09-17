# Workflow Reference

Read this when building a redesign draft: it carries the two build orders, the
static-draft rules a mock obeys, the prototype architecture the selected build
implements, the inventory fields each mode reads, the marker placement rules, the
self-check commands at both levels, and the acceptance checklists.

## Contents

1. Two modes, one skill
2. Build order — mock build
3. Static-draft rules
4. Build order — selected build
5. Inventory fields each mode reads
6. Prototype architecture (selected build)
7. Marker placement
8. Self-check commands
9. Decision rules
10. Acceptance checklists
11. Collaboration notes

## Two Modes, One Skill

`../../pipelines.yaml` gives this skill two stages in the `redesign` pipeline,
and a delegation is always one of them.

| Stage | Fan-out | Output directory | Files | Parity level |
| --- | --- | --- | --- | --- |
| `mock-build` | 4, one per direction | `redesign/artifacts/mocks/<id>/` | `variant.md`, `tokens.css`, `components.css`, `components.html`, `mock.html` | `--level mock` |
| `selected-build` | none; one delegation | `redesign/artifacts/variants/<id>/` | `variant.md`, `tokens.css`, `components.css`, `components.js`, `components.html`, `app.html` | `--level full` |

`selected-build` runs only when a variant was selected — the stage's `when`
condition in `../../pipelines.yaml` — and only for the id `selection.chosen`
names. A merge or a deferral commissions no build at all, and `design/redesign`
records the sanctioned fallback strings instead.

## Build Order — Mock Build

1. Tokens (`tokens.css`): light and dark values for every shadcn token, the type scale, the spacing scale, radius, shadow, and motion durations. Verify contrast before moving on.
2. Component styles (`components.css`): base styles per primitive, variant and size classes, and the *appearance* of every state. A disabled button looks disabled; nothing disables it.
3. Catalog (`components.html`): every primitive, every variant, size, and state, light and dark side by side, each instance marked `data-component`.
4. Screens (`mock.html`): one drawn screen per inventory route, `data-route` on the screen's root, `data-mock="true"` on the root element, hard-coded sample content.
5. Specification (`variant.md`): the doctrine §5 templates, token table, differentiation statement, Taste traceability, the **Mock scope** note, and any recorded deviations.
6. Self-check with `check_parity.py --level mock`, then return.

## Static-Draft Rules

These are what make a mock a mock. A draft that breaks one of them has become an
implementation built before the decision that justifies it.

- **One screen per route.** Every `routes[].id` in the inventory is drawn once in `mock.html`, with `data-route="<id>"` on that screen's root element. Screens may all be in the document at once, or hidden and revealed by the screen picker; either way the markup is there.
- **Every component present.** Every `components[].id` appears somewhere across `components.html` and `mock.html`, marked `data-component="<id>"`. The catalog carries most of them; the screens show them in context.
- **Hard-coded content.** Sample rows, sample names, sample counts, written so the screen reads like the real product. Nothing is generated, fetched, or computed.
- **`data-mock="true"` on the root.** The `<html>` or top-level container of `mock.html` carries it. `check_parity.py --level mock` and the reviewers read it to tell a mock from a living prototype; a mock without it will be judged as one.
- **Both themes.** Light and dark come from `tokens.css` alone.
- **JavaScript, allowed:** an optional theme toggle, and an optional screen picker that only shows and hides the static screens.
- **JavaScript, not allowed:** a hash router with real navigation state, any in-memory data store or state machine, any wired interaction or flow, and `components.js` — the file does not exist in a mock.
- **Markers not required:** `data-interaction` and `data-flow`. Mock parity does not score them.
- **Route states, optional.** A route state may be drawn as an extra static screen carrying `data-route-state="route.x:empty"`, and is worth drawing where the direction is easier to judge with it. Mock parity reports states as an informational count and never fails on them.

## Build Order — Selected Build

1. Confirm the selection: `decision: variant`, and `chosen` equal to the id this delegation was given. Without both, build nothing and return to `design/redesign`.
2. Read the selected mock's `tokens.css`, `components.css`, and `components.html`. The living prototype is derived from them; the direction was already decided and re-deriving it loses the thing the user chose.
3. Tokens (`tokens.css`): carry the mock's values forward, complete only the scales the mock left unused, and re-verify contrast in both themes.
4. Component library (`components.css`, `components.js`): the mock's styles plus the behaviours that need script — dialog open and close with focus trap, menus, tabs, toasts, tooltips, reduced-motion handling.
5. Catalog (`components.html`): the mock's catalog grown into a living one — every primitive in every variant, size, and real state.
6. Prototype (`app.html`): shell, router, views, state switcher, mocked data, interactions, flows.
7. Specification (`variant.md`): the doctrine §5 templates, token table, differentiation statement, Taste traceability, state coverage matrix, and any recorded deviations.
8. Self-check with `check_parity.py --level full`, then return.

## Inventory Fields Each Mode Reads

`design-inventory.json` is `design/design-mapper`'s artifact and its authoritative
schema lives with that skill. These are the fields a draft consumes; they are
restated here so the packaged skill stands alone. The last column says which mode
needs the field.

| Path in the inventory | What the build does with it | Mode |
| --- | --- | --- |
| `routes[].id` | One screen in `mock.html` or one view in `app.html`, marked `data-route` | both |
| `routes[].path` | The hash route that renders the view (`/orders` → `#/orders`) | selected |
| `routes[].purpose`, `routes[].primary_action` | The screen's heading and its primary control | both |
| `routes[].states[]` | One reachable rendering per state, marked `data-state` or `data-route-state` | selected (optional in a mock) |
| `routes[].components[]` | The catalog primitives the screen composes | both |
| `components[].id`, `.name`, `.shadcn` | The catalog entry, its name, and the shadcn primitive it maps to (`null` means the direction names it itself) | both |
| `components[].variants[]`, `.sizes[]`, `.states[]` | The axes `components.html` must show in full | both |
| `interactions[].id`, `.keyboard`, `.confirmation` | A working control, its keyboard path, and its confirmation step | selected |
| `flows[].steps[]` | An end-to-end traversal, each step referencing an existing route, state, and interaction | selected |
| `tokens.*` | The current values a direction departs from — read for contrast, never copied | both |
| `accessibility_baseline[]` | Findings the draft must not reproduce | both |
| `limitations[]` | Rows marked `inferred`; a state marked unreachable is still rendered in the selected build | both |

Ids are lowercase and dot-separated, unique within their list, and never renamed.
A draft never invents an id and never drops one.

## Prototype Architecture (Selected Build)

This section describes `app.html` only. None of it belongs in a mock.

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

| Inventory id | Marker | Placement | Required in a mock |
| --- | --- | --- | --- |
| route | `data-route="route.x"` | the screen container in `mock.html`, the view container in `app.html` | yes |
| component | `data-component="component.x"` | every instance in `components.html`; at least one instance in `mock.html` or `app.html` | yes |
| state | `data-state="empty"` inside the view, or `data-route-state="route.x:empty"` on any element that renders that state | one element per declared state per route in `app.html` | no — optional extra screens |
| interaction | `data-interaction="interaction.x"` | the control that triggers it | no |
| flow | `data-flow="flow.x"` | the entry control or the container of the first step | no |

One marker belongs to the mock alone: `data-mock="true"` on `mock.html`'s root
element. It is never placed on `app.html`.

Markers are attributes on rendered elements. A marker inside a comment, a
template string that never renders, or a script constant does not count; the
checker scans markup, and the mapper's rendered check would catch the gap.

## Self-Check Commands

Two commands, in this order, in both modes. The first resolves a governed scratch
destination; the second runs the check against it at the level the mode requires.

```bash
python skills/scripts/output_paths.py --kind test_work --name parity-selfcheck-v2.json
# -> {"ok": true, "kind": "test_work", "path": "...", "relative": ".harness-state/test-work/parity-selfcheck-v2.json"}

# mock build
python skills/scripts/check_parity.py --level mock \
  --inventory redesign/artifacts/inventory/design-inventory.json \
  --app redesign/artifacts/mocks/v2/mock.html \
  --components redesign/artifacts/mocks/v2/components.html \
  --out .harness-state/test-work/parity-selfcheck-v2.json \
  --project-root .

# selected build
python skills/scripts/check_parity.py --level full \
  --inventory redesign/artifacts/inventory/design-inventory.json \
  --app redesign/artifacts/variants/v2/app.html \
  --components redesign/artifacts/variants/v2/components.html \
  --out .harness-state/test-work/parity-selfcheck-v2.json \
  --project-root .
```

- Pass the resolver's `relative` value to `--out`. The resolver rejects an
  absolute or traversing name with a non-zero exit, which is why the scratch path
  is never composed by hand.
- `--level mock` scores **routes and components only**. Interactions, flows, and
  states appear in the record as informational counts and never fail the level.
  `--level full` scores every list.
- Exit 0 is full coverage of the scored lists, 1 is missing ids with the exact
  ids in the record, 2 is an input or engine error with no record written. Only 0
  permits returning.
- `--min-coverage` stays at its default `1.0` at both levels; at mock level it
  applies to the two scored lists. Lowering it converts a defect into a pass and
  the mapper's authoritative run would catch it anyway.
- The scratch record is not gate evidence and never ships beside the draft;
  `design/design-mapper` runs the authoritative check and owns its record.

## Decision Rules

- The direction decides every aesthetic choice; the inventory decides every
  functional one. When they conflict, function wins and the conflict is
  recorded in `variant.md`.
- Prefer composition over configuration: build screens from the catalog's
  primitives rather than one-off elements.
- Keep the shell honest: the same navigation and the same primary action per
  route as the inventory records, and — in the selected build — the same
  confirmations.
- Never borrow from a sibling mock; the four are compared for differentiation
  and cross-pollination defeats the comparison.
- When in doubt in a mock, draw it rather than wire it. Fidelity of appearance is
  what the comparison is judging; behaviour is what the selected build is for.

## Acceptance Checklists

### Mock

- `tokens.css` covers the full shadcn token set in both themes and passes WCAG 2.2 AA for body and large text.
- `components.html` shows every primitive in every variant, size, and state appearance, marked `data-component`.
- `mock.html` draws every inventory route with `data-route` on the screen root, carries `data-mock="true"` on the root element, and opens offline with no console errors.
- No `components.js` exists; no router, store, or wired interaction is present; the only script is the optional theme toggle and screen picker.
- `variant.md` fills the doctrine §5 Component Template and UI/UX Handoff concretely, lists the differentiators, traces decisions to the direction's Taste rows, and states the Mock scope — which routes are drawn and which route states, if any, are shown.
- `check_parity.py --level mock` reports full coverage of routes and components before the mock is returned.

### Selected variant

- The `selection` record names `decision: variant` and a `chosen` id equal to this build's id.
- `tokens.css` carries the selected mock's values forward and still passes the contrast floor.
- `components.html` shows every primitive in every variant, size, and state, marked `data-component`.
- `app.html` renders every route and every declared state, wires every interaction and flow, and opens offline with no console errors.
- Keyboard paths, focus management, dark mode, and reduced motion work.
- `variant.md` adds the state coverage matrix to the §5 templates.
- `check_parity.py --level full` reports full coverage before the variant is returned.

## Collaboration Notes

- `design/redesign` delegates one direction per mock build and, after the selection stage, one selected build; it receives the file set with hashes each time.
- `design/design-mapper` runs the authoritative parity check — `--level mock` per mock, `--level full` on the selected variant — and returns missing ids in one batch.
- `review/design-qa` captures the four mocks across the six tiers and two themes, and the selected variant the same way once it exists.
- `review/frontier` grades accessibility and interaction resilience on the selected variant.
- `design/architect` implements the chosen variant in the production stack after the redesign gate.
