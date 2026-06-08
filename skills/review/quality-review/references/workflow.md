# Workflow Reference

## Contents

1. Structural review sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Structural Review Sequence

1. Identify the boundaries in scope: modules, layers, configuration seams, and shared abstractions.
2. Compare the current change against those boundaries for duplication, drift, ownership confusion, and long-term maintenance cost.
3. Write findings that explain why the issue will increase future delivery cost or fragility, not just why the reviewer dislikes the shape.
4. Package the maintainability concerns with pragmatic remediation order for `review/code-chief`.

## Decision Rules

- Judge architecture drift against the existing system commitments, not against a theoretical greenfield target.
- Distinguish one-off cleanup from structural debt that will recur across future changes.
- Prefer evidence of change friction, configuration sprawl, or ownership confusion over abstract design purity arguments.
- Merge duplicate symptoms when they come from the same layering or abstraction failure.

## Acceptance Checklist

- Structural findings name the affected modules, layers, or abstractions.
- Long-term cost is explicit for each major issue.
- Lower-confidence debt notes stay separate from confirmed blockers.
- Remediation order is practical for the current system constraints.

## Contract Notes

- Before/After Evidence: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.

## Collaboration Notes

- `review/code-chief` consumes the maintainability packet and merges it with correctness, security, and adversarial findings.
- `review/gatekeeper-code` checks that architecture drift and debt findings are preserved accurately in the final package.
