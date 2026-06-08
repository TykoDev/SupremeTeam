# Example Invocations

## Example 1

**User request:** validate the build deliverable

**Output:**
- Verdict: `REVISE`.
- Missing evidence: the implementation summary mentions end-to-end coverage, but no rerun output is attached for the submitted revision.
- Required fix: rerun the relevant test suite or narrow the completeness claim before resubmission.

## Example 2

**User request:** review build phase output

**Output:**
- Verdict: `APPROVED`.
- Evidence map: implementation diff, unit and integration results, security-clean note, and completeness certification all point to the same revision.
- Boundary note: the package is ready for review as long as later edits do not change the build revision.

## Example 3

**User request:** check build readiness

**Output:**
- Verdict: `ESCALATE`.
- Conflict: the package resolves a migration failure by changing the persistence model, which exceeds the approved design scope.
- Required decision: obtain a design-level approval or rewind the build packet to the prior contract.

## Example 4

**User request:** validate the build deliverable (package-dir not present in expected working area)

**Context:** The build context supplies `package-dir` as `../../shared/releases/candidate-v2`, which traverses above the designated build working area.

**Output:**
- Verdict: `ESCALATE`.
- Reason: the supplied `<package-dir>` path contains traversal sequences (`../`) and does not resolve inside the expected build/package working area. The gate script was not invoked.
- Required action: build-management must supply a valid package directory path inside the designated working area before this submission can be evaluated.
