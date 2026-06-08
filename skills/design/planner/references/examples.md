# Example Invocations

## Example 1

**User request:** plan this project

**Output:**
- Milestones: scope validation -> core API and auth -> admin workflow -> reporting and rollout hardening.
- Critical gate: do not start reporting until the event model and permission matrix are approved.
- Next move: hand the plan to `architect` with the high-risk integration boundaries highlighted.

## Example 2

**User request:** create the rollout plan

**Output:**
- Release shape: internal alpha for operations users, then tenant-limited beta before general availability.
- Risk note: the plan depends on a migration rehearsal before beta because rollback is not instantaneous.
- Decision gate: choose between a feature-flagged rollout and a tenant-by-tenant migration before implementation slicing begins.

## Example 3

**User request:** sequence the implementation work

**Output:**
- Sequence: identity and permissions first, customer records second, billing hooks third, analytics last.
- Constraint: analytics cannot start until the event taxonomy is locked by architecture.
- Delivery note: the plan narrows the first release to the minimum workflow that proves account activation and billing success.
