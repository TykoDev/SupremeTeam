# Example Invocations

## Example 1 — the approved diff, and the file it produces

**User request:** set up deployment config

**Output:**
- Destination: `python skills/scripts/output_paths.py --run-id 2026-04-19-web --phase release --kind artifacts --name deploy-config.yaml` resolves to `skillset-saves/runs/2026-04-19-web/release/artifacts/deploy-config.yaml`, referenced from the gate package as `artifacts/deploy-config.yaml`.
- Proposed diff: six added keys and two changed values against the file already there — image tag policy, environment variables, secret references, and domain mappings — with every secret rendered as a reference and the effective value shown per environment.
- Approval: the platform owner approved that exact diff before the write; the approver, the approved diff, and the resulting file hash are stored with the configuration.

```yaml
# artifacts/deploy-config.yaml
target: { platform: ecs, region: eu-west-1 }
environments:
  staging:
    host: staging.example.com
    image_tag_policy: digest
    secrets: { DB_URL: "arn:aws:secretsmanager:eu-west-1:...:staging/db" }
    health_probe: { path: /healthz, expect: 200, timeout_s: 5 }
  production:
    host: www.example.com
    image_tag_policy: digest
    secrets: { DB_URL: "arn:aws:secretsmanager:eu-west-1:...:prod/db" }
    health_probe: { path: /healthz, expect: 200, timeout_s: 5 }
promotion: { from: staging, to: production, requires: [smoke_pass, human_go] }
artifact: { source: ghcr.io/example/web, retain_versions: 10 }
owners: { config: platform-team, rollback: release-owner }
```

- Risk removed: the release no longer depends on one engineer remembering a manual production override.
- Next move: feed the persisted config into the rollout flow and verify the staging environment uses the same contract.

## Example 2 — the rollback plan as a file, and what makes it incomplete

**User request:** prepare the release settings

**Output:**
- Environment model: staging and production share one artifact, but their secret references and public hostnames are documented explicitly rather than implied.
- Rollback plan written beside the config as `artifacts/rollback-plan.md`:

```markdown
# Rollback Plan - web, config revision 4

## Trigger
Signal: checkout error rate (dashboard "Checkout Health", panel 2)
Threshold: above 2% over a 5-minute window, sustained 5 minutes
Called by: on-call release owner; escalation: platform lead
Decision deadline: 60 minutes after rollout start; after that, repair forward

## Procedure
1. Redeploy `web-2026.04.12` - `deploy web --version 2026.04.12` (~4 min)
   Check: /healthz returns 200 and reports build 2026.04.12
2. Restore secret bundle v7 and certificate `star-example-2026-03`
   Check: TLS chain valid; no auth errors for 2 minutes after restart

## Data considerations
- `orders.currency` migration: forward-only. Compensating script
  `scripts/currency_backfill.py`, owned by payments.
```

- Blocker: the procedure restores a certificate the configuration does not preserve anywhere durable, so `rollback_plan` is not yet satisfiable at `deploy-readiness` — one of the three gate checks in `rollback-plan.md`.
- Recommendation: capture the certificate rollback path before approving the deploy setup.

## Example 3 — an unparseable file already at the canonical path

**User request:** persist the deployment details

**Output:**
- Stop before the diff: the file at `artifacts/deploy-config.yaml` fails to parse — `while scanning a simple key, could not find expected ':'` at line 42, where an unresolved merge-conflict marker sits.
- Consequence stated plainly: the mandated diff is uncomputable, so no owner approval is possible and no write happens. No partial parse, no text-level diff of a structured file, no silent overwrite.
- Two bounded choices offered: repair line 42 and rerun the diff unchanged, or approve an explicit full replacement presented as the whole proposed file against the 61 unparseable lines quoted verbatim.
- Preservation: the unparseable file stays beside the proposal as `deploy-config.yaml.unparsed` until the owner confirms, because it may hold the only record of a setting nobody remembers making.

## Example 4 — manual step that makes the setup non-replayable

**User request:** configure the deploy flow

**Output:**
- Persisted details: deployment target, artifact source, health-check URL, DNS record owner, and required smoke checks are now written into the reusable release config.
- Manual-step note: one database allowlist change still requires operator action and is called out as a release blocker.
- Unverified setting: the production secrets manager could not be reached during setup, so the production `DB_URL` reference is recorded as unverified rather than persisted as proven.
- Boundary note: the setup is not yet replay-safe until the manual step is automated or formally documented, and the unverified reference is confirmed.
