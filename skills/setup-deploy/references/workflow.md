# Workflow Reference

## Contents

1. Deployment-config setup sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Deployment-Config Setup Sequence

1. Confirm the environments, deploy mechanism, artifact boundaries, and secrets model the release path depends on.
2. Define one durable configuration surface for variables, secrets references, domains, certificates, and promotion rules.
3. Check that the setup survives environment drift, rollback, and operator handoff without hidden manual steps.
4. Resolve the canonical path, show the diff against the configuration already there, and obtain a named owner's approval of that diff before writing.
5. When the file already at that path cannot be parsed, stop rather than approximate: the diff is uncomputable, so report the path, the parser error, and the failing line, and offer the owner a repair-then-rediff or an explicit full replacement shown against the unparseable content quoted verbatim. Preserve the original until the replacement is confirmed.
6. Write the rollback plan as its own artifact: trigger, procedure, and data considerations, to the shape in `rollback-plan.md`. It is written *after* the approval, not before — it is a durable artifact like the config, so approval-before-any-durable-write covers it too, and the order here matches `../SKILL.md` Workflow steps 4-6.
7. Package the result so later deployment flows can reuse the same proven configuration safely, recording the approver, the approved diff, and each file hash.

## Decision Rules

- Prefer explicit durable config over scattered environment folklore.
- Treat secret and certificate handling as first-class release setup work, not late-stage patch notes.
- Keep promotion and rollback rules tied to the real artifact and environment model.
- Escalate when safe deploy setup requires infrastructure or product decisions outside the current release boundary.
- A write to durable deployment settings waits for an approved diff; nothing about setup is urgent enough to skip that.
- `deploy_config` and `rollback_plan` are artifact-backed at `deploy-readiness` with no sanctioned fallback, so neither can be asserted in prose at the gate.
- An unparseable existing file is a stop, not a reason to overwrite: an approval given on a diff that could not be computed approves nothing.
- A setting that could not be verified against its environment is recorded as unverified, never persisted as proven; a later release reuses it without rechecking.
- A `REVISE` naming `deploy_config` or `rollback_plan` is repaired here and returned to `ship` with a new hash; `ship` may not stand in for either key.

## Acceptance Checklist

- Environment model and deploy path are explicit.
- Variables, secrets, domains, and certificates are captured durably.
- Promotion rules are documented, and the rollback plan states its trigger, its procedure, and its data considerations.
- The canonical path resolves inside the workspace, and a named owner approved the diff that was written; where the existing file was unparseable, the owner approved an explicit full replacement instead.
- Manual steps and drift risks are named honestly.
- The setup is reusable by later rollout flows.

## Contract Notes

The contracts this workflow runs under are stated in `../SKILL.md` § Required Contracts.

## Collaboration Notes

This skill's collaboration surface is stated in `../SKILL.md` § Collaboration Surface.
