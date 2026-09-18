---
name: qa
description: >-
  Exercises a running product surface — clicking through it, driving its workflows,
  watching what it actually does — then records hashed evidence, applies scoped atomic
  fixes, and reruns the affected paths until they pass repeatedly. Use for "run QA",
  "test this product thoroughly", "find and fix the issues", or "verify the workflow
  end to end" — even when the request is only "make sure it works". Runs the product
  rather than reading the change: reading code is `review/code-chief`. Report-only
  runs go to `qa-only`, performance measurement to
  `benchmark`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---


# QA

## Purpose

Testing that stops at a list of failures leaves the surface exactly where it was found. This skill closes the loop instead: it exercises a designed matrix, isolates each defect to a minimal reproduction before touching code, fixes one thing at a time, and reruns the affected paths until they pass repeatedly. What it returns is therefore a statement about how the surface behaves now, backed by before-and-after evidence, rather than a snapshot of one bad run.

## Use This Skill When

Use this skill to **test, fix, and re-verify** until the surface stabilizes — the close-the-loop QA mode:

- "run QA" / "test this product thoroughly" — exercise the surface systematically and record evidence
- "find and fix the issues" — apply scoped fixes, then rerun the failing checks
- "verify the workflow end to end" — confirm the full path stabilizes after fixes
- "make sure it works" — the underspecified ask, answered by testing and fixing until it holds

Route elsewhere when fixes must NOT be applied and a defect report is sufficient (`qa-only`), or when the goal is performance measurement (`benchmark`).

## Entry Routing

This skill is reachable two ways, and how it was reached decides which one is running
(`../routing-doctrine.md`). Check before starting, because only one of them closes a gate:

| Signal | Mode | Behavior |
|--------|------|----------|
| A `### Save Context` block, or an active run lock under `skillset-saves/` | **Pipeline** | Run the `qa` pipeline, persist to the run, and assemble the `qa-review` package described under Gate evidence. |
| Neither present | **Standalone** | Run the same workflow directly and return the record inline. Persist nothing and submit no gate. |

Say which mode is active in the first response, so the operator knows whether a gate verdict
is coming.

### Delegation surface

| Stage | Owner | When |
|-------|-------|------|
| `browser-session` | `open-browser` | A browser surface is under test |
| `evidence-capture` | this skill, delegating to `browse` | A browser surface is under test |

Both browser stages are conditional in `../pipelines.yaml` (`when: browser surface under
test`), so a surface with no browser simply skips them. An unavailable browser is the
different case: when the surface does need a browser and `open-browser` cannot supply one,
run the non-browser flows, record each browser-dependent probe as not-run with its reason,
and carry that gap into `residual_risk` — never infer a browser outcome from an API result.
`references/gate-package.md` gives the exact shape of that record.

Browser tooling is engaged inside this pipeline, never as a parallel lifecycle. Every other
stage — scope and matrix, defect record, scoped fixes, rerun until stable — belongs to this
skill. Two of them are conditional in `../pipelines.yaml`, and they are mutually
exclusive: `defect-record` runs `when: report-only run (fixes not authorized)` and
`scoped-fixes` runs `when: fixes authorized`. Which one applies is settled before the
first probe, never after the defects are in hand.

## Execution Contract

Canonical source: `../execution-contract.md`. Stated locally because that file
requires every orchestrator and gatekeeper to carry the clauses verbatim; a paraphrase
is drift, and `skills/validation/test_catalog_contracts.py` compares them exactly.

1. Select the preamble tier before acting: Tier 0 for minor, understood, reversible tasks under the Tier 0 fast path in `skills/routing-doctrine.md`; Tier 1 for bounded read-only work beyond Tier 0; Tier 2 for multi-step edits, delegation, or external coordination beyond Tier 0; Tier 3 for destructive, security-sensitive, production, or irreversible work. Record the tier and rationale in the handoff, or the brief completion note for Tier 0. Tier 0 skips pipeline ceremony and full security audits, but retains focused verification and applicable guardrails; escalate when its eligibility no longer holds.
2. Trigger proactively when the task matches the skill's declared scope, even when the request uses different words; decline adjacent work and route end-to-end or specialist ownership explicitly. Offer a next safe action only after the current step, scope, and approval lineage are resolved; suppress that offer while any is unresolved.
3. Use Critical | Major | Minor | Info for findings. Block on Critical, resolve Major before a gate, record Minor, and preserve Info as context. Use APPROVED | REVISE | ESCALATE for gate verdicts.
4. Validate paths, inputs, revisions, and handoff fields before acting. Keep file operations inside the workspace, use read-only or dry-run probes first, and require explicit owner intent for destructive or externally visible actions.
5. Handle missing or malformed input, conflicting evidence, unsupported hosts or tools, empty results, and unavailable checks explicitly: preserve evidence, do not fabricate, return REVISE or ESCALATE, and state the next safe action.
6. Return Outcome, Evidence, Open risks, Next action, Revision, and Verdict when the skill owns a gate. A concise result without evidence is incomplete.

