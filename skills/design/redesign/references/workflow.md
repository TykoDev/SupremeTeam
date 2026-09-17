# Workflow Reference

The stage-by-stage procedure for the `redesign` pipeline: the fourteen stages and
their evidence keys, how the four-way mock fan-out is verified, where the user's
decision sits, and what each stage writes. Read this before starting a redesign
run, and before any stage that fans out, collapses the set, or depends on the
selection.

## Contents

1. Stage order
2. Fan-out and verification rules
3. Decision rules
4. Acceptance checklist
5. Save instructions per stage, with the write triggers and the Save Context block
6. Collaboration notes

## Stage Order

| # | Stage | Owner | Artifact | Gate evidence key | Condition | Fan-out |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | intake-grilling | admiral | `grilling-log` | (design-to-build later) | | |
| 2 | design-inventory | design-mapper | `design-inventory` | `design_inventory` | | |
| 3 | taste-grilling | taste | `taste-grilling-log`, then the taste pipeline's `effective-taste-profile` | `taste_grilling`, `taste_snapshot` | | |
| 4 | design-directions | architect | `design-directions` | `design_directions` | | |
| 5 | mock-build | prototyper | `design-mock` x4 | `mock_set` | | 4 |
| 6 | mock-parity | design-mapper | `mock-parity-evidence` | `mock_parity` | | |
| 7 | mock-review | design-qa | `mock-rendering` | `mock_rendering` | | |
| 8 | selection | redesign | `redesign-selection` | `selection` | | |
| 9 | selected-build | prototyper | `design-system-variant` | `selected_variant` | runs only when a variant was selected | |
| 10 | parity-verification | design-mapper | `parity-evidence` | `parity_evidence` | runs only when a variant was selected | |
| 11 | visual-qa | design-qa | `rendered-verification` | `rendered_verification` | runs only when a variant was selected | |
| 12 | frontend-review | frontier | `frontend-review-report` | `accessibility_evidence` | runs only when a variant was selected | |
| 13 | recommendation | redesign | `redesign-package` | `recommendation`, `residual_risk` (see `gate-evidence.md` for what each must say) | | |
| 14 | phase-gate | gatekeeper-design | `gate-verdict` | | | |

Stages 2 through 4 are strictly sequential: the inventory is the parity contract,
the grilling reads the inventory, and the directions read both. Stage 5 fans out
once per direction into four static mocks. Stages 6 and 7 run across the mock set
and may run in parallel once each mock is hashed.

Stage 8 is the hinge. Everything before it is drawing and measuring; everything
after it is implementation. Stages 9 through 12 run only when a variant was
selected — that is the stage condition `../../pipelines.yaml` declares for each of
them. When the decision is a merge or a deferral, none of the four runs and their
keys carry the sanctioned fallback wording instead:
`merge brief recorded - implemented as a fifth direction in the design pipeline`
or `selection deferred - no variant built`. At schema 2 that wording is never the
key's bare value: `check.py` requires the applicability record
`{applicable: false, reason, scope, decided_by}` with the wording as `reason`.

## Fan-out and Verification Rules

- One `prototyper` `mock-build` delegation per direction, each with the same
  inventory hash, the same snapshot digest, and only its own direction. A mock
  that reads a sibling is a defect: the four must be independently derived from
  the directions.
- A mock is static. It carries `data-mock="true"` on its root, one drawn screen
  per inventory route, and every inventory component somewhere across
  `components.html` and `mock.html`. It carries no router, no in-memory state, no
  wired interaction or flow, and no `components.js`. A returned draft that
  behaves goes back to its builder to be reduced.
- Every mock self-checks with `check_parity.py --level mock` before returning.
  The mapper re-runs the check as the parity owner; the mapper's records, not the
  builder's, are gate evidence.
- `mock-parity` produces one record per mock under
  `redesign/evidence/mock-parity-<id>.json` and one aggregated typed probe record
  whose `artifacts` list names the four. Mock level scores routes and components
  only; interactions, flows, and states are informational counts and never fail
  it, and `--min-coverage` stays at `1.0` for the two scored lists.
- `design-qa` captures every mock screen at the six responsive tiers in light and
  dark themes, bound by sha256 to `mock.html` and `tokens.css`. A capture set that
  skips a tier or a theme is a partial record and is labelled as such; it does not
  pass the gate.
- A failed mock returns to `prototyper` with a batched list of every missing route
  and component id, so one revision closes it.
- The `selected-build` delegation is single. It names the id `selection.chosen`
  holds, carries the selected mock's files as the derivation base, and asks for
  the full living prototype. A `selected-build` delegated for any other id, or
  with no selection record behind it, is refused by the builder and is a
  sequencing defect here.
- `parity-verification` runs `check_parity.py --level full` against `app.html`,
  scoring every inventory list. `visual-qa` captures every route in every declared
  state at the six tiers in both themes, bound to `app.html` and `tokens.css`.
  `frontier` grades accessibility on that one variant with the shared severities;
  a Critical finding (unreachable primary action, contrast below the floor on body
  text, keyboard trap) blocks the package until the builder fixes it.

## Decision Rules

- Differentiation is decided at stage 4, from prose, before anything is drawn.
  Four directions must diverge in at least three Taste categories; recommend the
  categories to diverge on from the grilling log's strongest and most uncertain
  answers.
