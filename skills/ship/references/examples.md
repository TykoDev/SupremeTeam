# Example Invocations

## Example 1 — pipeline mode, package assembled and approved

**User request:** (delegated with a Save Context block, run `2026-04-19-web`) ship this release tonight

**Output:**
- Mode: pipeline — persisting to `skillset-saves/runs/2026-04-19-web/release/`, closing at `deploy-readiness`. Stated in the opening line.
- Candidate: web release 2026.04.19 at `rev-8f21c0a`, approved at `review-to-delivery` on 2026-04-18; rollback build 2026.04.12 already staged.
- Launch sequence: package verification, canary rollout, live smoke checks, then broader rollout only if the canary stays healthy.
- Verification plan: written to `artifacts/verification-plan.md` **before** the rollout — error rate below 0.5% over 10 minutes, checkout p95 under 400 ms, zero payment-webhook failures — and hashed into the package so the pass conditions cannot be chosen after the rollout already looks healthy.
- Go decision: `approver: release-owner; reference: GO-2026-04-19-01; revision: rev-8f21c0a; decided_at: 2026-04-19T20:05:00Z`.
- Gate: `python skills/harness/gatekeeper/check.py --boundary deploy-readiness --package skillset-saves/runs/2026-04-19-web/release/manifest.json` passed the mechanical check first; the verdict returned **APPROVED**, and only then was the rollout delegated to `land-and-deploy`.

## Example 2 — the package shape that gate check reads

**User request:** what exactly gets submitted at the deploy-readiness boundary

**Output:**

| Evidence key | Value in the manifest | Backing |
| --- | --- | --- |
| `approved_delivery` | `rev-8f21c0a (review-to-delivery APPROVED, 2026-04-18)` | Typed `revision_ref` — no artifact, no fallback |
| `deploy_config` | `artifacts/deploy-config.yaml` | Hashed file, owned by `setup-deploy` |
| `verification_plan` | `artifacts/verification-plan.md` | Hashed file, owned by `ship` |
| `rollback_plan` | `artifacts/rollback-plan.md` | Hashed file, owned by `setup-deploy` |
| `human_go_required` | approver, reference, revision, timestamp | Narrative — no artifact, no fallback |

- Manifest: `schema_version: 2`, `boundary: deploy-readiness`, `owner: ship`, `run_id`, `submission_id`, and a single `revision` matching `revisions`.
- `artifact_hashes` carries one sha256 per artifact-backed path, each manifest-relative and inside the run directory; `output_paths.py` composes every one of them.
- Repeat release: the `setup` stage did not run, so the two `setup-deploy` keys name the artifacts persisted on the first deployment, with the revision and the hash each carried at re-verification time. See `gate-submission.md`.

## Example 3 — standalone mode, no gate, go decision carries the release

**User request:** prepare the launch for the mobile API update

**Output:**
- Mode: standalone — no Save Context block and no run lock, so no package is assembled and no `deploy-readiness` verdict will exist. Stated in the opening line.
- Readiness statement in place of the package: approved delivery `rev-3c9e11b`; `deploy-config` re-verified against the production target at revision 4 (environment, artifact flow, and secret references unchanged); rollback path re-verified against build 2026.04.02; verification plan fixed with its pass conditions before any rollout step.
- Missing prerequisite: partner notification is still pending, so the launch stays in no-go state and no go decision is sought yet.
- Boundary note: the result says explicitly that the rollout would proceed on the owner's go decision alone, with no gate assurance behind it, and that the gated route through `admiral` is available when this release needs more than an owner's word.
- Safe next action: finish partner communication, then recheck the launch window before any deployment step starts.

## Example 4 — verification contradicts the plan mid-rollout

**User request:** run the release flow for the dashboard refresh

**Output:**
- Rollout state: canary succeeded, but live verification found p95 latency at 620 ms against the 400 ms pass condition fixed in the verification plan.
- Decision: pause before the broader rollout and keep rollback ready while the team inspects the regression; the plan's threshold is not renegotiated after the fact, because a pass condition rewritten mid-rollout verifies nothing.
- Ownership: the latency regression goes to the owner of the release record as a finding rather than an edit made here, and the post-ship checklist keeps the pause condition and the rollback trigger explicit.
- Delivery: post-ship checklist with next launch actions, the outstanding checks, and the partial state recorded honestly rather than compressed into success.
