# Example Invocations

## Example 1

**User request:** debug this failure

**Output:**
- Symptom boundary: the worker crashes only when one optional webhook payload includes an empty `events` array, which never appears in the passing fixtures.
- Root cause: the new parser assumes at least one event before checking payload shape.
- Next move: add the guard, reproduce against the real failing payload, and rerun the adjacent worker tests.

## Example 2

**User request:** find the root cause

**Output:**
- Evidence: staging failures started immediately after a connection-pool setting changed, and the same timeout reproduces locally only when that config is enabled.
- Conclusion: the defect is configuration-driven, not a query planner regression.
- Boundary note: fix the pool setting first, then rerun the same load case before widening the claim.

## Example 3

**User request:** repair the broken path

**Output:**
- Repair plan: restore the missing null check, add one regression test for the empty payload case, and keep the fix isolated to the parser boundary.
- Validation: the original failing scenario now passes and nearby parsing tests still fail when the guard is removed.
- Remaining risk: production data still needs one replay check because the local fixture set is incomplete.
