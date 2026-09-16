# Boundary Evidence Reference

Read this when a review submission is in hand and the question is *what a
specific key must be* — a hashed artifact or a claim, which typed record shape,
and whether a waiver is admissible. `../SKILL.md` carries the boundary table, the
owner table, and the two key spaces; this file carries the per-key detail.
`../../../gates.yaml` is the authority: where this file and the spec disagree,
the spec wins and this file is the defect.

## Contents

1. `review-to-delivery`, key by key
2. `probe` and `render` records, and input-hash drift
3. The `verdict` record and a preserved challenge
4. The one sanctioned waiver, verbatim
5. Reading the untyped keys

## 1. `review-to-delivery`, key by key

Submitter `code-chief`. Six required keys; two artifact-backed.

| Key | Backing | Record type | What the validator enforces | Owner |
| --- | --- | --- | --- | --- |
| `executed_probes` | artifact | `probe` | a path in `artifact_hashes` and `result.status: pass`; the executed logs are the artifacts | code-chief |
| `rendered_verification` | artifact | `render` | hashed captures, the breakpoints and themes covered, `inputs` bound by sha256 to the rendered source, and `result.status` `pass` or `inferred` | design-qa |
| `review_verdict` | claim | `verdict` | APPROVED, or REVISE/ESCALATE accompanied by a challenge record `{by, reason}` | code-chief |
| `findings` | claim | `findings` | `{items: [{id, severity, status, owner?, reopen_trigger?, reason?}]}` under the shared severity model and the finding policy | code-chief |
| `residual_risk` | claim | untyped | present and non-falsy | code-chief |
| `revision_lineage` | claim | untyped | present and non-falsy | code-chief |

## 2. `probe` and `render` records, and input-hash drift

`../../../gates.yaml` `evidence_type_rules` defines both shapes:

- **`probe`** — hashed artifacts plus `result.status: pass`, where the executed logs are the artifacts. A count of probes run is not evidence that they ran.
- **`render`** — hashed captures or artifacts, `breakpoints`, `themes`, `inputs` bound to the rendered source, and `result.status` `pass` or `inferred`. An `inferred` status requires a limitation statement and is labelled INFERRED - no browser available. Breakpoints cover the responsive tiers `../../../design-doctrine.md` section 4 requires for the changed surface.

`inputs` is the field that makes either record falsifiable. It binds the evidence
to its source by sha256, so the validator can tell whether the source still
matches what was probed or rendered. When it does not, the failure is **input
hash drift**: the artifact is intact and correctly hashed, but the file it
describes has changed since capture.

Drift is a `REVISE`, not an `ESCALATE`, and it routes by key — `code-chief` for
`executed_probes`, `design-qa` for `rendered_verification`. The evidence is not
wrong; it proves a state the package no longer ships.

A record whose `result.status` is `fail`, `error`, `not-run`, or `unavailable`
does not satisfy its key. An unavailable check is a data gap, never a pass.

## 3. The `verdict` record and a preserved challenge

`review_verdict` is APPROVED, or REVISE/ESCALATE accompanied by a challenge
record naming `by` and `reason`. The gate preserves that challenge as a disputed
recommendation rather than resolving it.

That is a deliberate asymmetry. Consolidation is where a specialist's dissent is
most likely to be smoothed into consensus, so the spec requires the dissent to
travel with the package and this gate to carry it into the verdict record. A
`review_verdict` of REVISE with no challenge record fails mechanically; a
challenge that this gate silently agrees or disagrees with is a judgment failure
the validator cannot see.

## 4. The one sanctioned waiver, verbatim

Only `rendered_verification` is waivable at this boundary, and only as a typed
applicability record — `{applicable: false, reason, scope, decided_by}` — whose
reason is exactly:

```text
no visible surface changed - rendered verification not applicable
```

Any other string fails the artifact-backing and fallback checks, and a waiver on
any of the other five keys fails as *evidence not waivable* rather than as a bad
reason. The distinction matters when routing the `REVISE`: the first is
`design-qa` rewording a record or capturing a render, the second is a key that
simply has to be produced by `code-chief`.

Note that the same key is `no_fallback` at `redesign-review`, where no waiver is
admissible at all. The key's rules are per boundary, not global.

## 5. Reading the untyped keys

`residual_risk` and `revision_lineage` are checked only for presence and
non-falsiness. The validator cannot tell an adequate residual-risk statement from
a sentence containing the word "risk".

That gap is the judgment half of this gate:

- For `residual_risk`, ask whether every deferred Major in `findings` appears here with its owner and reopen trigger, and whether anything listed is actually residual rather than unaddressed.
- For `revision_lineage`, ask whether the chain reaches an approved build revision without a gap, and treat a lineage that starts mid-pipeline as broken.
- Treat a value that only restates the key name as absent.

## Cross-references

- `../../../gates.yaml` — the authority for everything on this page.
- `../SKILL.md` — boundary table, owner routing, the two key spaces, failure modes.
- `workflow.md` — the order these checks run in.
- `examples.md` — worked submissions applying them.
