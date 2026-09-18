# Example Invocations

Four delegations and the actual files returned: token values, marked markup, and
`variant.md` rows. The build orders, static-draft rules, marker rules, and
self-check commands are in `workflow.md`.

## Contents

1. Example 1 — "build the mock for direction two (dense-operational)"
2. Example 2 — "the mapper says mock two is missing two components"
3. Example 3 — "the direction wants a pale amber on cream for body text"
4. Example 4 — "v2 was selected; build the living prototype"

## Example 1 — "build the mock for direction two (dense-operational)"

A `mock-build` delegation, one of four fanned out from the directions.

Returned: `redesign/artifacts/mocks/v2/{variant.md,tokens.css,components.css,components.html,mock.html}`
with sha256 digests. Excerpts from three of them.

`tokens.css` — the direction's dense-operational reading, both themes:

```css
:root {
  --background: oklch(0.99 0.002 250);
  --foreground: oklch(0.21 0.01 250);
  --primary: oklch(0.52 0.16 250);
  --primary-foreground: oklch(0.99 0.002 250);
  --muted-foreground: oklch(0.47 0.01 250); /* 4.8:1 on --background */
  --border: oklch(0.90 0.004 250);
  --ring: oklch(0.52 0.16 250);
  --radius: 0.25rem;                        /* dense: one step, not four */
  --space: 4px;                             /* 4 8 12 16 24 32 */
  --text: 13px;                             /* 13 15 17 20 26 */
  --motion: 120ms;
}
.dark {
  --background: oklch(0.19 0.01 250);
  --foreground: oklch(0.96 0.003 250);
  --muted-foreground: oklch(0.72 0.01 250); /* 4.7:1 on --background */
  --border: oklch(0.29 0.01 250);
}
```

`mock.html` — the orders screen, drawn with hard-coded content and the two
markers mock parity scores:

```html
<html lang="en" data-mock="true">
…
<section data-route="route.orders">
  <h1>Order queue</h1>
  <button class="btn btn-primary btn-sm" data-component="component.button">Claim next</button>

  <table data-component="component.table">
    <tr><td>SO-4417</td><td>Ridgeline Supply</td><td>2 lines</td><td>Awaiting pick</td></tr>
    <tr><td>SO-4418</td><td>Halvorsen &amp; Co</td><td>7 lines</td><td>Picking</td></tr>
    <tr><td>SO-4419</td><td>Delta Provisioning</td><td>1 line</td><td>Short</td></tr>
  </table>
</section>

<!-- optional: one route state drawn as an extra static screen -->
<section data-route="route.orders" data-route-state="route.orders:empty" hidden>
  <h1>Order queue</h1>
  <p>No orders in this queue.</p>
</section>
```

No router, no fixtures object, no `components.js`. The only script in the file is
the theme toggle and the screen picker.

`variant.md` — the Taste traceability rows and the Mock scope note:

```markdown
| Decision | Traced to | Snapshot digest |
| -------- | --------- | --------------- |
| 13px base type, 4px spacing unit | taste:density/`prefers compact operational tables` (hard) | sha256:4c7e… |
| 0.25rem radius, one elevation | taste:visual-style/`plain surfaces, no decorative depth` (strong) | sha256:4c7e… |
| 120ms transitions, none on lists | taste:motion/`motion only for state change` (soft) | sha256:4c7e… |

## Mock scope

Drawn: all 9 inventory routes, one screen each.
Route states shown: `route.orders:empty`, `route.dashboard:loading` — drawn
because density reads very differently when the table is empty or skeletonised.
Not shown: the remaining 34 declared states, every interaction, and all 4 flows.
Those are the selected build's work.
```

**Self-check**: `--level mock`, exit 0, coverage 1.0 on the two scored lists
(9 routes, 27 components); states, interactions, and flows reported
informationally (2 of 36, 0 of 12, 0 of 4). Body contrast measured 4.8:1 light
and 4.7:1 dark.

## Example 2 — "the mapper says mock two is missing two components"

Two ids returned by `design/design-mapper` from its `--level mock` run:
`component.badge` and `component.breadcrumb`. Neither appeared anywhere across
the catalog or the screens. The fix, in `components.html`:

