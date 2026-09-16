# Boundary Evidence Reference

Read this when a design or redesign submission is in hand and the question is
*what a specific key must be* — a hashed artifact or a claim, which typed record
shape, and whether a waiver is admissible. `../SKILL.md` carries the boundary
table, the owner tables, and the two key spaces; this file carries the per-key
detail. `../../../gates.yaml` is the authority: where this file and the spec
disagree, the spec wins and this file is the defect.

## Contents

1. `design-to-build`, key by key
2. `redesign-review`, key by key
3. Sanctioned waivers, verbatim
4. Why `rendered_verification` behaves differently at `redesign-review`

## 1. `design-to-build`, key by key

Submitter `commander`. Nine required keys; four artifact-backed.

| Key | Backing | Record type | What the validator enforces |
| --- | --- | --- | --- |
| `decisions` | artifact | untyped | a path in `artifact_hashes`. Backed by the intake grilling report, so a package whose decisions trace to nothing fails mechanically rather than on judgment |
| `architecture` | artifact | untyped | a path in `artifact_hashes` |
| `plan` | artifact | untyped | a path in `artifact_hashes` |
| `taste_snapshot` | artifact | untyped | a path in `artifact_hashes`, or a sanctioned applicability record |
| `stack_lock` | claim | `stack_lock` | `{slug, versions, overlay_sha256}` checked against `../../../tech-stacks/registry.yaml`: the slug exists, the overlay digest matches both the registry and the file, and the versions intersect |
| `interfaces` | claim | untyped | present and non-falsy |
| `acceptance` | claim | untyped | present and non-falsy. This is the criteria build will be measured against, so an empty-but-wordy value is a judgment failure the validator cannot see |
| `security_seed` | claim | untyped | present and non-falsy. The threat-model seed `security-builder` answers at build |
| `ui_evidence` | claim | untyped | present and non-falsy, or a sanctioned applicability record |

## 2. `redesign-review`, key by key

Submitter `redesign`. Ten required keys; seven artifact-backed.

| Key | Backing | Record type | What the validator enforces |
| --- | --- | --- | --- |
| `design_inventory` | artifact | untyped | a path in `artifact_hashes`; the JSON parity contract the probes bind to |
| `taste_grilling` | artifact | untyped | a path in `artifact_hashes` |
| `taste_snapshot` | artifact | untyped | a path in `artifact_hashes`, or a sanctioned applicability record |
| `design_directions` | artifact | untyped | a path in `artifact_hashes`. Differentiation between the directions is judgment (`../../../design-doctrine.md` §9), not a mechanical check |
| `variant_set` | artifact | `variant_set` | `{artifacts, variants: [{id, name, direction, spec, tokens, components, app}], count}`. Exactly `evidence_type_params.variant_set.required_count` variants — four — with unique ids; every variant's `spec`, `tokens`, `components`, and `app` correctly hashed in the package; `count`, when present, equal to the list length |
| `parity_evidence` | artifact | `probe` | one `check_parity.py` probe record — a single mapping covering the whole variant set, with hashed artifacts and `result.status: pass`. A list of per-variant records fails with `parity_evidence must be a typed probe record at schema 2`. `inputs` is *optional* on a `probe` (only `scan` and `render` records must bind it) and is checked by sha256 only when supplied, so whether the record actually binds to the inventory and the prototype files is judgment, not a mechanical check |
| `rendered_verification` | artifact | `render` | hashed captures, the breakpoints and themes covered, `inputs` bound to the rendered source, and `result.status` `pass` or `inferred`. No waiver is admissible here; see §4 |
| `accessibility_evidence` | claim | `findings` | `{items: [{id, severity, status, …}]}` under the shared severity model and the finding policy |
| `recommendation` | claim | untyped | present and non-falsy |
| `residual_risk` | claim | untyped | present and non-falsy |

## 3. Sanctioned waivers, verbatim

A waiver is a typed applicability record — `{applicable: false, reason, scope,
decided_by}`. The validator checks three things about it: that `applicable` is
`false`, that the key is waivable at this boundary, and that `reason`, `scope`,
and `decided_by` are each a non-empty string. A waiver on a key not listed below
fails mechanically with `evidence not waivable: <key>`.

The reason *text* is not mechanically checked. `applicability_record()` never
compares `reason` against `fallback_values`, so an invented reason on a waivable
key passes the validator untouched. The strings below are still the only reasons
the gate accepts — but enforcing that is judgment at the gate, not a machine
failure, so a waiver carrying any other reason is a judgment finding the verdict
has to name itself.

| Key | Boundary | The only sanctioned reason |
| --- | --- | --- |
| `stack_lock` | `design-to-build` | no new runtime or framework - existing stack unchanged |
| `ui_evidence` | `design-to-build` | no user-facing surface - design system not engaged |
| `taste_snapshot` | both | no saved Taste profile available |
| `rendered_verification` | *not at `redesign-review`* | no visible surface changed - rendered verification not applicable |

Six `design-to-build` keys and nine `redesign-review` keys accept no fallback at
all, so a bare explanatory string in place of any of them fails before judgment
begins.

## 4. Why `rendered_verification` behaves differently at `redesign-review`

`../../../gates.yaml` lists `rendered_verification` under `redesign-review`'s
`no_fallback`. At that boundary the key accepts neither the sanctioned string in
§3 nor an applicability record, even though the global fallback exists everywhere
else the key appears.

The reasoning is substantive rather than procedural: a redesign changes a visible
surface by definition, so "no visible surface changed" cannot be a true statement
about a redesign package. A boundary-level `no_fallback` beats a global fallback;
never grant a waiver the boundary refuses.

Two consequences at the gate:

- An attempted waiver is a `REVISE` routed to `design-qa`, asking for hashed captures across the required breakpoints and themes, bound by `inputs` to the rendered variant.
- The `UNCHECKED` that `../scripts/check_redesign.py` reports when no capture file is found is an unresolved question, not permission. `../SKILL.md` records why the script keeps that key conditional while the spec refuses every waiver on it.

## Cross-references

- `../../../gates.yaml` — the authority for everything on this page.
- `../SKILL.md` — boundary table, owner routing, key-space collisions, failure modes.
- `workflow.md` — the order these checks run in.
- `examples.md` — worked submissions at both boundaries.
