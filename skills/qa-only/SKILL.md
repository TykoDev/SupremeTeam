---
name: qa-only
description: >-
  Runs systematic product testing with no fixes applied, so the surface ends as
  it started and the team gets an evidence-backed defect report. Use for "run QA
  without fixing", "test and report only", "audit the workflow", or a read-only
  audit — even when the request is only "just tell me what's broken". Reports,
  never edits; defers fix-and-reverify QA to `qa` and performance
  measurement to `benchmark`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---


# QA Only

## Purpose

A defect report is trustworthy only when the surface that produced it did not move underneath the tester. This skill separates finding from fixing: it exercises the product, records reproducible evidence, and leaves both the remediation and the decision to remediate with the team that owns the code. The read-only posture is recorded in the harness rather than asserted in prose, so the report is provably a report.

## Use This Skill When

Use this skill to **test and report only** — produce a defect report without touching the code:

- "run QA without fixing" / "test and report only" — exercise the surface and document what fails
- "audit the workflow" / "read-only audit" — assess the workflow and record evidence, not fixes
- "gather product defects" / "don't touch anything, just tell me what's broken" — deliver a clear, evidence-backed defect list

Route elsewhere when fixes should be applied in the same loop (`qa`) or when the goal is quantitative performance measurement (`benchmark`).

## Entry Routing

`../routing-doctrine.md` classes `qa-only` a standalone tool, invokable directly at any time. It is also the report-only sweep the gated `qa` pipeline runs, and inside that pipeline it runs as a delegate: `../pipelines.yaml` names `qa-only` only as the `delegate` on the `defect-record` stage, whose owner is `qa`, so the sweep happens here while the stage, the package, and the submission stay with `qa`. Resolve the entry path before the first probe, because only one of them has a gate behind it:

| Signal | Mode | Behavior |
|--------|------|----------|
| A `### Save Context` block, or an active run lock under `skillset-saves/` | **Delegated, inside the `qa` pipeline** | Run the sweep under `qa`'s ownership, persist to the run's `qa/` phase directory, and return the defect report and its evidence to `qa`, which assembles and submits the `qa-review` package. Submit nothing here. |
| Neither present | **Standalone** | Run the same sequence directly and return the defect report inline. Persist nothing; no package and no gate are involved. |

Say which mode is active in the first response, so the operator knows whether a gate verdict is coming from `qa` afterwards. Both modes record the read-only boundary of Workflow step 1; only the run id differs, and `references/read-only-boundary.md` names the one to use in each.

This skill never submits a gate, in either mode. `../gates.yaml` makes `qa` the submitter of `qa-review` and the owner of all six of its evidence keys, and `../ownership.yaml` carries no `qa-only` entry at all. A report-only run changes what the package contains, not who owns or submits it: `qa` declares `boundary: qa-review` with `owner: qa`, alongside the `submission_id`, `run_id`, and single `revision` that `schema_version: 2` requires, and `fixes_applied` carries the sanctioned fallback instead of a fix list because this sweep applies none.

## Inputs

- Product surface under test, including critical workflows, supported environments, and expected behaviors.
- Known defects, prior QA findings, and any scope limitations such as environment access or data constraints.
- Test-scope boundaries defining what is in scope and what should be excluded from the report.
- The requester identity that owns the read-only boundary, because only that owner or a recorded approver can release it.

## Outputs

- QA-only defect report with reproducible issues, severity ratings, and reproduction steps for the remediation team.
- Evidence bundle with screenshots, logs, or recordings for each defect — no fixes applied.
- Blocked-environment summary listing any surfaces that could not be tested and why.
- Read-only boundary record: the run id, the allow globs, and the `release-read-only` result, reported as evidence that the surface was protected rather than as a claim that nothing was touched.

### Gate evidence

Delegated inside the `qa` pipeline, this sweep produces every required evidence key of the `qa-review` boundary and hands them to `qa`, which assembles and submits the package. Each key is produced here or `qa` cannot close the gate (`../gates.yaml`):

