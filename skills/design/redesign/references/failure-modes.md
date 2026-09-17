# Failure Modes Reference

`../SKILL.md` carries the six failures that change what Redesign does next (no
readable surface, a browserless host, an unusable request, a draft that was built
as an implementation, an exhausted revise cycle, a missing host capability). This
file carries the rest: the differentiation, parity, conflict, and decision
failures whose handling is procedural. Nothing here repeats a row stated in
`../SKILL.md`.

## Contents

The table below covers, in order: directions that fail the differentiation bar,
a mock below full route or component coverage, a selected build delegated against
the wrong id, a selected variant below full parity, a user choice that collides
with a mandatory requirement, a Taste revision changing mid-run, an undecided
user, and a user who changes the choice after the build.

| Scenario | Response |
| --- | --- |
| The four directions differ only in palette or one category | Return `REVISE` to `design/architect` naming the categories that must diverge; do not commission mocks for near-duplicates. |
| A mock misses inventory routes or components, or draws a route only in prose | Return the exact missing ids to `design/prototyper`; mock parity below full route and component coverage keeps the mock out of the comparison. States, interactions, and flows are informational at mock level and are never the reason a mock is returned. |
| A `selected-build` is about to be delegated for an id the `selection` record does not name, or before `reports/selection.md` exists | Do not delegate. Write and register the selection record first, then delegate for `selection.chosen` alone. The builder refuses the delegation anyway, and the sequencing defect is redesign's to fix. |
| The selected variant misses inventory ids or renders a state only in prose | Return the exact missing ids to `design/prototyper`; full parity below full coverage keeps the package out of the gate. This is the one build in the pipeline, so it is repaired rather than replaced. |
| The user's choice conflicts with a mandatory accessibility, security, or gate requirement | Surface the conflict, keep the requirement, and record the user's decision as a scoped exception only with explicit intent. |
| Taste source revisions change after the directions were written | Invalidate `taste_snapshot`, request re-resolution, and replay only the directions and mocks that used the changed entries; a selected build already underway is re-derived from the corrected mock. |
| The user cannot decide between mocks | Record `decision: deferred` with `chosen: null`, owner, and reopen trigger; carry `selection deferred - no variant built` on the four selection-dependent keys, gate the package with `recommendation` stating the deferral, and hand nothing to the design pipeline. No prototype is built for a deferral. |
| The user changes the choice after the selected variant is built | Record a new `selection` revision naming the new `chosen`, delegate one fresh `selected-build` for it, and keep the superseded variant on disk as evidence rather than overwriting it. The mocks are unchanged, so nothing before stage 8 is re-run. |