```html
<section>
  <h2>Badge</h2>
  <span class="badge" data-component="component.badge">Short</span>
  <span class="badge badge-muted" data-component="component.badge">Picking</span>
</section>
<section>
  <h2>Breadcrumb</h2>
  <nav class="crumbs" data-component="component.breadcrumb">
    <a href="#">Warehouse</a> / <a href="#">Orders</a> / <span>SO-4417</span>
  </nav>
</section>
```

**Returned**: updated `components.html` and `variant.md` with new sha256 digests,
in one revision rather than two. The mapper re-runs the authoritative mock parity
check; the prototyper does not edit the record.

Note what the fix is not: neither element was wired. A breadcrumb in a mock is
markup with the right marker and the direction's styling, and nothing navigates
when it is clicked.

## Example 3 — "the direction wants a pale amber on cream for body text"

The direction's palette fails the accessibility floor, so the token moves and the
deviation is recorded rather than the floor being lowered. The rule is the same
in both modes, because the comparison itself depends on it.

```markdown
## Deviation — body text contrast

**Direction asked for**: `--foreground: oklch(0.82 0.11 80)` (pale amber) on
`--background: oklch(0.97 0.02 85)` (cream).
**Measured**: 2.8:1, below the 4.5:1 WCAG 2.2 AA floor for body text.
**Applied**: `--foreground: oklch(0.44 0.08 65)` — the nearest amber-brown that
measures 4.6:1 on the same cream. The pale amber is kept for headings at 24px and
above, where it measures 3.2:1 against the 3:1 large-text floor.
**Why not the direction's value**: `../../../design-doctrine.md` §6 treats an
inaccessible flow as broken, not unpolished; a mock that shows failing contrast
cannot be compared fairly against three that do not, and the user would be
choosing a direction that cannot be built as drawn.
**Reported**: Minor finding against the direction, returned to `design/redesign`.
```

The direction's intent survives — warm, low-contrast, amber-led — and the body
text is legible. Both facts are in `variant.md` so the comparison is honest.

## Example 4 — "v2 was selected; build the living prototype"

A `selected-build` delegation, commissioned after the selection stage recorded
`{decision: "variant", chosen: "v2"}`. One delegation, one variant.

**First move**: confirm the selection record names `decision: variant` and that
`chosen` is `v2`, the id this delegation was given. Had the delegation named `v3`
with `chosen: "v2"`, or carried no selection record at all, the answer is to
build nothing and return to `design/redesign`.

Returned: `redesign/artifacts/variants/v2/{variant.md,tokens.css,components.css,components.js,components.html,app.html}`
with sha256 digests. `tokens.css` is the mock's file carried forward with the
motion scale completed; `components.css` is the mock's file plus the dialog,
menu, and toast behaviours; `app.html` is new.

`app.html` — the same orders view, now with everything the mock deliberately
left out:

```html
<section data-route="route.orders" hidden>
  <h1 tabindex="-1">Order queue</h1>
  <button class="btn btn-primary btn-sm"
          data-component="component.button"
          data-interaction="interaction.claim-order"
          data-flow="flow.claim">Claim next</button>

  <div data-state="success">
    <table data-component="component.table"><!-- rows from mock state --></table>
  </div>
  <div data-state="loading" hidden>…</div>
  <div data-state="empty" hidden>No orders in this queue.</div>
  <div data-state="error" hidden>Could not load the queue. <button>Retry</button></div>
  <div data-state="permission-denied" hidden>This queue belongs to another team.</div>
</section>
```

```js
// the in-memory store the mock had no business carrying
const fixtures = {
  "route.orders": {
    success: orders,
    empty:   [],
    error:   { fail: true, message: "Could not load the queue." },
  },
};
```

`variant.md` gains the state coverage matrix the mock did not owe:

```markdown
| Route | loading | empty | error | success | permission-denied |
| ----- | ------- | ----- | ----- | ------- | ----------------- |
| route.orders | ✓ | ✓ | ✓ | ✓ | ✓ |
| route.dashboard | ✓ | ✓ | ✓ | ✓ | n/a |
```

**Self-check**: `--level full`, exit 0, coverage 1.0 across all five lists
(9 routes, 36 states, 27 components, 12 interactions, 4 flows). The root element
carries no `data-mock`; this is the implementation, and the mocks stay on disk as
the record of what was compared.
