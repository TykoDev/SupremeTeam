---
name: setup-deploy
description: >-
  Defines durable deployment settings and the rollback plan that goes with them,
  so later rollouts reuse proven configuration and can be undone. Use for "set
  up deployment config", "configure the deploy flow", "prepare the release
  settings", or "persist the deployment details" — even when the request is only
  "get deploys set up". Owns `deploy-config` and `rollback-plan`; defers running
  a rollout to `land-and-deploy` and orchestration to
  `ship`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---


# Setup Deploy

## Purpose

Deployment settings that live in one engineer's terminal history are not settings; they are a person. This skill turns the deploy path into two artifacts that outlive the run that created them: the configuration a later release reuses, and the rollback plan saying when to undo that release and what undoing cannot reach. Both are written only against a diff a named owner approved, because deployment configuration is production state and changing it is a production change made ahead of time.

## Use This Skill When

Use this skill to **establish durable deploy configuration** that later rollouts reuse — setup, not execution:

- "set up deployment config" / "configure the deploy flow" — define environments and conventions once
- "prepare the release settings" — capture the settings a rollout will depend on
- "persist the deployment details" — store proven configuration for safe reuse

Route elsewhere to run an actual rollout (`land-and-deploy`), orchestrate a full release (`ship`), or write release notes (`document-release`).

## Inputs

- Release targets, deployment environments, build artifact shape, and the current project or pipeline context.
- Existing configuration material such as pipeline vars, environment files, secrets references, DNS or certificate settings, and rollout notes.
- Constraints such as protected environments, secret-handling rules, promotion model, or rollback expectations.

## Outputs

`../ownership.yaml` grants `setup-deploy` two artifacts, `deploy-config` and `rollback-plan`. Both are artifact-backed evidence at the `deploy-readiness` boundary that `ship` submits, so each one leaves this skill as a hashed file, not as a description.

- **`deploy-config`** — the deployment configuration itself: environments and target, artifact flow, variables and secret references, domains and certificates, promotion rules, health probes, ownership, and environment-specific guardrails. Secret values are never inline; only references to a secrets manager.
- **`rollback-plan`** — a separate deliverable, not a line inside the settings bundle, with three required parts: the **rollback trigger** (the observable threshold that starts a rollback, its caller, and its decision deadline), the **rollback procedure** (the ordered steps back to the previous state, each with the check that confirms it), and the **data considerations** (what the rollback cannot undo). `references/rollback-plan.md` carries the required content of each part and the checks that decide whether the artifact satisfies `rollback_plan` at the gate.
- **`deploy_config`** — evidence key at `deploy-readiness`, owner `setup-deploy`. Its content is the deploy-config artifact above: environment settings and target, plus the secrets handling policy (`../ownership.yaml`). Artifact-backed, so its value must name a path present in the gate package's `artifact_hashes` map and a bare claim fails the check. `../gates.yaml` sanctions no fallback value for this key, so no applicability record can waive it; a missing configuration is a blocker that reopens this stage.
- **`rollback_plan`** — evidence key at `deploy-readiness`, owner `setup-deploy`. Its content is the rollback-plan artifact: rollback trigger and procedure, and data considerations. Artifact-backed on the same terms, and with no sanctioned fallback value either.
- Readiness gap list for missing credentials, protected-environment approvals, DNS/cert work, or automation prerequisites.

`../pipelines.yaml` runs the `setup` stage only `when: first deployment`, so both artifacts are built to outlive the run that created them: they are the durable source a later release carries forward and `ship` re-verifies. A re-verification failure returns here rather than being waived at the gate.

The two evidence keys above exist only inside a run. `../routing-doctrine.md` also classes this skill a standalone tool, invokable directly at any time, and standalone there is no package, no `deploy_config` or `rollback_plan` gate key, and no verdict: the same two artifacts are written to the project's own deployment surface under the same filenames, and the result says plainly that nothing judged them. The owner-approved diff is still required — it is a property of writing production configuration, not of being inside a run.

## Workflow

