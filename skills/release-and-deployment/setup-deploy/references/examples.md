# Example Invocations

## Example 1

**User request:** set up deployment config

**Output:**
- Durable config: image tag policy, environment variables, secret references, and domain mappings now live in one project-owned deploy config surface.
- Risk removed: the release no longer depends on one engineer remembering a manual production override.
- Next move: feed the persisted config into the rollout flow and verify the staging environment uses the same contract.

## Example 2

**User request:** prepare the release settings

**Output:**
- Environment model: staging and production share one artifact, but their secret references and public hostnames are documented explicitly rather than implied.
- Blocker: rollback is still weak because the previous certificate binding is not preserved anywhere durable.
- Recommendation: capture the certificate rollback path before approving the deploy setup.

## Example 3

**User request:** persist the deployment details

**Output:**
- Persisted details: deployment target, artifact source, health-check URL, DNS record owner, and required smoke checks are now written into the reusable release config.
- Manual-step note: one database allowlist change still requires operator action and is called out as a release blocker.
- Boundary note: the setup is not yet replay-safe until that manual step is automated or formally documented.
