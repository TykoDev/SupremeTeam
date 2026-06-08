# Code Chief Stub Contract

## Scope

Code chief owns the review pipeline from intake through consolidated gate submission and final review package delivery.

## Core Review Sequence

1. Bug review
2. Code review
3. Quality review
4. Security review
5. Adversarial review

## Conditional Review Sequence

- Add CSO/security-leadership review when accepted risk, release security posture, operating-model controls, regulated commitments, or explicit security-chief review language are in scope.
- Add frontend review when a user-facing frontend is in scope.
- Add visual review when there is meaningful rendered UI or styling to inspect.
- Add developer-experience review when onboarding, CLI, SDK, or public integration surfaces are in scope.

## Required Inputs

- Review target and scope statement
- Risk tier and detected technology stack
- Upstream design or build context when available

## Gate Contract

- Code chief owns the consolidated review submission.
- Core phases are always executed, though depth may vary by scope.
- Every skipped optional phase requires a written justification in the execution manifest.

## Package Shape

- Specialist reports for all executed phases
- Execution manifest with invoked phases and skip reasons
- CSO/security-leadership packet or explicit skip reason when security governance or accepted-risk claims are present
- Consolidated risk summary and remediation priorities
- Final approval record from the review gate

## Downstream Expectations

- Delivery consumers can trace each major issue back to a named specialist report and evidence source.
