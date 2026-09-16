# Workflow Reference

## Contents

1. Freeze sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Freeze Sequence

1. Name the boundary to freeze and confirm why it must stop changing.
2. Check for active work inside that boundary and capture any bounded exception that must complete first.
3. Record the frozen state through `python skills/harness/hooks/guard_state.py freeze --glob <boundary> --owner <contributor>` — the record's only writer — and write down the blocked actions and release conditions beside it.
4. Route work toward safe surfaces that remain outside the freeze.

## Decision Rules

- Freezes must be specific enough to enforce mechanically or socially.
- Every recorded freeze carries an owner, and a named `--approver` whenever the owner may be unavailable when the lift is needed: a release is authorized against `owner` **or** `approvers`, so those two fields are the whole of the authority check. A bare glob string carries neither and `release` refuses it outright; a record with no `owner` can be lifted only by a listed approver, and with an empty list by nobody.
- Express the boundary as a glob before recording it. `--glob` is what the hook matches; a boundary described only in prose ("the migration scripts") enforces nothing, and one prose boundary often becomes two globs.
- Freeze records should stop ambiguous writes, deploys, and deletes inside the protected boundary.
- Exceptions must stay explicit so the freeze is not eroded by side agreements.
- Reuse an active freeze record when it already governs the same boundary and revision context.

## Acceptance Checklist

- Boundary and blocked actions are explicit.
- The freeze is recorded through `guard_state.py` with an owner, not by editing `.harness-state/guard-state.json`, and the writer exited 0 — any other exit means no boundary exists (`enforcement.md`).
- Release conditions are written down.
- Active overlapping work is addressed directly.
- Safe work outside the freeze is named.

## Contract Notes

The contracts this workflow runs under are stated in `../SKILL.md` § Required Contracts.

## Collaboration Notes

This skill's collaboration surface is stated in `../SKILL.md` § Collaboration Surface.