## Inputs

- Product surface under test, including critical user flows, supported environments, and pass/fail checkpoints.
- Known defects, prior QA findings, and any test-scope limitations such as environment restrictions or data constraints.
- Acceptance criteria defining when the surface is considered stable enough to stop testing.

## Outputs

- QA execution record with findings, applied fixes, rerun results, and residual risks.
- Before/after evidence for each fix so improvements are verifiable, not just asserted.
- Stabilization summary stating whether the surface passed, what remains blocked, and what follow-up is needed.

### Gate evidence

In pipeline mode this skill submits the `qa-review` boundary and owns every one of its
required evidence keys, so each one is produced here or the gate cannot close
(`../gates.yaml`):

`references/gate-package.md` § Evidence keys is authoritative for what each key
must contain. Three shapes cause almost every mechanical failure:

- `test_matrix` and `executed_probes` are typed `probe` records naming **hashed files** under the run's `evidence/` destination. A pass rate or a count is a claim about evidence, not evidence.
- `defects` is a typed `findings` record — `{items: [{id, severity, status}]}` — never prose.
- `fixes_applied` on a report-only run carries `report-only run - no fixes applied` as the `reason` of an applicability record, never as a bare string.

`scope` and `residual_risk` are narrative and have no sanctioned fallback.


Self-check before submitting, so the package is judged deterministically rather than by
claim:

```bash
python skills/harness/gatekeeper/check.py --boundary qa-review --package <manifest.json>
```

A bare pass rate is not evidence: `test_matrix` and `executed_probes` must reference hashed
files under the run's `evidence/` destination, resolved with `skills/scripts/output_paths.py`.
`references/gate-package.md` carries the manifest shape, the evidence-path rules, and the
`REVISE` mechanics — one packet, parallel owner groups, one resubmission with `--prior`, and
the `cycle_cap: 2` that turns a second `REVISE` into an escalation.

## Workflow

Steps 1 to 4 are identical in both entry modes; step 5 is where the two diverge, because only
one of them closes a gate.

1. Resolve the entry mode from the Entry Routing table and state it in the first response, so the operator knows from the start whether a gate verdict is coming. In pipeline mode, resolve the run id and its `qa/` phase destinations with `python skills/scripts/output_paths.py --run-id <run> --phase qa --kind evidence --name <file>` before the first probe, so evidence lands where the gate can resolve it. In standalone mode, persist nothing.
2. Map the critical user flows, supported environments, and pass or fail checkpoints for the requested surface before testing starts. Design test cases explicitly: each case must cover a happy path, at least one boundary condition, and at least one negative/error scenario.
3. Execute the test sweep. For each defect, capture: reproduction steps, expected vs. actual behavior, environment details, and relevant logs. Isolate the defect to a minimal reproduction before applying a fix — bisect or narrow the trigger condition so the fix is targeted, not speculative.
4. Apply one atomic fix at a time. Re-test the affected path plus its closest risk neighbors. The surface is considered stabilized when all targeted defects no longer reproduce across at least 3 consecutive runs and no new regressions have been introduced. Document the before/after evidence for each fix.
5. Close according to the mode:
   - **Pipeline** — write the executed matrix and the probe log to the run's `evidence/` destination, assemble `manifest.json` (`schema_version: 2`, `boundary: qa-review`, `owner: qa`, the run id, the single revision, and an `artifact_hashes` entry per evidence file), self-check it with `check.py` as shown under Gate evidence, fix every mechanical failure before submitting, and submit at the `qa-review` boundary. Return Outcome, Evidence, Open risks, Next action, Revision, and Verdict. `references/gate-package.md` carries the manifest shape and the `REVISE` handling.
   - **Standalone** — return the QA execution record inline with findings, fixes applied, rerun results, and residual risks, and state plainly that no package was assembled and no `qa-review` verdict was sought.

   See `references/workflow.md` for full decision rules and `references/examples.md` for a sample execution record in each mode.

## Required Contracts

