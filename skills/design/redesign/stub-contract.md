# Redesign Stub Contract

## Scope

Redesign owns the redesign pipeline boundary from an existing user-facing surface
through the `redesign-review` gate and the handoff of the chosen variant into the
design pipeline.

## Stage Order

The order `../../pipelines.yaml` declares for the `redesign` pipeline. Every
stage is unconditional; only the taste grilling has a documented skip, and only
when the user declines preference capture.

1. `design-mapper` (inventory, baseline captures)
2. `taste` (project taste grilling, confirmation, persistence, effective profile)
3. `architect` (four design directions)
4. `prototyper`, four times (one design-system variant per direction)
5. `design-mapper` (parity evidence per variant), `design-qa` (rendered verification per variant), `frontier` (accessibility findings per variant)
6. `redesign` (comparison matrix, recommendation, recorded decision)
7. `gatekeeper-design` (phase gate at `redesign-review`)

## Required Inputs

- Surface in scope and the flows that define functional parity
- Application source, running instance, or captures of the current surface
- Effective Taste snapshot, or the sanctioned no-profile applicability record
- Current stack lock when one exists (read-only; prototypes are framework-free)

## Gate Contract

- Redesign is the only owner that submits `redesign-review`.
- Maximum revisions per stage: 2 (`gates.yaml` `revise_policy.cycle_cap`); every revision delegation batches all findings for one owner.
- Exactly four variants; `variant_set` is validated mechanically for count, unique ids, and hashed files.
- Required evidence: `design_inventory`, `taste_grilling`, `taste_snapshot`, `design_directions`, `variant_set`, `parity_evidence`, `rendered_verification`, `accessibility_evidence`, `recommendation`, `residual_risk`. All but the last three are artifact-backed.
- `rendered_verification` is listed under `no_fallback` at this boundary, so it accepts neither a fallback string nor an applicability record; a browserless host returns an `inferred` render record labelled `INFERRED - no browser available`. `taste_snapshot` accepts only the sanctioned no-profile record.
- `recommendation` and `residual_risk` are redesign's own: the first names the variant and records the user's decision verbatim, the second names each open item, who carries it, and what closes it. An empty `residual_risk` is a claim that nothing is open.
- Self-check before submitting: `python skills/harness/gatekeeper/check.py --boundary redesign-review --package redesign/manifest.json`, without `--verdict-out`; resubmit once with `--prior` so the gate re-judges only `changed_evidence`.
- A variant below full parity coverage or with an open Critical accessibility finding never enters the comparison.

## Package Shape

- Design inventory (JSON and report) with baseline captures
- Taste grilling log and effective-profile snapshot
- Four design directions with Taste traceability
- Four variants: `variant.md`, `tokens.css`, `components.css`, `components.js`, `components.html`, `app.html`
- Parity, rendered, and accessibility evidence per variant
- Comparison matrix, recommendation, and the recorded decision or deferral

## Downstream Expectations

- `design/commander` reads the chosen variant's `variant.md`, `tokens.css`, and `components.html` as the design-system input; `design/architect` implements it in the project's real stack and locks it at `design-to-build`.
- A merge choice is a brief for a fifth direction implemented in the design pipeline, not a fifth prototype.
