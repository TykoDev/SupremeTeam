# Key Spaces Reference

Read this when a validator's finding names a key that also appears in
`../../../gates.yaml`, or when a capture key comes back `UNCHECKED`. `../SKILL.md`
states the two decision rules; this file carries the name-by-name detail behind
them.

## Contents

1. The two key spaces collide by name
2. The capture-key requirement discrepancy

### The two key spaces collide by name

The shape keys are declared by the two scripts; the evidence keys are declared by
`../../../gates.yaml`. Nine names appear in both spaces meaning different things,
and reading a `PASS` on the left as satisfaction of the right is how a package
advances with a file present and its evidence key empty.

| Name | As a shape key (script) | As an evidence key (`../../../gates.yaml`) |
| --- | --- | --- |
| `plan` | `check.py`: a `*plan*.md` file exists in the package directory | required at `design-to-build`, artifact-backed — a path in `artifact_hashes` |
| `architecture` | `check.py`: an `*architect*.md` or `*adr*.md` file exists | required at `design-to-build`, artifact-backed |
| `taste_snapshot` | `check.py`: a `*taste*snapshot*` file carrying digest/source markers | required at both boundaries, artifact-backed, waivable |
| `stack_locks` / `stack_lock` | `check.py` `stack_locks`: any `*stack*.md`, `*lock*.md`, or `*tech*.md` file | spec `stack_lock`: a typed record `{slug, versions, overlay_sha256}` validated against `../../../tech-stacks/registry.yaml` |
| `design_inventory` | `check_redesign.py`: a `*design-inventory*` file exists | required at `redesign-review`, artifact-backed |
| `taste_grilling` | `check_redesign.py`: a grilling log file exists | required at `redesign-review`, artifact-backed |
| `design_directions` | `check_redesign.py`: `*direction*.md` files exist | required at `redesign-review`, artifact-backed |
| `parity_evidence` | `check_redesign.py`: a `*parity*.json` file exists | the full-level `probe` record for the selected variant, bound by `inputs` to the inventory and prototype files; conditional on `selection.decision` |
| `rendered_verification` | `check_redesign.py`: conditional — a `*render*` or `*capture*` file, absence reported `UNCHECKED` | a `render` record for the selected variant with hashed captures, breakpoints, themes, and bound `inputs`; conditional on `selection.decision` |

A shape key and an evidence key of the same name answer different questions, and
several evidence keys have no shape counterpart at all — `decisions`,
`interfaces`, `acceptance`, `security_seed`, `ui_evidence`, `mock_set`,
`mock_parity`, `mock_rendering`, `selection`, `selected_variant`,
`accessibility_evidence`, `recommendation`, `residual_risk` — while the shape
keys `research`, `impl_spec`, `api_contracts`, and `ui_handoff` have no evidence
counterpart. Read `../scripts/check_redesign.py` for the current shape manifest
rather than this table's memory of it. Neither absence is a defect in the other
validator; it is why both run.

### The capture-key requirement discrepancy

`../scripts/check_redesign.py` declares the capture keys with
`requirement="conditional"`, so their absence from the redesign phase directory is
reported `UNCHECKED` rather than `FAIL`. `../../../gates.yaml` lists `mock_rendering`
under `redesign-review`'s `no_fallback`, where it is neither waivable nor
optional. The two are answering different questions, and the discrepancy is
recorded here rather than repaired in the script:

- The script asks whether a capture file is present, and cannot know which filenames a given redesign produced; marking it `required` would fail honest packages on a naming mismatch.
- The spec asks whether the evidence key carries a hashed `render` record, which the boundary validator can answer exactly.
- Therefore: treat the script's `UNCHECKED` on `mock_rendering` as **unresolved, never as a waiver**. The boundary validator is the authority, and it fails the key outright.
- On `rendered_verification` the same `UNCHECKED` is resolved against the selection: when a variant was selected the key owes a `render` record and the boundary validator fails it outright; when the decision was a merge or a deferral no prototype exists, and the key legitimately carries its sanctioned wording as the `reason` of an applicability record.
