# Redesign Stub Contract

## Scope

Redesign owns the redesign pipeline boundary from an existing user-facing surface
through the `redesign-review` gate and the handoff of the chosen variant into the
design pipeline.

## Delegation Order

The canonical stage numbering is the fourteen-row table in
`references/workflow.md` §Stage Order, which mirrors `../../pipelines.yaml`.
**This list is not a second numbering.** It is the same fourteen stages grouped
into the eight delegations Admiral actually issues, with the canonical stage
numbers in brackets so the two can always be reconciled. Where they appear to
disagree, the workflow table is right.

Stages 1 through 8 are unconditional; only the taste grilling (stage 3) has a
documented skip, and only when the user declines preference capture. Stages 9
through 12 are conditional: they run only when a variant was selected.

| # | Delegation | Canonical stages |
| --- | --- | --- |
| D1 | `admiral` (intake grilling) — the stage this contract is handed across, not one redesign delegates | 1 |
| D2 | `design-mapper` (inventory, baseline captures) | 2 |
| D3 | `taste` (project taste grilling, confirmation, persistence, effective profile) | 3 |
| D4 | `architect` (four design directions) | 4 |
| D5 | `prototyper`, four times (one static mock per direction) | 5 |
| D6 | `design-mapper` (mock parity across the set), `design-qa` (mock rendering) | 6, 7 |
| D7 | `redesign` (comparison matrix, recommendation, the user's recorded decision) | 8 |
| D8 | `prototyper`, once (the living prototype for the chosen id), then `design-mapper` (full parity), `design-qa` (rendered verification), `frontier` (accessibility findings) — all four only when a variant was selected | 9, 10, 11, 12 |
| D9 | `redesign` (package consolidation) | 13 |
| D10 | `gatekeeper-design` (phase gate at `redesign-review`) | 14 |

## Required Inputs

- Surface in scope and the flows that define functional parity
- Application source, running instance, or captures of the current surface
- Effective Taste snapshot, or the sanctioned no-profile applicability record
- Current stack lock when one exists (read-only; mocks and prototypes are framework-free)

## Gate Contract

- Redesign is the only owner that submits `redesign-review`.
- Maximum revisions per stage: 2 (`gates.yaml` `revise_policy.cycle_cap`); every revision delegation batches all findings for one owner.
- Exactly four mocks; `mock_set` is validated mechanically for count, unique ids, and hashed files. Exactly one selected variant when the decision is `variant`; `selected_variant` is validated the same way at a count of one.
- Required evidence: `design_inventory`, `taste_grilling`, `taste_snapshot`, `design_directions`, `mock_set`, `mock_parity`, `mock_rendering`, `selection`, `selected_variant`, `parity_evidence`, `rendered_verification`, `accessibility_evidence`, `recommendation`, `residual_risk`. All but the last three are artifact-backed.
- `mock_rendering` is listed under `no_fallback` at this boundary, so it accepts neither a fallback string nor an applicability record; a browserless host returns an `inferred` render record labelled `INFERRED - no browser available`. `taste_snapshot` accepts only the sanctioned no-profile record.
- When `selection.decision` is not `variant`, the four selection-dependent keys — `selected_variant`, `parity_evidence`, `rendered_verification`, `accessibility_evidence` — carry the matching sanctioned string, `selection deferred - no variant built` or `merge brief recorded - implemented as a fifth direction in the design pipeline`. When it is `variant`, none of them may carry a string and `selected_variant.variants[0].id` must equal `selection.chosen`.
- `selection`, `recommendation`, and `residual_risk` are redesign's own: the first records the user's decision verbatim and names who decided and why, the second names the recommended direction and reports the comparison, the third names each open item, who carries it, and what closes it. An empty `residual_risk` is a claim that nothing is open.
- Self-check before submitting: `python skills/harness/gatekeeper/check.py --boundary redesign-review --package redesign/manifest.json`, without `--verdict-out`; resubmit once with `--prior` so the gate re-judges only `changed_evidence`.
- A mock below full route or component coverage never enters the comparison; a selected variant below full parity coverage or with an open Critical accessibility finding never reaches the gate.

## Package Shape

- Design inventory (JSON and report) with baseline captures
- Taste grilling log and effective-profile snapshot
- Four design directions with Taste traceability
- Four mocks: `variant.md`, `tokens.css`, `components.css`, `components.html`, `mock.html`
- Mock parity records and mock captures across the set
- `reports/selection.md` and the typed selection record
- When a variant was selected: one variant with `variant.md`, `tokens.css`, `components.css`, `components.js`, `components.html`, `app.html`, plus its parity, rendered, and accessibility evidence
- Comparison matrix, recommendation, and the recorded decision

## Downstream Expectations

- `design/commander` reads the selected variant's `variant.md`, `tokens.css`, and `components.html` — from the living build, not the mock — as the design-system input; `design/architect` implements it in the project's real stack and locks it at `design-to-build`.
- A merge choice is a brief for a fifth direction implemented in the design pipeline, not a fifth mock and not a second prototype.
- A deferral hands nothing downstream; the four mocks stay on disk as the record of what was compared.
