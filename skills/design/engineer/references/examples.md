# Example Invocations

## Example 1

**User request:** prepare the implementation spec

**Output:**
- Slice order: auth and tenant model -> core API contracts -> admin UI integration -> background notifications.
- Operational note: tenant migration requires a dry-run backfill before feature flags can open the new workflow.
- Next move: hand the spec to `build-management` with the migration and validation expectations attached.

## Example 2

**User request:** translate design into delivery slices

**Output:**
- Slice map: API contract, persistence layer, worker queue, UI shell, and audit reporting.
- Risk: the queue worker cannot be implemented before the retry and idempotency rules are locked.
- Recommendation: separate the worker shell from the retry-policy slice so build work can start safely.

## Example 3

**User request:** write the engineering plan

**Output:**
- Build-facing detail: each slice includes owned modules, tests to add, rollout guardrails, and non-goals.
- Constraint: release one excludes historical backfill, so the plan marks it as a post-launch operational task rather than hiding it in implementation.
- Boundary note: the plan is build-ready once the remaining data-retention decision is approved.
