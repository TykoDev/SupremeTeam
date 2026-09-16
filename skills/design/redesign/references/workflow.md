# Workflow Reference

The stage-by-stage procedure for the `redesign` pipeline: the stage order and its evidence keys, how the four-direction fan-out is verified, and what each stage writes. Read this before starting a redesign run, and before any stage that fans out or collapses variants.

## Contents

1. Stage order
2. Fan-out and verification rules
3. Decision rules
4. Acceptance checklist
5. Save instructions per stage, with the write triggers and the Save Context block
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
| 9 | recommendation | redesign | `redesign-package` | `recommendation`, `residual_risk` (see `gate-evidence.md` for what each must say) |
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

This is the single statement of the procedure; `../SKILL.md` carries only the
pointer and the two rules that decide path resolution. When persistence is active
(Save Context received from admiral), redesign is the phase lead for
`skillset-saves/runs/{run-id}/redesign/` and writes only the classes
`../../../save-ownership.yaml` grants a phase lead: `manifest.json`, `reports/`,
`artifacts/`, `evidence/`, and `packages/`:

1. **Before delegating** a specialist: checkpoint through `session-memory` (`save_run.py checkpoint --run-id {run-id} --expect-revision <n> --owner redesign --set phase_state=REDESIGN_ACTIVE`; the active owner follows `--owner`, which `--set` refuses as a reserved field) and include the canonical `### Save Context` block naming the specialist as `Owner` and its `reports/`, `artifacts/`, or `evidence/` destination as `Expected artifact`. Do not create per-specialist directories or phase-state files.
2. **After specialist returns**: verify the named artifact exists at its destination (for example `artifacts/inventory/design-inventory.json` or `artifacts/variants/v2/app.html`), then checkpoint with `--evidence <path>` so its sha256 is registered.
3. **After gatekeeper-design verdict**: the gatekeeper has written `redesign/verdict_redesign-review.json`; record the semantic verdict and next action in the next checkpoint (`--set phase_state=REDESIGN_GATE_PENDING`, `REDESIGN_GATE_REVISE`, or the next active state). Never edit the verdict record.
4. **On package consolidation**: write `redesign/reports/redesign-package.md` and `redesign/manifest.json` (schema 2) summarizing all stage outcomes with hashes; admiral submits that manifest to `gatekeeper-admiral`.

### Save Context Block Template

Include this block in every specialist delegation, populating each field from the
current run state. It is the canonical field set from
`../../../contracts/handoff-templates.md`; neither file may drop a field the
other carries.

```markdown
### Save Context
- Run ID: {run-id}
- Phase: redesign
- Save path: skillset-saves/runs/{run-id}/redesign/
- Persistence active: {yes|no}
- Persistence probe result: {ok|reason}
- Context tier: {1|2|3}
- Preamble tier: {0|1|2|3} + rationale
- Artifact mode: {inline|file|reference}
- Session pin: {true|false}
- Execution mode: {agent|skill}
- Submission ID: {id}
- Revision: {revision}
- Owner: {specialist}
- Expected artifact: {reports/...|artifacts/...|evidence/...}
- Evidence paths: {relative paths}
- Artifact hashes: {path: sha256|none yet}
- Risks: {known risks|none declared}
- Return boundary: redesign-review
```

When Save Context is absent or `Persistence active: no`, skip all save operations
and return the deliverable inline.

### Write Triggers

| Trigger | What Redesign Writes |
|---------|----------------------|
| Phase start | Nothing on disk: the phase state is published through `session-memory` (`save_run.py checkpoint --run-id {run-id} --expect-revision <n> --owner redesign --set phase_state=REDESIGN_ACTIVE`) before the first specialist delegation |
| Specialist delegation | The delegation block above, naming the specialist as `Owner`, the exact `reports/`, `artifacts/`, or `evidence/` destination as `Expected artifact`, and `redesign-review` as `Return boundary` |
| Specialist return | Verify the named artifact exists at its destination, then register its sha256 through a `session-memory` checkpoint (`--evidence <path>`) |
| Gate submission | `redesign/manifest.json` (schema 2: `boundary: redesign-review`, `owner: redesign`), carrying the hashed inventory, taste grilling log, snapshot, directions, the `variant_set` record for the four variants, parity probe records, rendered verification, and accessibility findings |
| Phase-gate verdict | Nothing: `design/gatekeeper-design` writes `redesign/verdict_redesign-review.json` through `check.py --verdict-out`; redesign records the semantic verdict in its next checkpoint |
| Package consolidation | `redesign/reports/redesign-package.md` plus the manifest revision admiral submits to `gatekeeper-admiral` |

## Collaboration Notes

The stage owners this workflow delegates to are listed in `../SKILL.md` § Delegation Surface. What this workflow adds:

- `design/architect` owns the four directions and, later, the production design system for the chosen variant.
- `design/gatekeeper-design` validates the `redesign-review` boundary with `../../gatekeeper-design/scripts/check_redesign.py` and the boundary validator.
- `session-memory` provides checkpoints at every delegation and return.
