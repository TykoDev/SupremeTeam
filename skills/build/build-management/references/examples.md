# Example Invocations

## Example 1

**User request:** implement this design

**Output:**
- Phase path: bob-the-builder -> test-builder -> security-builder -> cross-check-build-confirm.
- Revision note: a schema migration added during implementation forces tests and security evidence to rerun on the updated revision.
- Delivery: consolidated build package with aligned code, tests, security disposition, and completeness certification.

## Example 2

**User request:** start the build pipeline

**Output:**
- Scope: tenant onboarding workflow with API, worker, and admin console changes.
- Build issue: security hardening discovered an unsafe dependency upgrade, so the pipeline routes back through implementation and then reruns the affected checks.
- Boundary note: the package does not advance to `build/gatekeeper-build` until the evidence set is coherent again.

## Example 3

**User request:** build this project

**Output:**
- Package contents: production diff summary, test results, security report, completeness confirmation, and build-gate submission notes.
- Non-first-party handling: generated SDK files are explicitly listed with ownership and scan notes instead of folded into first-party claims.
- Next move: submit the revision-aligned package to the build gate for review-readiness validation.
