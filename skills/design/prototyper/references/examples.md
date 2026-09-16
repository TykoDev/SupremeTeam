# Example Invocations

Three delegations and the actual files returned: token values, marked markup, and
`variant.md` rows. The build order, marker rules, and self-check command are in
`workflow.md`.

## Contents

1. Example 1 — "build variant two (dense-operational) from the directions"
2. Example 2 — "the mapper says variant two is missing two states"
3. Example 3 — "the direction wants a pale amber on cream for body text"

## Example 1 — "build variant two (dense-operational) from the directions"

Returned: `redesign/artifacts/variants/v2/{variant.md,tokens.css,components.css,components.js,components.html,app.html}`
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

`app.html` — the orders view with every marker the checker reads:

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

`variant.md` — the Taste traceability and state coverage rows:

```markdown
| Decision | Traced to | Snapshot digest |
| -------- | --------- | --------------- |
| 13px base type, 4px spacing unit | taste:density/`prefers compact operational tables` (hard) | sha256:4c7e… |
| 0.25rem radius, one elevation | taste:visual-style/`plain surfaces, no decorative depth` (strong) | sha256:4c7e… |
| 120ms transitions, none on lists | taste:motion/`motion only for state change` (soft) | sha256:4c7e… |

| Route | loading | empty | error | success | permission-denied |
| ----- | ------- | ----- | ----- | ------- | ----------------- |
| route.orders | ✓ | ✓ | ✓ | ✓ | ✓ |
| route.dashboard | ✓ | ✓ | ✓ | ✓ | n/a |
```

**Self-check**: exit 0, coverage 1.0 across all five lists (9 routes, 36 states,
27 components, 12 interactions, 4 flows); body contrast measured 4.8:1 light and
4.7:1 dark.

## Example 2 — "the mapper says variant two is missing two states"

Two ids returned by `design/design-mapper`: `route.orders:empty` and
`route.orders:error`. The fix, in `app.html`:

```html
<div data-route-state="route.orders:empty" hidden>
  <p>No orders in this queue.</p>
  <button data-interaction="interaction.refresh-queue">Refresh</button>
</div>
<div data-route-state="route.orders:error" hidden>
  <p role="alert">Could not load the queue.</p>
  <button data-interaction="interaction.refresh-queue">Retry</button>
</div>
```

```js
// mock state gained the two datasets the switcher needs
const fixtures = {
  "route.orders": {
    success: orders,
    empty:   [],
    error:   { fail: true, message: "Could not load the queue." },
  },
};
```

**Returned**: updated `app.html` and `variant.md` (state coverage matrix now ✓ for
both cells) with new sha256 digests, in one revision rather than two. The mapper
re-runs the authoritative parity check; the prototyper does not edit the record.

## Example 3 — "the direction wants a pale amber on cream for body text"

The direction's palette fails the accessibility floor, so the token moves and the
deviation is recorded rather than the floor being lowered.

```markdown
## Deviation — body text contrast

**Direction asked for**: `--foreground: oklch(0.82 0.11 80)` (pale amber) on
`--background: oklch(0.97 0.02 85)` (cream).
**Measured**: 2.8:1, below the 4.5:1 WCAG 2.2 AA floor for body text.
**Applied**: `--foreground: oklch(0.44 0.08 65)` — the nearest amber-brown that
measures 4.6:1 on the same cream. The pale amber is kept for headings at 24px and
above, where it measures 3.2:1 against the 3:1 large-text floor.
**Why not the direction's value**: `../../../design-doctrine.md` §6 treats an
inaccessible flow as broken, not unpolished; a variant that ships failing contrast
cannot be compared fairly against three that do not.
**Reported**: Minor finding against the direction, returned to `design/redesign`.
```

The direction's intent survives — warm, low-contrast, amber-led — and the body
text is legible. Both facts are in `variant.md` so the comparison is honest.
