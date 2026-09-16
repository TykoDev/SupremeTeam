---
name: ship
description: >-
  Orchestrates a controlled release: readiness, launch sequencing, a named
  owner's go decision, verification, and follow-up. Use for "ship this release",
  "prepare the launch", "run the release flow", or "coordinate the rollout" —
  even when the request is only "let's launch". Owns the `deploy-readiness`
  gate; defers the merge-and-rollout to
  `land-and-deploy`, deploy config to
  `setup-deploy`, and notes to
  `document-release`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---


# Ship

## Purpose

A release is the one step in the lifecycle that cannot be undone by rerunning it, so its safety comes from the order things happen in rather than from any single check. This skill holds that order: verification criteria fixed before the rollout instead of chosen after it looks healthy, a named owner's go decision separate from every automated signal, and durable configuration re-verified against this release rather than inherited from the last one. It coordinates the specialists that merge, configure, and document; it performs none of those itself.

## Entry Routing

`ship` is directly invokable **and** owns a gated pipeline, so the entry path decides which of the two is running (`../routing-doctrine.md`). Resolve it before any release work starts: a handoff is present when the prompt carries a `### Save Context` block, or an active run lock with `session_pin: true` exists under `skillset-saves/`.

- **Handoff present** → run the gated `release` pipeline defined in `../pipelines.yaml`: `readiness` under `ship`, `setup` under `setup-deploy` on a first deployment, `land-and-deploy` under `land-and-deploy` once the human go decision is recorded, and `document` under `document-release`. Persist to the run's `release/` phase directory and close at the `deploy-readiness` boundary with the submission described below.
- **Handoff absent** → run the standalone orchestration, and say so in the opening line of the result. The readiness, sequencing, verification, and follow-up work is the same, but there is no saved run, no gate package, and no gate verdict, so the result reports no `deploy-readiness` verdict, because no package was submitted for one. A cold lifecycle release request that needs intake, persistence, and the gate belongs to `admiral` first; standalone mode covers an explicit, bounded request to drive a release directly.

## Execution Contract

Canonical source: `../execution-contract.md`. Stated locally because that file requires every orchestrator and gatekeeper to carry the clauses verbatim; a paraphrase is drift.

1. Select the preamble tier before acting: Tier 0 for minor, understood, reversible tasks under the Tier 0 fast path in routing-doctrine.md; Tier 1 for bounded read-only work beyond Tier 0; Tier 2 for multi-step edits, delegation, or external coordination beyond Tier 0; Tier 3 for destructive, security-sensitive, production, or irreversible work. Record the tier and rationale in the handoff, or the brief completion note for Tier 0. Tier 0 skips pipeline ceremony and full security audits, but retains focused verification and applicable guardrails; escalate when its eligibility no longer holds.
2. Trigger proactively when the task matches the skill's declared scope, even when the request uses different words; decline adjacent work and route end-to-end or specialist ownership explicitly. Offer a next safe action only after the current step, scope, and approval lineage are resolved; suppress that offer while any is unresolved.
3. Use Critical | Major | Minor | Info for findings. Block on Critical, resolve Major before a gate, record Minor, and preserve Info as context. Use APPROVED | REVISE | ESCALATE for gate verdicts.
4. Validate paths, inputs, revisions, and handoff fields before acting. Keep file operations inside the workspace, use read-only or dry-run probes first, and require explicit owner intent for destructive or externally visible actions.
5. Handle missing or malformed input, conflicting evidence, unsupported hosts or tools, empty results, and unavailable checks explicitly: preserve evidence, do not fabricate, return REVISE or ESCALATE, and state the next safe action.
6. Return Outcome, Evidence, Open risks, Next action, Revision, and Verdict when the skill owns a gate. A concise result without evidence is incomplete.

A production release is externally visible, changes live state, and cannot be undone by rerunning it, so clause 1 places it at Tier 3: the full pipeline route with a saved run and a gate package, plus explicit owner intent and a fresh human go decision for this release at this time. `ship` states that tier and its rationale in the handoff. A lower tier covers only release work that touches no production state, such as a rehearsal against a disposable environment, and such a run is labelled a rehearsal rather than a ship.

## Use This Skill When

Use this skill to **orchestrate a full, multi-step release** — readiness, sequencing, verification, and follow-up:

- "ship this release" / "run the release flow" — drive the release from readiness to follow-up
- "prepare the launch" — confirm readiness and sequence the launch steps
- "coordinate the rollout" — manage verification and post-launch actions across the release
- "let's launch" — the bare go-ahead, with the release flow still to be assembled

Route elsewhere for a single merge-and-deploy of one change (`land-and-deploy`), first-time deploy configuration (`setup-deploy`), or release documentation (`document-release`).

## Inputs

