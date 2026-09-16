# Example Invocations

Three delegations and the actual artifacts returned: inventory rows, a report
excerpt, and a parity record. The schema and marker rules behind them are in
`workflow.md`.

## Contents

1. Example 1 — "map the current UI of the admin app"
2. Example 2 — "document what the interface does today, we have no dev server"
3. Example 3 — "check that variant three reproduces the existing app"

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
  cannot exercise. It is in the inventory and the prototype must still render it.

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

## Example 3 — "check that variant three reproduces the existing app"

Command run, exactly as the workflow specifies it. `--project-root .` is not
optional dressing: it makes the record's `inputs[].path` values project-relative,
which is what the gate binds by sha256.

```bash
python skills/scripts/check_parity.py \
  --inventory redesign/artifacts/inventory/design-inventory.json \
  --app redesign/artifacts/variants/v3/app.html \
  --components redesign/artifacts/variants/v3/components.html \
  --out redesign/evidence/parity-v3.json \
  --project-root .
```

Exit 1 — missing ids. The record it wrote, abridged to the failing lists:

```json
{
  "kind": "probe",
  "tool": "check_parity.py",
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