- The comparison matrix reports, per mock: mock parity coverage (routes and
  components), tiers and themes captured, Taste conformance rows, and the
  direction's differentiators. It never reports a taste score; Taste is a
  preference, not a metric. Once the selected variant exists, the package reports
  its full parity coverage, its rendering, and its accessibility findings
  alongside the matrix rather than inside it.
- The recommendation names one mock and the reason it best satisfies the
  effective Taste profile within the mandatory requirements. The user may choose
  differently, choose a merge, or defer; each is recorded verbatim in
  `reports/selection.md`.
- A merge choice produces a merge brief (which mock supplies palette, type,
  density, layout, components, motion) that `architect` implements as a fifth
  direction in the design pipeline; the redesign package builds no prototype for
  it, and the four dependent keys carry the merge fallback string.
- A deferral records owner and reopen trigger, builds nothing, and hands nothing
  to the design pipeline; the same four keys carry the deferral fallback string.
- The chosen variant's `variant.md`, `tokens.css`, and `components.html` — the
  files from the selected living build, not from the mock it was derived from —
  are the `design-system` input the design pipeline reads; `app.html` is
  reference behaviour, not production code.

## Acceptance Checklist

- The inventory names every route, state, component, interaction, and flow in
  scope with stable ids, and the baseline captures exist or are labelled
  INFERRED with a limitation.
- The taste grilling log records one decision per Taste category with source,
  recommendation, and the user's answer, and the snapshot digest is bound.
- Four directions, each traced to preferences and differentiated on at least
  three categories.
- Four mocks, each with `variant.md`, `tokens.css`, `components.css`,
  `components.html`, and `mock.html`, all hashed, each carrying `data-mock="true"`
  and none carrying `components.js`.
- Four per-mock parity records at full route and component coverage, plus the one
  aggregated probe record; mock captures across six tiers and two themes.
- `reports/selection.md` recording the user's decision verbatim, and a typed
  `selection` record whose `chosen` is a `mock_set` id when the decision is
  `variant` and `null` otherwise.
- When a variant was selected: one variant with `variant.md`, `tokens.css`,
  `components.css`, `components.js`, `components.html`, and `app.html`, all
  hashed, whose id equals `selection.chosen`; a full-level parity record at full
  coverage; a render record across six tiers and two themes; an accessibility
  findings record with no open Critical.
- When no variant was selected: `selected_variant`, `parity_evidence`,
  `rendered_verification`, and `accessibility_evidence` all carrying the same
  sanctioned fallback string for that decision.
- A comparison matrix, a recommendation, and the recorded decision.
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
2. **After specialist returns**: verify the named artifact exists at its destination (for example `artifacts/inventory/design-inventory.json`, `artifacts/mocks/v2/mock.html`, or `artifacts/variants/v2/app.html`), then checkpoint with `--evidence <path>` so its sha256 is registered.
3. **At the selection stage**: write `redesign/reports/selection.md` with the user's answer recorded verbatim, register its sha256 through a checkpoint, and build the typed `selection` record from it. Do not commission `selected-build` before both exist.
4. **After gatekeeper-design verdict**: the gatekeeper has written `redesign/verdict_redesign-review.json`; record the semantic verdict and next action in the next checkpoint (`--set phase_state=REDESIGN_GATE_PENDING`, `REDESIGN_GATE_REVISE`, or the next active state). Never edit the verdict record.
5. **On package consolidation**: write `redesign/reports/redesign-package.md` and `redesign/manifest.json` (schema 2) summarizing all stage outcomes with hashes; admiral submits that manifest to `gatekeeper-admiral`.

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
| Mock set complete | Nothing new on disk: the four mock directories are the specialists' writes; redesign registers their hashes and assembles the `mock_set` record for the manifest |
| User decision | `redesign/reports/selection.md` carrying the decision verbatim, plus the typed `selection` record; registered with `--evidence` before any `selected-build` delegation |
| Selected build commissioned | The delegation block for `prototyper` naming `artifacts/variants/{chosen}/` as `Expected artifact`; commissioned only when `selection.decision` is `variant` |
| Gate submission | `redesign/manifest.json` (schema 2: `boundary: redesign-review`, `owner: redesign`), carrying the hashed inventory, taste grilling log, snapshot, directions, the `mock_set` record for the four mocks, the mock parity and mock rendering records, the selection record, and — when a variant was built — the `selected_variant` record, its full parity probe, its rendered verification, and its accessibility findings |
| Phase-gate verdict | Nothing: `design/gatekeeper-design` writes `redesign/verdict_redesign-review.json` through `check.py --verdict-out`; redesign records the semantic verdict in its next checkpoint |
| Package consolidation | `redesign/reports/redesign-package.md` plus the manifest revision admiral submits to `gatekeeper-admiral` |

## Collaboration Notes

The stage owners this workflow delegates to are listed in `../SKILL.md` § Delegation Surface. What this workflow adds:

- `design/architect` owns the four directions and, later, the production design system for the chosen variant.
- `design/prototyper` owns two stages, `mock-build` and `selected-build`, and never runs both in one delegation.
- `design/gatekeeper-design` validates the `redesign-review` boundary with `../../gatekeeper-design/scripts/check_redesign.py` and the boundary validator.
- `session-memory` provides checkpoints at every delegation and return.
