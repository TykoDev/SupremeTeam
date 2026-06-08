# Example Invocations

## Example 1

**User request:** implement the approved scope

**Output:**
- Scope slice: add idempotent retry handling to the payment webhook plus the matching unit and integration coverage.
- Evidence: changed files, tests run, and remaining risk if the external provider still times out unexpectedly.
- Gate note: package is ready for build review because the implementation and evidence point to the same revision.

## Example 2

**User request:** write the production code

**Output:**
- Constraint: the approved scope excludes schema redesign.
- Result: implement the feature within the current schema, attach migration-free validation evidence, and escalate the future redesign as out of scope.
- Residual risk: note the follow-up debt without leaving an unowned TODO in the delivered surface.

## Example 3

**User request:** apply the required fixes

**Output:**
- Build finding addressed: sanitize attachment filenames and add regression coverage for path traversal attempts.
- Non-goal: do not patch the third-party upload library because that exceeds the approved ownership boundary.
- Next move: hand the package back to `build/gatekeeper-build` with the updated evidence.

## Example 4

**User request:** implement the approved scope — user notification system (three modules, two config files, one DB migration)

**Context:** Design package covers `notifications/dispatcher.py`, `notifications/templates.py`, `api/endpoints/notify.py`, environment config additions in `config/settings.py` and `config/env.sample`, and a migration adding the `notification_log` table.

**Output:**
- Change list: five source files and one migration touched; auto-generated ORM migration file isolated and flagged as non-first-party surface requiring explicit scan.
- Implementation: dispatcher routes events to template renderer; API endpoint validates request body against the approved contract; migration is idempotent and rollback-safe with a matching down-migration.
- Validation run: unit tests for dispatcher routing and template rendering, integration test for the API endpoint against a seeded test DB, and migration verified both up and down on the local schema.
- Config drift found: `env.sample` was missing two required keys present in `settings.py`; added and noted as a non-functional fix within approved scope.
- Residual risk: end-to-end delivery confirmation (email/push backend calls) depends on a sandbox credential not present in CI; recorded as explicit out-of-scope gap for the health-check pass.
- Gate note: package ready for `build/gatekeeper-build`; migration file and ORM output are marked as non-first-party surfaces in the handoff manifest.
