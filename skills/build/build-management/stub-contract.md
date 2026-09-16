# Build Management Stub Contract

## Scope

Build management owns the full build pipeline from approved design inputs to a ready-for-review build package.

## Mandatory Phase Order

The order `../../pipelines.yaml` declares for the `build` pipeline. A stage
carrying a condition runs only when the condition holds; every other stage runs
on every build.

1. `bob-the-builder` for implementation
2. `test-builder` for automated validation coverage, producing the `tests` probe log
3. `security-builder` for hardening and remediation guidance, when a trust boundary is in scope
4. `health-check` for runtime health, producing the `runtime` probe log — unconditional, and the one evidence key at `build-to-review` that a passing test suite can never stand in for
5. `debugger` for a reproduced build-phase failure, when one exists
6. `investigate` for the investigation pipeline, when the failure mechanism is unknown
7. `cross-check-build-confirm` for completeness confirmation
8. `gatekeeper-build` for the phase gate at `build-to-review`

## Required Inputs

- Approved design package with implementation guidance
- Explicit scope boundaries for the requested build
- Environment or runtime constraints that affect implementation choices

## Gate Contract

- No unconditional phase may be skipped in the canonical build path; `runtime-health` in particular runs on every build, because `runtime` is required at `build-to-review` and accepts no fallback.
- Build management owns the build gate cycle for every phase.
- Security remediations that change code must re-enter the gate before completeness confirmation, because the earlier `tests` and `runtime` logs describe the pre-remediation revision.
- Required evidence: `approved_design_revision`, `implementation`, `tests`, `runtime`, `traceability`, `security_evidence`. Only `security_evidence` is waivable, through the sanctioned value `no trust-boundary change - security-builder not engaged` carried as an applicability record.
- Self-check before submitting: `python skills/harness/gatekeeper/check.py --boundary build-to-review --package build/manifest.json`, without `--verdict-out`.
- Maximum revisions per boundary: 2 (`gates.yaml` `revise_policy.cycle_cap`); a third cycle escalates to admiral instead of resubmitting.

## Package Shape

- Production code
- Test suite and the executed runner log hashed as `tests`
- Runtime smoke log from `health-check`, hashed as `runtime`
- Security disposition with resolved or escalated items
- Non-first-party inventory with source, version, owner, and scan note per path
- Design-decision-to-changed-artifact traceability, with unproven rows stating why
- Completeness certification
- Approval records for every executed phase

## Downstream Expectations

- Review consumers can assume the package includes code, tests, security disposition, and final completeness evidence.