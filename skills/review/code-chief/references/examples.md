# Example Invocations

## Example 1

**User request:** run the full review flow for the payments API before merge

**Output:**
- Scope: backend-only payments API changes touching auth, retries, and database writes.
- Invoked lenses: `review/bug-review`, `review/code-review`, `review/quality-review`, `review/security-review`, `review/mr-robot`.
- Skipped lenses: `review/frontier`, `review/design-qa`, and `review/devex-review` with a written no-UI/no-developer-surface justification.
- CSO skip: no accepted-risk, release-governance, or operating-model security claim is in scope.
- Delivery: consolidated review package grouped into blocking defects, security follow-ups, and merge-readiness fixes before `review/gatekeeper-code` submission.

## Example 2

**User request:** review this codebase comprehensively for the admin dashboard release

**Output:**
- Scope: full-stack dashboard release with React screens, shared API handlers, and a new design-token rollout.
- Invoked lenses: all five core lenses plus `review/cso`, `review/frontier`, and `review/design-qa` because rendered UI, screenshots, and release security posture are in scope.
- Consolidation rule: preserve any disagreement between code, security, and visual findings instead of flattening them into one average severity.
- Delivery: review package with per-lens findings, skip manifest, and prioritized remediation ordered by release-blocking risk.

## Example 3

**User request:** audit this change before merge for the public CLI and SDK

**Output:**
- Scope: release candidate for a CLI plus SDK setup docs and integration snippets.
- Invoked lenses: the five core lenses plus `review/devex-review` because onboarding and integration flows are part of the merge decision.
- Gate intent: require documented skips for any omitted optional lens and include a revision delta if the package is a resubmission.
- Delivery: consolidated packet with onboarding friction findings, merge blockers, and the exact items that `review/gatekeeper-code` must validate.
