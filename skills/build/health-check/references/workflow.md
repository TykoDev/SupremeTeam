# Workflow Reference

The runtime-health verification sequence, what a readiness window means before
any probe is sent, the probe matrix with its command shapes and capture
destinations, and how the executed logs become the `runtime` evidence
`build/build-management` carries to `build-to-review`. `SKILL.md` states the
order; this file states the procedure.

## Contents

1. Runtime-health verification sequence
2. Start-command discovery
3. Readiness window
4. Probe matrix
5. Evidence assembly
6. REVISE handling
7. Decision rules
8. Acceptance checklist
9. Collaboration notes

## Runtime-Health Verification Sequence

1. Confirm the named probe target, revision, and runtime contract the pass is meant to prove, plus the authorization and probe budget that cover authenticated traffic against that target.
2. Declare the readiness window, its predicate, and the poll policy before the first request, so "ready" is not decided after the fact.
3. Execute the probe matrix — startup, readiness poll, dependency reachability, smoke flow — capturing each to its own log under the phase `evidence/` directory, scrubbed as it is written.
4. Evaluate each boundary as healthy, degraded, or unverified, using repeatability across the poll series rather than a single sample.
5. Package the hashed smoke log, its typed probe record, the dependency status, and every side effect the pass created, so build-management and the gate see exactly what is ready and what still blocks confidence.
6. Tear down what the pass started: stop the process the startup probe left running, confirm it stopped, dispose of or hash every response body the polls wrote, and state both in the pass. A probe that returns while its service is still listening has not finished.

## Start-Command Discovery

Find the entry point before starting anything. `check_runtime.py` records
candidates **without running them**, which is the safe first step:

```bash
python skills/scripts/check_runtime.py --project-root . --detect-start-command --json
```

The `project_inspection.start_commands` list is the candidate set, drawn from
the project's own manifests. Then walk the same ladder used everywhere else:

1. **The handoff.** A named start command and base address win over anything
   discovered.
2. **The probe output** above.
3. **The project manifest** — `scripts.start` in `package.json`, a declared
   entry point in `pyproject.toml`, a service command in a container or compose
   file, the command the deployment spec runs.
4. **No candidate found.** Record the gap rather than inventing an invocation.
   `runtime` has no fallback, so the honest return is a blocked boundary.

## Readiness Window

"Healthy" is worthless without a stated window, and a window chosen after
watching the logs is not a measurement. Fix all five values before the first
probe and state them in the report:

| Value | Definition | Default when the deployment spec states none |
| --- | --- | --- |
| Window | Maximum wall-clock duration from process start to the first satisfying readiness response | 60s for a local or ephemeral instance; for an orchestrated deployment, the spec's own `initialDelaySeconds + failureThreshold × periodSeconds` |
| Predicate | What counts as satisfying: an HTTP status in the declared healthy set **and** the declared body assertion | `200` plus a body that reports no dependency as degraded |
| Poll interval | Gap between probes, so the window has visible resolution in the log | 2s |
| Stability requirement | Number of consecutive satisfying responses before readiness is declared | 3 — a single healthy response during a restart loop is indistinguishable from readiness |
| Timeout outcome | What the window being exceeded means | Not ready. Never "slow", and never extended mid-pass to obtain a pass |

A `200` whose body reports a degraded dependency fails the predicate. Reporting
it as ready is the single most common way a health pass produces a green result
for a service that cannot serve traffic.

## Probe Matrix

Log paths are shown relative to the phase directory; resolve the real
destination with
`python skills/scripts/output_paths.py --run-id <run-id> --phase build --kind evidence --name <file>`.
Redirect combined streams so a failing probe captures its own error text, and
scrub each capture as it is written.

Two things the matrix creates are neither a log nor a product side effect, so the
side-effect ledger — which is data-only by `../SKILL.md`'s scope — does not cover
them. Both are this workflow's to close:

- **The response body.** `curl -o` writes the readiness and liveness bodies somewhere. Resolve that somewhere under the run (`output_paths.py --kind evidence --name runtime-readiness-body.json`), scrub it on the same pass as the log, and evaluate the predicate against it. Once the predicate is decided, either hash it into the package as evidence — a body reporting a degraded dependency is exactly what a later reader needs — or delete it. What it must never be is a stray file at the project root, unscrubbed and unhashed, holding whatever the service chose to return.
- **The started process.** Step 1 deliberately leaves it running so the poll has something to poll. Step 8 stops it: terminate the process the startup probe started, confirm it is gone, and record the teardown in the pass. A probe run that leaves a service listening has changed the machine's state after returning, which is the thing the ledger exists to make visible even though this particular residue is not data.

| Probe | What it proves | Log |
| --- | --- | --- |
| Startup | The entry point boots and reaches a running state without crashing or restart-looping | `evidence/runtime-startup.log` |
| Readiness poll | Readiness is reached inside the declared window, and holds for the stability requirement | `evidence/runtime-readiness.log` |
| Liveness | The process answers at all, separately from readiness | appended to `evidence/runtime-readiness.log` |
| HTTP dependency | A declared downstream service is reachable from inside the runtime's network position | `evidence/runtime-dependencies.log` |
| TCP dependency | A database, cache, or broker accepts a connection | appended to `evidence/runtime-dependencies.log` |
| Environment references | Every required credential and config reference resolves, by name | `evidence/runtime-environment.log` |
| Smoke flow | One critical user path works end to end on the real target | `evidence/runtime-smoke.log` |
| Startup ordering | A migration, warm-up, or cache fill completes before the first authenticated request succeeds | cited from the two logs above |

