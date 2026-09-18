# Failure Modes Reference

`../SKILL.md` carries the five failures that change what Investigate does next
(an unreproducible incident, an access boundary, an exhausted revise cycle, an
unusable request, a missing host capability). This file carries the rest: the
competing-hypothesis, provisional-mitigation, fix-path-scope, and first-REVISE
cases whose handling is procedural. Nothing here repeats a row stated in
`../SKILL.md`.

## Contents

1. Several failures beginning at once
2. A mitigation that removes the symptom without proving the chain
3. A fix path that outgrows its mechanism
4. Evidence that expires mid-chain
5. A partially reproducible multi-failure incident
6. The first REVISE packet

| Scenario | Response |
| --- | --- |
| Several failures begin at the same time after both code and environment changes | Track competing hypotheses in parallel and avoid collapsing the incident onto the first plausible narrative; carry the surviving suspects in `mechanism` until the evidence chain separates them. |
| A candidate fix removes the symptom but leaves the causal chain unproven | Report the mitigation as provisional in `fix_path`, keep the unproven link visible in `evidence_chain`, and do not overclaim root-cause confidence. |
| The bounded fix path would be larger than the mechanism requires, or lands outside the owning phase | Narrow it to the smallest change that addresses the mechanism and hand it to the owning phase; investigate returns a path, not a build. |
| A link in the chain rests on evidence that expires before the chain closes — a rotating log window, a torn-down staging environment, an ephemeral container's stdout | Re-capture the link to a hashed artifact under the run's `evidence/` destination before it ages out, and record the capture timestamp on the link. A link whose source is already gone is downgraded to a labelled inference and drops out of the observed-link count; if the mechanism depends on it, the incident is unreproducible and takes that row in `../SKILL.md`. |
| Only some of the failures reproduce — one symptom replays on demand, the others appear intermittently or not at all | Split `scope` to the reproducible subset, settle its mechanism, and return that fix path. Carry the non-reproducing symptoms in `residual_uncertainty` with what was tried, and state plainly that the conclusion does not cover them. Do not let a reproduced mechanism absorb symptoms nothing connected to it — a partial reproduction is a bounded answer, not a whole one. |
| The gate returns `REVISE` | Re-judge only what the packet names: repair the failing keys, re-hash the affected artifacts, and resubmit once with `--prior`. All six keys have one owner, so the whole packet is resolved in a single pass. |
