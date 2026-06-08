# Example Invocations

## Example 1

**User request:** confirm build completeness for the release candidate

**Output:**
- Required deliverables: production bundle, test suite results, security signoff, and packaging metadata.
- Blocking gap: the security report is referenced by the build summary but missing from the actual package.
- Delivery: completeness packet that marks the build incomplete until the missing artifact is attached.

## Example 2

**User request:** cross-check the build package before review

**Output:**
- Scope: web app bundle, API container image, and integration test evidence.
- Contradiction: the package manifest lists one image digest while the deployment notes cite a different digest.
- Next action: reconcile the artifact lineage before the package advances to `build/gatekeeper-build`.

## Example 3

**User request:** verify the implementation is complete

**Output:**
- Scope: implementation diff, generated artifacts, and regression test record.
- Confirmation: all required deliverables are present and the remaining risks are explicitly limited to post-build monitoring, not missing build proof.
- Delivery: gate-ready build confirmation packet with explicit artifact evidence.

## Example 4

**User request:** re-confirm build completeness after gaps were fixed and the package resubmitted

**Context:** A previous completeness check returned an incomplete verdict because the security report was missing and one test slice lacked evidence. Both gaps have since been addressed and the package is being resubmitted.

**Output:**
- Prior gaps addressed: security report is now attached and points to the same revision as the implementation diff; previously missing test evidence for the permission-check slice is present and timestamped after the implementation commit.
- Re-check: all required deliverables re-inventoried — implementation diff, test results (unit and integration), security report, and packaging metadata are present and internally consistent.
- Residual: one advisory warning in the security report is noted as accepted risk with owner sign-off; not a completeness blocker.
- Delivery: updated gate-ready build confirmation packet, marking the prior incomplete verdict superseded; package is ready for `build/gatekeeper-build`.
