---
name: test-builder
description: >-
  Authors the automated test surface and returns the `tests` evidence for
  `build-to-review`: the hashed test-runner log plus its typed probe record, not
  a pass-rate claim. Internal build specialist reached through
  `build/build-management`, not directly, even when the request is only "add
  some tests". Defers feature code to `build/bob-the-builder`, failure diagnosis
  to `build/debugger`, and startup and runtime health to `build/health-check`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

# Test Builder

## Purpose

Turns the changed surface into executable proof. The deliverable is the runner's own log — hashed, bound by input digests to the source it exercised, and paired with the explicit statement of which paths it did not reach. A count, a percentage, or a summary of what passed is not that deliverable.

## Use This Skill When

Use this skill to **author the automated test surface** — prove behavior across scope and the failure paths that matter:

- "build the test suite" / "cover the implementation with tests" — add coverage for the intended behavior
- "verify the changed behavior" — pin the new behavior with tests that would fail before the change
- "add regression protection" — lock down the paths most likely to break later

Route elsewhere when the task is writing the feature code (`build/bob-the-builder`), diagnosing a specific failure (`build/debugger`), or checking that the system runs (`build/health-check`).

## Entry Routing

Test-builder is an internal build specialist, not an entry point.
`../../routing-doctrine.md` places every `build/` skill it does not name
separately in the internal-specialist row, reached only through the owning
sub-orchestrator. Run the active-handoff check before authoring anything,
because the revision under test, the coverage expectation, and the evidence
destination arrive with the handoff, and a test suite bound to the wrong
revision proves nothing while looking like proof.

A handoff is present when the delegation prompt carries a `### Save Context`
block, an active run lock with `session_pin: true` exists under
`skillset-saves/`, or the invocation explicitly names `build/build-management`
as the delegating owner for the build boundary.

- **Handoff present** → proceed; this is a delegated test-surface assignment.
- **Reached cold** → author nothing. Return to `build/build-management`, which
  owns scope assignment and package assembly, then accept the delegation back.
  A cold invocation names no revision, so any log produced binds to nothing the
  gate can check.

## Inputs

- Implementation source code, delivery slices, and the interface contracts the tests must verify.
- Coverage targets, testing framework preferences, and any existing test infrastructure to extend.
- Known failure paths, edge cases, and regression risks identified during build or review.

## Outputs

Everything below returns to `build/build-management`, the only skill
`../../gates.yaml` `boundaries.build-to-review` permits to submit that boundary.
Test-builder submits nothing itself; it owns the `tests` key inside that
submission (`../../gates.yaml`, `evidence_owners.build-to-review`).

- The executed test-runner log, written as a file under the phase `evidence/` directory and hashed. `evidence_type_rules.probe` is explicit that at `build-to-review` `tests` is that log, and that a bare count or claim is not evidence.
- The typed `probe` record that carries it: hashed `artifacts`, `result.status: pass`, the `tool` and `command` that produced it, `observed_at`, and `inputs` binding the record by sha256 to the source files it exercised so stale evidence fails as input hash drift.
- The coverage statement: which delivery slices and failure paths the run exercised, which it did not reach, and why — plus any quarantine record, which narrows the coverage claim rather than hiding a gap.

`references/workflow.md` states the record shape, the path resolution, and how
the hash reaches the manifest.

## Workflow

1. Derive a test matrix from the changed modules, promised behavior, and the failure paths most likely to regress.
2. Add or update the right mix of unit, integration, contract, or end-to-end coverage around the changed behavior instead of relying on one generic test layer.
3. Discover the project's runner before running anything — the discovery ladder is in `references/workflow.md`, and this repository has no pytest, so a pytest command written from habit fails on invocation.
4. Execute the targeted suites, capture the runner's own output to a file under the phase `evidence/` directory, send any coverage data or report to the run's `evidence/coverage/` destination rather than the project root, and record exactly what passed, failed, or stayed out of scope, including the command needed to reproduce the result.
5. Return the hashed log, its typed probe record, the coverage statement, any quarantine record, and any blocked dependency that still needs owner input.

## Required Contracts

Full normative text for each contract is in `references/contracts.md`; the lines
below are the operative rule, not a summary that softens it.