- Release candidate package with the approved delivery revision and its review evidence.
- The `deploy-config` artifact from `setup-deploy` — the one input `../ownership.yaml` declares under `ship.consumes`, taken as it stands and re-verified against the current release rather than rebuilt here.
- Three further documents this skill reads with no ownership relation to them, because `../ownership.yaml` declares no `consumes` edge for any of them and none belongs to `ship`: the `rollback-plan` artifact from `setup-deploy`, the release record from `land-and-deploy`, and the release notes drafted by `document-release`. Each is read exactly as its owner published it, and a disagreement returns to that owner as a finding rather than being reconciled here. Reading them is what makes the readiness check and the post-ship reconciliation possible; it grants no authorship, and the boundary table below stays the authority on which keys `ship` actually owes.
- Launch window, rollout sequence, and verification checkpoints from the release plan.
- Known constraints such as partial-rollout requirements, feature-flag dependencies, and communication obligations.

## Outputs

`../ownership.yaml` grants `ship` exactly two artifacts and lists `deploy-config` and `release-record` under `does_not_write`; the release record belongs to `land-and-deploy` and is consumed here, never authored here.

The first five entries below are the gate submission and its evidence keys, so they exist in pipeline mode only. Standalone mode does the same readiness, sequencing, and verification thinking and returns the last two entries plus the verification plan as an ordinary deliverable rather than as hashed gate evidence — Gate Submission states exactly what stands in for the package there.

- **`deploy-readiness-package`** — the gate submission itself (`release/manifest.json`, schema 2, `boundary: deploy-readiness`, `owner: ship`), carrying the approved delivery revision, the human go decision requirement, and the hashed artifact set behind every evidence key in the boundary table below.
- **`verification-plan`** — the post-release checks and their pass conditions as a hashed artifact, fixed before the gate so the checks are agreed in advance instead of chosen after the rollout already looks healthy.
- **`approved_delivery`** — evidence key at `deploy-readiness`, owner `ship`: the approved upstream delivery revision identifier.
- **`verification_plan`** — evidence key at `deploy-readiness`, owner `ship`: the verification-plan artifact above, named by its hashed path.
- **`human_go_required`** — evidence key at `deploy-readiness`, owner `ship`: the go decision for this specific release at this specific time — named approver identity, approval reference, the exact revision approved, and the decision timestamp. Prerequisite checks, artifact validation, and CI status are readiness signals, not this decision, and `../gates.yaml` sanctions no fallback value for any of the three keys, so none can be waived by an applicability record. `references/gate-submission.md` carries each key's type, its artifact-backing rule, and the value shape the checker accepts.
- Post-ship checklist identifying remaining verification steps, rollback triggers, and follow-up actions.
- Escalation notes when a rollout gate fails and the release must be paused or rolled back.

## Workflow

1. Confirm the release candidate and launch window, then re-verify the persisted deployment settings and rollback path from `setup-deploy` against this release instead of assuming the first deployment's assumptions still hold.
2. Draft the verification plan before the rollout: each post-release check, the signal it reads, and the condition that counts as a pass. Sequence the launch around those checks with explicit go or no-go points so packaging, deployment, communication, and verification happen in the right order.
3. **Require an explicit owner go-decision before committing the production ship**: a named owner or approver must issue a clear "go" for this specific release at this specific time. Prerequisite checks, artifact validation, and CI status satisfy readiness but do not substitute for an explicit human go-decision. Capture the approver identity, the approval reference, the exact revision approved, and the decision timestamp as the `human_go_required` evidence inside the deploy-readiness package.
4. Close the readiness boundary according to the entry mode resolved above:
   - **Pipeline** — assemble the deploy-readiness package, self-check it against the boundary, and submit it. Delegate the rollout to `land-and-deploy` only once the gate approves and the go decision is on file.
   - **Standalone** — no package is assembled and no verdict is sought, so nothing mechanical stands between the plan and the rollout; the go decision from step 3 carries the release alone. State the readiness explicitly instead: the re-verified configuration and rollback path with the revision each was verified at, the verification plan and its pass conditions, the approved delivery revision, and the recorded go decision. Say in the result that no `deploy-readiness` verdict exists and that the rollout proceeds on the go decision alone. Hand that statement and the decision to `land-and-deploy`, and route the release through `admiral` for the gated path instead whenever it needs the gate's assurance rather than an owner's word.
5. Read the release record `land-and-deploy` returns, reconcile it against the verification plan, and return the post-ship checklist with next launch actions, rollback triggers, and the checks still outstanding. Rollout evidence that contradicts the plan becomes a finding routed to its owner, not a quiet edit of the returned evidence.

## Required Contracts

