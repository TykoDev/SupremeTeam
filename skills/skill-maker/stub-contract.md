# Skill Maker Stub Contract

## Scope

Skill-maker owns the full skill creation lifecycle: intake classification, delegation to creation and review specialists, quality-gate management, description optimization, packaging, and delivery. Also owns team creation — generating coordinated skill sets.

## Stage Model

1. Create through skill-creator (Create mode)
2. Review through skill-reviewer
3. Improve through skill-creator (Improve mode) — loops back to Review, max 5 cycles
4. Optimize through skill-creator (Optimize mode) — runs after 100/100
5. Package and deliver through skill-creator (Package mode)

## Required Stage Inputs

- Create stage: skill intent, constraints, example files, entry mode
- Review stage: skill directory path, iteration number, previous scorecard
- Improve stage: skill path, findings list, user guidance
- Optimize stage: skill path, current description, eval queries
- Package stage: skill path

## Handoff Rules

- Skill-maker never modifies skill files directly. All changes go through skill-creator.
- Skill-maker never scores rubric dimensions. All scoring goes through skill-reviewer.
- Skill-maker never overrides a reviewer verdict without explicit user confirmation.
- Verdict vocabulary from skill-reviewer: SHIP, ITERATE, BLOCKED.
- When invoked by Admiral, verdicts map to: SHIP → APPROVED, ITERATE → REVISE, BLOCKED → ESCALATE.
- Maximum review-improve cycles: 5.
- Plateau detection: score unchanged for 2 consecutive iterations triggers user escalation.

## Delivery Contract

- Deliver a .skill package file plus a delivery report with iteration history, final scorecard, and changes summary.
- For team creation, deliver a coordinated set of .skill packages with a team manifest.

## Quality Contract

- Score threshold for shipping: 100/100 on the 10-dimension rubric.
- Critical findings block shipping unless the user explicitly overrides.
- Description optimization only runs after achieving 100/100.
