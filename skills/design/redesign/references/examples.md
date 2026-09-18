# Example Invocations

Each example shows the stage path, the `redesign-review` evidence the run
produces, and the one decision that would otherwise be got wrong. Every example
assumes an active Admiral handoff; a cold invocation hands off to `admiral`
first.

## Contents

1. Inventory dashboard, decision made
2. Directions returned for insufficient differentiation
3. Full-parity build of the selected variant
4. Browserless host
5. Second REVISE on the same keys
6. A deferral, and the four keys that carry a string instead

## Example 1 — Inventory dashboard, decision made

**User request:** redesign the UI of our inventory dashboard, I want a few options

**Output:**
- Scope: the six dashboard routes and the two flows (receive stock, adjust count) that define parity; settings pages out of scope with a reopen trigger.
- Stage path: `design/design-mapper` inventory of 6 routes, 23 components, 4 flows, 11 interactions → `taste` grilling over 11 categories → `design/architect` four directions (quiet-editorial, dense-operational, warm-approachable, high-contrast-utility) → `design/prototyper` fanned out four ways into static mocks → `design/design-mapper` mock parity, `review/design-qa` mock captures → the choice put to the user → `design/prototyper` once for the chosen id → `design/design-mapper` full parity, `review/design-qa` rendering, `review/frontier` accessibility → recommendation → `design/gatekeeper-design`.
- Evidence assembled: `design_inventory`, `taste_grilling`, `taste_snapshot`, `design_directions`, `mock_set` (four mocks, unique ids, every spec, tokens, components, and mock file hashed), `mock_parity` at full route and component coverage, `mock_rendering` at six tiers in both themes, `selection` (`decision: variant`, `chosen: v2`, `recommended: v2`), `selected_variant` (one variant, id `v2`), `parity_evidence` at full coverage, `rendered_verification` at six tiers in both themes, `accessibility_evidence` with no open Critical, plus redesign's own `recommendation` and `residual_risk`.
- What was built once instead of four times: one `app.html`. The other three directions exist as mocks and nothing more, which is the point — the user saw four and paid for one.
- `residual_risk` recorded: the chosen direction's dense table behaviour was judged from a drawn screen and verified in one prototype; it may not reproduce identically in the production grid component. Owner is `design/architect`, and the reopen trigger is the first production render at `design-to-build`.
- Handoff: the package hands the selected variant's `variant.md`, `tokens.css`, and `components.html` — the living build's files, not the mock's — to `design/commander` as the design-system input; nothing was written to the application source.

## Example 2 — Directions returned for insufficient differentiation

**User request:** explore design directions before we rebuild the frontend

**Output:**
- Grilling: the user declines to persist preferences globally but confirms project scope, so `taste_snapshot` is the project-only effective profile and `taste_grilling` still records one decision per category.
- Differentiation check: the first set of directions is returned `REVISE` to `design/architect` because two directions differed only in palette. Differentiation is judged at stage 4, from prose, before any mock is commissioned — returning it later would waste four drawings, and returning it after a build would waste the build.
- Second set: diverges on density, typography, and component behaviour, satisfying the at-least-three-categories rule from `../../../design-doctrine.md` §9.
- Result: mock parity at full route and component coverage for all four mocks, the comparison matrix assembled from the mocks alone, recommendation recorded, and the decision deferred to the product owner.
- `residual_risk` recorded: the decision itself is open, with the product owner as owner and the next planning session as the reopen trigger. Nothing was implemented, and the package hands nothing to the design pipeline until the choice is made.

## Example 3 — Full-parity build of the selected variant

**User request:** give me a modern version of this app that still does everything the current one does

