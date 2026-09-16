# Example Invocations

Five worked passes. The first three show the reasoning shape; Example 4 carries
a pass all the way to the changed artifact set with hashes and the executed-check
log paths `build/build-management` folds into the `build-to-review` manifest, and
Example 5 shows the REVISE round trip.

## Contents

1. Implement the approved scope
2. Write the production code within a frozen schema
3. Apply the required fixes
4. Full pass returned as hashed evidence
5. REVISE returned from the gate

## Example 1 — Implement the approved scope

**User request:** implement the approved scope

**Output:**
- Scope slice: add idempotent retry handling to the payment webhook plus the matching unit and integration coverage.
- Evidence: changed files, tests run, and remaining risk if the external provider still times out unexpectedly.
- Gate note: the package is ready for build review because the implementation and evidence point to the same revision.

## Example 2 — Write the production code within a frozen schema

**User request:** write the production code

**Output:**
- Constraint: the approved scope excludes schema redesign.
- Result: implement the feature within the current schema, attach migration-free validation evidence, and escalate the future redesign as out of scope.
- Residual risk: the follow-up debt is named in the returned package rather than left as an unowned follow-up marker in the delivered surface.

## Example 3 — Apply the required fixes

**User request:** apply the required fixes

**Output:**
- Build finding addressed: sanitize attachment filenames and add regression coverage for path-traversal attempts.
- Non-goal: do not patch the third-party upload library, because that exceeds the approved ownership boundary.
- Next move: hand the updated set back to `build/build-management` with the re-hashed artifacts.

## Example 4 — Full pass returned as hashed evidence

**User request:** implement the approved scope — user notification system (three modules, two config files, one DB migration)

**Context:** The design package covers `notifications/dispatcher.py`, `notifications/templates.py`, `api/endpoints/notify.py`, environment config additions in `config/settings.py` and `config/env.sample`, and a migration adding the `notification_log` table. Run `2026-04-19-notify`, revision 3, phase `build`.

**Runner discovery:** the handoff named no test command (rung 1 empty);
`python skills/scripts/check_runtime.py --project-root . --detect-project --json`
returned `classification: "library/CLI"` with no registered stack (rung 2);
`pyproject.toml` declares no test script (rung 3); the built-in runner applies
(rung 4), so every suite below runs through
`python -m unittest discover -s tests -p "test_*.py" -k <selector>`.

**Changed artifact set** — repository-relative path, sha256, surface class, slice:

| Path | sha256 | Surface | Slice |
| --- | --- | --- | --- |
| `notifications/dispatcher.py` | `1ae141ad1dd336f29462b4b8aa0ace76f5dd3bf51c79e03c0fe0edf0de64fa20` | first-party | S1 event routing |
| `notifications/templates.py` | `f787e8159a70f7adc7b94d67c8a80ab66e6617cd8de90d35da4966863e45da5f` | first-party | S1 event routing |
| `api/endpoints/notify.py` | `02c0661b801f6ab63d33fb28afd092e5149bfd12cee1f632f4afa0ee101a3762` | first-party | S2 API contract |
| `config/settings.py` | `389dc7861514df10c2d9499d7141a3ee936b34752d35b5537ebff3a6bee88aff` | first-party | S3 configuration |
| `config/env.sample` | `7b9e596e2e5ec4d1352c55fe7a5504fb4f2a31363f4623d044c50e4bf2558af0` | first-party | S3 configuration |
| `migrations/0042_notification_log.py` | `c70fdfbc4371181906864e1079f43d4e6ee153ea3b1969871b654d922786e01a` | generated (ORM), isolated | S4 migration |

**Executed checks** — each captured to its own log under
`skillset-saves/runs/2026-04-19-notify/build/evidence/`, each path registered
with `save_run.py checkpoint --evidence`:

| Matrix row | Command | Log | Exit |
| --- | --- | --- | --- |
| First-party module | `python -m unittest discover -s tests -p "test_*.py" -k dispatcher > evidence/impl-unit-s1.log 2>&1` | `evidence/impl-unit-s1.log` | 0 |
| Public interface | `python -m unittest discover -s tests -p "test_*.py" -k notify_endpoint > evidence/impl-contract-s2.log 2>&1` | `evidence/impl-contract-s2.log` | 0 |
| Configuration sample | `git diff --stat -- config/ > evidence/impl-config.log 2>&1` | `evidence/impl-config.log` | 0 |
| Migration | up then down against a disposable local schema, both appended to one log | `evidence/impl-migration.log` | 0 |

**`implementation` evidence handed to `build/build-management`:**

```text
implementation:
  changed_artifact_set: 6 paths, sha256 per path (table above)
  first_party: 5   generated_or_vendored: 1 (migrations/0042_notification_log.py)
  placeholders_or_unowned_markers: none present
  executed_checks:
    evidence/impl-unit-s1.log        exit 0
    evidence/impl-contract-s2.log    exit 0
    evidence/impl-config.log         exit 0
    evidence/impl-migration.log      exit 0   (disposable local schema, both directions)
  revision: 3
```

**Notes carried with it:**
- Config drift found: `env.sample` was missing two required keys present in `settings.py`. The key names were added with values left to the environment; no credential value appears in either file or in this package.
- Migration proof ran up and down on a disposable local schema that was dropped and rebuilt for the check. No shared or staging target was touched, and none was authorized.
- Residual risk: end-to-end delivery confirmation (email and push backend calls) depends on a sandbox credential absent from CI; recorded as an explicit gap for the `build/health-check` pass, not closed here.
- The generated ORM migration is marked non-first-party so `build/security-builder` and the gate apply the tighter rules that surface needs.

## Example 5 — REVISE returned from the gate

**User request:** (none — `build/build-management` forwards a REVISE packet)

**Context:** `build/gatekeeper-build` returned `REVISE` at `build-to-review` for run `2026-04-19-notify`, revision 3. The packet's `revise_packet.by_owner` carries two groups: `implementation` (this skill) and `tests` (`build/test-builder`). Cycle 1 of 2.

**Output:**
- Group taken: `implementation` only. The `tests` group is left to `build/test-builder`, which fixes it in parallel; the two owners never wait on each other (`../../../gates.yaml` `revise_policy.parallel_fix`).
- Findings in the group: (a) `api/endpoints/notify.py` validates the request body after the side effect rather than before it — Major; (b) the migration log records only the up direction — Major.
- Repairs, one pass: validation moved ahead of the dispatch call; the down-migration re-run on a fresh disposable schema and appended to the same log.
- Re-hashed artifacts returned: `api/endpoints/notify.py` → `8b2b61804cde9170827b2a37abbfb701c00812a4f00ae5a236c2e516dbb94dbb`, `evidence/impl-migration.log` → `dbdae20ce0b3038817681d1118f97fc5f1cccb5f82e7ea6524dc8f3ce8e7f100`. Every unchanged path keeps its revision-3 hash so the gate re-judges only `changed_evidence`.
- Cycle note: this is cycle 1 of the `revise_policy.cycle_cap` of 2. A second REVISE on the same two findings escalates to `build/build-management` instead of a third resubmission, because a repeated failure on the same key is not an implementation defect.