| Key | Content | Backing |
|-----|---------|---------|
| `scope` | The surface under test, the flows in and out of scope, and the environment. | Narrative |
| `test_matrix` | Flow × environment × outcome, one row per exercised path. | Artifact-backed, typed `probe` — a record naming a hashed file, not a count |
| `executed_probes` | The probes actually run, with commands, targets, and results. | Artifact-backed, typed `probe` — a record naming a hashed file |
| `defects` | Each defect with severity on the shared four-tier model and reproduction steps. | Typed `findings` record — `{items: [{id, severity, status}]}`, not prose. A narrative value fails with `defects must be a findings record with an items list at schema 2` |
| `fixes_applied` | The sanctioned fallback `report-only run - no fixes applied`, always, because this skill applies none. At `schema_version: 2` that waiver is the typed applicability record `{"applicable": false, "reason": "report-only run - no fixes applied", "scope": "<surface>", "decided_by": "<named owner>"}`; the bare string is rejected with `bare fallback string not accepted at schema 2`. | Applicability record carrying the verbatim fallback as its `reason` |
| `residual_risk` | What remains unverified, and why it was acceptable to stop. | Narrative |

`qa` self-checks the assembled package before it submits. Run the same validator against the evidence produced here before handing it over, so a defect in shape surfaces at the handoff rather than at the gate:

```bash
python skills/harness/gatekeeper/check.py --boundary qa-review --package <manifest.json>
```

A bare pass rate is not evidence. `test_matrix` and `executed_probes` are typed `probe` records at schema 2 — `artifacts`, `tool`, `command`, `exit_code`, `observed_at`, and `result.status` of `pass` — whose artifact paths are hashed files under the run's `evidence/` destination, resolved with `skills/scripts/output_paths.py`; a bare path string fails with `must be a typed probe record at schema 2`. A `REVISE` arrives through `qa` as one packet; re-run only the evidence it names as changed and return it, and `qa` resubmits once with `--prior`. `../gates.yaml` `revise_policy` sets `cycle_cap: 2`, so a second `REVISE` escalates rather than starting a third cycle.

## Workflow

1. Record the read-only boundary before the first probe, naming the run id and the one writable glob, so a stray write is denied by the harness instead of discovered in review:

   ```bash
   python skills/harness/hooks/guard_state.py read-only --run-id <run> --owner <requester> \
       --allow "skillset-saves/runs/<run>/**"
   ```

   `references/read-only-boundary.md` gives the run id and allow glob for each mode, and what the boundary does and does not stop.
2. Map the critical workflows, supported environments, and failure checkpoints that must be tested before any report is written.
3. Execute the test sweep without mutating the product surface. For each defect, capture: (a) numbered reproduction steps, (b) observed vs. expected behavior, (c) environment details (OS, runtime, test data state), (d) relevant logs or screenshots. If environment access is partial, record what could and could not be verified — do not imply coverage for untested surfaces.
4. Re-run flaky or ambiguous paths only to tighten the evidence boundary, not to apply fixes. If a path cannot be reliably reproduced, record the unstable reproduction boundary and mark confidence accordingly.
5. Release the boundary once the evidence is written and before the run ends:

   ```bash
   python skills/harness/hooks/guard_state.py release-read-only --run-id <run> --requester <requester>
   ```

   An unreleased record keeps denying writes project-wide in every later session, so the release is part of finishing the run, not tidying after it. Confirm with `python skills/harness/hooks/guard_state.py status` and carry that result into the report.
6. Return the QA-only report with reproducible defects, severity ratings, blocked environments, the boundary record and its release, and the clearest next action for the team that owns remediation. Delegated inside the `qa` pipeline, hand the report and the evidence keys above to `qa`, which assembles, self-checks, and submits the `qa-review` package; standalone, return the report inline and state that no gate verdict was sought. See `references/workflow.md` for full decision rules and `references/examples.md` for a sample defect report.

## Required Contracts

