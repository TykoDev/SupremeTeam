# Example Invocations

Four delegations and the actual artifacts returned: inventory rows, a report
excerpt, and a parity record at each level. The schema and marker rules behind
them are in `workflow.md`.

## Contents

1. Example 1 — "map the current UI of the admin app"
2. Example 2 — "document what the interface does today, we have no dev server"
3. Example 3 — "check the four mocks against the inventory"
4. Example 4 — "check that the selected variant reproduces the existing app"

## Example 1 — "map the current UI of the admin app"

Returned: `design-inventory.json` and `design-inventory.md` with 9 routes, 27
components, 14 declared tokens, and 108 baseline captures. Representative rows
from the JSON, verbatim:

```json
{
  "routes": [
    {"id": "route.orders", "path": "/orders", "purpose": "order queue triage",
     "primary_action": "interaction.claim-order",
     "states": ["loading", "empty", "error", "success", "permission-denied"],
     "components": ["component.table", "component.button", "component.badge"],
     "source": "src/app/orders/page.tsx"}
  ],
  "components": [
    {"id": "component.badge", "name": "Badge", "shadcn": "Badge",
     "variants": ["default", "warning", "destructive"], "sizes": ["sm"],
     "states": ["default"], "source": "src/components/ui/badge.tsx",
     "usage_count": 12,
     "inconsistency": "PrimaryButton duplicates component.button with a hard-coded radius"}
  ],
  "tokens": {
    "off_scale": [{"value": "13px", "location": "src/components/Badge.tsx:12"},
                  {"value": "#3b82f6", "location": "src/app/orders/page.tsx:88"}]
  },
  "accessibility_baseline": [
    {"id": "a11y.contrast.muted", "severity": "Major",
     "location": "src/styles/globals.css:40",
     "description": "muted foreground on background measures 3.9:1"}
  ],
  "limitations": []
}
```

Returned with it: `design-inventory.md` (the human report), the baseline captures
under `redesign/evidence/baseline/` at 320, 375, 640, 1024, 1440, and 1920 px in
both themes, and the sha256 of both inventory files.

## Example 2 — "document what the interface does today, we have no dev server"

Structure mapped from source; no browser, so the baseline is an INFERRED record.
The report's limitations and inconsistencies sections, verbatim:

```markdown
## Limitations

- **Baseline captures: INFERRED.** No running instance and no supplied captures.
  Contrast findings below are computed from declared token values, not measured
  from rendered pixels. Captures are pending a running instance; the inventory is
  otherwise complete from source.
- **Reachability of `route.orders:permission-denied` is `inferred`.** The state is
  rendered by `src/app/orders/page.tsx:214` behind a role guard that source alone
  cannot exercise. It is in the inventory and the selected variant must still
  render it.

## Inconsistencies

| Id | Finding | Location |
| -- | ------- | -------- |
| component.button / component.primary-button | Two components render the same shadcn Button primitive under different names | `src/components/ui/button.tsx`, `src/components/PrimaryButton.tsx` |
| tokens.color.hardcoded | 11 hard-coded hex colours bypass the declared palette | listed in `tokens.off_scale` with file and line |

## Accessibility baseline

| Id | Severity | Finding | Location |
| -- | -------- | ------- | -------- |
| a11y.contrast.muted | Major | muted foreground 3.9:1, below the 4.5:1 body floor | `src/styles/globals.css:40` |
| a11y.contrast.badge-warning | Major | warning badge text 3.1:1 on its own fill | `src/components/ui/badge.tsx:22` |
```

The inventory is returned as complete-with-limitations, not as blocked: the
redesign proceeds, and the limitation travels with it.

## Example 3 — "check the four mocks against the inventory"

The `mock-parity` stage, run once per mock at mock level. Two of the four
abridged, then the aggregate.

```bash
python skills/scripts/check_parity.py --level mock --inventory redesign/artifacts/inventory/design-inventory.json --app redesign/artifacts/mocks/v1/mock.html --components redesign/artifacts/mocks/v1/components.html --out redesign/evidence/mock-parity-v1.json --project-root .
```

`v1` — exit 0. The record, abridged:

