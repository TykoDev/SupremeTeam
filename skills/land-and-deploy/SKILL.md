---
name: land-and-deploy
description: >-
  Takes one approved revision from merge into a live environment in a single
  controlled flow, with a recorded go decision, post-release verification, and
  rollback awareness. Use for "land and deploy this", "merge and release it",
  "ship the branch", or "merge then verify the rollout" — even when the request
  is only "get this live". Executes the merge-to-environment step; defers
  orchestration to `ship` and deploy config to
  `setup-deploy`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

# Land And Deploy

## Purpose

Merging, deploying, and verifying are usually three flows with three places to lose the thread — a branch that drifted after approval, a rollout against configuration nobody re-read, a health probe green while the user-visible path is broken. Holding all three in one flow keeps the shipped revision, the configuration it ran against, and the evidence that it worked tied to each other, and keeps the rollback path live the whole way through. Two preconditions gate the merge, and neither is mechanical: a named owner's recorded decision to go, and a current review approval of that exact revision.

## Use This Skill When

Use this skill to **take one approved change from merge into a live environment** in a single controlled flow:

- "land and deploy this" / "merge and release it" — merge, roll out, then verify
- "ship the branch" / "merge then verify the rollout" — run the rollout with post-release checks
- "take an approved change all the way into a live environment" — keep rollback awareness throughout
- "get this live" — one approved change, out to the environment now, with no release flow to assemble

Route elsewhere for multi-step release orchestration and sequencing (`ship`), first-time deploy configuration (`setup-deploy`), or release documentation (`document-release`).

## Entry Routing

`../routing-doctrine.md` classes this skill as directly invokable, and `../pipelines.yaml` also runs it as the `land-and-deploy` stage of the `release` pipeline `when: human go decision recorded`. The two entry paths differ in where the go decision lives, never in whether one is required:

| Signal | Mode | Where the go decision comes from |
|--------|------|----------------------------------|
| A `### Save Context` block, or an active run lock under `skillset-saves/` | **Pipeline** | The `human_go_required` evidence inside `ship`'s approved deploy-readiness package (`../gates.yaml`, boundary `deploy-readiness`) |
| Neither present — a direct "ship the branch" or "get this live" | **Standalone** | A named owner's go decision recorded for the exact revision before the merge, carrying the same four fields the package key carries: approver identity, approval reference, exact revision, and decision timestamp |

Say which mode is active before anything is landed. The standalone decision is recorded the same way and checked against the same revision; what it lacks is the gate's assurance that the configuration, rollback path, and verification plan were judged mechanically first, and the result says so rather than implying a package existed. `references/preconditions.md` gives the shape of each precondition in each mode, and what a decision that names a different revision means.

## Inputs

- Merge target, deployable revision, release environment, and current repository/pipeline state.
- In pipeline mode, `ship`'s approved `deploy-readiness-package`, which carries the `human_go_required` evidence this flow depends on and names the `deploy-config` and `rollback-plan` revisions the rollout must use.
- In standalone mode, the named owner's recorded go decision for the exact revision, plus the persisted `deploy-config` and rollback path read directly from `setup-deploy`, since no package names the revisions for this flow.
- Deployment target, branch or release identifier, and verification expectations.
- Known constraints, such as protected environments, release windows, or rollback requirements.

## Outputs

`../ownership.yaml` grants `land-and-deploy` one artifact, `release-record`, and lists `deploy-config` under `does_not_write`: the configuration is consumed from `setup-deploy` as it stands, never amended here.

- **`release-record`** — the land-and-deploy execution record. `../ownership.yaml` requires two kinds of evidence in it, so both are present or the record is incomplete: **the release result with its timestamps** — merge command and result, deployment id, target environment, and the start, finish, and rollback-checkpoint times of the rollout window, each timestamped so the release can be placed against an incident later — and **post-release verification evidence**: the health probes, smoke paths, and user-visible checks actually executed after the rollout, with their observed values against their pass conditions, not a summary that they passed. The consumed `deploy-config` revision and both precondition references travel with it.
- Rollout evidence bundle with build output, deployment logs, health checks, smoke tests, and post-deploy observations.
- Go/no-go follow-up list for failed checks, rollback triggers, partial rollout holds, or documentation handoff.