- **Reproduction Evidence**: For each defect, capture reproduction steps and observed-vs-expected state so the remediation team can act without re-investigating.
- **Deterministic read-only boundary**: This skill changes nothing, and that is enforced rather than promised. Workflow steps 1 and 5 record and release the boundary. While the record is unreleased, `pre_tool_use.py` denies every edit-tool write and every mutating shell command outside the run's own save path, and the release is authority-checked, so the boundary cannot be dropped by whoever happens to be running. Read-only means **no code or config changes**: exercising a flow may still create product data (an account, an invite), which is expected — record those side effects rather than avoiding the flow, and stop and report instead when a flow's side effects are not acceptable to the owner. `references/read-only-boundary.md` holds the run-id convention per mode, the allow globs, and the recovery path for a record left unreleased.
- **Coverage output belongs to the run**: A sweep that invokes the project's test tooling sends coverage data and reports to `skillset-saves/runs/<run>/qa/evidence/coverage/`, resolved with `python skills/scripts/output_paths.py --run-id <run> --phase qa --kind coverage --name .coverage --mkdir`, through `COVERAGE_FILE` / `--data-file`, `--cov-report`, `--coverage.reportsDirectory`, or `--report-dir` + `--temp-dir`. Never in parallel or per-process mode (`-p`, `--parallel-mode`, `parallel = True`) without a `coverage combine` into that destination, and never looped per test file. The read-only boundary is a tool-call guard, so it does not stop a runner writing `.coverage`, `.coverage.*`, `htmlcov/`, or `.nyc_output/` at the project root — and a report-only sweep that leaves residue there has changed the workspace it promised to leave alone. `references/read-only-boundary.md` § 3 carries the detail.
- **Partial-access transparency**: When environment access is incomplete, explicitly list what was tested and what could not be reached. Never imply coverage for surfaces that were not exercised.
- **Input validation**: Confirm that the product surface, the scope boundaries, the environment specification, and the requester who will own the read-only record are present and coherent before recording the boundary. Ambiguous scope is refused rather than guessed, because a boundary recorded against the wrong run id blocks the wrong workspace.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../execution-contract.md` defines, so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- None required beyond the active task surface.

## Review Expectations

- Report every defect with reproducible steps and evidence so the remediation team can act without re-investigating.
- Distinguish confirmed defects from flaky or environmental artifacts so severity ratings are trustworthy.
- Shape the report so the owning team can triage and assign defects directly from the output.
- Show the boundary record and its release in the result, because a read-only claim with no released record is the one shape that looks finished and leaves the workspace blocked.

## Skip Rule

Skip only when the requested surface, tool, or environment does not exist and a safe fallback is unavailable.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The product surface, scope boundary, or environment specification is missing, empty, or self-contradictory | Refuse to record the boundary and run nothing. Name the missing or conflicting input and the smallest clarification that unblocks the sweep; a boundary recorded on a guess blocks writes under a run id nobody will think to release. |
| A required environment, account, or test fixture is missing for one of the target workflows | Mark the workflow as untested, keep the report honest about the gap, and continue only with the flows that can still be exercised. |
| The browser surface, harness, or another required tool is unavailable for a planned probe | Record the probe as not-run with the reason rather than inferring its outcome, narrow the report to what was actually exercised, and list the unreached surface in the blocked-environment summary. |
| A defect reproduces inconsistently across runs | Capture the unstable reproduction boundary and avoid overstating confidence in the failure narrative. |
| Someone requests a quick fix while the QA-only boundary is active | Refuse the mutation, keep the scope report-only, and hand the defect to the team that owns remediation. The harness denies the write regardless, so agreeing would produce a denial rather than a fix; offer the alternative instead — finish the report, then rerun under `qa`, which is the skill that may fix. |
| The run ends before the boundary is released — a crash, an interrupt, a refused release, or a handoff that never returns | Treat the workspace as blocked, not the run as finished. The unreleased record makes hook Rule D deny every edit-tool write and mutating shell command project-wide in later sessions. Recover with `python skills/harness/hooks/guard_state.py status` to read the stuck run id and its owner, then release it as that owner or a recorded approver: `python skills/harness/hooks/guard_state.py release-read-only --run-id <run> --requester <owner> --reason "<why the run ended>"`. Nobody else can release it, and hand-editing `guard-state.json` is denied by the hook, so record the owner in the report while the run is still live. |
| Multiple failures collapse into one probable root cause | Group them under one evidence-backed defect chain so the report does not exaggerate the number of independent issues. |
| `qa` reports that `check.py` returned `REVISE` twice on the same package | Stop re-running the sweep for a third attempt. `../gates.yaml` `revise_policy` sets `cycle_cap: 2`, so the second `REVISE` escalates rather than starting another cycle: return the evidence that did and did not change between the two packets, plus the released boundary, and leave the `ESCALATE` to `qa`, which owns the boundary. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Never write `_phase-state.md`. No class in the save-ownership policy declares that path, so it is not an orchestrator-owned file either — phase state is published only through `save_run.py checkpoint`, which keeps revision lineage and the audit trail coherent.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed operating sequence and decision rules.
- `references/read-only-boundary.md` for the run-id convention per mode, the allow globs, what the boundary does and does not stop, and the recovery path for a record left unreleased.
- `references/examples.md` for concrete request patterns and response shapes.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/read-only-boundary.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
