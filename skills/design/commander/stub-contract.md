# Commander Stub Contract

## Scope

Commander owns the design pipeline boundary from intake through final design package assembly.

## Phase Order

The order `../../pipelines.yaml` declares for the design pipeline. Architecture precedes the plan; the plan sequences delivery against the approved component boundaries.

1. Admiral's confirmed intake; Taste (`taste-snapshot`) produces the immutable profile or no-profile record
2. Researcher
3. Architect (includes the frontend/UI visual design system when a frontend surface exists)
4. Security-builder (`security-seed`) on every design, including a typed no-boundary assessment
5. Planner
6. Engineer
7. Commander (`stack_lock`), before submission at `design-to-build`

## Required Inputs

- Project goal and target users
- Constraints, preferences, and banned technologies
- Current stack-lock state when resuming or re-entering downstream phases
- Admiral/Taste effective-profile snapshot when Taste storage exists

## Gate Contract

- Commander is the only phase owner that advances design work through the design gate in pipeline mode.
- Maximum REVISE rounds per boundary: 2, shared between phase and cross-stage verdicts under `../../contracts/workflow-protocol.md`; self-checks do not count.
- Skip decisions must be explicit and justified.
- All nine `design-to-build` keys are required: `decisions`, `architecture`, `interfaces`, `plan`, `acceptance`, `security_seed`, `stack_lock`, `taste_snapshot`, `ui_evidence`.
- Exactly three are waivable, each only through its own sanctioned fallback carried as an applicability record: `stack_lock` (`no new runtime or framework - existing stack unchanged`), `taste_snapshot` (`no saved Taste profile available`), `ui_evidence` (`no user-facing surface - design system not engaged`). `security_seed` has no sanctioned fallback and is never waived.
- Self-check before submitting: `python skills/harness/gatekeeper/check.py --boundary design-to-build --package skillset-saves/runs/<run>/design/manifest.json`, without `--verdict-out`.
- Source revisions are rechecked before approval; changed revisions invalidate the snapshot and affected design work.

## Package Shape

- Requirements and domain model
- Architecture decision set, API endpoint contracts, and interface contracts
- Security seed when a trust boundary is in scope, or the recorded determination that none moved
- Delivery plan and milestones
- Frontend specification when applicable
- Implementation guidance and inherited stack decisions
- Approval records for every executed phase
- Taste snapshot plus preference-to-design-artifact/rendered-evidence traceability rows

## Downstream Expectations

- Build consumers can rely on a complete package shape, stable stack decisions, and explicit skip justifications.
