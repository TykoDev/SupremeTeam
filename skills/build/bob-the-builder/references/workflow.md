# Workflow Reference

The implementation sequence, how the project's runners are found before anything
is executed, which check proves which kind of change, and how the executed logs
become the `implementation` evidence `build/build-management` carries to
`build-to-review`. `SKILL.md` states the order; this file states the procedure.

## Contents

1. Implementation sequence
2. Runner discovery
3. Validation matrix
4. Evidence assembly
5. REVISE handling
6. Decision rules
7. Acceptance checklist
8. Collaboration notes

## Implementation Sequence

1. Confirm the approved scope, affected modules, and expected evidence for the build boundary.
2. Enumerate the change list and identify prerequisite gaps before editing anything.
3. Apply the change in the smallest coherent implementation slices that can be defended.
4. Discover the runners, execute the checks the changed surface calls for, and capture each to its own log file.
5. Return the changed artifact set, its hashes, and the executed-check log paths so the build gate reviews concrete evidence instead of promises.

## Runner Discovery

Never assume a runner. A command guessed from habit either fails loudly, which
wastes a cycle, or succeeds against the wrong surface, which is worse. Walk this
ladder and stop at the first rung that answers:

1. **The handoff.** Build constraints in the delegation may name the test
   command, the type checker, and the lint command outright. Named runners win
   over discovered ones.
2. **The project inspection probe.** Run
   `python skills/scripts/check_runtime.py --project-root . --detect-project --json`.
   It inspects read-only and returns `manifests`, `configs`, `stacks`, and
   `classification` without installing or mutating anything. An empty
   `stacks` list means no registered stack matched, not that no runner exists.
3. **The project manifest.** Read the declared script table for the ecosystem the
   probe found — `scripts` in `package.json`, `[project.scripts]` and tool
   sections in `pyproject.toml`, targets in a `Makefile`, tasks in a CI workflow.
   The command the project already uses is the command the evidence should show.
4. **The interpreter's built-in runner.** When no project-declared runner exists,
   fall back to what the language ships. For Python that is
   `python -m unittest discover -s <test-root> -p "test_*.py"`; `-k <pattern>`
   narrows to the changed surface and `-t <top-level>` fixes imports when the
   test root is not the import root. This repository has no pytest, so a command
   written against pytest here fails on invocation.
5. **No runner found.** Record the gap: the surface, the checks that would have
   proven it, and what was searched. An unrun check is reported as unverified in
   the returned set and escalated to `build/build-management`; it is never
   recorded as a pass.

## Validation Matrix

Which check proves which kind of change, the command shape to run it, and where
its log goes. Log paths are shown relative to the phase directory; resolve the
real destination with
`python skills/scripts/output_paths.py --run-id <run-id> --phase build --kind evidence --name <file>`
and append `2>&1` so a failing run captures its own error text rather than
losing it to the terminal.

| Changed surface | Check that proves it | Command shape | Log |
| --- | --- | --- | --- |
| First-party module or function | Targeted unit tests over the changed module | `python -m unittest discover -s <test-root> -p "test_*.py" -k <selector> > <log> 2>&1` | `evidence/impl-unit-<slice>.log` |
| Public interface or API contract | Contract or integration test exercising the declared contract end to end | `python -m unittest discover -s <test-root> -p "test_*.py" -k <contract-selector> > <log> 2>&1` | `evidence/impl-contract-<slice>.log` |
| Typed or compiled source | The project's declared type-check or build command, from discovery rung 3 | `<declared type or build command> > <log> 2>&1` | `evidence/impl-typecheck.log` |
| Dependency manifest or lockfile | Resolution plus a typed scan record bound to the lockfile | `python skills/scripts/scan_record.py --out <evidence>/impl-deps.json --input <lockfile> -- <scanner command>` | `evidence/impl-deps.json` plus the raw output stored beside it |
| Migration | Up then down against a disposable local schema, per the migration contract | `<project migration command up> > <log> 2>&1` then the down command appended to the same log | `evidence/impl-migration.log` |
| Configuration or environment sample | Key-name parity between the sample and the settings module, values excluded | `git diff --stat -- <config paths> > <log> 2>&1` plus the key-name list | `evidence/impl-config.log` |
| Generated or vendored surface | Re-run the generator and confirm the output is unchanged, then mark the surface non-first-party | `<generator command> && git diff --stat -- <generated paths> > <log> 2>&1` | `evidence/impl-generated.log` |
| Startup, entry point, or readiness | Not proven here | Hand to `build/health-check`; the `runtime` key is its evidence and a passing unit suite never substitutes for it | not applicable |

