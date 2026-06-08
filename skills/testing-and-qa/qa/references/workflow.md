# Workflow Reference

## Contents

1. QA execution sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## QA Execution Sequence

1. Define the workflows, environments, and success checkpoints that must be tested. Design test cases with three layers: happy path (expected normal usage), boundary conditions (edge inputs, limits, empty states), and negative/error scenarios (invalid input, missing auth, unavailable dependencies).
2. Run the targeted checks. For each defect, capture: (a) numbered reproduction steps, (b) expected vs. actual behavior, (c) environment details (OS, browser/runtime version, test data), (d) relevant logs or screenshots. Isolate the defect to a minimal reproduction — bisect commits or narrow input conditions — before writing a fix.
3. Apply one atomic fix at a time and retest the touched path plus its closest risk neighbors. Never perform destructive operations or touch production environments without explicit owner approval; if a fix would exceed QA scope, stop and report instead of proceeding.
4. Stop when the surface stabilizes or when a blocker requires escalation. **Stabilized** means: all targeted defects no longer reproduce across at least 3 consecutive clean runs and no new regressions were introduced during the fix cycle.

## Sample QA Execution Record Entry

| # | Flow | Defect | Severity | Repro steps | Expected | Actual | Fix applied | After-fix result |
|---|------|--------|----------|-------------|----------|--------|-------------|-----------------|
| 1 | Checkout | Submit button disabled after payment error | High | 1. Add item. 2. Enter invalid card. 3. Dismiss error. | Button re-enables | Button stays disabled | Reset button state on error dismissal (commit abc123) | Pass — 3 consecutive clean runs |

## Decision Rules

- Prefer honest coverage over inflated claims that skip missing environments or test accounts.
- Keep each fix atomic so rollback and blame remain clear.
- Treat intermittent failures as evidence gaps until the triggering condition is narrow enough to verify.
- Preserve residual risks explicitly when the surface improves but is not fully stable.
- Stabilization requires the targeted defects to not reproduce across at least 3 consecutive runs with no new regressions introduced.
- Never perform destructive or irreversible operations; stop and hand off if a fix exceeds QA scope.

## Acceptance Checklist

- Tested workflows and environments are named explicitly.
- Every defect has numbered reproduction steps, expected vs. actual, and environment details.
- Every fix has before and after evidence and a minimal reproduction rationale.
- Retest scope is recorded for each change.
- Remaining risks and blockers are visible in the QA record.
- Stabilization criterion is stated and met (or blocker is named).

## Contract Notes

- Before/After Evidence: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- Atomic commit per fix: Keep each fix isolated, explain what changed, and preserve easy rollback boundaries even when several issues are found.
- Proactive triggers: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.

## Collaboration Notes

- None required beyond the active task surface.
