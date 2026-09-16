# Workflow Reference

## Contents

1. Cautious decision sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Cautious Decision Sequence

0. Read the live boundary first — `python skills/harness/hooks/guard_state.py status` — because a go verdict on a destructive action is unsound while `allow_dangerous` is lifted: the deterministic block behind the verdict is then off for every command in the session.
1. Name the exact action being requested and the boundary it can damage if handled carelessly.
2. Gather the evidence that proves the target, environment, and operator intent are aligned.
3. Decide whether the action is safe to continue, must stay blocked, or needs escalation.
4. Write the decision record with release conditions and the safest next action.

## Decision Rules

- Never treat a vague risky request as implicitly approved.
- Prefer an explicit no-go with clear proof requirements over a weak yes based on assumptions.
- Treat an enforcement fault as a reason to tighten the verdict, never to relax it: a missing `guard_state.py`, a `status` that exits 1 on a corrupt record, or an unregistered hook all mean the boundary is unknown rather than clear (`enforcement.md`).
- Keep residual risk visible so downstream contributors do not treat the record as unconditional clearance.
- Offer the next safe move proactively when it can reduce ambiguity without expanding risk.

## Acceptance Checklist

- The live guard state is read and reported, naming any lifted `allow_dangerous` grant, or the fault that made it unreadable.
- The risky boundary is explicit.
- Evidence proves the target and intent match.
- Residual risk and release conditions are written down.
- The next safe action is stated clearly.

## Contract Notes

The contracts this workflow runs under are stated in `../SKILL.md` § Required Contracts.

## Collaboration Notes

This skill's collaboration surface is stated in `../SKILL.md` § Collaboration Surface.
