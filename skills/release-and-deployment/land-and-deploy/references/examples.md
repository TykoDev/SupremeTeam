# Example Invocations

## Example 1

**User request:** land and deploy this

**Output:**
- Merge target: `release/2026-04-19`.
- Verification: capture pre-release health, deploy the approved revision, then rerun checkout and sign-in smoke tests against the live target.
- Result: return shipped revision, smoke outcome, and rollback status.

## Example 2

**User request:** merge and release it

**Output:**
- Release blocker: the branch contains an extra commit not covered by the approved review packet.
- Action: stop before merge and require a fresh review boundary for the drifted revision.
- Evidence: include the exact divergence and the last approved commit.

## Example 3

**User request:** ship the branch

**Output:**
- Deployment note: the rollout completed in staging, but production verification shows elevated error rates on the primary user flow.
- Status: partial deployment with hold.
- Next move: decide between rollback and targeted remediation before calling the release complete.
