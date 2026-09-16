# Redesign Stub Contract

## Scope

Redesign owns the redesign pipeline boundary from an existing user-facing surface
through the `redesign-review` gate and the handoff of the chosen variant into the
design pipeline.

## Stage Order

1. Design mapper (inventory, baseline captures)
2. Taste (project taste grilling, confirmation, persistence, effective profile)
3. Architect (four design directions)
4. Prototyper, four times (one design-system variant per direction)
5. Design mapper (parity evidence per variant), design-qa (rendered verification per variant), frontier (accessibility findings per variant)
6. Redesign (comparison matrix, recommendation, recorded decision)

## Required Inputs

- Surface in scope and the flows that define functional parity
- Application source, running instance, or captures of the current surface
- Effective Taste snapshot, or the sanctioned no-profile applicability record
- Current stack lock when one exists (read-only; prototypes are framework-free)

## Gate Contract

- Redesign is the only owner that submits `redesign-review`.
- Maximum revisions per stage: 3; every revision delegation batches all findings for one owner.
- Exactly four variants; `variant_set` is validated mechanically for count, unique ids, and hashed files.
- `rendered_verification` accepts no fallback at this boundary; `taste_snapshot` accepts only the sanctioned no-profile record.
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
