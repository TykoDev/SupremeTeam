# Workflow Reference

## Contents

1. Investigation sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Investigation Sequence

1. Establish the symptom boundary, timing, and known impact.
2. Assemble the evidence set from logs, traces, diffs, runtime checks, and environment context.
3. Separate facts from hypotheses before testing any theory.
4. Attempt reproduction or narrowing checks that can falsify competing explanations.
5. End with either one supported root cause or a clearly bounded suspect list.

## Decision Rules

- Prefer the simplest theory that explains all surviving evidence, not the first theory that explains part of it.
- Keep mitigations distinct from confirmed root causes.
- Preserve contradictory evidence instead of smoothing it away.
- Escalate when a missing data source prevents confident causal claims.

## Acceptance Checklist

- The symptom timeline is explicit.
- Key evidence sources are named.
- Facts and hypotheses are separated.
- The conclusion is proportional to the evidence available.
- Next steps are concrete: fix, capture more data, or escalate.

## Contract Notes

- Before/After Evidence: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.

## Collaboration Notes

- None required beyond the active task surface.