Command shapes, in the same order:

```bash
# Startup — leave the process running for the readiness poll; step 8 tears it down.
<discovered start command> > evidence/runtime-startup.log 2>&1

# Readiness poll, and liveness against its own path. Repeat at the poll interval
# until the window expires, appending every line to the one log.
curl -sS -o "$BODY" -w "%{http_code} %{time_total}\n" --max-time 5 <base>/<readiness path>

# HTTP dependency
curl -sS -o /dev/null -w "%{http_code} %{time_total}\n" --max-time 5 <dependency url>

# TCP dependency
python -c "import socket,sys; s=socket.create_connection((sys.argv[1],int(sys.argv[2])),5); s.close(); print('open')" <host> <port>
```

The remaining three are not single commands. **Environment references** are a
resolution step printing each reference name with `present` or `empty`, never the
value. The **smoke flow** is the declared flow's own requests in order, with
status and duration per step. **Startup ordering** is read out of the startup log
against the first smoke-flow step's timestamp rather than probed separately.

A probe that cannot run is recorded as not run, with the command attempted and
the observed error. It is never recorded as a pass, and the surface it would
have covered is marked unverified.

## Evidence Assembly

`../../../gates.yaml` `evidence_owners.build-to-review` assigns health-check one
key. `build/build-management` is the sole submitter at that boundary, so the key
is authored here and handed over unchanged.

| Key | What it must contain | Artifact-backed | Typed record | Sanctioned fallback |
| --- | --- | --- | --- | --- |
| `runtime` | The startup or entry-point smoke log as a hashed file under the phase `evidence/` directory, plus the environment dependency status — the two evidence lines `../../../ownership.yaml` attaches to the `runtime` artifact | Yes. `artifact_evidence` at `build-to-review` lists `tests` and `runtime`, so the value must reference a path present in the manifest's `artifact_hashes` map | `probe`: hashed `artifacts`, `result.status: pass`. `evidence_type_rules.probe` names the startup/entry-point smoke log as the artifact at this boundary and rejects a bare claim | **None.** `../../../gates.yaml` `fallback_values` carries no entry for this key. An unverifiable runtime hard-blocks the boundary; no applicability record and no passing test suite substitutes for it |

Procedure: resolve the destination with `output_paths.py`, run the probe with
its output redirected there, scrub as written, register the hash through
`python skills/harness/hooks/save_run.py checkpoint --run-id <run-id> --owner health-check --evidence <path>`,
then build the record with `artifacts`, `result.status: pass`, `tool`,
`command`, `observed_at`, and the environment and revision probed. Artifacts are
hashed byte-for-byte, so no log is reformatted after its hash is taken.

If a probe command is one that also produces coverage — a smoke run through the
project's test runner, for instance — its coverage output goes to the run's
`evidence/coverage/` destination
(`python skills/scripts/output_paths.py --run-id <run-id> --phase build --kind coverage --name .coverage --mkdir`)
through `COVERAGE_FILE` / `--data-file`, `--cov-report`,
`--coverage.reportsDirectory`, or `--report-dir` + `--temp-dir`, never in
parallel or per-process mode without a `coverage combine` into that destination.
A runtime probe leaves no `.coverage`, `.coverage.*`, `.coverage/`, `htmlcov/`,
or `.nyc_output/` at the project root; see
`../../test-builder/references/workflow.md` § Coverage destination.

## REVISE Handling

A `REVISE` arrives through `build/build-management` as one packet, already
grouped by owner in `revise_packet.by_owner` (`../../../gates.yaml`
`revise_policy.one_packet`). Take the group for `runtime` and nothing else;
other groups belong to `build/bob-the-builder`, `build/test-builder`, or
`build/security-builder`, and each owner fixes its own group in parallel.

Re-probe against the **same authorized target**: a REVISE is not fresh
authorization for a different environment, and re-probing elsewhere makes the
resubmission incomparable to the original. Re-hash the log, hand the record back
once. `revise_policy.cycle_cap` is 2; a third cycle escalates to the build owner
rather than resubmitting.

## Decision Rules

- Prefer health evidence from real user-critical paths over shallow green infrastructure signals alone.
- Keep transient warm-up behavior separate from repeatable degradation, judged across the poll series.
- Treat unexercised dependencies and feature paths as unverified, not implicitly healthy.
- Escalate when the environment can run but still fails the approved readiness contract.
- Default to a non-production target, and treat a production or shared target as unreachable until the owner's authorization is recorded in the handoff.
- Scrub logs and transcripts as they are captured, so an unscrubbed copy never enters the evidence bundle.
- Never extend the readiness window mid-pass to turn a timeout into a pass; the window is part of the contract being tested.

## Acceptance Checklist

- Environment and revision under test are explicit, and both match the handoff.
- The readiness window, predicate, poll interval, and stability requirement were declared before the first probe.
- Startup, readiness, and critical dependency checks are named, each with its captured log.
- The report distinguishes healthy, degraded, and unverified boundaries.
- Every claim cites a line of captured output.
- The probe target was authorized, and the sweep stayed inside its stated bound.
- Every side effect the smoke flow created is recorded.
- Every attached log and transcript is scrubbed, and credentials appear by reference name only.
- The smoke log exists as a file, is hashed, and its path is registered.
- Next remediation or release action is clear.

## Collaboration Notes

The skills this workflow hands to and receives from are named in `../SKILL.md` § Collaboration Surface. What this workflow adds:

- `build/test-builder` — owns the `tests` key; neither key stands in for the other.
