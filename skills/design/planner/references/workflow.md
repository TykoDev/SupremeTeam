# Workflow Reference

Read this when producing a `plan`: it carries the planning sequence, the delivery-plan
document template, the acceptance and Decision Register tables, the
migration/deprecation template, and the acceptance checklist.

## Contents

1. Planning sequence
2. Delivery-plan template
3. Acceptance criteria table
4. Decision Register table
5. Migration/deprecation template
6. Decision rules
7. Acceptance checklist
8. Collaboration notes

## Planning Sequence

1. Confirm the delivery objective, release window, and the requirements that must
   land in the first credible milestone, using one host-native decision prompt per
   unresolved judgment call.
2. Read the approved architecture for the dependency order: which component owns
   what, which interfaces cross a trust boundary, and which invariant forces two
   pieces of work to land together. The sequence is derived from those facts, not
   proposed beside them.
3. Break the work into tracks, dependency chains, and decision gates instead of a
   flat chronological list.
4. Write the acceptance row for every slice — condition, check, acceptor — before
   the plan is packaged. This is the `acceptance` evidence key, and it has no
   sanctioned fallback at the gate.
5. Check the rollout path for prerequisite risks: vendor work, migrations,
   staffing bottlenecks, environment dependencies, support coverage.
6. Package the plan with the Decision Register so the next design consumer can tell
   what is fixed, what is optional, what was rejected, and what still needs an
   executive choice.

## Delivery-Plan Template

```markdown
# Delivery Plan — {scope}

**Revision**: {n}   **Architecture**: {path}@{sha256}   **Security seed**: {path or "no trust boundary"}

## Milestone path

| # | Milestone | Delivery slices | Depends on | Decision gate before it | Target |
| - | --------- | --------------- | ---------- | ----------------------- | ------ |

## Acceptance criteria

{one row per slice — see the table below}

## Rollout and rollback shape

| Stage | Audience | Mechanism | Rollback | Trigger to advance |
| ----- | -------- | --------- | -------- | ------------------ |

## Risk handling

| Risk | Kind | Consequence if it lands | Mitigation | Owner |
| ---- | ---- | ----------------------- | ---------- | ----- |

{kind: rollout, staffing, technical dependency, or external — kept separate so the
gate can challenge the right part of the plan}

## Decision Register

{see the table below}

## Migration / deprecation

{the template below, or "not applicable — nothing existing is removed or replaced"}

## Non-goals and YAGNI deferrals

| Deferred | Why it is safe to defer | Reopen trigger | Owner |
| -------- | ----------------------- | -------------- | ----- |
```

## Acceptance Criteria Table

The `acceptance` evidence key in table form. Three fields, all required; a slice
missing one is not yet planned.

| Slice | Observable condition | Check that proves it | Acceptor |
| ----- | -------------------- | -------------------- | -------- |

- **Observable condition** — what is true in the world when the slice is done,
  stated so two people would agree whether it holds. Not "the API is finished".
- **Check** — the command, query, report, or observation that decides it. A
  condition whose check is "review it" is an intention.
- **Acceptor** — a named person or role. A check nobody is named to run is not a
  check, and the build phase cannot close the slice against it.

## Decision Register Table

| Decision | Status | Chosen | Source | Rejected options (why) | Owner | Reopen trigger / latest safe point |
| -------- | ------ | ------ | ------ | ---------------------- | ----- | ---------------------------------- |

- **Status** — `resolved`, `deferred`, `rejected`, or `yagni-deferred`.
- **Source** — `user`, `codebase`, `prior-artifact`, or `delegated-default`, per
  `../../../grill-me-doctrine.md`. A delegated default is a real answer and is
  recorded as one, so the gate can see the user accepted it.
- Every `deferred` and `yagni-deferred` row carries a reopen trigger; every
  `resolved` row that is still reversible carries the point at which it stops being
  reversible.

## Migration/Deprecation Template

Used whenever the plan removes, replaces, or changes an existing system, API,
dependency, feature, or operational workflow. Nothing is deprecated without a
replacement path.

```markdown
## Migration / deprecation — {what is being replaced}

**Replacement readiness**: {what must exist and be proven before the old path is
discouraged — feature parity, performance, migration tooling, documentation}
**Consumer discovery**: {how active consumers were enumerated: telemetry, logs,
dependency graph, registry. State the coverage and what it misses}
**Consumers found**: {count and the ones that matter, each with an owner}
**Posture**: advisory {date} → compulsory {date}, or advisory only
**Migration path**: {the steps a consumer takes, and the tooling or documentation
that carries them}
**Removal criteria**: {the evidence required before removal — zero traffic for a
stated window, every named consumer migrated, or an explicit owner decision}
**Fallback**: {what happens to a consumer that has not migrated at the compulsory
date}
```

A deprecation whose consumer discovery could not be completed stays advisory. A
compulsory removal against an unknown consumer set is a breakage plan, not a
migration plan.

## Decision Rules

- Prefer a smaller believable release slice over a broad but fragile schedule.
- Make dependency risk explicit wherever one team or system blocks another.
- Treat unresolved sequencing decisions as blockers when later phases would
  otherwise guess.
- Record every design/configuration choice as `user`, `codebase`,
  `prior-artifact`, or `delegated-default`; do not hide an assumption in prose.
- Keep the plan tied to user value, not activity volume — a milestone nobody
  outside the team can perceive is a checkpoint, and it is labelled as one.
- Never extend the sequence past the approved architecture's scope; the unapproved
  remainder is a non-goal with a decision gate, not a later milestone.

## Acceptance Checklist

- Milestones and rollout slices are explicit and tied to user value.
- Every dependency edge names the architecture boundary or contract that creates it.
- Every slice has an acceptance row with all three fields filled.
- Rollout and rollback shape is stated per stage, including the trigger to advance.
- Risks are separated by kind and each has a consequence, a mitigation, and an owner.
- The Decision Register includes resolved, deferred, rejected, and YAGNI-deferred
  material options with sources and reopen triggers.
- A migration/deprecation section exists whenever something existing changes, or
  the plan states explicitly that nothing does.
- The plan stops at the edge of the approved architecture, and anything beyond it
  is a named non-goal.
- The next downstream consumer can reuse the plan without reinterpreting it.

## Contract Notes

The contracts this workflow runs under are stated in `../SKILL.md` § Required Contracts.

## Collaboration Notes

This skill's collaboration surface is stated in `../SKILL.md` § Collaboration Surface.
