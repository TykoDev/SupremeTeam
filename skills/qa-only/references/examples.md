# Example Invocations

## Example 1 — standalone, boundary recorded and released

**User request:** run QA without fixing on the signup flow

**Output:**
- Mode: standalone — no Save Context block and no run lock, so nothing is persisted and no gate verdict is sought.
- Boundary: `guard_state.py read-only --run-id qa-only-2026-04-19-signup --owner release-owner --allow ".harness-state/packages/**"` recorded before the first probe. That glob is the standalone report destination `output_paths.py --kind standalone_packages` resolves, and as an allow it grants nothing: Rule D in `skills/harness/hooks/pre_tool_use.py` already allows `.harness-state/**` unconditionally so the record itself stays writable. It is passed to state the destination, not to unlock it — the boundary's effect is that everything outside that directory is denied.
- Scope: account creation, email verification, and welcome-state transitions.
- Findings: one blocking defect (verification link expires in 60 seconds, not 24 hours), two moderate regressions, and two environments still untested.
- Release: `guard_state.py release-read-only --run-id qa-only-2026-04-19-signup --requester release-owner` returned ok, and `status` reports no active read-only run; both lines travel in the report.

## Example 2 — delegated inside the `qa` pipeline, with the sanctioned fallback

**User request:** (delegated with a Save Context block) test and report only for the new dashboard filters

**Output:**
- Mode: delegated inside the `qa` pipeline — run `2026-04-19-dashboard`, persisting to `skillset-saves/runs/2026-04-19-dashboard/qa/`. The sweep runs here; the package and the submission belong to `qa`.
- Boundary: recorded against the run id with `--allow "skillset-saves/runs/2026-04-19-dashboard/**"`, so evidence writes pass and everything else is denied.
- Evidence: `evidence/test-matrix.md` (12 flow × environment rows) and `evidence/executed-probes.log` written through `output_paths.py` and hashed into `manifest.json` (`schema_version: 2`, `boundary: qa-review`, `owner: qa`, `submission_id: 2026-04-19-dashboard_qa-review_attempt-1`, `revision: 3`), each wrapped in a typed `probe` record with its command and `result.status: pass`.
- Findings: one mobile-only blocker and one flaky desktop regression whose trigger is still being narrowed.
- `fixes_applied`: `{"applicable": false, "reason": "report-only run - no fixes applied", "scope": "dashboard filter surface", "decided_by": "release-owner"}` — the sanctioned fallback carried as the record's reason, not a description of restraint.
- Handoff: `check.py --boundary qa-review --package skillset-saves/runs/2026-04-19-dashboard/qa/manifest.json` passed the mechanical check on the evidence before it went back to `qa`. `qa` submitted, and the verdict returned APPROVED with the residual risk recorded.

## Example 3 — the fix request during an active boundary

**User request:** the filter bug is one line, just fix it while you're in there

**Output:**
- Refusal: the QA-only boundary is active, so the mutation is declined on scope before the harness declines it on enforcement — Rule D would deny the edit and produce a denial, not a fix.
- Kept: the defect stays in the report with its reproduction steps and the one-line fix described as a recommendation for the owning team.
- Alternative offered: finish the report, release the boundary, then rerun the same surface under `qa`, which is the skill that may fix and re-verify.

## Example 4 — partial access, and a boundary stranded by an interrupt

**User request:** audit the workflow for partner onboarding

**Output:**
- Scope: invite acceptance, credential setup, and first API call.
- Evidence gap: partner sandbox credentials are missing, so the final API call remains untested and is listed in the blocked-environment summary rather than inferred.
- Interrupt: the sweep was cancelled after the credential-setup probe, leaving the read-only record open; `guard_state.py status` named run `qa-only-2026-04-19-partner` and owner `qa-lead`, who released it with `--reason "sweep cancelled before step 5"` before any other work resumed in the project.
- Delivery: defect report that distinguishes confirmed failures from coverage gaps, with the boundary's record and its recovery shown.
