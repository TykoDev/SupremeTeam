# Workflow Reference

## Contents

1. Stage order
2. Fan-out and verification rules
3. Decision rules
4. Acceptance checklist
5. Save instructions per stage
6. Collaboration notes

## Stage Order

| # | Stage | Owner | Artifact | Gate evidence key |
| --- | --- | --- | --- | --- |
| 1 | intake-grilling | admiral | `grilling-log` | (design-to-build later) |
| 2 | design-inventory | design-mapper | `design-inventory` | `design_inventory` |
| 3 | taste-grilling | taste | `taste-grilling-log`, then the taste pipeline's `effective-taste-profile` | `taste_grilling`, `taste_snapshot` |
| 4 | design-directions | architect | `design-directions` | `design_directions` |
| 5 | variant-build (fan out 4) | prototyper | `design-system-variant` x4 | `variant_set` |
| 6 | parity-verification | design-mapper | `parity-evidence` x4 | `parity_evidence` |
| 7 | visual-qa | design-qa | `rendered-verification` | `rendered_verification` |
| 8 | frontend-review | frontier | `frontend-review-report` | `accessibility_evidence` |
| 9 | recommendation | redesign | `redesign-package` | `recommendation`, `residual_risk` |
| 10 | phase-gate | gatekeeper-design | `gate-verdict` | |

Stages 2 through 4 are strictly sequential: the inventory is the parity contract,
the grilling reads the inventory, and the directions read both. Stage 5 fans out
once per direction. Stages 6 through 8 run per variant and may run in parallel
across variants once each prototype is hashed.

## Fan-out and Verification Rules

- One `prototyper` delegation per direction, each with the same inventory hash,
  the same snapshot digest, and only its own direction. A prototype that reads a
  sibling variant is a defect: the four must be independently derived from the
  directions.
- Every prototype self-checks with `check_parity.py` before returning. The
  mapper re-runs the check as the parity owner; the mapper's record, not the
  builder's, is gate evidence.
- `design-qa` captures every route in every declared state at the six responsive
  tiers in light and dark themes per variant, bound by sha256 to `app.html` and
  `tokens.css`. A capture set that skips a tier or a theme is a partial record and
  is labelled as such; it does not pass the gate.
- `frontier` grades accessibility per variant with the shared severities. A
  Critical accessibility finding (unreachable primary action, contrast below the
  floor on body text, keyboard trap) blocks the variant from the comparison until
  the builder fixes it.
- A failed variant returns to `prototyper` with a batched list of every missing
  id and every Critical or Major finding, so one revision closes the variant.

## Decision Rules

- Differentiation is decided at stage 4, from prose, before anything is built.
  Four directions must diverge in at least three Taste categories; recommend the
  categories to diverge on from the grilling log's strongest and most uncertain
  answers.
- The comparison matrix reports, per variant: parity coverage, tiers and themes
  captured, accessibility findings by severity, Taste conformance rows, and the
  direction's differentiators. It never reports a taste score; Taste is a
  preference, not a metric.
- The recommendation names one variant and the reason it best satisfies the
  effective Taste profile within the mandatory requirements. The user may choose
  differently, choose a merge, or defer; each is recorded verbatim.
- A merge choice produces a merge brief (which variant supplies palette, type,
  density, layout, components, motion) that `architect` implements as a fifth
  direction in the design pipeline; the redesign package does not build it.
- The chosen variant's `variant.md`, `tokens.css`, and `components.html` are the
  `design-system` input the design pipeline reads; the prototype is reference
  behaviour, not production code.

## Acceptance Checklist

- The inventory names every route, state, component, interaction, and flow in
  scope with stable ids, and the baseline captures exist or are labelled
  INFERRED with a limitation.
- The taste grilling log records one decision per Taste category with source,
  recommendation, and the user's answer, and the snapshot digest is bound.
- Four directions, each traced to preferences and differentiated on at least
  three categories.
- Four variants, each with `variant.md`, `tokens.css`, `components.css`,
  `components.js`, `components.html`, and `app.html`, all hashed.
- Four parity records at full coverage, four render records across six tiers and
  two themes, four accessibility findings records with no open Critical.
- A comparison matrix, a recommendation, and a recorded decision or deferral.
- `redesign/manifest.json` passes `check.py --boundary redesign-review` before
  submission.

## Save Instructions Per Stage

When persistence is active (Save Context received from admiral), the phase lead
writes only the classes `../../../save-ownership.yaml` grants it under
`skillset-saves/runs/{run-id}/redesign/`:

1. **Before delegating** a specialist: checkpoint through `session-memory` (`save_run.py checkpoint --expect-revision <n> --set active_owner=redesign --set phase_state=REDESIGN_ACTIVE`) and include the canonical `### Save Context` block naming the specialist as `Owner` and its `reports/`, `artifacts/`, or `evidence/` destination as `Expected artifact`. Do not create per-specialist directories or phase-state files.
2. **After specialist returns**: verify the named artifact exists at its destination (for example `artifacts/inventory/design-inventory.json` or `artifacts/variants/v2/app.html`), then checkpoint with `--evidence <path>` so its sha256 is registered.
3. **After gatekeeper-design verdict**: the gatekeeper has written `redesign/verdict_redesign-review.json`; record the semantic verdict and next action in the next checkpoint (`--set phase_state=REDESIGN_GATE_PENDING`, `REDESIGN_GATE_REVISE`, or the next active state). Never edit the verdict record.
4. **On package consolidation**: write `redesign/reports/redesign-package.md` and `redesign/manifest.json` (schema 2) summarizing all stage outcomes with hashes; admiral submits that manifest to `gatekeeper-admiral`.

## Collaboration Notes

- `design/design-mapper` owns the inventory, the baseline, and parity evidence.
- `taste` owns the taste grilling log, the confirmed preferences, and the snapshot; it is reached through Admiral because it mutates the preference store.
- `design/architect` owns the four directions and, later, the production design system for the chosen variant.
- `design/prototyper` owns one variant per delegation.
- `review/design-qa` and `review/frontier` own the rendered and accessibility evidence per variant.
- `design/gatekeeper-design` validates the `redesign-review` boundary with `scripts/check_redesign.py` and the boundary validator.
- `session-memory` provides checkpoints at every delegation and return.
