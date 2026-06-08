# Example Invocations

## Example 1

**User request:** build the test suite

**Output:**
- Coverage plan: unit tests for validation logic, integration tests for webhook persistence, and one contract test for the outbound event payload.
- Evidence: targeted test commands and pass results are attached for the submitted revision.
- Next move: hand the build packet to `security-builder` once the retry-path regression case is added.

## Example 2

**User request:** cover the implementation with tests

**Output:**
- Gap found: the feature is covered in unit tests but the permission boundary is untested.
- Remediation: add an integration test that proves unauthorized users cannot trigger the workflow.
- Readiness: do not mark the package complete until the authorization path is exercised.

## Example 3

**User request:** verify the changed behavior

**Output:**
- Behavior checked: duplicate webhook delivery now results in one persisted record and one idempotent no-op.
- Limitation: the external sandbox was unavailable, so the package includes a mocked contract test and notes the missing live environment run.
- Boundary note: the build gate must treat the live-sandbox gap as residual risk, not hidden completion.

## Example 4

**User request:** build the test suite — CI runner crashes mid-run and two existing tests produce inconsistent results across re-runs

**Context:** After implementing the authorization refactor, the CI runner exits with a process-level error on the integration test step; two pre-existing tests in the session-management suite have been failing intermittently with no code change.

**Output:**
- Harness failure: CI runner crash is an infrastructure failure, not a test failure — no pass/fail verdict can be read from the aborted run. Infrastructure gap reported to `build/build-management`; test evidence is not produced until a clean run completes.
- Flaky tests identified: `test_session_expiry_race` and `test_concurrent_refresh` in `tests/session/` fail non-deterministically across identical runs. These tests are quarantined from the current verdict, documented with reproduction notes (failure rate ~40% over five re-runs, no consistent error message), and flagged for reliability triage before the next submission.
- Coverage authored: unit tests for the authorization boundary and one integration test for the permission-check path are ready and pass consistently in the local environment. These are held pending a clean CI run.
- Next move: restore CI runner and re-run; quarantined tests must achieve a stable pass before they can contribute to build readiness evidence.
