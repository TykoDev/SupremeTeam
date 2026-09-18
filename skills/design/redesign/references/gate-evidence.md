# Gate Evidence Reference — `redesign-review`

Redesign is the only submitter at `redesign-review` (`../../../gates.yaml`,
`boundaries`), so it assembles all fourteen required keys into
`redesign/manifest.json` and authors three of them itself: `selection`,
`recommendation`, and `residual_risk`. The other eleven are authored by their
stage owners and carried in unchanged.

Read this file before assembling the manifest or answering a REVISE.
`../SKILL.md` states only the four decisions that change what redesign does; the
columns below state what each key must contain and what may stand in for it.

## Contents

1. The fourteen keys
2. The `selection` record
3. The selection-dependent keys and their two sanctioned strings
4. What `recommendation` and `residual_risk` must say
5. `mock_rendering` and the browserless host
6. Fallbacks that exist, and the ones that do not

## The Fourteen Keys

| Key | Owner | Stage | Must contain | Artifact-backed | Typed record |
| --- | --- | --- | --- | --- | --- |
| `design_inventory` | `design/design-mapper` | design-inventory | Every route, state, component, interaction, and flow in scope with stable ids — the parity contract every draft is measured against | Yes | None |
| `taste_grilling` | `taste` | taste-grilling | The grilling log: one decision per Taste category with its source, the recommendation offered, and the user's answer | Yes | None |
| `taste_snapshot` | `taste` | taste-grilling, then the taste pipeline | The immutable effective-profile snapshot with its canonical digest and source revisions | Yes | None |
| `design_directions` | `design/architect` | design-directions | Four directions differing in at least three Taste categories, each tracing every effective preference or explicit instruction to a concrete token, layout, or component decision | Yes | None |
| `mock_set` | `design/prototyper` | mock-build | Exactly four mocks with unique ids; the `spec`, `tokens`, `components`, and `mock` of every mock correctly hashed in the package, and `count` equal to the list length when present | Yes | `variant_set` |
| `mock_parity` | `design/design-mapper` | mock-parity | One aggregated `check_parity.py --level mock` probe record whose `artifacts` list names the four per-mock records, at full coverage of routes and components; interactions, flows, and states appear as informational counts | Yes | `probe` |
| `mock_rendering` | `review/design-qa` | mock-review | Hashed captures of every mock screen at the six responsive tiers in light and dark themes, bound by sha256 to `mock.html` and `tokens.css` | Yes | `render` |
| `selection` | redesign | selection | The decision, the chosen id or `null`, the recommended id, who decided and when, and the one-line basis — backed by `reports/selection.md` carrying the user's answer verbatim | Yes | `selection` |
| `selected_variant` | `design/prototyper` | selected-build | Exactly one variant whose `id` equals `selection.chosen`, with `spec`, `tokens`, `components`, and `app` correctly hashed in the package | Yes | `variant_set` |
| `parity_evidence` | `design/design-mapper` | parity-verification | The `check_parity.py --level full` probe record for the selected variant, bound by `inputs` to the inventory and the prototype files, at full coverage of every inventory id | Yes | `probe` |
| `rendered_verification` | `review/design-qa` | visual-qa | Hashed captures of every route in every declared state at the six responsive tiers in light and dark themes for the selected variant, bound by sha256 to `app.html` and `tokens.css` | Yes | `render` |
| `accessibility_evidence` | `review/frontier` | frontend-review | Graded accessibility and interaction findings on the selected variant, with no open Critical | No | `findings` |
| `recommendation` | redesign | recommendation | The comparison matrix across the four mocks, the named direction with the reason it best satisfies the effective Taste profile inside the mandatory requirements, and the selected variant's results when one was built | No | None |
| `residual_risk` | redesign | recommendation | What the package leaves open after the comparison, who carries it, and the condition that reopens it | No | None |

Eleven are artifact-backed: every key above except `accessibility_evidence`,
`recommendation`, and `residual_risk`.

## The `selection` Record

`selection` is the hinge of this boundary: it is the only key that decides
whether four other keys carry evidence or a sanctioned string. It is a typed
`selection` record backed by the hashed `reports/selection.md`:

```json
{
  "schema_version": 2,
  "artifacts": ["reports/selection.md"],
  "decision": "variant",
  "chosen": "v2",
  "recommended": "v2",
  "decided_by": "product owner",
  "decided_at": "2026-04-18T14:05:00Z",
  "basis": "dense-operational reads fastest at the tier the warehouse team actually uses"
}
```

The rules the record must satisfy:

- `decision` is one of `variant`, `merge`, or `deferred`.
- `decision: variant` requires a non-null `chosen` that is one of the `mock_set`
  ids. `merge` and `deferred` require `chosen: null`.
