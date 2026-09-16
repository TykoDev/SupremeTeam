# Example Invocations

## Example 1 — standalone mode, fix-and-reverify

**User request:** run QA on the checkout flow

**Output:**
- Mode: standalone — no Save Context block and no run lock, so nothing is persisted and no `qa-review` verdict is sought. Stated in the first line of the reply.
- Scope: cart, address, payment, and confirmation states across desktop Chrome 124 and iOS Safari 17 on staging v2.3.1.
- Findings: two blocking defects. The submit button stayed disabled after a dismissed payment error; the fix reset the button state on dismissal and the path then passed 3 consecutive clean runs. The second is still blocked on a missing payment test account.
- Delivery: QA record with before-and-after evidence per fix, the retest scope for each, and the exact blocker that still prevents signoff — returned inline, with no package assembled.

## Example 2 — pipeline mode, package assembled and approved

**User request:** (delegated with a Save Context block, run `2026-04-19-auth`) test this product thoroughly after the auth refactor

**Output:**
- Mode: pipeline — persisting to `skillset-saves/runs/2026-04-19-auth/qa/`, destinations resolved with `output_paths.py`, and a `qa-review` verdict expected.
- Scope: sign-in, password reset, session refresh, and account lockout across two browsers and the API client.
- Evidence: `evidence/test-matrix.md` (18 flow × environment rows) and `evidence/executed-probes.log` (41 probes, 3 not-run) written to the run and hashed into `manifest.json` — `schema_version: 2`, `boundary: qa-review`, `owner: qa`, `run_id: 2026-04-19-auth`, `submission_id: 2026-04-19-auth_qa-review_attempt-1`, `revision: 4`, with an `artifact_hashes` entry per file. Both keys are typed `probe` records naming their tool, command, exit code, and `result.status: pass`, not bare paths.
- Execution: one fix to the lockout timer, reverified across the affected flows plus session refresh; `fixes_applied` names the commit and the rerun result.
- Residual risk: social login is blocked until the staging provider credentials are restored; the three dependent probes are recorded not-run with that reason rather than inferred.
- Gate: `python skills/harness/gatekeeper/check.py --boundary qa-review --package skillset-saves/runs/2026-04-19-auth/qa/manifest.json` passed the mechanical check before submission; the verdict returned **APPROVED** with the social-login gap carried as recorded residual risk.

## Example 3 — pipeline mode, REVISE and one resubmission

**User request:** (delegated, run `2026-04-19-onboarding`) find and fix the issues in onboarding

**Output:**
- Scope: account creation, email verification, and the first-run checklist.
- First submission: `REVISE`. One packet, two keys — `test_matrix` carried a pass rate instead of a typed probe record, and one Major defect was deferred with no reopen trigger.
- Repair: the executed matrix was written to `evidence/test-matrix.md`, hashed, and wrapped in a probe record with its command and `result.status: pass`; the deferred Major gained a named owner and a reopen trigger; the revision advanced to 3 and the `submission_id` to `attempt-2`.
- Resubmission: one cycle, with `--prior skillset-saves/runs/2026-04-19-onboarding/qa/verdict.json`, so `changed_evidence` named exactly those two keys and the gatekeeper carried its prior judgment on the rest. Verdict **APPROVED**.
- Boundary note: a second `REVISE` would have ended the cycle at `cycle_cap: 2` and escalated with both packets rather than opening a third round.

## Example 4 — browser surface required but unavailable

**User request:** verify the workflow end to end for the new signup page

**Output:**
- Scope: signup, verification email, and first-run state; the page is browser-only above the API boundary.
- Tooling gap: `open-browser` reports no browser surface on this host, so the `browser-session` and `evidence-capture` stages cannot run.
- Coverage: the API-level flows ran and are reported normally; each browser-dependent probe is recorded not-run with the reason, and the matrix rows stay present and marked untested rather than being dropped.
- Delivery: the record states which claims are supported by executed probes and which surface was never exercised, and `residual_risk` names the unverified rendering and interaction paths. No browser outcome is inferred from an API result.
