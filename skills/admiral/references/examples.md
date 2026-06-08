# Example Invocations

## Example 1

**User request:** run the full pipeline for a two-sided marketplace MVP

**Output:**
- Mode: full pipeline.
- Intake summary: user roles, payment risk, and launch deadline are captured before design begins.
- Next action: delegate to `design/commander`, then gate the returned package before any build work starts.

## Example 2

**User request:** resume from the approved design package and get me through review

**Output:**
- Mode: resume at build.
- Validation: confirm the design package still carries the matching approval lineage and has not drifted since the last handoff.
- Boundary rule: skip design only if the package revision is unchanged; otherwise rewind and re-gate.

## Example 3

**User request:** create a skill for automated invoice extraction with a strong eval loop

**Output:**
- Mode: create-skill.
- Delegation: pass the skill intent, trigger phrases, packaging target, and success criteria to `skill-maker`.
- Delivery: return the `.skill` package, score outcome, and any remaining follow-up tasks if the result does not ship on the first pass.

## Example 4

**User request:** build me a team of skills for design review, bug triage, and release coordination

**Output:**
- Mode: create-team.
- Intake note: capture the specialist roster, coordination model, and expected handoff pattern before invoking skill-maker.
- Delivery: return the coordinated team package plus the recommendation for how Admiral should consume it in later runs.

## Example 5

**User request:** ship this end to end, but stop if the build package drifts from the approved architecture

**Output:**
- Constraint: preserve architectural lineage across every handoff.
- Gate behavior: if build output no longer matches the approved design package, route the package back for revision instead of allowing review to absorb the inconsistency.
- Final package: include approved artifacts, rewound boundaries, and any disputed items that still require user judgment.
