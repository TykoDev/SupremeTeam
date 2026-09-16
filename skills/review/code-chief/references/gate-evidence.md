# Gate Evidence Reference — `review-to-delivery`

Code-chief is the `review-to-delivery` submitter (`../../../gates.yaml`,
`boundaries`), so it assembles all six required keys into `review/manifest.json`
and authors five of them itself (`evidence_owners`). The sixth,
`rendered_verification`, belongs to `review/design-qa` and is carried in
unchanged.

Read this file before assembling the manifest or answering a REVISE.
`../SKILL.md` states only the three decisions that change what code-chief does;
the columns below state what each key must contain and what may stand in for it.

## Contents

1. The six keys
2. `rendered_verification` and the browserless host
3. Fallbacks that exist, and the ones that do not

## The Six Keys

| Key | Owner | What it must contain | Artifact-backed | Typed record | Sanctioned fallback |
| --- | --- | --- | --- | --- | --- |
| `review_verdict` | code-chief | The consolidated recommendation the review reached for the change under review, and nothing broader | No. `artifact_evidence` at this boundary lists only `executed_probes` and `rendered_verification` | `verdict`: APPROVED, or REVISE/ESCALATE accompanied by a challenge record `{by, reason}` that the gate preserves as a disputed recommendation | None |
| `findings` | code-chief | The graded finding set merged from every executed lens, as `../../../ownership.yaml` requires: graded items with id, severity, and status, plus an owner and a reopen trigger on every deferred Major | No | `findings`: `{items: [{id, severity, status, owner?, reopen_trigger?, reason?}]}`. Critical is verified or not-applicable with a reason; Major is verified, not-applicable with a reason, or deferred with an owner and a reopen trigger; Minor and Info are recorded | None |
| `executed_probes` | code-chief | The probe log the review actually ran, as a hashed file, carrying a result status per probe | Yes. The value names a path that appears in the manifest `artifact_hashes` map | `probe`: hashed artifacts with `result.status` pass. The executed log is the artifact; a bare count or a claim that a probe passed is not evidence | None |
| `rendered_verification` | `review/design-qa` | Hashed captures across the declared breakpoints and themes, with inputs bound to the rendered source | Yes | `render`: `result.status` pass, or `inferred` with a limitation statement labelled `INFERRED - no browser available` | `no visible surface changed - rendered verification not applicable` |
| `residual_risk` | code-chief | The risk the package leaves open after triage: what stayed unproven, who carries it, and the condition that reopens it | No | None. `evidence_types` assigns this key no shape, so a plain statement satisfies the mechanical check | None |
| `revision_lineage` | code-chief | The chain from the submitted review revision back to the approved upstream revisions it rests on, stated so a resubmission reads as a delta rather than a rewrite — for example `r1 <- build r1 <- design r1` | No | None | None |

## `rendered_verification` And The Browserless Host

Three situations look alike from inside the review and are settled differently:

| Situation | What goes in the manifest |
| --- | --- |
| No visible surface changed | The sanctioned fallback `no visible surface changed - rendered verification not applicable`, carried at schema 2 as an applicability record with reason, scope, and decided_by. The `visual-qa` stage does not run, because `../../../pipelines.yaml` conditions it on a changed visible surface |
| A visible surface changed and the host can render it | The `render` record `review/design-qa` returns, with `result.status: pass`, hashed captures across the declared responsive tiers and both themes, and inputs bound to the rendered source |
| A visible surface changed and the host has no browser | Still the record `review/design-qa` returns, now with `result.status: inferred`, the limitation statement, and the label `INFERRED - no browser available` that `evidence_type_rules.render` requires. The verdict states that rendering was not observed, and the limitation is carried into `residual_risk` with the condition that would close it |

The failure to avoid is substituting the no-visible-surface fallback for the
third case. That value asserts that nothing visible changed; using it to cover a
missing browser, or a `design-qa` stage that was skipped while a surface did
change, states something false and is caught as a judgment finding even when the
mechanical pass succeeds.

## Fallbacks That Exist, And The Ones That Do Not

One key at this boundary is waivable: `rendered_verification`, and only when no
visible surface changed. `review_verdict`, `findings`, `executed_probes`,
`residual_risk`, and `revision_lineage` accept nothing but their evidence, and
all five are code-chief's own to close — a gap in them routes to no one else.