**Output:**
- Parity contract: 14 routes with 38 declared states, 31 components, 6 flows. At mock level the four mocks are scored on the 14 routes and 31 components alone, each carried through `data-route` and `data-component` markers; states, interactions, and flows come back as informational counts.
- Selection: the user picks `v3` after reading the four mocks side by side. `reports/selection.md` records the answer verbatim and the typed record carries `{decision: "variant", chosen: "v3", recommended: "v1"}` — the recommendation was not taken, and the package says so rather than rewriting it.
- The one build: `design/prototyper` builds `artifacts/variants/v3/` from `v3`'s tokens and catalog, wiring every one of the 38 states, 6 flows, and the interactions through `data-state`, `data-interaction`, and `data-flow`.
- Verification: `python skills/scripts/check_parity.py --level full` failed the variant on three missing states. The builder received the exact ids in one batched revision delegation and the second run reported full coverage.
- Whose record counts: the prototyper self-checks, but the `design/design-mapper` record is the `parity_evidence` the gate reads, bound by `inputs` to the inventory and prototype hashes.
- Delivery: four static mocks that open offline, one living single-page prototype that does the same with no build step and no network access, rendered captures at six tiers in both themes, and a recommendation.
- Before submitting: `python skills/harness/gatekeeper/check.py --boundary redesign-review --package redesign/manifest.json`, no `--verdict-out`; every mechanical failure is fixed first.

## Example 4 — Browserless host

**User request:** compare four redesigns before we commit (run on a CI host with no browser)

**Output:**
- Constraint: `review/design-qa` cannot capture anything, and `mock_rendering` is listed under `no_fallback` at `redesign-review`, so the key is still required and the sanctioned no-visible-surface string is rejected.
- Evidence: the `render` record for the mocks carries `result.status: inferred`, a limitation statement, and the label `INFERRED - no browser available` that `../../../gates.yaml` `evidence_type_rules.render` requires. The selected variant's `rendered_verification` carries an inferred record on the same terms once the build exists.
- Comparison matrix: rendering is marked unobserved for every mock, so the recommendation rests on mock parity coverage and Taste conformance alone, and says so.
- `residual_risk` recorded: rendering unverified across all four mocks and on the selected variant; owner is `review/design-qa`, and the reopen trigger is a capture run at the same hashes on a host with a browser.

## Example 5 — Second REVISE on the same keys

**User request:** (continuation) the gate came back REVISE again on `design_directions` and `mock_set`

**Output:**
- Cycle state: this is the second `REVISE` on `redesign-review`, which exhausts `../../../gates.yaml` `revise_policy.cycle_cap` of 2.
- Action: stop resubmitting. Escalate to Admiral with both revise packets, both verdict records, and the unclosed keys named with their owners (`design_directions` → `design/architect`, `mock_set` → `design/prototyper`).
- Why the cap exists: two failed cycles on the same keys mean the disagreement is about the requirement — where the differentiation bar sits, what the mock parity contract covers — rather than about the artifact.
- What Admiral receives: the dispute, the recommended default for each key, and both revisions preserved as evidence rather than overwritten into one history.

## Example 6 — A deferral, and the four keys that carry a string instead

**User request:** (continuation) the team wants to sit with the four mocks for a week before choosing

**Output:**
- Selection: `{decision: "deferred", chosen: null, recommended: "v4", decided_by: "head of product", basis: "wants the warehouse leads to use the mocks in a session first"}`, with the same words in `reports/selection.md`.
- What is not delegated: `selected-build`, `parity-verification`, `visual-qa`, and `frontend-review`. Those four stages run only when a variant was selected, so none of them runs here.
- What the four dependent keys carry: `selected_variant`, `parity_evidence`, `rendered_verification`, and `accessibility_evidence` each carry `selection deferred - no variant built`, the sanctioned wording for this decision, as the `reason` of an applicability record `{applicable: false, reason, scope, decided_by}` — never as a bare string, which `check.py` refuses at schema 2. A built variant beside that wording, or that wording beside a built variant, fails mechanically.
- What still gates: `mock_set`, `mock_parity`, `mock_rendering`, `selection`, `recommendation`, and `residual_risk` are complete, so the package is gate-eligible as a deferral rather than being held open.
- `residual_risk` recorded: the decision, owner head of product, reopen trigger the review session in seven days; and the fact that no direction has been proven at full parity, which is what the selected build would have established.
