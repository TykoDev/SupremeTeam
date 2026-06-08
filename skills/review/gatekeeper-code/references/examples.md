# Example Invocations

## Example 1

**User request:** validate the review package

**Output:**
- Verdict: `REVISE`.
- Missing requirement: `review/security-review` is absent even though the package claims dependency and auth changes were assessed.
- Required fix: resubmit with the missing specialist report or explicitly narrow the scope before another gate attempt.

## Example 2

**User request:** check review readiness

**Output:**
- Verdict: `APPROVED`.
- Evidence map: all five core lenses are present, `review/cso` is skipped with a no-accepted-risk/no-release-posture justification, `review/frontier` is skipped with a no-rendered-UI justification, and the revision delta explains how prior blockers were cleared.
- Delivery note: preserve the approval record and reuse it on resume if the package revision does not change.

## Example 3

**User request:** challenge this review packet

**Output:**
- Verdict: `ESCALATE`.
- Conflict: `review/security-review` treats a token exposure as release-blocking while `review/code-review` marks the same path unreachable because the deployment config is missing.
- Required decision: obtain the missing runtime evidence or ask the user to resolve the risk-acceptance question before advancing.
