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
4. Why `mock_rendering` behaves differently at `redesign-review`
5. The four selection-dependent keys

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

Submitter `redesign`. Fourteen required keys; eleven artifact-backed.

The order is the pipeline's order, and it matters: everything above `selection`
is drawn and measured, everything below it is implementation that the selection
authorised.

| Key | Backing | Record type | What the validator enforces |
| --- | --- | --- | --- |
| `design_inventory` | artifact | untyped | a path in `artifact_hashes`; the JSON parity contract the probes bind to |
| `taste_grilling` | artifact | untyped | a path in `artifact_hashes` |
| `taste_snapshot` | artifact | untyped | a path in `artifact_hashes`, or a sanctioned applicability record |
| `design_directions` | artifact | untyped | a path in `artifact_hashes`. Differentiation between the directions is judgment (`../../../design-doctrine.md` §9), not a mechanical check |
| `mock_set` | artifact | `variant_set` | `{artifacts, mocks: [{id, name, direction, spec, tokens, components, mock}], count}`. Exactly `evidence_type_params.mock_set.required_count` mocks — four — with unique ids; every mock's `spec`, `tokens`, `components`, and `mock` correctly hashed in the package; `count`, when present, equal to the list length. That each draft stayed a static mock is judgment: the record shape is identical for an implementation |
| `mock_parity` | artifact | `probe` | one `check_parity.py --level mock` probe record — a single mapping covering the whole mock set, with hashed artifacts and `result.status: pass`. A list of per-mock records fails the same way `parity_evidence` does. Mock level scores routes and components; the state, interaction, and flow counts it carries are informational and must not be read as failures |
| `mock_rendering` | artifact | `render` | hashed captures of the mock screens, the breakpoints and themes covered, `inputs` bound to the rendered source, and `result.status` `pass` or `inferred`. No waiver is admissible here; see §4 |
| `selection` | artifact | `selection` | `{schema_version, artifacts, decision, chosen, recommended, decided_by, decided_at, basis}`. `decision` is `variant`, `merge`, or `deferred`; `variant` requires a non-null `chosen` that is a `mock_set` id, and `merge` and `deferred` require `chosen: null`; `recommended` is always a `mock_set` id; `reports/selection.md` is a hashed artifact. That the recorded decision is a person's rather than the recommendation restated is judgment |
| `selected_variant` | artifact | `variant_set` | `{artifacts, variants: [{id, name, direction, spec, tokens, components, app}], count}`. Exactly one variant, whose id equals `selection.chosen`; `spec`, `tokens`, `components`, and `app` correctly hashed. Conditional on `selection.decision`; see §5 |
| `parity_evidence` | artifact | `probe` | one `check_parity.py --level full` probe record for the selected variant — a single mapping with hashed artifacts and `result.status: pass`. A list of per-variant records fails with `parity_evidence must be a typed probe record at schema 2`. `inputs` is *optional* on a `probe` (only `scan` and `render` records must bind it) and is checked by sha256 only when supplied, so whether the record actually binds to the inventory and the prototype files is judgment, not a mechanical check. Conditional on `selection.decision` |
| `rendered_verification` | artifact | `render` | hashed captures of the selected variant, the breakpoints and themes covered, `inputs` bound to the rendered source, and `result.status` `pass` or `inferred`. Conditional on `selection.decision`; unlike `mock_rendering` it is not under `no_fallback` here |
| `accessibility_evidence` | claim | `findings` | `{items: [{id, severity, status, …}]}` under the shared severity model and the finding policy, graded on the selected variant. Conditional on `selection.decision` |
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
| `rendered_verification` | `review-to-delivery` only | no visible surface changed - rendered verification not applicable |

Most keys at both boundaries accept no waiver at all, so a bare explanatory string
in place of one of them fails before judgment begins. The `redesign-review`
did-not-arise wordings in §5 are a separate mechanism from the waivers here.

## 4. Why `mock_rendering` behaves differently at `redesign-review`

`../../../gates.yaml` lists `mock_rendering` under `redesign-review`'s
`no_fallback`. At that boundary the key accepts neither the sanctioned string in
§3 nor an applicability record, even though the global fallback exists everywhere
the `render` kind otherwise appears.

The reasoning is substantive rather than procedural: the four mocks are always
built, so "no visible surface changed" cannot be a true statement about them. A
boundary-level `no_fallback` beats a global fallback; never grant a waiver the
boundary refuses.

Two consequences at the gate:

- An attempted waiver is a `REVISE` routed to `design-qa`, asking for hashed captures across the required breakpoints and themes, bound by `inputs` to the rendered mocks.
- The `UNCHECKED` that `../scripts/check_redesign.py` reports when no capture file is found is an unresolved question, not permission. `../SKILL.md` records why the script keeps the capture keys conditional while the spec refuses every waiver on this one.

`rendered_verification` is deliberately *not* under `no_fallback` here. It covers
the selected variant, and a merge or a deferral leaves no variant to render — the
next section is how that case is expressed.

## 5. The four selection-dependent keys

`selected_variant`, `parity_evidence`, `rendered_verification`, and
`accessibility_evidence` describe work that only exists when the user chose a
direction. `selection.decision` decides which of two states each must be in, and
`check.py` enforces the correspondence:

| `selection.decision` | Those four keys |
| --- | --- |
| `variant` | Real evidence, no sanctioned wording anywhere among them, and `selected_variant.variants[0].id` equal to `selection.chosen` |
| `merge` | `merge brief recorded - implemented as a fifth direction in the design pipeline` |
| `deferred` | `selection deferred - no variant built` |

Both wordings are carried the same way every stand-in is at schema 2: as the
`reason` of an applicability record `{applicable: false, reason, scope,
decided_by}`, never as a bare string. What they are *not* is a waiver. A waiver
says a requirement was set aside; these say the requirement never arose, because
no prototype was commissioned. Judge them accordingly — a deferred package with
all four carrying the deferral wording is complete, and a package that built a
variant and then reached for one of them is concealing evidence it owes.

## Cross-references

- `../../../gates.yaml` — the authority for everything on this page.
- `../SKILL.md` — boundary table, owner routing, key-space collisions, failure modes.
- `workflow.md` — the order these checks run in.
- `examples.md` — worked submissions at both boundaries.
