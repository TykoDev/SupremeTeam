# Gate Evidence Reference — `redesign-review`

Redesign is the only submitter at `redesign-review` (`../../../gates.yaml`,
`boundaries`), so it assembles all ten required keys into
`redesign/manifest.json` and authors two of them itself: `recommendation` and
`residual_risk`. The other eight are authored by their stage owners and carried
in unchanged.

Read this file before assembling the manifest or answering a REVISE.
`../SKILL.md` states only the three decisions that change what redesign does; the
columns below state what each key must contain and what may stand in for it.

## Contents

1. The ten keys
2. What `recommendation` and `residual_risk` must say
3. `rendered_verification` and the browserless host
4. Fallbacks that exist, and the ones that do not

## The Ten Keys

| Key | Owner | Stage | Must contain | Artifact-backed | Typed record |
| --- | --- | --- | --- | --- | --- |
| `design_inventory` | `design/design-mapper` | design-inventory | Every route, state, component, interaction, and flow in scope with stable ids — the parity contract every variant is measured against | Yes | None |
| `taste_grilling` | `taste` | taste-grilling | The grilling log: one decision per Taste category with its source, the recommendation offered, and the user's answer | Yes | None |
| `taste_snapshot` | `taste` | taste-grilling, then the taste pipeline | The immutable effective-profile snapshot with its canonical digest and source revisions | Yes | None |
| `design_directions` | `design/architect` | design-directions | Four directions differing in at least three Taste categories, each tracing every effective preference or explicit instruction to a concrete token, layout, or component decision | Yes | None |
| `variant_set` | `design/prototyper` | variant-build | Exactly four variants with unique ids; the spec, tokens, components, and app of every variant correctly hashed in the package, and `count` equal to the list length when present | Yes | `variant_set` |
| `parity_evidence` | `design/design-mapper` | parity-verification | The `check_parity.py` probe record per variant, bound by `inputs` to the inventory and the prototype files, at full coverage of every inventory id | Yes | `probe` |
| `rendered_verification` | `review/design-qa` | visual-qa | Hashed captures of every route in every declared state at the six responsive tiers in light and dark themes, per variant, bound by sha256 to `app.html` and `tokens.css` | Yes | `render` |
| `accessibility_evidence` | `review/frontier` | frontend-review | Graded accessibility and interaction findings per variant, with no open Critical on any variant that enters the comparison | No | `findings` |
| `recommendation` | redesign | recommendation | The comparison matrix, the named variant with the reason it best satisfies the effective Taste profile inside the mandatory requirements, and the user's recorded decision, merge brief, or deferral | No | None |
| `residual_risk` | redesign | recommendation | What the package leaves open after the comparison, who carries it, and the condition that reopens it | No | None |

## What `recommendation` And `residual_risk` Must Say

These two are redesign's own, and neither is a summary of the other.

**`recommendation`** names one variant and the reason it best satisfies the
effective Taste profile within the mandatory accessibility, security, and gate
requirements. It reports the comparison matrix — per variant: parity coverage,
tiers and themes captured, accessibility findings by severity, Taste conformance
rows, and the direction's differentiators — and never a taste score, because
Taste is a preference and not a metric. The user's answer is recorded verbatim in
the same key: one variant, a merge brief naming which variant supplies which
decision, or a deferral.

**`residual_risk`** is what survives the recommendation. It is not a restatement
of open findings; it names, for each open item, what stayed unproven, who carries
it, and the observation or decision that would close it. Typical entries:

- A decision deferred by the user, with its owner and reopen trigger.
- A capture set that is partial or inferred, with the tier, theme, or capability that is missing.
- A Major accessibility finding deferred on the chosen variant, with its owner and reopen trigger.
- A parity id covered by a prototype behaviour the production stack may not reproduce identically.
- A Taste entry whose source revision may move before the design pipeline reads the variant.

An empty `residual_risk` is a claim that nothing is open, and the gate reads it
as one.

## `rendered_verification` And The Browserless Host

`rendered_verification` is listed under `no_fallback` at this boundary, so the
sanctioned string `no visible surface changed - rendered verification not
applicable` is rejected here even though it exists globally — a redesign changes
a visible surface by definition. The key is therefore always a `render` record,
and `evidence_type_rules.render` permits exactly two statuses:

| Host | Record |
| --- | --- |
| Can render the prototypes | `result.status: pass`, hashed captures at the six tiers in both themes per variant, inputs bound to `app.html` and `tokens.css` |
| Has no browser | `result.status: inferred`, a limitation statement, and the label `INFERRED - no browser available`. The comparison matrix marks rendering as unobserved for every variant, and `residual_risk` carries the gap with the condition that closes it — a capture run at the same variant hashes on a host with a browser |

An inferred record is a bounded limitation, not a pass: the gate records it as
such, and a variant chosen on inferred rendering carries that fact into the
design pipeline.

## Fallbacks That Exist, And The Ones That Do Not

One key at this boundary is waivable: `taste_snapshot`, through
`no saved Taste profile available`, and only when the user declines preference
capture — in which case the grilling log's answers are current-run instructions
and `taste_grilling` is still produced. Every other key accepts nothing but its
evidence, and `rendered_verification` is additionally barred from any fallback by
`no_fallback`.

The waiver is not that string on its own. At manifest schema 2 it is the `reason`
of an applicability record `{applicable: false, reason, scope, decided_by}`, and
`check.py` fails a bare fallback string before judgment begins.
