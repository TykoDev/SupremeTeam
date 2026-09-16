# Workflow Reference

The test-design sequence, how the project's runner is found before a suite is
executed, and how the executed output becomes the `tests` evidence
`build/build-management` carries to `build-to-review`. `SKILL.md` states the
order; this file states the procedure.

## Contents

1. Test-design sequence
2. Runner discovery
3. Layer selection
4. Evidence assembly
5. REVISE handling
6. Decision rules
7. Acceptance checklist
8. Collaboration notes

## Test-Design Sequence

1. Confirm the changed behavior, risk surface, and the boundaries that actually need test proof.
2. Choose the right layers for coverage instead of defaulting to whichever test harness already exists.
3. Discover the runner, then execute the relevant suites and capture the runner's own output to a file.
4. Hash the log, build its typed probe record, and bind the record to the source by input digests.
5. Package the result so the build gate sees what is covered, what remains unverified, and why.

## Runner Discovery

Never assume a runner. Walk this ladder and stop at the first rung that answers:

1. **The handoff.** The delegation may name the test command outright. A named
   runner wins over a discovered one.
2. **The project inspection probe.** Run
   `python skills/scripts/check_runtime.py --project-root . --detect-project --json`.
   It inspects read-only and returns `manifests`, `configs`, `stacks`, and
   `classification` without installing or mutating anything. An empty `stacks`
   list means no registered stack matched, not that no runner exists.
3. **The project manifest.** Read the declared script table for the ecosystem
   the probe found — `scripts` in `package.json`, `[project.scripts]` and tool
   sections in `pyproject.toml`, targets in a `Makefile`, steps in a CI
   workflow. The command the project already uses is the command the evidence
   should show, because it is the command CI will run next.
4. **The interpreter's built-in runner.** When no project-declared runner
   exists, fall back to what the language ships. For Python that is
   `python -m unittest discover -s <test-root> -p "test_*.py"`, with `-k
   <pattern>` to narrow to the changed surface, `-t <top-level>` when the test
   root is not the import root, and `-v` when per-test lines are wanted in the
   log. **This repository has no pytest**, so a command written against pytest
   here fails on invocation and produces no evidence at all.
5. **No runner found.** Record the gap: the surface, the suites that would have
   proven it, and what was searched. Return the infrastructure gap to
   `build/build-management`; produce no `tests` evidence.

## Layer Selection

Match the layer to what would actually break, not to the harness that already
exists.

| Changed surface | Layer that proves it | Why not a cheaper layer |
| --- | --- | --- |
| Pure function or isolated branch logic | Unit | Nothing crosses a boundary, so an integration test only adds setup that can fail for unrelated reasons. |
| Declared API or interface contract | Contract or integration | A unit test over the handler asserts the handler's beliefs about the contract, not the contract. |
| Persistence, transaction, or idempotency behavior | Integration against a seeded store | Mocked persistence proves the mock is consistent with itself. |
| Authorization or permission boundary | Integration exercising a denied path | A test that only asserts the allowed path proves nothing about the boundary; the denial is the assertion. |
| Retry, timeout, or partial-failure handling | Integration with an injected failure | Happy-path coverage reports green on exactly the code that was added to handle failure. |
| Cross-service flow the build claims end to end | End-to-end, or an explicitly declared gap | An unrunnable end-to-end path is stated as unverified rather than approximated. |

## Evidence Assembly

`../../../gates.yaml` `evidence_owners.build-to-review` assigns test-builder one
key. `build/build-management` is the sole submitter at that boundary, so the key
is authored here and handed over unchanged.

| Key | What it must contain | Artifact-backed | Typed record | Sanctioned fallback |
| --- | --- | --- | --- | --- |
| `tests` | The test-runner log as a hashed file under the phase `evidence/` directory, plus the statement that the intended scope and key failure paths are covered — the two evidence lines `../../../ownership.yaml` attaches to the `tests` artifact | Yes. `artifact_evidence` at `build-to-review` lists `tests` and `runtime`, so the value must reference a path present in the manifest's `artifact_hashes` map | `probe`: hashed `artifacts`, `result.status: pass`. `evidence_type_rules.probe` names the test-runner log as the artifact at this boundary and rejects a bare count or claim | None. `../../../gates.yaml` `fallback_values` carries no entry for this key, so it is not waivable and no applicability record substitutes for a run that never happened |

Procedure:

1. Resolve the log destination with
   `python skills/scripts/output_paths.py --run-id <run-id> --phase build --kind evidence --name tests-<runner>.log`.
   Never compose the path by hand.
2. Run the suite with its output redirected to that file, combining streams so a
   failing run captures its own error text:
   `python -m unittest discover -s tests -p "test_*.py" > <log> 2>&1`.
3. Register the hash through a `session-memory` checkpoint —
   `python skills/harness/hooks/save_run.py checkpoint --run-id <run-id> --owner test-builder --evidence <path>`
   — so the same writer that owns the run record owns the digest.
4. Build the probe record: `artifacts` naming the manifest-relative log path,
   `result.status: pass`, `tool`, `command`, `observed_at`, and `inputs` binding
   `{path, sha256}` for each implementation file the suite exercised.
5. State coverage beside the record: slices and failure paths exercised, paths
   not reached, and any quarantine record.

A failing or aborted run produces no `tests` evidence. `result.status` accepts
only `pass` at this boundary; a record carrying any other status is a data gap,
and the honest return is the gap plus the log that shows it.

## REVISE Handling

A `REVISE` arrives through `build/build-management` as one packet, already
grouped by owner in `revise_packet.by_owner` (`../../../gates.yaml`
`revise_policy.one_packet`). Take the group for `tests` and nothing else; other
groups belong to `build/bob-the-builder`, `build/health-check`, or
`build/security-builder`, and each owner fixes its own group in parallel.

Fix every finding in the group in a single pass, re-run the affected suites,
re-hash the log, refresh `inputs` against the current source digests, and hand
the record back once. `revise_policy.cycle_cap` is 2; a third cycle escalates to
the build owner rather than resubmitting, because two failed repairs on the same
key means the finding is not a coverage defect.

## Decision Rules

- Prefer coverage at the boundary where failure would matter most.
- Treat missing reproduction paths as missing evidence, not a documentation nicety.
- Keep out-of-scope coverage explicit whenever environment limits prevent a full run.
- Escalate when the right test surface requires design or infrastructure decisions outside the assigned build scope.
- Capture the runner's output to a file first and describe it second, so the description can never outrun the log.
- Quarantine only with recorded owner approval and a reopen trigger; otherwise return the instability as an open Major finding.

## Acceptance Checklist

- The tested behavior and boundaries are explicit.
- Coverage includes critical failure paths, not just success cases.
- The runner came from a named discovery rung rather than from habit.
- The executed log exists as a file, is hashed, and its path is registered.
- The probe record carries `result.status: pass`, the command, and `inputs` bound to the exercised source.
- Every quarantined test has an owner, a reopen trigger, and a stated coverage loss.
- Remaining risk is narrow and honest.

## Collaboration Notes

The skills this workflow hands to and receives from are named in `../SKILL.md` § Collaboration Surface. What this workflow adds:

- `build/health-check` — owns the `runtime` key; a passing suite never stands in for the startup smoke log.
