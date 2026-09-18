# Example Invocations

Five passes. Examples 1-4 run inside an Admiral run, where the save path makes
the destination unambiguous. Example 5 is the standalone mode `../SKILL.md`
describes and the other four never render: no package, no gate key, no verdict,
and a destination that has to be resolved and recorded rather than derived from a
run id.

## Contents

1. Example 1 — the approved diff, and the file it produces
2. Example 2 — the rollback plan as a file, and what makes it incomplete
3. Example 3 — an unparseable file already at the canonical path
4. Example 4 — manual step that makes the setup non-replayable
5. Example 5 — standalone mode, and the resolved destination it has to record

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

## Example 5 — standalone mode, and the resolved destination it has to record

**User request:** set up the deploy config for this project (no run, no handoff, no `admiral`)

**Output:**
- Mode: **standalone**. `../routing-doctrine.md` classes this skill as directly invokable, and nothing about this invocation is inside a run — there is no run id, no package, no `deploy_config` or `rollback_plan` gate key, and **no verdict**. Said plainly up front, because the artifacts this produces are indistinguishable from the in-run ones once written, and a later reader must not mistake an unjudged file for a gated one.
- Destination, resolved and recorded: the project's deployment surface resolved to **`/srv/projects/notify-web/deploy/deploy-config.yaml`** — recorded as that absolute path, not as "the project's deployment surface". The resolution was bounded by the same rule that applies in a run: a canonical path inside the workspace, reached without traversal and without following a link. Recording it absolute is not a breach of the Canonical-config-path contract's rejection of absolute paths — that rejection governs a destination *offered to* the skill and a reference written *into a gate manifest*. Here the skill resolved the destination itself and there is no manifest, so the absolute form is the record, not an accepted input. `deploy/` was already a real directory in the tree, so no path component was created to make the write land, and the resolved path is itself the evidence that the boundary held.
- Why the absolute path is the deliverable and not a detail: in a run, `output_paths.py` and the run id make the destination re-derivable by anyone. Standalone there is nothing to re-derive it from, so a package that records only the filename leaves the next release guessing which of the project's several plausible config locations this one actually wrote — which is the exact ambiguity the durable-artifact contract exists to remove.
- Proposed diff: four added keys against the file already present — image tag policy, health-check URL, environment variables, and secret references, every secret rendered as a reference and never an inline value.
- Approval: the platform owner approved that exact diff before the write. The owner-approved diff is required here too; it is a property of writing production configuration, not of being inside a run, and standalone mode removes the gate, not the approval.
- Artifacts written: `deploy-config.yaml` → `sha256:5f1c8ae0…`; `rollback-plan.md` → `sha256:b307d24f…`, both at the resolved destination above, both hashes recorded beside the absolute path.
- What judged this: nothing. No gatekeeper read these files and no boundary closed over them. If this project later needs the gate's assurance over the configuration, rollback path, and verification plan, that is a `ship` run under `admiral`, and these artifacts are the durable input it carries forward — not a substitute for it.
