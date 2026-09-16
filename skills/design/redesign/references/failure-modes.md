# Failure Modes Reference

`../SKILL.md` carries the five failures that change what Redesign does next (no
readable surface, a browserless host, an unusable request, an exhausted revise
cycle, a missing host capability). This file carries the rest: the
differentiation, parity, conflict, and decision failures whose handling is
procedural. Nothing here repeats a row stated in `../SKILL.md`.

## Contents

The table below covers, in order: directions that fail the differentiation bar,
a prototype below full parity, a user choice that collides with a mandatory
requirement, a Taste revision changing mid-run, and an undecided user.

| Scenario | Response |
| --- | --- |
| The four directions differ only in palette or one category | Return `REVISE` to `design/architect` naming the categories that must diverge; do not commission prototypes for near-duplicates. |
| A prototype misses inventory ids or renders a state only in prose | Return the exact missing ids to `design/prototyper`; parity below full coverage keeps the variant out of the comparison. |
| The user's choice conflicts with a mandatory accessibility, security, or gate requirement | Surface the conflict, keep the requirement, and record the user's decision as a scoped exception only with explicit intent. |
| Taste source revisions change after the directions were written | Invalidate `taste_snapshot`, request re-resolution, and replay only the directions and variants that used the changed entries. |
| The user cannot decide between variants | Record a deferral with owner and reopen trigger, gate the package with `recommendation` stating the deferral, and hand nothing to the design pipeline. |