- `recommended` is always a `mock_set` id — the recommendation stands whether or
  not the user took it, and a decision that departs from it is a fact the package
  records rather than hides.
- `decided_by` names the person or owner who decided; `decided_at` is ISO-8601.
- `basis` is one line: why this decision, not a summary of the matrix.
- A merge additionally records the merge brief in `selection.md` — which mock
  supplies palette, type, density, layout, components, and motion.
- `reports/selection.md` carries the user's decision **verbatim**. The typed
  record is the machine's view of it and never the only copy.

## The Selection-Dependent Keys And Their Two Sanctioned Strings

Four keys — `selected_variant`, `parity_evidence`, `rendered_verification`, and
`accessibility_evidence` — exist only when something was built. `check.py`
enforces the correspondence mechanically:

| `selection.decision` | What those four keys must carry |
| --- | --- |
| `variant` | Real evidence, none of it a fallback string, and `selected_variant.variants[0].id` equal to `selection.chosen` |
| `merge` | `merge brief recorded - implemented as a fifth direction in the design pipeline`, on all four |
| `deferred` | `selection deferred - no variant built`, on all four |

Both strings are sanctioned in `../../../gates.yaml` `fallback_values`, and
neither is a waiver of a requirement: each is the accurate statement that the
requirement did not arise, because no prototype was commissioned. Using one
beside a variant that was in fact built, or omitting it after a deferral, fails
before judgment begins.

## What `recommendation` And `residual_risk` Must Say

These two are redesign's own, and neither is a summary of the other or of
`selection`.

**`recommendation`** names one direction and the reason it best satisfies the
effective Taste profile within the mandatory accessibility, security, and gate
requirements. It reports the comparison matrix — per mock: mock parity coverage,
tiers and themes captured, Taste conformance rows, and the direction's
differentiators — and never a taste score, because Taste is a preference and not
a metric. When a variant was built, it also reports that variant's full parity
coverage, rendering, and accessibility results, which the matrix cannot carry
because only one of the four has them. The user's answer lives in `selection`;
`recommendation` states what was recommended and why, not what was decided.

**`residual_risk`** is what survives the recommendation. It is not a restatement
of open findings; it names, for each open item, what stayed unproven, who carries
it, and the observation or decision that would close it. Typical entries:

- A decision deferred by the user, with its owner and reopen trigger.
- A capture set that is partial or inferred, with the tier, theme, or capability that is missing.
- A Major accessibility finding deferred on the selected variant, with its owner and reopen trigger.
- A behaviour that was only ever drawn: a direction chosen on mocks carries the
  risk that an interaction the mock never wired reads differently once it does.
- A parity id covered by a prototype behaviour the production stack may not reproduce identically.
- A Taste entry whose source revision may move before the design pipeline reads the variant.

An empty `residual_risk` is a claim that nothing is open, and the gate reads it
as one.

## `mock_rendering` And The Browserless Host

`mock_rendering` is listed under `no_fallback` at this boundary, so the sanctioned
string `no visible surface changed - rendered verification not applicable` is
rejected on it even though it exists globally — the four mocks are always built,
so there is always a surface to capture. The key is therefore always a `render`
record, and `evidence_type_rules.render` permits exactly two statuses:

| Host | Record |
| --- | --- |
| Can render the mocks | `result.status: pass`, hashed captures at the six tiers in both themes across the four mocks, inputs bound to `mock.html` and `tokens.css` |
| Has no browser | `result.status: inferred`, a limitation statement, and the label `INFERRED - no browser available`. The comparison matrix marks rendering as unobserved for every mock, and `residual_risk` carries the gap with the condition that closes it — a capture run at the same mock hashes on a host with a browser |

An inferred record is a bounded limitation, not a pass: the gate records it as
such, and a direction chosen on inferred rendering carries that fact into the
design pipeline.

`rendered_verification` is not under `no_fallback` here, and the difference is
deliberate: a merge or a deferral legitimately leaves no living prototype to
render, so that key carries one of the two sanctioned strings instead. When a
variant *was* built, the same two-status rule applies to it.

## Fallbacks That Exist, And The Ones That Do Not

Three kinds of stand-in exist at this boundary and they are not interchangeable:

- **A waiver.** `taste_snapshot` alone, through `no saved Taste profile available`, and only when the user declines preference capture — in which case the grilling log's answers are current-run instructions and `taste_grilling` is still produced.
- **A did-not-arise statement.** The four selection-dependent keys, through the two strings above, and only in the decision case that matches.
- **Nothing at all.** Every other key accepts only its evidence, and `mock_rendering` is additionally barred from any fallback by `no_fallback`.

A waiver is not the string on its own. At manifest schema 2 it is the `reason` of
an applicability record `{applicable: false, reason, scope, decided_by}`, and
`check.py` fails a bare fallback string before judgment begins.
