# Example Invocations

## Example 1

**User request:** run the security oversight pass

**Output:**
- Highest-risk gap: privileged admin actions are protected by role checks but not step-up authentication, which leaves the most damaging path exposed to session theft.
- Governance note: the current monitoring playbook detects the action after the fact and does not qualify as a preventive control.
- Next move: add step-up auth for destructive admin flows and require a separate owner decision on break-glass access.

## Example 2

**User request:** review this like a security chief

**Output:**
- Strategic finding: the product posture depends on one third-party identity provider, but the release package never documents token revocation, outage fallback, or emergency lockout procedures.
- Severity: high because the business cannot explain how privileged access is contained during provider disruption.
- Recommendation: treat identity-provider resilience as a leadership-level control gap, not a minor implementation detail.

## Example 3

**User request:** challenge the product security posture

**Output:**
- Control review: data encryption at rest is present, but tenant isolation still depends on application-layer filters with no database-level guardrail.
- Risk framing: a single query-path mistake becomes a cross-tenant incident rather than a local bug.
- Next move: require a stronger isolation boundary or formally accept the risk with named ownership.
