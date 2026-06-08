# Example Invocations

## Example 1

**User request:** validate the handoff

**Output:**
- Verdict: `REVISE`.
- Boundary: design to build.
- Missing evidence: the design package contains ADRs and API contracts, but the gate record for the current revision is absent.
- Required fix: resubmit with the matching approval lineage or rewind the package to the last approved revision.

## Example 2

**User request:** check build readiness

**Output:**
- Verdict: `APPROVED`.
- Evidence map: build package, completeness certification, and revision delta all point to the same submission and are clean for the review boundary.
- Resume note: reuse this verdict only if the build package revision remains unchanged.

## Example 3

**User request:** review delivery readiness

**Output:**
- Verdict: `ESCALATE`.
- Conflict: the review package marks a production token exposure as unresolved while the delivery summary claims release acceptance.
- Required decision: user or release owner must resolve the risk acceptance question before the package can advance.

## Example 4

**User request:** validate the shadcn/ui design delivery package

**Output:**
- Verdict: `APPROVED`.
- Boundary: design package (with frontend/UI design output) to delivery.
- Evidence map: approved frontend/UI design output, generated tokens (`globals.css`) + components, `design-system.md`, the design-gate scorecard, and the active Save Context all point to the same revision.
- Resume note: if the UI design output, tokens, or scorecard change, generate a new submission id before reusing this verdict.