```json
{
  "kind": "probe",
  "tool": "check_parity.py",
  "level": "mock",
  "artifacts": ["redesign/evidence/mock-parity-v1.json"],
  "inputs": [
    {"path": "redesign/artifacts/inventory/design-inventory.json", "sha256": "9f2c…"},
    {"path": "redesign/artifacts/mocks/v1/mock.html", "sha256": "b104…"},
    {"path": "redesign/artifacts/mocks/v1/components.html", "sha256": "55de…"}
  ],
  "min_coverage": 1.0,
  "coverage": 1.0,
  "scored": ["routes", "components"],
  "lists": {
    "routes": {"expected": 9, "found": 9, "missing": []},
    "components": {"expected": 27, "found": 27, "missing": []},
    "states": {"expected": 36, "found": 2, "informational": true},
    "interactions": {"expected": 12, "found": 0, "informational": true},
    "flows": {"expected": 4, "found": 0, "informational": true}
  },
  "result": {"status": "pass", "summary": "36/36 scored ids present"}
}
```

Read the three informational lines the way they are meant: `v1` wires nothing and
draws two route states, which is exactly what a mock is. None of those counts can
fail the level, and returning a mock because it scored 0 of 12 interactions would
ask its builder to implement before the user has chosen.

`v3` — exit 1, missing `component.badge` and `component.breadcrumb`. Those are
scored, so `v3` goes back to `design/prototyper` with those two ids and stays out
of the comparison until it comes back.

The aggregate, once all four pass, is one probe record of the same shape whose
`artifacts` list names the four per-mock records:

```json
{
  "kind": "probe",
  "tool": "check_parity.py",
  "level": "mock",
  "artifacts": [
    "redesign/evidence/mock-parity-v1.json",
    "redesign/evidence/mock-parity-v2.json",
    "redesign/evidence/mock-parity-v3.json",
    "redesign/evidence/mock-parity-v4.json"
  ],
  "min_coverage": 1.0,
  "coverage": 1.0,
  "result": {"status": "pass", "summary": "4 mocks at full route and component coverage"}
}
```

That aggregate is what `design/redesign` packages as `mock_parity`.

## Example 4 — "check that the selected variant reproduces the existing app"

The `parity-verification` stage. It runs only when a variant was selected, so the
first move is to read the `selection` record: `{decision: "variant", chosen:
"v3"}`. Command run, exactly as the workflow specifies it. `--project-root .` is
not optional dressing: it makes the record's `inputs[].path` values
project-relative, which is what the gate binds by sha256.

```bash
python skills/scripts/check_parity.py --level full --inventory redesign/artifacts/inventory/design-inventory.json --app redesign/artifacts/variants/v3/app.html --components redesign/artifacts/variants/v3/components.html --out redesign/evidence/parity-v3.json --project-root .
```

Exit 1 — missing ids. The record it wrote, abridged to the failing lists:

```json
{
  "kind": "probe",
  "tool": "check_parity.py",
  "level": "full",
  "artifacts": ["redesign/evidence/parity-v3.json"],
  "inputs": [
    {"path": "redesign/artifacts/inventory/design-inventory.json", "sha256": "9f2c…"},
    {"path": "redesign/artifacts/variants/v3/app.html", "sha256": "41ab…"},
    {"path": "redesign/artifacts/variants/v3/components.html", "sha256": "7d0e…"}
  ],
  "min_coverage": 1.0,
  "coverage": 0.9773,
  "lists": {
    "routes": {"expected": 9, "found": 9, "missing": []},
    "states": {"expected": 36, "found": 34,
               "missing": ["route.orders:empty", "route.orders:error"]},
    "components": {"expected": 27, "found": 27, "missing": [],
                   "missing_in_catalog": [], "missing_in_app": []},
    "interactions": {"expected": 12, "found": 12, "missing": []},
    "flows": {"expected": 4, "found": 4, "missing": []}
  },
  "result": {"status": "fail", "summary": "86/88 inventory ids present"}
}
```

Returned to `design/redesign`: the record path, `status: fail`, and the two exact
missing ids for one batched revision by `design/prototyper`. The threshold is not
lowered and the prototype is not edited here.

Note which list failed. `route.orders:empty` and `route.orders:error` were
informational when `v3` was a mock and are scored now that it is the one built
variant — the same two ids, a defect only at the level where the surface is
supposed to behave.
