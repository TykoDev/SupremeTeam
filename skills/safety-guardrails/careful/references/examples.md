# Example Invocations

## Example 1

**User request:** be careful with this schema migration

**Output:**
- Risky boundary: production billing tables and the migration that rewrites invoice status values.
- Decision: no-go until a rollback path and verified backup timestamp are attached to the request.
- Next safe action: collect the missing rollback proof and rerun the careful check before touching production data.

## Example 2

**User request:** add a safety guard before this deploy

**Output:**
- Risky boundary: container rollout for the public API during business hours.
- Decision: go only for a canary rollout because health checks exist, but the full rollout stays blocked until the error-budget owner signs off.
- Record: release conditions are written directly into the careful note so the deploy cannot be misread as fully approved.

## Example 3

**User request:** protect the risky action while I clean up stale files

**Output:**
- Risky boundary: a cleanup command that deletes files across shared build output and cached release artifacts.
- Decision: no-go because the target path and retention window are still ambiguous.
- Next safe action: scope the delete command to one directory and attach the retention rule before retrying.