1. Map the deployment path across environments, artifacts, secrets, variables, domains, and promotion boundaries before writing any durable config.
2. Define how deploy settings are stored, injected, versioned, and reused so the release flow does not depend on hidden terminal history or tribal knowledge.
3. **Never persist secret values inline in config files, templates, or any durable artifact** — store only references or pointers to a secrets manager (e.g., `${{ secrets.MY_KEY }}`, ARN, Vault path). If a secret value is encountered during setup, redact it immediately and replace it with the appropriate reference. Storing actual credentials inline creates exfiltration risk and defeats secret rotation.
4. **Preview, diff, and obtain owner approval before writing anything durable**: resolve the canonical destination, read the configuration already at that path, and present the diff — keys added, changed, and removed, with the effective value per environment and every secret shown as its reference rather than its value. A named owner approves that exact diff before the write happens; a widened diff needs a new approval, and an absent owner blocks the write rather than downgrading it to a notification. When nothing exists at the path yet, the diff is the whole proposed file against empty — an empty file and a missing file are the same starting point and neither is an obstacle.
5. **Handle an existing file that cannot be parsed as its own decision**: a truncated file, invalid YAML, unresolved merge-conflict markers, or an unexpected format makes the diff uncomputable, and a diff that cannot be computed cannot be approved. Do not fall back to a partial parse, a line-by-line text diff of a structured file, or a silent overwrite — each of those produces an approval for something other than the real change. Report the parse failure with the resolved path, the parser's error, and the line or offset it failed at, then offer the owner exactly two bounded choices: repair the existing file first and rerun step 4 unchanged, or approve an explicit full replacement, presented as the whole proposed file against the unparseable content quoted verbatim so the owner sees precisely what is being discarded. Preserve the unparseable file beside the new one until the owner confirms the replacement, because it may hold the only record of a setting nobody remembers making.
6. Check the configuration model against rollback needs, environment drift, secret rotation, and manual intervention boundaries, and write the rollback plan as its own artifact to the required shape in `references/rollback-plan.md`.
7. Return a deployment configuration package with persisted settings, environment deltas, the approving owner and approved diff, the resulting file hashes, and the unresolved release blockers that still prevent safe rollout.

## Required Contracts

