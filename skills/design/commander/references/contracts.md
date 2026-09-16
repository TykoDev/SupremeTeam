# Contracts Reference

The full normative text of every contract `../SKILL.md` binds the design phase
to. The SKILL.md section of the same name carries one decision line per contract
and points here; this file is the single statement of the procedure behind each,
so neither document paraphrases the other.

## Contents

1. Grill-Me Intake — what to resolve before assigning specialist work
2. Save-Protocol Adherence — what to persist and what to propagate
3. Taste read boundary — consuming the snapshot without mutating either store
4. Taste revision and drift — what invalidates a snapshot, and when
5. Taste traceability — preference id to design artifact to rendered evidence

## The Contracts

- **Grill-Me Intake**: Before assigning any specialist work, run the intake interview in `../../../grill-me-doctrine.md` — resolve every load-bearing branch one question at a time, use the planning-mode decision prompt contract for unresolved design/configuration choices, always recommend an answer, explore the codebase instead of asking when the answer is discoverable, and apply YAGNI to avoid speculative commitments. Record resolved, deferred, rejected, and YAGNI-deferred material options in the Decision Register.
- **Save-Protocol Adherence**: When a Save Context block is received from admiral, persist every phase state transition, gatekeeper capture, and consolidated package to the save path. Include a `### Save Context` block in every specialist delegation. Saving is mandatory, not optional.
- **Taste read boundary**: Commander and Architect may consume the resolved snapshot but must not edit the project or global preference store. New design feedback is emitted as Taste candidate records (source context, proposed preference, rationale, and affected artifacts) and routed through Admiral to the Taste pipeline for user confirmation; it is not treated as an effective preference in the current run unless Taste confirms it and Commander re-resolves before the gate.
- **Taste revision and drift**: Recheck the snapshot's project and global source revisions immediately before `design-to-build`. A changed revision before that gate invalidates the snapshot and requires Admiral/Taste re-resolution plus replay of affected design decisions. A change after approval is a next-revision candidate unless the user explicitly requests replay. Report a project preference that conflicts with an approved project design rather than applying it retroactively. Surface revocation of a preference used by an active design as drift and obtain a user decision.
- **Taste traceability**: For each effective preference used, record a row from preference id and snapshot digest to the resulting design-system artifact(s), decision provenance, and the rendered-verification evidence slot that review must fill. Explicit run instructions, existing project conventions, and documented architect judgment use the same table with their provenance kind but no invented Taste id.
