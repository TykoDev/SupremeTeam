# Example Invocations

## Example 1

**User request:** run the health check

**Output:**
- Passed: app boot completes, readiness probe stabilizes within the expected window, and the authenticated smoke request returns successfully.
- Failed: background queue health remains degraded because the worker cannot reach one dependency over the configured network path.
- Next move: fix the dependency route and rerun the health pass before release approval.

## Example 2

**User request:** verify runtime readiness

**Output:**
- Environment tested: staging revision `2026-04-19-rc2`.
- Evidence: startup logs, probe history, dependency checks, and one end-to-end smoke flow are attached.
- Boundary note: production readiness is still unverified because the pass only exercised staging.

## Example 3

**User request:** check startup health

**Output:**
- Observation: the service reaches a healthy probe state, but a required migration silently retries and leaves the first authenticated request broken for two minutes.
- Classification: degraded startup, not healthy startup.
- Recommendation: either fix the startup ordering or narrow the readiness claim to infrastructure-only health.

## Example 4

**User request:** run the health check — runtime target is inaccessible and credentials are missing

**Context:** The health pass is delegated against a staging environment, but the environment URL is unreachable and the required service-account credentials are absent from the current build context.

**Output:**
- Status: health pass cannot execute — runtime target is inaccessible and no valid credentials are available to authenticate the probe requests.
- Evidence gathered: connection attempt to the staging endpoint timed out after the configured probe window; credential lookup returned empty for both the environment variable and the secrets path specified in the deployment config.
- Scope of claim: no health assertions can be made; the environment readiness contract is unverified, not healthy.
- Escalation: returning an environmental gap report to `build/build-management` with the unreachable endpoint and the missing credential reference named explicitly. Health pass must be re-run once the environment is reachable and credentials are provisioned.
