# Commander Stub Contract

## Scope

Commander owns the design pipeline boundary from intake through final design package assembly.

## Phase Order

1. Researcher
2. Planner
3. Architect (includes the frontend/UI visual design system when a frontend surface exists)
4. Engineer

## Required Inputs

- Project goal and target users
- Constraints, preferences, and banned technologies
- Current stack-lock state when resuming or re-entering downstream phases

## Gate Contract

- Commander is the only phase owner that advances design work through the design gate in pipeline mode.
- Maximum revisions per phase: 3.
- Skip decisions must be explicit and justified.

## Package Shape

- Requirements and domain model
- Delivery plan and milestones
- Architecture decision set, API endpoint contracts, and interface contracts
- Frontend specification when applicable
- Implementation guidance and inherited stack decisions
- Approval records for every executed phase

## Downstream Expectations

- Build consumers can rely on a complete package shape, stable stack decisions, and explicit skip justifications.
