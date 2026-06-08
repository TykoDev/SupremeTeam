# Example Invocations

## Example 1

**User request:** guard this work on the release branch

**Output:**
- Boundary: release branch plus the deployment manifest files.
- Allowed actions: read, review, and propose patches outside the guarded files.
- Blocked actions: direct edits to release manifests until the owner lifts the guard.

## Example 2

**User request:** turn on the safety guard for the billing configs

**Output:**
- Boundary: billing configuration files and the job that syncs them to production.
- Guard rule: no writes without the billing owner and the current config checksum attached to the request.
- Next safe action: continue analysis work outside the guarded config path.

## Example 3

**User request:** protect this area while we investigate the incident

**Output:**
- Boundary: incident-related runbooks and the failing queue worker config.
- Violation detected: the requested change would also rewrite an unrelated shared config file outside the stated incident scope.
- Resolution: split the change set and keep the guarded incident boundary intact.

## Example 4

**User request:** lock down src/payments and turn on hard enforcement while we patch the charge bug

**Output:**
- Boundary: `src/payments/**` guarded; `**/secrets/**` blocked outright.
- Enforcement: recorded in `.harness-state/guard-state.json` so the pre-tool-use hook blocks stray writes — with the caveat that the hook fails open, so it is a discipline aid, not isolation (see `enforcement.md`).
- `allow_dangerous`: left `false`. The owner asked to run a destructive migration; enabling `allow_dangerous: true` is held pending the owner's named, scoped approval and will be reverted to `false` as soon as the migration completes.
- Next safe action: patch the charge bug inside the guarded path; secrets and unrelated configs stay blocked.
