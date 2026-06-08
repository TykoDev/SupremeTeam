# Workflow Reference

## Contents

1. Planning sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Planning Sequence

1. Confirm the delivery objective, release window, and the requirements that must land in the first credible milestone using one host-native decision prompt per unresolved judgment call.
2. Break the work into tracks, dependency chains, and decision gates instead of a flat chronological list.
3. Check the rollout path for prerequisite risks such as vendor work, migrations, staffing bottlenecks, or environment dependencies.
4. Package the plan with a Decision Register so the next design consumer can tell what is fixed, what is optional, what was rejected, and what still needs executive choice.

## Decision Rules

- Prefer a smaller believable release slice over a broad but fragile schedule.
- Make dependency risk explicit wherever one team or system blocks another.
- Treat unresolved sequencing decisions as blockers when later phases would otherwise guess.
- Record every design/configuration choice as `user`, `codebase`, `prior-artifact`, or `delegated-default`; do not hide an assumption in prose.
- Keep the plan tied to user value, not just activity volume.

## Acceptance Checklist

- Milestones and rollout slices are explicit.
- Dependencies and decision gates are named clearly.
- The Decision Register includes resolved, deferred, and rejected material options.
- Delivery risks are tied to specific schedule or scope consequences.
- The next downstream consumer can reuse the plan without reinterpreting it.

## Contract Notes

- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- Proactive triggers: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.

## Collaboration Notes

- `design/commander` owns phase sequencing and package assembly.
- `design/gatekeeper-design` validates that the plan is specific enough for later design phases to consume.
