# Workflow Reference

## Contents

1. Implementation-spec sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Implementation-Spec Sequence

1. Confirm the approved design boundaries, runtime surfaces, and delivery constraints the build phase must honor.
2. Break the design into implementation slices with explicit module ownership, API endpoint contract-test mapping when endpoints exist, dependency order, and validation expectations.
3. Check the slice plan for migration risk, rollout safety, operational support work, and observability needs.
4. Package the result so build consumers know exactly what to implement first and what cannot proceed yet.

## Decision Rules

- Prefer slice boundaries that can be built, tested, and rolled out independently.
- Treat hidden migration or cutover work as a real blocker, not deferred housekeeping.
- Keep implementation detail consistent with approved design contracts and stack locks.
- Escalate when the engineering plan requires a design change rather than a delivery choice.

## Acceptance Checklist

- Slice order is explicit and dependency-aware.
- API endpoint contracts map to implementation slices and contract tests when endpoints are in scope.
- Module ownership and validation expectations are clear.
- Operational and rollout constraints are recorded.
- Remaining blockers are narrow and actionable.

## Contract Notes

- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- Proactive triggers: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.

## Collaboration Notes

- `design/commander` owns phase sequencing and consolidated package assembly.
- `design/gatekeeper-design` validates that the implementation specification is detailed enough for build planning.
