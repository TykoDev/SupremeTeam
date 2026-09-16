# Failure Modes Reference

`../SKILL.md` carries the five failures that change what Investigate does next
(an unreproducible incident, an access boundary, an exhausted revise cycle, an
unusable request, a missing host capability). This file carries the rest: the
competing-hypothesis, provisional-mitigation, fix-path-scope, and first-REVISE
cases whose handling is procedural. Nothing here repeats a row stated in
`../SKILL.md`.

## Contents

The table below covers, in order: several failures starting at once, a
mitigation that removes the symptom without proving the chain, a fix path that
outgrows its mechanism, and the first REVISE packet.

| Scenario | Response |
| --- | --- |
| Several failures begin at the same time after both code and environment changes | Track competing hypotheses in parallel and avoid collapsing the incident onto the first plausible narrative; carry the surviving suspects in `mechanism` until the evidence chain separates them. |
| A candidate fix removes the symptom but leaves the causal chain unproven | Report the mitigation as provisional in `fix_path`, keep the unproven link visible in `evidence_chain`, and do not overclaim root-cause confidence. |
| The bounded fix path would be larger than the mechanism requires, or lands outside the owning phase | Narrow it to the smallest change that addresses the mechanism and hand it to the owning phase; investigate returns a path, not a build. |
| The gate returns `REVISE` | Re-judge only what the packet names: repair the failing keys, re-hash the affected artifacts, and resubmit once with `--prior`. All six keys have one owner, so the whole packet is resolved in a single pass. |
