# Example Invocations

Five worked passes. The first three show the reasoning shape; Example 4 renders
the full traceability matrix, its reason codes, and the hashed completeness
report `build/build-management` authors its `traceability` key from, and
Example 5 shows a correctly waived package passing rather than being blocked.

## Contents

1. Confirm build completeness for the release candidate
2. Cross-check the build package before review
3. Verify the implementation is complete
4. Full pass with a rendered traceability matrix
5. Correctly waived package

## Example 1 — Confirm build completeness for the release candidate

**User request:** confirm build completeness for the release candidate

**Output:**
- Required deliverables: implementation change set, test log, runtime smoke log, security findings record, and package metadata.
- Blocking gap: the security record is cited by the build summary but absent from the package — `unproven`, reason `unbound-claim`.
- Delivery: a completeness report marking the package incomplete until the missing artifact is attached, with the gap routed to `build/security-builder` through `build/build-management`.

## Example 2 — Cross-check the build package before review

**User request:** cross-check the build package before review

**Output:**
- Scope: web app bundle, API container image, and integration test evidence.
- Contradiction: the package manifest lists one image digest while the deployment notes cite a different one. Both rows marked `unproven`, reason `contradicted`; neither digest is chosen here.
- Next action: reconcile the artifact lineage through `build/build-management` before the package advances to `build/gatekeeper-build`.

## Example 3 — Verify the implementation is complete

**User request:** verify the implementation is complete

**Output:**
- Scope: implementation diff, generated artifacts, and the regression test record.
- Confirmation: every row `proven`; the remaining risks are limited to post-build monitoring, not missing build proof.
- Delivery: a gate-ready completeness report with explicit artifact evidence per row.

## Example 4 — Full pass with a rendered traceability matrix

**User request:** confirm build completeness — notification service

**Context:** Run `2026-04-19-notify`, revision 3, phase `build`. Baseline: approved design revision `design-r7`, five approved decisions (`D-01` … `D-05`) plus the package-level runtime row.

**Traceability matrix:**

| decision_id | changed_artifact | test_evidence | security_evidence | status | reason |
| --- | --- | --- | --- | --- | --- |
| `D-01` event routing | `notifications/dispatcher.py` `1ae141ad…fa20` | `evidence/tests-unittest.log` :: `test_dispatcher_routes` | `SEC-04` verified | `proven` | waiver: none |
| `D-02` template rendering | `notifications/templates.py` `f787e815…da5f` | `evidence/tests-unittest.log` :: `test_template_render` | `SEC-04` verified | `proven` | waiver: none |
| `D-03` API contract | `api/endpoints/notify.py` `02c0661b…3762` | `evidence/tests-unittest.log` :: `test_notify_endpoint`, `test_notify_denied` | `SEC-07` verified | `proven` | waiver: none |
| `D-04` config keys | `config/settings.py` `389dc786…8aff`, `config/env.sample` `7b9e596e…8af0` | `evidence/tests-unittest.log` :: `test_config_parity` | `SEC-09` deferred | `proven` | waiver: none; `SEC-09` carried, owner `build/build-management` |
| `D-05` delivery receipts | — | — | — | `unproven` | `missing-artifact` |
| `runtime` (package-level) | — | `evidence/runtime-smoke.log` `ff1dd65d…bf0d` | — | `proven` | waiver: none |

**Bindings actually verified, not read from the summary:** every cited path was
located in the package, found in the manifest's `artifact_hashes` map, and
confirmed against package revision 3. `evidence/tests-unittest.log` carries
`input_revision: 3`, matching.

**Reading the deferred security cell.** `D-04` cites `SEC-09` as `deferred`,
not `verified`, because that is the grade the run's own `security_evidence`
record carries — `../../security-builder/references/examples.md` grades it
`deferred` with owner `build/build-management` and a reopen trigger. The two
records describe one finding and must agree: copying a `verified` into the matrix
because the row's tests passed would launder a security grade through a build
artifact, which is the single thing this pass exists to catch.

A deferred finding does not make the row `unproven`. The `status` column grades
build completeness — an approved decision with a hashed artifact and bound test
evidence — and `D-04` has both. The deferral is a live security obligation
travelling with an owner and a reopen trigger, recorded here so the gatekeeper
reads one consistent grade, and it does not convert into a traceability gap.
Grade the two axes separately and quote each from its own owner's record.

