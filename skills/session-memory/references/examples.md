# Example Invocations

## Example 1

**User request:** save progress

**Output:**
- Checkpoint: review phase active, waiting on adversarial findings for the current revision.
- Saved continuity: approved design artifact path, build package revision, open blocker, and next action for the next session.
- Next move: resume at the same gate once the missing review packet is regenerated.

## Example 2

**User request:** checkpoint this run

**Output:**
- Run state: build pipeline paused after test failures on the staging-only integration suite.
- Learning recorded: staging fixtures drift frequently; rerun seed setup before treating those failures as app regressions.
- Resume note: restore the build package and rerun fixtures before retesting.

## Example 3

**User request:** resume from saved state

**Output:**
- Restored: last approved artifact set, current phase boundary, and pending blocker from the prior session.
- Drift warning: one referenced review artifact is missing, so the resume path is narrowed to the last verified checkpoint.
- Recommendation: regenerate the missing artifact before continuing the downstream stage.

## Example 4

**User request:** record a learning / save what we learned

**Output:**
- Learning recorded: auth token refresh must be triggered before any downstream API call in the pipeline; skipping it causes silent 401s that the retry logic misidentifies as network errors.
  - layer: environment-contract
  - failure-category: environment-contract
  - evidence: `src/api/client.ts` line 84 — token expiry not checked before request dispatch
  - confidence: high
- Reuse trigger: any skill that performs authenticated API calls should query this learning before issuing requests.
