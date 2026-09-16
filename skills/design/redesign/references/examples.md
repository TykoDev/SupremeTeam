# Example Invocations

Each example shows the stage path, the `redesign-review` evidence the run
produces, and the one decision that would otherwise be got wrong. Every example
assumes an active Admiral handoff; a cold invocation hands off to `admiral`
first.

## Contents

1. Inventory dashboard, decision made
2. Directions returned for insufficient differentiation
3. Full-parity rebuild with a failed variant
4. Browserless host
5. Second REVISE on the same keys

## Example 1 — Inventory dashboard, decision made

**User request:** redesign the UI of our inventory dashboard, I want a few options

**Output:**
- Scope: the six dashboard routes and the two flows (receive stock, adjust count) that define parity; settings pages out of scope with a reopen trigger.
- Stage path: `design/design-mapper` inventory of 6 routes, 23 components, 4 flows, 11 interactions → `taste` grilling over 11 categories → `design/architect` four directions (quiet-editorial, dense-operational, warm-approachable, high-contrast-utility) → `design/prototyper` fanned out four ways → `design/design-mapper` parity, `review/design-qa` rendering, `review/frontier` accessibility → comparison and decision → `design/gatekeeper-design`.
- Evidence assembled: `design_inventory`, `taste_grilling`, `taste_snapshot`, `design_directions`, `variant_set` (four variants, unique ids, every spec, tokens, components, and app file hashed), `parity_evidence` at full coverage per variant, `rendered_verification` at six tiers in both themes, `accessibility_evidence` with no open Critical, plus redesign's own `recommendation` and `residual_risk`.
- `residual_risk` recorded: the chosen variant's dense table behaviour was verified in a prototype and may not reproduce identically in the production grid component; owner is `design/architect`, and the reopen trigger is the first production render at `design-to-build`.
- Handoff: the package hands the chosen variant's `variant.md`, `tokens.css`, and `components.html` to `design/commander` as the design-system input; nothing was written to the application source.

## Example 2 — Directions returned for insufficient differentiation

**User request:** explore design directions before we rebuild the frontend

**Output:**
- Grilling: the user declines to persist preferences globally but confirms project scope, so `taste_snapshot` is the project-only effective profile and `taste_grilling` still records one decision per category.
- Differentiation check: the first set of directions is returned `REVISE` to `design/architect` because two directions differed only in palette. Differentiation is judged at stage 4, from prose, before any prototype is commissioned — returning it later would waste four builds.
- Second set: diverges on density, typography, and component behaviour, satisfying the at-least-three-categories rule from `../../../design-doctrine.md` §9.
- Result: parity at full coverage for all four variants, one Major accessibility finding fixed in variant three before it entered the comparison, recommendation recorded, and the decision deferred to the product owner.
- `residual_risk` recorded: the decision itself is open, with the product owner as owner and the next planning session as the reopen trigger. The package hands nothing to the design pipeline until the choice is made.

## Example 3 — Full-parity rebuild with a failed variant

**User request:** give me a modern version of this app that still does everything the current one does

**Output:**
- Parity contract: 14 routes with 38 declared states, 31 components, 6 flows; every id carried into each prototype through `data-route`, `data-state`, `data-component`, `data-interaction`, and `data-flow` markers.
- Verification: `python skills/scripts/check_parity.py` failed variant two on three missing states. The builder received the exact ids in one batched revision delegation and the second run reported full coverage.
- Whose record counts: the prototyper self-checks, but the `design/design-mapper` record is the `parity_evidence` the gate reads, bound by `inputs` to the inventory and prototype hashes.
- Delivery: four living single-page prototypes that open offline with no build step and no network access, four component catalogs, rendered captures at six tiers in both themes, and a recommendation.
- Before submitting: `python skills/harness/gatekeeper/check.py --boundary redesign-review --package redesign/manifest.json`, no `--verdict-out`; every mechanical failure is fixed first.

## Example 4 — Browserless host

**User request:** compare four redesigns before we commit (run on a CI host with no browser)

**Output:**
- Constraint: `review/design-qa` cannot capture the prototypes, and `rendered_verification` is listed under `no_fallback` at `redesign-review`, so the key is still required and the sanctioned no-visible-surface string is rejected.
- Evidence: the `render` record carries `result.status: inferred`, a limitation statement, and the label `INFERRED - no browser available` that `../../../gates.yaml` `evidence_type_rules.render` requires.
- Comparison matrix: rendering is marked unobserved for every variant, so the recommendation rests on parity coverage, accessibility findings, and Taste conformance alone, and says so.
- `residual_risk` recorded: rendering unverified across all four variants; owner is `review/design-qa`, and the reopen trigger is a capture run at the same variant hashes on a host with a browser.

## Example 5 — Second REVISE on the same keys

**User request:** (continuation) the gate came back REVISE again on `design_directions` and `variant_set`

**Output:**
- Cycle state: this is the second `REVISE` on `redesign-review`, which exhausts `../../../gates.yaml` `revise_policy.cycle_cap` of 2.
- Action: stop resubmitting. Escalate to Admiral with both revise packets, both verdict records, and the unclosed keys named with their owners (`design_directions` → `design/architect`, `variant_set` → `design/prototyper`).
- Why the cap exists: two failed cycles on the same keys mean the disagreement is about the requirement — where the differentiation bar sits, what the parity contract covers — rather than about the artifact.
- What Admiral receives: the dispute, the recommended default for each key, and both revisions preserved as evidence rather than overwritten into one history.