- **Before/After Evidence**: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- **Atomic commit per fix**: Keep each fix isolated, explain what changed, and preserve easy rollback boundaries even when several issues are found.
- **Safe defaults and scope limits**: Fixes must be atomic and reversible. Never perform destructive operations (dropping tables, deleting data, mutating production data) or touch production environments without explicit owner approval. If a proposed fix would exceed QA scope — e.g., schema migrations, infrastructure changes, or irreversible deletions — stop, report the finding, and hand it to the appropriate owner instead of proceeding.
- **Input validation**: Validate that the product surface, acceptance criteria, and environment specification are present and coherent before starting the test sweep. Refuse to proceed if scope is ambiguous.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../execution-contract.md` defines, so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

- **Product-data side effects are recorded, not avoided**: Exercising a real workflow creates real data — an account, an invite, an order, a webhook delivery. That is expected and is not a violation of anything; what is required is that each one is recorded in the sweep with what it created and where, so a later reader can tell a test artifact from a user's. Two limits bound it: a flow whose side effects are **not acceptable to the owner** — a live payment, an email to a real address, a write to shared production state — is stopped and reported rather than walked, and nothing created by the sweep is cleaned up by guessing. Where teardown is needed, name what was created and hand the teardown to the surface's owner. This is the same contract `qa-only` states, and it holds identically here: applying fixes changes what this skill may write to the *code*, never what it may do to *product data*.

## Collaboration Surface

- None required beyond the active task surface.

## Review Expectations

- Back every fix with before/after evidence so the improvement is verifiable by any downstream consumer.
- Distinguish stabilized flows from residual defects so the caller knows exactly what passed and what remains at risk.
- Shape the QA record so downstream pipelines can consume it without re-running the test sweep.

## Skip Rule

Skip only when the requested surface, tool, or environment does not exist and a safe fallback is unavailable.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The product surface, acceptance criteria, or environment specification is missing, empty, or self-contradictory | Refuse to start the sweep and name the missing or conflicting input with the smallest clarification that unblocks it. A matrix designed against a guessed scope produces evidence for a surface nobody asked about, and the gate cannot tell the difference. |
| The environment, test data, or account setup is incomplete for a critical workflow | Stop the affected test path, record the missing prerequisite, and continue only with the flows that can still be tested honestly. |
| The browser surface is under test but `open-browser` cannot supply one, or another required tool or environment is unavailable | Run the flows that do not need it, record every dependent probe as not-run with its reason rather than inferring an outcome, and carry the untested surface into `residual_risk`. An unavailable check is a data gap, never a pass. |
| `check.py` returns `REVISE` twice on the same package | Stop resubmitting. `../gates.yaml` `revise_policy` sets `cycle_cap: 2`, so the second `REVISE` escalates: return `ESCALATE` carrying both packets, the `changed_evidence` and `unchanged_evidence` from the `--prior` comparison, and the specific keys that did not converge, and hand the decision to the delegating owner rather than opening a third cycle. |
| A defect reproduces intermittently and cannot yet be tied to one trigger | Record the unstable reproduction boundary, preserve the evidence gathered so far, and avoid claiming the fix is verified. |
| Several failing tests appear to share one root cause | Collapse them into one blocker and rerun the dependent paths after the first credible fix instead of applying scattered changes. |
| A scoped fix lands on a path an active `freeze` or `blocked_globs` record covers, and the hook denies the write | Do not work around it, and do not hand-edit the guard record — the hook denies that too. The defect stays recorded with its reproduction and its fix direction; only the *landing* is blocked. Two routes are open, and the boundary's owner chooses: have them lift the boundary with `unfreeze` and re-run the fix inside the reopened area, or hand the fix direction to the owner of the frozen surface and record the defect as `open` with the blocking boundary named. Either way `fixes_applied` reports what was actually applied, never what would have been; a defect whose fix the guard refused is not a fixed defect. |
| A scoped fix destabilizes a neighboring path during retest | Keep the atomic fix boundary explicit, record the regression, and decide whether to continue or escalate before more changes stack up. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Never write `_phase-state.md`. No class in the save-ownership policy declares that path, so it is not an orchestrator-owned file either — phase state is published only through `save_run.py checkpoint`, which keeps revision lineage and the audit trail coherent.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed operating sequence and decision rules.
- `references/gate-package.md` for the pipeline-mode manifest shape, evidence-path rules, `REVISE` packet handling, and the not-run record for an unavailable probe.
- `references/examples.md` for concrete request patterns and response shapes in both entry modes.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/gate-package.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
