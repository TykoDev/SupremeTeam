# Example Invocations

## Example 1

**User request:** ship this release tonight

**Output:**
- Candidate: web release 2026.04.19 with rollback build 2026.04.12 already staged.
- Launch sequence: package verification, canary rollout, live smoke checks, then broader rollout only if the canary stays healthy.
- Record: release note includes the rollback trigger and the first post-ship monitoring checkpoint.

## Example 2

**User request:** prepare the launch for the mobile API update

**Output:**
- Missing prerequisite: partner notification is still pending, so the rollout remains in no-go state.
- Safe next action: finish partner communication and recheck the launch window before any deployment step starts.
- Delivery: release record that preserves the blocked state instead of implying readiness.

## Example 3

**User request:** run the release flow for the dashboard refresh

**Output:**
- Rollout state: canary succeeded, but live verification found one high-latency metric above the agreed threshold.
- Decision: pause before the broader rollout and keep rollback ready while the team inspects the metric regression.
- Follow-up: explicit next actions and pause conditions stay in the release record.
