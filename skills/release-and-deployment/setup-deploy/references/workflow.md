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
4. Package the result so later deployment flows can reuse the same proven configuration safely.

## Decision Rules

- Prefer explicit durable config over scattered environment folklore.
- Treat secret and certificate handling as first-class release setup work, not late-stage patch notes.
- Keep promotion and rollback rules tied to the real artifact and environment model.
- Escalate when safe deploy setup requires infrastructure or product decisions outside the current release boundary.

## Acceptance Checklist

- Environment model and deploy path are explicit.
- Variables, secrets, domains, and certificates are captured durably.
- Promotion and rollback rules are documented.
- Manual steps and drift risks are named honestly.
- The setup is reusable by later rollout flows.

## Contract Notes

- Deploy config persistence: Store verified deployment configuration in a durable project location so later release flows can reuse it safely.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.

## Collaboration Notes

- None required beyond the active task surface.
