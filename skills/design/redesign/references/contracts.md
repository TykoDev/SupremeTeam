# Contracts Reference

The full normative text of every contract `../SKILL.md` binds the redesign phase
to. The SKILL.md section of the same name carries one decision line per contract
and points here; this file is the single statement of the procedure behind each,
so neither document paraphrases the other.

## Contents

1. Grill-Me Intake — what to confirm before delegating any stage
2. Four distinct variants — how differentiation is judged, and when
3. Functional parity — the mechanical and rendered halves of the parity test
4. Framework-free prototypes — what a variant may and may not depend on
5. Taste read boundary — consuming the snapshot without mutating either store
6. Design doctrine — which sections bind every direction and variant
7. Save-Protocol Adherence — what to persist and when to checkpoint

## The Contracts

- **Grill-Me Intake**: Before delegating any stage, run the intake interview in `../../../grill-me-doctrine.md` — one load-bearing question at a time, always with a recommendation, exploring the codebase instead of asking when the answer is discoverable. Record resolved, deferred, and rejected decisions.
- **Four distinct variants**: Exactly four, differentiated across at least three Taste categories from `../../../taste-doctrine.md` §3. Differentiation is judged from `design-directions.md` before any prototype is built.
- **Functional parity**: Parity is mechanical (`check_parity.py` reports full coverage of every inventory id) and rendered (`design-qa` captures every declared state at the six tiers). Pixel similarity is never the criterion; a prototype missing an inventory id is not a variant.
- **Framework-free prototypes**: No build step, no network access, shadcn-shaped component names and token names, so the chosen variant maps one-to-one onto the production design system per `../../../design-doctrine.md` §9.
- **Taste read boundary**: Consume the snapshot read-only. Feedback that surfaces during comparison becomes Taste candidate records routed through Admiral to `taste`; it never becomes a silent edit or an effective preference in this run.
- **Design doctrine**: Every direction and variant honours `../../../design-doctrine.md` §0 to §6 and §9; a doctrine violation is a `REVISE` to the variant's builder.
- **Save-Protocol Adherence**: When a Save Context block is received from admiral, persist every phase artifact to the save path through the classes below and checkpoint through `session-memory` at every delegation and return. Saving is mandatory, not optional.
