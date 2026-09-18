# Example Invocations

Five worked passes. The first three show the reasoning shape; Example 4 carries
a pass all the way to the hashed smoke log and the typed `probe` record
`build/build-management` folds into the `build-to-review` manifest, and Example 5
shows an unreachable target returned as the hard block it is.

## Contents

1. Run the health check
2. Verify runtime readiness
3. Check startup health
4. Full pass returned as a hashed smoke log and probe record
5. Unreachable target, credentials missing

## Example 1 — Run the health check

**User request:** run the health check

**Output:**
- Passed: app boot completes, readiness stabilizes inside the declared window, and the authenticated smoke request returns successfully.
- Failed: background queue health remains degraded because the worker cannot reach one dependency over the configured network path.
- Next move: fix the dependency route and rerun the health pass before release approval.

## Example 2 — Verify runtime readiness

**User request:** verify runtime readiness

**Output:**
- Environment tested: staging revision `2026-04-19-rc2`, named in the handoff, with the owner's authorization for authenticated probes against it recorded there and the sweep capped at the agreed request budget.
- Evidence: startup log, readiness poll series, dependency checks, and one end-to-end smoke flow are attached, each scrubbed of connection strings, tokens, and session identifiers before it entered the bundle.
- Boundary note: production readiness is still unverified because the pass only exercised staging.

## Example 3 — Check startup health

**User request:** check startup health

**Output:**
- Observation: the service reaches a healthy probe state, but a required migration silently retries and leaves the first authenticated request broken for two minutes.
- Classification: degraded startup, not healthy startup — the readiness predicate requires a body reporting no degraded dependency, and the first three satisfying responses arrived only after the migration settled.
- Recommendation: fix the startup ordering, or narrow the readiness claim to infrastructure-only health.

## Example 4 — Full pass returned as a hashed smoke log and probe record

**User request:** run the health check — notification service, staging

**Context:** Run `2026-04-19-notify`, revision 3, phase `build`. The handoff names target `staging`, base `https://notify.staging.internal`, revision `2026-04-19-rc2`, with owner authorization for authenticated probes recorded, a budget of 40 requests, a rate ceiling of 2 per second, and a stop condition of "first hard failure or budget exhaustion".

**Declared before the first probe:**

```text
window       90s   (deployment spec: initialDelay 30s + failureThreshold 6 x period 10s)
predicate    HTTP 200 AND body.dependencies contains no entry with state != "ok"
interval     2s
stability    3 consecutive satisfying responses
timeout      window exceeded => not ready
```

**Executed probes** — each captured under
`skillset-saves/runs/2026-04-19-notify/build/evidence/`, scrubbed as written:

| Probe | Command | Log | Result |
| --- | --- | --- | --- |
| Startup | `<start command> > evidence/runtime-startup.log 2>&1` | `evidence/runtime-startup.log` | boot at t+0, no restart loop |
| Readiness poll | `curl -sS -o evidence/runtime-readiness-body.json -w "%{http_code} %{time_total}\n" --max-time 5 https://notify.staging.internal/readyz` at 2s intervals | `evidence/runtime-readiness.log` | first satisfying response t+38s, stability reached t+42s, inside the 90s window |
| HTTP dependency | `curl -sS -o /dev/null -w "%{http_code} %{time_total}\n" --max-time 5 https://templates.staging.internal/health` | `evidence/runtime-dependencies.log` | 200 |
| TCP dependency | `python -c "import socket,sys; s=socket.create_connection((sys.argv[1],int(sys.argv[2])),5); s.close(); print('open')" pg.staging.internal 5432` | appended to the same log | open |
| Environment references | reference resolution, names only | `evidence/runtime-environment.log` | 7 present, 0 empty |
| Smoke flow | enqueue → dispatch → read-back, three requests | `evidence/runtime-smoke.log` | 3 steps, all 2xx |

Requests sent: 31 of the 40-request budget. Rate stayed at or below 2 per second.

**`runtime` evidence handed to `build/build-management`** — the typed `probe`
record, with `artifacts` manifest-relative:

```json
"runtime": {
  "artifacts": ["evidence/runtime-smoke.log", "evidence/runtime-startup.log"],
  "result": { "status": "pass" },
  "tool": "curl 8.17.0",
  "command": "startup + readiness poll + smoke flow against https://notify.staging.internal",
  "observed_at": "2026-04-19T15:11:40Z",
  "environment": "staging",
  "target_revision": "2026-04-19-rc2",
  "input_revision": 3
}
```

**Response-body disposition (workflow step, the readiness body):** the readiness
poll wrote `evidence/runtime-readiness-body.json`. It was scrubbed on the same
pass as the logs, the predicate was evaluated against it, and because the body
reports a degraded dependency it is **hashed into the package** rather than
deleted — a later reader needs the reason the dependency was degraded, not just
the verdict that it was. Had the body been an unremarkable `{"status":"ok"}`, it
would have been deleted on the same pass instead. Either way it does not survive
as a stray unhashed file.

**Artifact hashes registered into the manifest's `artifact_hashes` map:**
`evidence/runtime-smoke.log` →
`ff1dd65d59241d578651b6ff7647e7a41ba9f2476e94020807c7f33b35c2bf0d`;
`evidence/runtime-startup.log` →
`c47b690fdf551281faf70c8e4b93bfe8876bae32728b00209f39a6a01cbbe52f`;
`evidence/runtime-readiness-body.json` →
`9e0c4a13f7b258de41c0a9e8b6f7213dc5a48ff0316be7d9c2054e81a7f3cb64`.

**Environment dependency status returned beside the record:**

| Dependency | State | Observed signal |
| --- | --- | --- |
| template service | reachable | `200` in `evidence/runtime-dependencies.log`, line 3 |
| primary database | reachable | TCP `open` in the same log, line 7 |
| push gateway | **unexercised** | no smoke step reaches it on staging; marked unverified, not healthy |

**Side effects recorded:** the smoke flow created two notification rows on
staging (`notification_log` ids withheld from this report by reference). The
handoff accepted that side effect on this target.

**Residual:** production readiness is unverified — the pass exercised staging
only, and the report does not generalize past it.

## Example 5 — Unreachable target, credentials missing

**User request:** run the health check

**Context:** The pass is delegated against a staging environment, but the environment URL is unreachable and the required service-account credential reference is absent from the current build context.

**Output:**
- **Status:** the health pass cannot execute. No `runtime` evidence is produced.
- **Attempted, with observations:** `curl -sS -o /dev/null -w "%{http_code} %{time_total}\n" --max-time 5 https://notify.staging.internal/readyz` returned `000` after the 5s timeout with `Could not connect to server`; the credential lookup returned empty for both the environment variable and the secrets path named in the deployment config. Both are named **by reference only** — never a value, not even a partial one.
- **This is a hard block, not a caveat.** `../../../gates.yaml` `fallback_values` carries no entry for `runtime`, so there is no sanctioned string and no applicability record that closes this key. `build-to-review` cannot be submitted until a reachable, authorized target produces a smoke log. The `tests` key passing changes nothing here.
- **Scope of claim:** no health assertions of any kind. The environment readiness contract is **unverified**, which is not the same as unhealthy and is not the same as healthy.
- **Escalation:** an environmental gap report returns to `build/build-management` naming the unreachable endpoint, the two empty credential references, and the owner able to provision them. The pass re-runs once the environment is reachable and the references resolve.
- **Not done:** no substitute target was probed. A reachable production instance is not a fallback for an unreachable staging one; probing it would need its own recorded authorization, and reaching for it because staging was down is exactly the decision the authorization contract exists to prevent.
