# Example Invocations

## Example 1

**User request:** redesign the UI of our inventory dashboard, I want a few options

**Output:**
- Scope: the six dashboard routes and the two flows (receive stock, adjust count) that define parity; settings pages out of scope with a reopen trigger.
- Stage order: inventory of 6 routes, 23 components, 4 flows, and 11 interactions; taste grilling over 11 categories; four directions (quiet-editorial, dense-operational, warm-approachable, high-contrast-utility); four prototypes; parity, render, and accessibility evidence per variant.
- Decision: the user chose the dense-operational variant; the package hands its `variant.md`, `tokens.css`, and `components.html` to `design/commander` as the design-system input.

## Example 2

**User request:** explore design directions before we rebuild the frontend

**Output:**
- Grilling: the user declines to persist preferences globally but confirms project scope; `taste_snapshot` is the project-only effective profile.
- Directions: architect proposes four; the gate returned `REVISE` once because two directions differed only in palette, and the second set diverged on density, typography, and component behaviour.
- Result: comparison matrix with parity at full coverage for all four, one Major accessibility finding fixed in variant three before comparison, recommendation recorded, decision deferred to the product owner with a reopen trigger on the next planning session.

## Example 3

**User request:** give me a modern version of this app that still does everything the current one does

**Output:**
- Parity contract: 14 routes with 38 declared states, 31 components, 6 flows; every id carried into each prototype through `data-route`, `data-state`, `data-component`, `data-interaction`, and `data-flow` markers.
- Verification: `check_parity.py` failed variant two on three missing states; the builder received the exact ids in one batched revision and the second run passed.
- Delivery: four living single-page prototypes that open offline, four component catalogs, rendered captures at six tiers in both themes, and a recommendation; nothing was written to the application source.