- **Single-writer boundary**: `../ownership.yaml` grants `ship` the `deploy-readiness-package` and `verification-plan` artifacts and lists `deploy-config` and `release-record` under `does_not_write`. Both of those belong to other owners — the persisted configuration to `setup-deploy`, the release record to `land-and-deploy` — so a disagreement with either returns a REVISE to its owner rather than an edit made here.
- **Before/After Evidence**: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../execution-contract.md` defines, so upstream and downstream packages interpret risk consistently.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Gate Submission

The `release` pipeline closes at the `deploy-readiness` boundary in `../gates.yaml`, which guards `GATE -> RELEASE`. `ship` is the submitter, so it assembles the package and owns the mechanical result, but it owns only three of the five keys; the remaining two are produced by `setup-deploy` and consumed here.

| Evidence key | Owning skill | Artifact-backed | Sanctioned fallback |
| --- | --- | --- | --- |
| `approved_delivery` | `ship` | no — typed `revision_ref` | none |
| `deploy_config` | `setup-deploy` | yes | none |
| `verification_plan` | `ship` | yes | none |
| `rollback_plan` | `setup-deploy` | yes | none |
| `human_go_required` | `ship` | no | none |

Self-check before submitting:

```bash
python skills/harness/gatekeeper/check.py --boundary deploy-readiness --package <manifest.json>
```

Run it without `--verdict-out` and fix every mechanical failure first; a package that fails the machine is never submitted (`../gates.yaml` `revise_policy.self_check`). `references/gate-submission.md` carries the manifest shape, the `REVISE` packet routing across two owners, the `cycle_cap: 2` escalation, and the repeat-release rule that keeps `deploy_config` and `rollback_plan` satisfiable when the `setup` stage does not run.

### Standalone mode: no package, no verdict

In standalone mode the boundary is not submitted, so the five keys above are not assembled, hashed, or judged. What replaces them is stated rather than implied: the approved delivery revision, the re-verified `deploy-config` and rollback path with the revision each was verified at, the verification plan with its pass conditions, and the named owner's recorded go decision for this revision at this time. The go decision is the one element that does not weaken outside the pipeline — it is an owner's judgment, not a mechanical check, so it is required identically in both modes. Everything else is a readiness statement carrying no gate assurance, and the result says so, so no downstream reader mistakes an unsubmitted release for an approved one.

## Collaboration Surface

- None required beyond the active task surface.

## Review Expectations

- Base every launch decision on live verification evidence — health checks, smoke tests, rollout metrics — not on build-phase assertions.
- Surface rollback triggers and partial-rollout risks before the release advances past each gate.
- Shape the deploy-readiness package and the verification plan so `land-and-deploy` can execute the rollout and `document-release` can draft the notes from them without reinterpreting the release intent.
- Keep the boundary honest in both directions: an evidence key owned by `setup-deploy` is requested from `setup-deploy`, and a rollout fact owned by `land-and-deploy` is quoted from its record rather than restated as a finding of ship's own.

## Skip Rule

Skip only when the requested surface, tool, or environment does not exist and a safe fallback is unavailable.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The release candidate, launch window, or rollback plan is missing | Block the rollout and name the missing launch prerequisite explicitly. |
| No owner go-decision is present — prerequisites pass but no named approver has issued an explicit go | Hold the release; do not ship. Record the missing go-decision as a blocker and wait for a named owner to provide an explicit approval for this specific release. |
| Verification signals are incomplete or contradictory during rollout | Freeze the next launch step, preserve the current state, and decide whether to retry, pause, or roll back. |
| A required approval or external coordination step has not happened yet | Keep the deploy-readiness package in no-go state until the dependency is resolved instead of launching optimistically. |
| A repeat release finds the carried-forward deployment settings or rollback procedure no longer matching the target environment | Treat the mismatch as drift on a `setup-deploy`-owned key, reopen the `setup` stage for this release, and hold the gate; `deploy_config` and `rollback_plan` have no sanctioned fallback, so neither can be asserted from here. |
| The returned rollout evidence contradicts the verification plan submitted at the gate | Preserve both, grade the contradiction as a finding against its owner, and decide rollback or controlled hold before any follow-up describes the release as complete. |
| The rollout partially succeeds but leaves uncertainty about user impact | Record the partial state, define the rollback trigger, and keep follow-up actions explicit rather than implying a full ship. |
| The deploy-readiness package comes back `REVISE` a second time, or the gate returns `ESCALATE` | Stop resubmitting and hold the release. `../gates.yaml` `revise_policy` sets `cycle_cap: 2`, so a second `REVISE` ends the cycle rather than starting a third: return `ESCALATE` with both packets, the `changed_evidence` and `unchanged_evidence` from the `--prior` comparison, and the owner of each key that did not converge — the configuration and rollback keys belong to `setup-deploy`, the rest to `ship`. An `ESCALATE` from the gate is handled the same way. Neither verdict is a slow approval, so no rollout is delegated while one stands. |
| The release candidate, configuration, or verification expectations arrive missing, empty, or contradicting each other | Refuse to sequence the launch and name the specific conflict. A launch order built on an ambiguous candidate sequences the wrong revision, and every later check then verifies the wrong thing convincingly. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Never write `_phase-state.md`. No class in the save-ownership policy declares that path, so it is not an orchestrator-owned file either — phase state is published only through `save_run.py checkpoint`, which keeps revision lineage and the audit trail coherent.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed operating sequence and decision rules.
- `references/gate-submission.md` for the manifest shape, the two-owner `REVISE` packet, the escalation cap, and the repeat-release rule.
- `references/examples.md` for concrete request patterns and response shapes in both entry modes.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/gate-submission.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