A row with no matching change is skipped and said to be skipped. A row whose
runner discovery ended at rung 5 is reported as a gap.

## Evidence Assembly

`../../../gates.yaml` `evidence_owners.build-to-review` assigns bob-the-builder one
key. `build/build-management` is the sole submitter at that boundary, so the key
is authored here and handed over unchanged.

| Key | What it must contain | Artifact-backed | Typed record | Sanctioned fallback |
| --- | --- | --- | --- | --- |
| `implementation` | The two evidence lines `../../../ownership.yaml` attaches to the `implementation` artifact: the changed artifact set with hashes, and the statement that no placeholder or unowned follow-up marker remains | No. `artifact_evidence` at `build-to-review` lists `tests` and `runtime` only, so the key itself is not required to name a hashed path | None. `evidence_types` assigns this key no shape, so a structured statement satisfies the mechanical check | None. `../../../gates.yaml` `fallback_values` carries no entry for this key, so it is not waivable and a build with no implementation cannot reach the gate |

Hand back, per changed file: the repository-relative path, its sha256, whether
it is first-party, generated, or vendored, and the delivery slice it serves.
Register each executed log through a `session-memory` checkpoint —
`python skills/harness/hooks/save_run.py checkpoint --run-id <run-id> --owner bob-the-builder --evidence <path>`
— so the hash is recorded by the same writer that owns the run record. Artifacts
are hashed byte-for-byte, so a log is never reformatted, re-indented, or
re-encoded after its hash is taken; do that and the gate reports hash drift on
evidence that was never actually changed.

A validation command that produces coverage sends it to the run, not the project
root. Resolve the destination with
`python skills/scripts/output_paths.py --run-id <run-id> --phase build --kind coverage --name .coverage --mkdir`
and point `COVERAGE_FILE` / `--data-file`, `--cov-report=<fmt>:<dest>/...`,
`--coverage.reportsDirectory`, or `--report-dir` + `--temp-dir` at it. Never use
parallel or per-process mode (`-p`, `--parallel-mode`, `parallel = True`) unless
the same command finishes with `coverage combine` into that destination, and
never loop a coverage run per test file. When the step ends nothing named
`.coverage`, `.coverage.*`, `.coverage/`, `htmlcov/`, or `.nyc_output/` is left
at the project root; the full rule and the per-runner flags are in
`../../test-builder/references/workflow.md` § Coverage destination.

## REVISE Handling

A `REVISE` arrives through `build/build-management` as one packet, already
grouped by owner in `revise_packet.by_owner` (`../../../gates.yaml`
`revise_policy.one_packet`). Take the group for `implementation` and nothing
else: another owner's group belongs to `build/test-builder`,
`build/health-check`, or `build/security-builder`, and fixing it here crosses an
ownership boundary the gate can see.

Fix every finding in the group in a single pass, re-run the affected matrix
rows, re-hash each changed artifact, and hand the updated set back once.
`revise_policy.cycle_cap` is 2; a third cycle escalates to the build owner
rather than resubmitting, because two failed repair attempts on the same key
means the finding is not an implementation defect.

## Decision Rules

- Do not turn a build task into a design rewrite.
- Keep generated or third-party surfaces on a short leash.
- Prefer one clean implementation slice over several entangled fixes.
- Escalate when proving the change would require unauthorized scope growth.
- Resolve every write against the repository root and keep it inside the approved change list; escalate any destination the list does not name.
- Execute a migration, in either direction, only against a disposable local schema unless the owner has approved the non-local target.
- Report an unrunnable check as a gap; never let a check that did not execute read as a check that passed.

## Acceptance Checklist

- Scope and touched surfaces are explicit.
- The runner for every executed check came from a named discovery rung, not from habit.
- Each executed check has its own log file, and each log path is registered with its hash.
- Validation evidence matches the submitted change set.
- Residual risks or blocked dependencies are recorded.
- Non-first-party content is clearly identified.
- Every written path resolves inside the working tree and inside the approved change list.
- Credential-shaped config was edited by key name only, with no secret value in the source or the package.
- The changed artifact set carries a sha256 per path and is ready for build-gate review.

## Collaboration Notes

The skills this workflow hands to and receives from are named in `../SKILL.md` § Collaboration Surface. What this workflow adds:

- `build/test-builder` and `build/health-check` own the `tests` and `runtime` keys; neither is authored here.