## Workflow

1. Verify the merge target, deployment target, and rollout window, then load the persisted deployment settings and rollback path and confirm the live environment still matches them before landing anything. Which revisions those are depends on the entry mode:
   - **Pipeline** — the deploy-readiness package names the `deploy-config` and `rollback-plan` revisions this rollout must use. Load those exact revisions rather than whatever the deployment surface currently holds; a newer configuration that the gate never judged is drift, not an upgrade.
   - **Standalone** — no package names them, so read the persisted configuration and rollback plan directly from `setup-deploy` at the durable location it wrote them to. Name the revision actually loaded in the release record, so the release is still tied to a specific configuration with no gate standing behind it.
2. **Require the recorded human go decision before anything is landed** — named approver, approval reference, the exact revision approved, and the decision timestamp, decided for this release at this time. Where that record lives depends on the entry mode:
   - **Pipeline** — it is the `human_go_required` evidence inside `ship`'s approved deploy-readiness package (`../gates.yaml`, boundary `deploy-readiness`). `../pipelines.yaml` starts this stage only `when: human go decision recorded`, so an absent decision is not a caution to note; it means the stage has not started.
   - **Standalone** — no package exists, so the decision itself is the precondition and it is obtained and recorded before the merge, with the same four fields. Quote them back to the owner against the exact revision to be merged and proceed only on an explicit go; silence, a prior release's approval, and a general "yes, ship it" that names no revision are all absent decisions. Record the decision **in the release record itself**, as the same four fields the pipeline's `human_go_required` key carries — `approver`, `reference`, `revision`, `decided_at` — so a standalone release and a gated one are read the same way afterwards. There is no package to hold it and no gate to check it, which makes the release record the only durable place it exists; a decision recorded anywhere else (a chat message, a commit trailer, a ticket comment) is not part of the artifact this skill returns and cannot be audited with it. State in the result that it stood alone with no gate behind it.
3. **Check the code-review approval separately and additionally**: confirm a named reviewer approved the exact revision being merged and that the approval is still current for it, with its reference (review link, sign-off record, or equivalent). Review approval and the go decision answer different questions — whether the change is sound, and whether the owner wants it live now — so neither substitutes for the other, and CI/CD artifact checks satisfy neither. Do not merge or deploy until both are present.
4. Land the approved change set in a reversible way, capture before and after state, and keep the release narrative tied to the exact shipped revision. **Where the rollback plan states a rollout shape, follow it.** Where it does not, the minimum is one of: the change **gated behind a flag** that is off at merge and turned on as a separate, observable step; or a **canary** — a bounded slice of traffic or instances first, held long enough for the plan's verification signals to register before the rest follows. Either way there is a point after the merge where the change is live, observed, and not yet everywhere. A merge that goes straight to full traffic is reversible only by a second deploy, which is not a rollback but a fix-forward with a nicer name. When neither is achievable — an all-or-nothing migration, a platform that cannot split traffic — that is not a reason to proceed quietly: name the constraint, record the release as irreversible past the merge, and get the owner's explicit go against *that* fact before landing.
5. Execute the rollout and post-deploy verification against live health signals, smoke paths, logs, and user-visible checks before declaring success.
6. Return a deployment record with merge outcome, environment evidence, rollback status, the go-decision and review references it relied on, and any follow-up tasks that still need owner attention.

## Required Contracts

