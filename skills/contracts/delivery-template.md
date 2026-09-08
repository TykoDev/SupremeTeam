# Delivery Template

## Responsibility

Use this template for the final delivery record of one bounded change. It
connects the requested goal to changed artifacts and proof without replacing the
underlying evidence. `admiral` writes it at `RUN_COMPLETE`.

```markdown
# Delivery Report: [change or artifact]

## Run identity

- run_id: [run id]
- submission_id: [submission id]
- revision: [revision]
- parent_revision: [parent revision or none]
- owner: [delivery owner]
- status: [candidate, revised, approved, blocked, or complete]
- preamble_tier: [0, 1, 2, or 3, with the blast-radius rationale]
- evidence_paths: [workspace-relative paths]

## Goal
[The outcome requested and the user or run that requested it.]

## Scope
- Included: [bounded work completed]
- Non-goals: [explicitly excluded work]

## Traceability

| Requirement or decision | Artifact or behavior | Evidence path | Status |
|-------------------------|----------------------|---------------|--------|
| [id and statement] | [what implements it] | [path] | [proven/unproven] |

## Stack lock

| Concern | Locked value | Evidence |
|---------|--------------|----------|
| Runtime and language | [version] | [path or command] |
| Framework and dependencies | [versions] | [manifest or command] |
| Host and deployment target | [target] | [path or decision] |
| Interfaces and data formats | [versions or schemas] | [path] |

Do not introduce a new runtime, framework, dependency, interface, or target
without recording the decision and its owner here. The registry slug and overlay
digest come from [`../tech-stacks/registry.yaml`](../tech-stacks/registry.yaml).

## Changed artifacts

| Path | Change | Owner | Revision | SHA-256 |
|------|--------|-------|----------|---------|
| [workspace-relative path] | [added, changed, or removed] | [owner] | [n] | [digest] |

## Tests and proof

| Check | Command or method | Result | Evidence |
|-------|-------------------|--------|----------|
| [test or validation] | `[command]` | [pass, fail, or unavailable] | [path or output] |

## Claims, gaps, and proof

Use the canonical [Evidence Standards](evidence-standards.md) records so every
delivery claim has a scope, trust level, evidence path, and proof. Expose all
three collections here:

```yaml
claims: [claim records or ids]
gaps: [gap records or none]
proof: [proof records or paths]
```

## Gate verdicts

| Boundary | Verdict | Verdict id | Revision |
|----------|---------|------------|----------|
| [boundary from gates.yaml] | [APPROVED/REVISE/ESCALATE] | [verdict_id] | [n] |

## Disputes

[Open decisions, conflicting evidence, or "none". Name the decision owner and
the revision that introduced each dispute.]

## Residual risks

[Known gaps, denied checks, operational risks, and their severity. Do not hide
unknowns behind a success label.]

## Next action

[One safe, owner-assigned action, or "none" when the delivery is terminal.]

## Return

- Outcome: [completed, revised, blocked, or escalated]
- Revision: [revision]
- Evidence paths: [paths]
- Verdict: [APPROVED, REVISE, or ESCALATE]
```
