# Workflow Reference

## Contents

1. Build order
2. Prototype architecture
3. Marker placement
4. Decision rules
5. Acceptance checklist
6. Collaboration notes

## Build Order

1. Tokens (`tokens.css`): light and dark values for every shadcn token, the type scale, the spacing scale, radius, shadow, and motion durations. Verify contrast before moving on.
2. Component library (`components.css`, `components.js`): base styles per primitive, variant and size classes, state styles, and the behaviours that need script (dialog open and close with focus trap, menus, tabs, toasts, tooltips).
3. Catalog (`components.html`): every primitive, every variant, size, and state, light and dark side by side.
4. Prototype (`app.html`): shell, router, views, state switcher, mocked data, interactions, flows.
5. Specification (`variant.md`): the doctrine §5 templates, token table, differentiation statement, Taste traceability, state coverage matrix, and any recorded deviations.
6. Self-check with `check_parity.py`, then return.

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