**Counts:** 5 rows `proven`, 0 proven by waiver, 1 `unproven`.

**Completeness verdict:** the package is **not complete**. The threshold is every
row proven, not a percentage — `D-05` leaves the `implementation` and `tests`
keys without evidence for an approved decision, and `../../../gates.yaml`
`evidence_rules.required_evidence` requires every key present and non-falsy, so
the package fails the machine before a gatekeeper reads it.

**Gap list routed to `build/build-management`:**

| Row | Reason | Evidence that closes it | Owner |
| --- | --- | --- | --- |
| `D-05` delivery receipts | `missing-artifact` | The receipt-handler change set with hashes, plus a test exercising a receipt callback | `build/bob-the-builder`, then `build/test-builder` |

Nothing was edited in the package. The gap is routed, not repaired — this pass
is the only independent check between assembly and the gate, and repairing what
it finds would end that.

**Completeness report written and hashed:**

```text
destination  python skills/scripts/output_paths.py --run-id 2026-04-19-notify \
               --phase build --kind reports --name report_completeness.md
             -> skillset-saves/runs/2026-04-19-notify/build/reports/report_completeness.md
sha256       5c322d7d4428e465c252d20c95f9f926e3742f16e7446bc99cd7f93474ee481f

register     python skills/harness/hooks/save_run.py checkpoint \
               --run-id 2026-04-19-notify --owner cross-check-build-confirm \
               --evidence skillset-saves/runs/2026-04-19-notify/build/reports/report_completeness.md
```

**Downstream note:** `build/build-management` authors its `traceability` key from
this matrix unchanged — the `proven` / `unproven` vocabulary is exactly what
`../../../ownership.yaml` names for `build-traceability`, "proven and unproven
status per row", so no translation step sits between the matrix and the manifest.
`gates.yaml` checks `traceability` for presence only.

## Example 5 — Correctly waived package

**User request:** cross-check the build package — documentation and copy changes only

**Context:** Run `2026-05-02-copy`, revision 1. The change set touches three template strings and one help page. `build/security-builder` was not engaged because no trust boundary moved, and the `security_evidence` key carries the sanctioned fallback.

**Matrix (abbreviated):**

| decision_id | changed_artifact | test_evidence | security_evidence | status | reason |
| --- | --- | --- | --- | --- | --- |
| `D-01` help copy | `web/help/index.html` `1a881292…b51b` | `evidence/tests-unittest.log` :: `test_help_render` | `no trust-boundary change - security-builder not engaged` | `proven` | waiver: `gates.yaml` `fallback_values.security_evidence` |
| `D-02` template strings | `web/templates/notify.txt` `54d463dd…68b5` | `evidence/tests-unittest.log` :: `test_template_strings` | same sanctioned fallback | `proven` | waiver: same |
| `runtime` (package-level) | — | `evidence/runtime-smoke.log` `ccba6169…a2b3` | — | `proven` | waiver: none |

The waiver wording above is the `reason` of an applicability record
`{applicable: false, reason, scope, decided_by}` in the manifest, not a bare
string — `check.py` refuses the bare form at schema 2.

**Counts:** 3 rows `proven`, of which 2 are proven by waiver, 0 `unproven`.

**Verdict: complete.** The waived cells are evidence present, not gaps. The gate
itself exempts a key whose value exactly equals a sanctioned fallback from the
artifact-backing check (`../../../gates.yaml` `evidence_rules.artifact_evidence`),
so marking these rows unproven would contradict the machine the package is about
to face and burn a REVISE cycle on nothing.

**Two checks that were still performed on the waiver:**
- **Sanctioned for the key:** the string matches `fallback_values.security_evidence` exactly. A near-miss such as `no trust boundary changed` would be `unproven`, reason `unsanctioned-waiver`.
- **Sanctioned at this boundary:** `build-to-review` declares no `no_fallback` list, so the global fallback stands here.

**What was not waived:** `runtime` carries no sanctioned fallback at this
boundary, so the smoke log was required and verified even for a copy-only
change. `tests` likewise. A waiver on either would have been `unproven`,
reason `unsanctioned-waiver`, regardless of how small the change set looked.
