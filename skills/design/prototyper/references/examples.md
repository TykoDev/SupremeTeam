# Example Invocations

## Example 1

**User request:** build variant two (dense-operational) from the directions

**Output:**
- Files: `redesign/artifacts/variants/v2/{variant.md,tokens.css,components.css,components.js,components.html,app.html}` with sha256 digests.
- Prototype: 9 routes under hash routing, 36 declared states reachable from the state switcher, 12 interactions and 4 flows wired against mocked data.
- Self-check: full coverage on all five lists; contrast verified at 4.6:1 body text in both themes.

## Example 2

**User request:** the mapper says variant two is missing two states

**Output:**
- Missing: `route.orders:empty` and `route.orders:error`.
- Fix: the orders view now renders both states from the switcher with `data-route-state` markers; mocked data gained an empty dataset and a failing fetch stub.
- Returned: updated `app.html` and `variant.md` (state coverage matrix) with new hashes; the mapper re-runs the parity check.

## Example 3

**User request:** the direction wants a pale amber on cream for body text

**Output:**
- Measured: 2.8:1, below the 4.5:1 floor.
- Adjustment: `--foreground` deepened to the nearest passing amber-brown at 4.6:1; the pale amber kept for large headings only, where 3:1 passes.
- Recorded: the deviation and its reason in `variant.md`; reported to `design/redesign` as a Minor finding against the direction.
