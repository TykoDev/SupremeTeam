# Example Invocations

## Example 1

**User request:** run QA on the checkout flow

**Output:**
- Scope: cart, address, payment, and confirmation states across desktop and mobile.
- Findings: two blocking defects, one fixed locally and reverified, one still blocked on a missing payment test account.
- Delivery: QA record with before and after evidence, retest coverage, and the exact blocker that still prevents signoff.

## Example 2

**User request:** test this product thoroughly after the auth refactor

**Output:**
- Scope: sign-in, password reset, session refresh, and account lockout flows.
- Execution: run the full auth sweep, apply one fix to the lockout timer bug, and rerun the affected flows plus session refresh.
- Residual risk: social-login coverage remains blocked until the staging provider credentials are restored.

## Example 3

**User request:** find and fix the issues in onboarding

**Output:**
- Scope: account creation, email verification, and first-run checklist.
- Fix strategy: isolate each fix so rollback remains easy if a follow-up retest opens a new regression.
- Delivery: QA execution record with scoped fixes, verification evidence, and the remaining open defect list.
