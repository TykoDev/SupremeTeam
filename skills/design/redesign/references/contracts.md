# Contracts Reference

The full normative text of every contract `../SKILL.md` binds the redesign phase
to. The SKILL.md section of the same name carries one decision line per contract
and points here; this file is the single statement of the procedure behind each,
so neither document paraphrases the other.

## Contents

1. Grill-Me Intake — what to confirm before delegating any stage
2. Four distinct mocks — how differentiation is judged, and when
3. Mocks before implementation — what may be built, and after what
4. Functional parity — the two mechanical levels and the rendered half
5. Framework-free drafts — what a mock and a prototype may and may not depend on
6. Taste read boundary — consuming the snapshot without mutating either store
7. Design doctrine — which sections bind every direction, mock, and variant
8. Save-Protocol Adherence — what to persist and when to checkpoint

## The Contracts

- **Grill-Me Intake**: Before delegating any stage, run the intake interview in `../../../grill-me-doctrine.md` — one load-bearing question at a time, always with a recommendation, exploring the codebase instead of asking when the answer is discoverable. Record resolved, deferred, and rejected decisions.
- **Four distinct mocks**: Exactly four, differentiated across at least three Taste categories from `../../../taste-doctrine.md` §3. Differentiation is judged from `design-directions.md` before any mock is drawn. `evidence_type_params.mock_set.required_count` fixes the count at four; a fifth mock fails the gate as mechanically as a third.
- **Mocks before implementation**: The four drafts the user compares are static. A mock draws one screen per inventory route, carries every inventory component, declares itself with `data-mock="true"`, and carries no router, no in-memory state, no wired interaction or flow, and no `components.js`. Nothing becomes a living prototype until `reports/selection.md` and the typed `selection` record name a chosen id, and then only for that id. Four living prototypes built before the choice is three implementations made to be thrown away; the sequencing exists to prevent it, and a specialist volunteering the extra work does not make it acceptable.
- **Functional parity**: Parity is mechanical at two levels and rendered at both. `check_parity.py --level mock` scores routes and components across the four mocks at `--min-coverage 1.0`, reporting interactions, flows, and states as informational counts that never fail the level; `check_parity.py --level full` scores every inventory id on the selected variant. Rendered parity is `design-qa` capturing every mock screen, and — once a variant exists — every declared state of that variant, at the six tiers in both themes. Pixel similarity is never the criterion; a mock missing an inventory route is not a mock, and a selected variant missing any inventory id is not a variant.
- **Framework-free drafts**: No build step, no network access, shadcn-shaped component names and token names, so the chosen direction maps one-to-one onto the production design system per `../../../design-doctrine.md` §9. A mock is further limited to at most two scripts: an optional theme toggle and an optional screen picker that shows and hides the static screens.
- **Taste read boundary**: Consume the snapshot read-only. Feedback that surfaces during comparison becomes Taste candidate records routed through Admiral to `taste`; it never becomes a silent edit or an effective preference in this run.
- **Design doctrine**: Every direction, mock, and variant honours `../../../design-doctrine.md` §0 to §6 and §9; a doctrine violation is a `REVISE` to the builder.
- **Save-Protocol Adherence**: When a Save Context block is received from admiral, persist every phase artifact to the save path through the classes below and checkpoint through `session-memory` at every delegation and return. `reports/selection.md` is written and registered before any `selected-build` is delegated. Saving is mandatory, not optional.
