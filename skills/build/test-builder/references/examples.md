# Example Invocations

Five worked passes. The first three show the reasoning shape; Example 4 carries
a pass all the way to the hashed runner log and the typed `probe` record
`build/build-management` folds into the `build-to-review` manifest, and Example 5
shows a harness failure plus a quarantine handled with an owner and a reopen
trigger.

## Contents

1. Build the test suite
2. Cover the implementation with tests
3. Verify the changed behavior
4. Full pass returned as a hashed log and probe record
5. Harness failure and an approved quarantine

## Example 1 — Build the test suite

**User request:** build the test suite

**Output:**
- Coverage plan: unit tests for validation logic, integration tests for webhook persistence, and one contract test for the outbound event payload.
- Evidence: the executed command and its captured log are attached for the submitted revision.
- Next move: hand the packet to `build/build-management` once the retry-path regression case is added.

## Example 2 — Cover the implementation with tests

**User request:** cover the implementation with tests

**Output:**
- Gap found: the feature is covered in unit tests but the permission boundary is untested.
- Remediation: add an integration test that proves unauthorized users cannot trigger the workflow — the denial is the assertion, not the allowed path.
- Readiness: the package is not complete until the authorization path is exercised.

## Example 3 — Verify the changed behavior

**User request:** verify the changed behavior

**Output:**
- Behavior checked: duplicate webhook delivery now results in one persisted record and one idempotent no-op.
- Limitation: the external sandbox was unavailable, so the package includes a mocked contract test and names the missing live-environment run.
- Boundary note: the build gate treats the live-sandbox gap as residual risk, not hidden completion.

## Example 4 — Full pass returned as a hashed log and probe record

**User request:** build the test suite — user notification system, three modules plus one migration

**Context:** Run `2026-04-19-notify`, revision 3, phase `build`. The implementation under test is `notifications/dispatcher.py`, `notifications/templates.py`, and `api/endpoints/notify.py`.

**Runner discovery:** the handoff named no test command (rung 1 empty);
`python skills/scripts/check_runtime.py --project-root . --detect-project --json`
returned `classification: "library/CLI"` with no registered stack (rung 2);
`pyproject.toml` declares no test script (rung 3); the built-in runner applies
(rung 4). No pytest exists in this project, so the command is
`python -m unittest discover`.

**Executed run:**

```text
destination  python skills/scripts/output_paths.py --run-id 2026-04-19-notify \
               --phase build --kind evidence --name tests-unittest.log
             -> skillset-saves/runs/2026-04-19-notify/build/evidence/tests-unittest.log

command      python -m unittest discover -s tests -p "test_*.py" -k notif \
               > skillset-saves/runs/2026-04-19-notify/build/evidence/tests-unittest.log 2>&1
exit         0
tail         Ran 41 tests in 6.812s / OK

register     python skills/harness/hooks/save_run.py checkpoint \
               --run-id 2026-04-19-notify --owner test-builder \
               --evidence skillset-saves/runs/2026-04-19-notify/build/evidence/tests-unittest.log
```

**`tests` evidence handed to `build/build-management`** — the typed `probe`
record, with `artifacts` manifest-relative and `inputs` bound by sha256 to the
source the suite exercised:

```json
"tests": {
  "artifacts": ["evidence/tests-unittest.log"],
  "result": { "status": "pass" },
  "tool": "python -m unittest",
  "command": "python -m unittest discover -s tests -p \"test_*.py\" -k notif",
  "observed_at": "2026-04-19T14:02:11Z",
  "inputs": [
    { "path": "notifications/dispatcher.py", "sha256": "1ae141ad1dd336f29462b4b8aa0ace76f5dd3bf51c79e03c0fe0edf0de64fa20" },
    { "path": "notifications/templates.py",  "sha256": "f787e8159a70f7adc7b94d67c8a80ab66e6617cd8de90d35da4966863e45da5f" },
    { "path": "api/endpoints/notify.py",     "sha256": "02c0661b801f6ab63d33fb28afd092e5149bfd12cee1f632f4afa0ee101a3762" }
  ]
}
```

**Artifact hash registered into the manifest's `artifact_hashes` map:**
`evidence/tests-unittest.log` →
`7587f02ca8468f067f77a527b2e8a68a7f5aad035f998cec1d66f38c23851fb9`.

**Coverage statement returned beside the record:**
- Exercised: S1 event routing (unit), S2 API contract (integration, including one 403 denial path), S3 configuration key parity (unit).
- Not reached: S4 live delivery to the email and push backends — the sandbox credential is absent from CI. Stated as unverified; not approximated with a mock that would read as coverage.
- Quarantine: none in this pass.

## Example 5 — Harness failure and an approved quarantine

**User request:** build the test suite — the CI runner crashes mid-run and two existing tests return inconsistent results across re-runs

**Context:** After an authorization refactor, the CI runner exits with a process-level error on the integration step; two pre-existing tests in the session-management suite fail intermittently with no code change.

**Output:**
- **Harness failure, not a test failure.** The aborted run yields no verdict in either direction. Recorded: command `python -m unittest discover -s tests -p "test_*.py"` (discovery rung 4), observed error `runner exited 3221225477 before the summary line`. Returned to `build/build-management` as an infrastructure gap. **No `tests` evidence is produced** — `result.status` accepts only `pass` at this boundary, and an absent failure is not one.
- **Quarantine requested, not taken unilaterally.** `test_session_expiry_race` and `test_concurrent_refresh` in `tests/session/` fail non-deterministically. Excluding them narrows the scope build-management approved, so the exclusion is requested and the decision recorded before the suite is re-run.
- **Quarantine record, once approved** — the first five fields are the shape `../../../gates.yaml` `finding_policy.major_deferral` accepts for a deferred Major, so it travels into the findings record unchanged:

| Field | Value |
| --- | --- |
| `test_id` | `tests/session/test_expiry.py::test_session_expiry_race` |
| `observed` | 2 failures in 5 consecutive identical runs; no consistent error message |
| `reason` | Believed to read the host clock directly, so expiry races the test's own setup |
| `owner` | build-management (reliability triage) |
| `reopen_trigger` | The session-expiry clock is injected rather than read from the host |
| `coverage_lost` | S5 session expiry under concurrent refresh — unverified until reopened |

- **Effect on the probe record**, once CI is restored and a clean run completes: `result.status: pass` is stated against the suite that ran, with the two excluded ids named in the coverage statement, so the status reads as "the suite that ran passed" rather than "the suite passed".
- **Refusal case:** had no owner been willing to hold the quarantine, or had no condition been named that would end it, the exclusion is refused and the instability returns as an open Major finding. A quarantine with no reopen trigger is a deletion with extra steps.
