# Build Management Stub Contract

## Scope

Build management owns the full build pipeline from approved design inputs to a ready-for-review build package.

## Mandatory Phase Order

1. Bob-the-builder for implementation
2. Test-builder for automated validation coverage
3. Security-builder for hardening and remediation guidance
4. Cross-check-build-confirm for completeness confirmation

## Required Inputs

- Approved design package with implementation guidance
- Explicit scope boundaries for the requested build
- Environment or runtime constraints that affect implementation choices

## Gate Contract

- No mandatory phase may be skipped in the canonical build path.
- Build management owns the build gate cycle for every phase.
- Security remediations that change code must re-enter the gate before completeness confirmation.

## Package Shape

- Production code
- Test suite and execution summary
- Security disposition with resolved or escalated items
- Completeness certification
- Approval records for every executed phase

## Downstream Expectations

- Review consumers can assume the package includes code, tests, security disposition, and final completeness evidence.