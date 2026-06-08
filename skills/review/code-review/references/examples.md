# Example Invocations

## Example 1

**User request:** review the code in the feature-flag rollout branch

**Output:**
- Scope: feature-flag evaluation, fallback behavior, and the tests covering the new branch.
- Merge blocker: the new helper changes the default flag behavior but leaves two call sites on the prior semantic path.
- Cleanup note: inline conditionals should move to a named function only after the semantic mismatch is fixed.

## Example 2

**User request:** check merge readiness for the billing service diff

**Output:**
- Scope: billing service handlers, migration script, and updated retry tests.
- Major finding: the diff adds a new API field without updating the serializer contract test, so the change is not yet merge-ready.
- Delivery: packet grouped into blockers, follow-up tests, and optional refactors.

## Example 3

**User request:** audit this change in the controller refactor

**Output:**
- Scope: controller refactor plus the error-mapping utility used by two endpoints.
- Finding set: response status mapping is now clearer, but one exception path loses the request id and hurts reviewer confidence in incident traceability.
- Handoff: ask `review/quality-review` to inspect whether the refactor also increases layering drift.