- **Evidence is the log**: The deliverable is the runner's executed output as a hashed file plus its typed probe record. A pass rate, a coverage percentage, or a summary sentence is a claim about evidence, not evidence, and `evidence_type_rules.probe` rejects it at the boundary.
- **Coverage output belongs to the run**: Coverage data files and reports are run evidence, never project-root residue. Resolve the destination with `python skills/scripts/output_paths.py --run-id <run-id> --phase build --kind coverage --name .coverage --mkdir`, then point `COVERAGE_FILE`, `--data-file`, `--cov-report=<fmt>:<dest>/...`, `--coverage.reportsDirectory`, or `--report-dir` + `--temp-dir` at it. Never run coverage in parallel or per-process mode (`-p`, `--parallel-mode`, `parallel = True`) unless the same command finishes with `coverage combine` into that destination, and never loop coverage per test file. When the step ends, nothing named `.coverage`, `.coverage.*`, `.coverage/`, `htmlcov/`, or `.nyc_output/` remains at the project root — one observed run left a `.coverage` tree of over three thousand files there in under two minutes. `references/workflow.md` § Coverage destination carries the per-runner flags.
- **Quarantine record**: No test leaves the pass/fail verdict without the build owner's recorded approval and a durable record naming the test id, the observed instability, the reason, the owner, and the reopen trigger — the same shape `../../gates.yaml` `finding_policy.major_deferral` requires of a deferred Major. Quarantining silently mutates effective coverage while the package still reads green.
- **Harness failure is not a test result**: A crashed runner, a misconfigured CI step, or an unavailable harness produces no verdict in either direction. Report the infrastructure gap and produce no `tests` evidence until a clean run completes.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../../execution-contract.md` defines, so upstream and downstream packages read risk identically. Critical blocks; Major resolves before the gate or defers with an owner and a reopen trigger.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- `build/build-management` — delegating owner; assigns scope, approves any quarantine, receives the `tests` evidence, and is the sole `build-to-review` submitter.
- `build/gatekeeper-build` — downstream gate; judges the assembled package and returns a REVISE packet through build-management, never directly.
- `build/debugger` — receives a reproduced failure the test surface exposes; diagnosis is its assignment, not this one.

## Review Expectations

- Prove that every critical delivery slice and failure path has at least one test with a clear pass/fail assertion.
- Flag untestable boundaries explicitly rather than pretending coverage is complete.
- Structure test output so the review pipeline can verify behavior without re-reading the implementation.

## Skip Rule

Do not skip a mandatory build activity inside the canonical path; route scope changes through the build owner instead.

## Failure Modes

| Scenario | Response |
| --- | --- |
| Invoked cold with no `### Save Context` block, no active run lock, and no named delegating owner | Author nothing and run nothing. Return to `build/build-management` for the revision, the coverage expectation, and the evidence destination, then accept the delegation back. A log produced against an unnamed revision binds to nothing the gate can check. |
| `build/gatekeeper-build` returns a REVISE naming the `tests` key | Read the packet's `by_owner` group for this key only, fix every finding in it in one pass, re-run the affected suites, re-hash the log, and hand it back for a single resubmission. `../../gates.yaml` `revise_policy.cycle_cap` is 2; a third cycle escalates to the build owner instead of resubmitting. |
| The runner, CI step, or test environment is unavailable, or no runner can be discovered at all | Do not infer test health from the absence of failures. Record which runner was sought, at which discovery rung the search ended, and the observed error; return the infrastructure gap to `build/build-management` and produce no `tests` evidence until a clean run completes. |
| The test package covers only the happy path even though the changed surface introduces obvious failure, retry, or permission behavior | Mark coverage as incomplete and add the missing regression paths before claiming build readiness. |
| A flaky or slow test is left as the primary proof for the change without a stable reproduction path | Keep the instability visible, narrow the readiness claim, and route the reliability issue back through the build owner instead of burying it. |
| Required coverage depends on an unavailable environment, dataset, or third-party service | Record the missing prerequisite explicitly and avoid claiming that the behavior is verified when only a subset could run. |
| Assertions are added at the wrong layer, so the changed behavior appears covered but the critical contract or integration boundary is never exercised | Rework the test plan around the correct boundary and stop the package from advancing on false coverage. |
| The test harness itself is broken — the runner crashes, CI configuration is misconfigured, or infrastructure is unavailable — so pass or fail cannot be determined | Record the infrastructure failure explicitly, distinguish it from a genuine test failure, and return an infrastructure-gap report to the build owner. No `tests` evidence is produced until the harness is restored and a clean run completes. |
| Tests produce non-deterministic results across identical runs with no obvious environment cause | Quarantine only with the build owner's recorded approval and a durable quarantine record (test id, observed failure rate and sample size, reason, owner, reopen trigger). Mark every path the quarantined test covered as unverified, and name the exclusion inside the probe record so the pass status is read against the suite that actually ran. |
| A quarantine is requested with no owner willing to hold it, or with no condition that would reopen it | Refuse the quarantine and return the instability as an open Major finding. A quarantine without a reopen trigger is a deletion with extra steps, and effective coverage drops with nobody accountable for the drop. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Resolve every destination with `python skills/scripts/output_paths.py`, using the run id and
   phase from the Save Context block. Never compose a path by hand: the resolver refuses an
   unknown kind, a name that is absolute or traverses, and any path that escapes the
   project root, which is the containment check.
2. Write deliverables (reports, evidence bundles, review packets) to the destination it returns.
3. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
4. Never write `_phase-state.md`. No class in the save-ownership policy declares that path, so it is not an orchestrator-owned file either — phase state is published only through `save_run.py checkpoint`, which keeps revision lineage and the audit trail coherent.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.

## References

- `references/workflow.md` for the test-design sequence, the runner-discovery ladder, evidence assembly, and REVISE handling.
- `references/contracts.md` for the full normative text of the evidence, quarantine, and harness-failure contracts.
- `references/examples.md` for worked passes ending in the hashed runner log and its typed probe record.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/contracts.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