- **Canonical config path**: "A durable project location" is not a destination, so the path is named and bounded before any write. Inside a run the deploy-config is the release phase artifact `skillset-saves/runs/<run-id>/release/artifacts/deploy-config.yaml`, resolved with `python skills/scripts/output_paths.py --run-id <run-id> --phase release --kind artifacts --name deploy-config.yaml` and referenced from the gate package as `artifacts/deploy-config.yaml`; the rollback plan sits beside it as `rollback-plan.md`. That destination is the `phase-artifacts` path class in `../save-ownership.yaml`, and the resolver is the only sanctioned way to compose it. Outside a run, the durable copy belongs to the project's own deployment surface under the same filenames. Every resolved path must stay inside the workspace root: reject absolute, drive-qualified, and UNC paths, `..` traversal, and links that leave the root, matching the containment rule `../gates.yaml` `evidence_rules.evidence_root` applies to gate evidence. An unresolved destination blocks the write.
- **Owner-approved writes**: Deployment configuration is production state, so a write is never the first action. Present the diff against the existing configuration and obtain a named owner's explicit approval of that diff before persisting, per Workflow step 4. Record the approver, the approved diff, and the resulting file hash with the configuration so a later release can tell an approved setting from an inherited one. When the existing file cannot be parsed, the diff is uncomputable and Workflow step 5 governs instead — an unreadable predecessor never becomes a reason to write without an approved diff.
- **Deploy config persistence**: Persist the verified configuration and rollback plan at the canonical path above so later release flows reuse proven settings instead of terminal history, and so a repeat release has something to carry forward.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../execution-contract.md` defines, so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- None required beyond the active task surface.

## Review Expectations

- Verify each persisted setting maps to a real environment, secret source, artifact, or promotion rule.
- Separate reusable deployment convention from one-off rollout decisions so future releases do not inherit accidental choices.
- Surface credential, DNS, certificate, or protected-environment blockers before `ship` or `land-and-deploy` consumes the config.
- Check the rollback plan against the configuration it depends on: a trigger with no signal behind it, a procedure that restores an artifact the config no longer retains, or an empty data-considerations section each make `rollback_plan` unsatisfied at the gate.

## Skip Rule

Skip only when the requested surface, tool, or environment does not exist and a safe fallback is unavailable.

## Failure Modes

| Scenario | Response |
| --- | --- |
| Deployment settings are scattered across CI variables, local shells, wikis, and manual memory with no durable source of truth | Consolidate the deploy config into one reusable project-level contract before trusting the release path. |
| A secret value would be written inline into a config file or template | Stop immediately; do not write the value. Replace it with a reference to the appropriate secrets manager entry. Surface the gap as a release blocker and do not advance setup until every inline secret is converted to a reference. |
| Promotion assumes one artifact behaves identically in every environment, but environment-specific variables, domains, or secrets are still implicit | Make the environment deltas explicit and block rollout until the config model reflects them honestly. |
| The release path depends on a manual portal edit, ad hoc DNS change, or undocumented certificate step that cannot be replayed | Record the manual dependency and do not describe the deploy setup as reliable until the step is captured or removed. |
| Rollback is claimed, but the configuration surface does not preserve the previous artifact, secret version, or routing state needed to undo the rollout | Reopen the deploy setup boundary and require a real rollback path before downstream release work advances. |
| A durable write is about to happen with no diff shown or no named owner approving it | Hold the write, present the diff against the existing configuration, and wait for the owner's approval of that exact diff; an unreviewed change to deployment settings is a production change made without a decision. |
| The requested destination is vague, outside the workspace, or reached through traversal or a link | Refuse the write and name the canonical path instead; an unbounded config path puts production settings somewhere no later release can find or audit. |
| The rollback plan names a trigger and a command but says nothing about migrations, consumed messages, or third-party side effects | Treat `rollback_plan` as incomplete: the data boundary is the part a responder cannot reconstruct mid-incident, and its absence blocks the gate rather than being noted as a caveat. |
| A file already sits at the canonical path but cannot be parsed — truncated, invalid YAML, merge-conflict markers, or an unexpected format | Stop before the diff. The mandated diff is uncomputable, so no approval is possible and no write happens. Report the path, the parser error, and the failing line, then offer the two bounded choices of Workflow step 5: repair first and rerun the diff, or approve an explicit full replacement shown against the unparseable content quoted verbatim. Preserve the original beside the new file until that replacement is confirmed. |
| Required inputs arrive missing or contradictory — no named environments, an artifact shape that does not match the promotion model, or a secrets model nobody can state | Refuse to persist anything and name each missing or conflicting input. Durable configuration is copied forward by every later release, so a guess made once becomes the convention nobody questions afterwards. |
| The target environment, secrets manager, or deploy platform cannot be reached to verify a setting | Record the setting as unverified with the reason, and keep it out of the persisted configuration as a proven value. An unreachable check is a gap, never a pass, and a configuration presented as verified is the thing a later release will trust without rechecking. |
| The `deploy-readiness` gate returns a `REVISE` packet naming `deploy_config` or `rollback_plan` | Take the owner group for those keys and repair them here; `ship` may not stand in for either, and neither key has a sanctioned fallback. Return the corrected artifact with its new hash so `ship` resubmits once with `--prior`. A second `REVISE` on the same keys reaches `../gates.yaml` `revise_policy` `cycle_cap: 2` and escalates with both packets rather than opening a third cycle. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Never write `_phase-state.md`. No class in the save-ownership policy declares that path, so it is not an orchestrator-owned file either — phase state is published only through `save_run.py checkpoint`, which keeps revision lineage and the audit trail coherent.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed deployment-config setup sequence and decision rules.
- `references/rollback-plan.md` for the required content of the rollback trigger, procedure, and data considerations, and the checks that decide whether the artifact satisfies the gate.
- `references/examples.md` for concrete deploy-configuration outputs, including the file shape of both artifacts.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/rollback-plan.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