- **Deploy config consumption**: `../ownership.yaml` gives `deploy-config` to `setup-deploy` and lists it under `does_not_write` for this skill, so the rollout reads the persisted configuration and never creates, widens, or amends it. Name the exact deploy-config revision the rollout used; when the live environment differs from it, stop and report the drift as a release blocker for `setup-deploy` to resolve rather than reconciling it from inside the rollout.
- **Recorded go decision**: The rollout proceeds on a recorded decision carrying approver identity, approval reference, exact revision, and decision timestamp — the `human_go_required` evidence in `ship`'s approved deploy-readiness package in pipeline mode, or a named owner's decision recorded before the merge in standalone mode (Entry Routing). A current code-review approval is a separate additional check in both. Every reference travels into the release record so the release can be audited back to the people who approved it.
- **Before/After Evidence**: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../execution-contract.md` defines, so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- None required beyond the active task surface.

## Review Expectations

- Tie every merge and deployment step to the requested revision and target environment before declaring the release landed.
- Record live verification evidence and rollback readiness at each gate, not only command success.
- Distinguish failed deployment, failed verification, and blocked environment access so the next action is unambiguous.
- Treat a missing go decision and a missing review approval as different blockers with different owners, because they are resolved by different people.

## Skip Rule

Skip only when the requested surface, tool, or environment does not exist and a safe fallback is unavailable.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The reviewed revision is approved, but the release branch has drifted since that approval | Stop before merge, name the drift boundary, and require a fresh review or a narrowed release target. |
| The deploy-readiness package carries no recorded `human_go_required` evidence, or it names a different revision or an earlier release | Stop immediately; the stage has not started. Return the missing go decision to `ship` as the blocker and wait for a named owner to decide on this revision at this time. |
| No deploy-readiness package exists at all — a direct "ship the branch" with no run, no handoff, and nothing from `ship` | This is standalone mode, not a defect, and it is not a reason to proceed without a decision either. Say that no package exists and no gate verdict stands behind this release, then obtain and record a named owner's go decision for the exact revision before the merge, quoting the four fields back for confirmation. If the release needs the gate's assurance over the configuration, rollback path, and verification plan, stop and route it through `ship` under `admiral` instead of substituting a decision for a package. |
| A go decision is on file but no named reviewer approved the exact revision being merged, or that approval is stale | Stop before merge and require a current review approval; the two checks are independent, so one satisfied check never covers the other, and artifact or CI checks cover neither. |
| The rollout depends on configuration that is not persisted with the project or environment | Capture the gap as a release blocker for `setup-deploy` and do not trust one-off terminal history as deploy evidence; this flow consumes deploy-config and never supplies it. |
| The live environment settings differ from the persisted deploy-config the package names | Stop before the rollout, report the drift as a release blocker owned by `setup-deploy`, and do not reconcile it from inside this flow; one writer per configuration is what makes the next rollout reproducible. |
| Health probes are green after deployment, but a critical user flow fails during smoke verification | Treat the release as incomplete, preserve the conflicting evidence, and decide between rollback or controlled hold before declaring success. |
| The rollout succeeds in one environment but fails in the next, leaving version skew across the release path | Return a partial deployment state explicitly and avoid describing the release as fully shipped until the skew is resolved. |
| The rollback plan's decision deadline lapses mid-rollout — the canary window closes, a migration passes the point of reversibility, or a stated "rollback available until" time expires | Stop at the current step and treat the release as **rollback-unavailable** from that moment, saying so before the next step rather than after. This flow owns the rollout window, so it is the only stage positioned to notice the lapse: read the deadline out of the `rollback_plan` the package carries, at the start and at each step boundary, and do not infer from green verification that the option to undo survives — a passing check proves the release works, not that it can be reversed. Record which steps are now irreversible, then obtain a fresh named-owner go for continuing without a rollback path. That is a new decision against materially different terms, not the original go carried forward, and `ship`'s matching row (`../ship/SKILL.md`) grades it the same way. If no owner is reachable, hold the environment at the current step rather than completing the rollout on an expired plan. |
| The rollback itself fails or leaves the environment in an inconsistent state | Do not declare the rollback complete; escalate to the named approver immediately, freeze forward progress, and hold the environment until a human-verified recovery path is confirmed. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Never write `_phase-state.md`. No class in the save-ownership policy declares that path, so it is not an orchestrator-owned file either — phase state is published only through `save_run.py checkpoint`, which keeps revision lineage and the audit trail coherent.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed land-and-deploy sequence and decision rules.
- `references/preconditions.md` for the shape of the go decision and the review approval in each entry mode, and for what a mismatched revision means.
- `references/examples.md` for concrete release and rollout examples in both entry modes.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/preconditions.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
