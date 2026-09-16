# Example Invocations

## Example 1

**User request:** map the current UI of the admin app

**Output:**
- Routes: 9, read from `src/app/**/page.tsx`; two unrouted modals recorded under their host routes.
- Components: 27 with shadcn mappings for 19; `PrimaryButton` and `Button` flagged as duplicates.
- Tokens: 14 declared CSS variables, 6 hard-coded hex values with file locations, one off-scale spacing value.
- Baseline: 108 captures (9 routes, 6 tiers, 2 themes) under `redesign/evidence/baseline/`; inventory hashed and returned.

## Example 2

**User request:** document what the interface does today, we have no dev server

**Output:**
- Structure mapped from source; reachability of `permission-denied` states marked `inferred` because no running surface existed.
- Baseline: INFERRED record with the limitation "no browser available; captures pending a running instance".
- Report: inconsistencies section lists 4 duplicate components and 11 hard-coded colours; accessibility baseline lists 2 Major contrast findings from source values.

## Example 3

**User request:** check that variant three reproduces the existing app

**Output:**
- Command: `python skills/scripts/check_parity.py --inventory redesign/artifacts/inventory/design-inventory.json --app redesign/artifacts/variants/v3/app.html --components redesign/artifacts/variants/v3/components.html --out redesign/evidence/parity-v3.json`
- Result: routes 9/9, states 34/36, components 27/27, interactions 12/12, flows 4/4; status `fail`.
- Returned: the two missing states (`route.orders:empty`, `route.orders:error`) to `design/redesign` for one batched revision by `design/prototyper`.
