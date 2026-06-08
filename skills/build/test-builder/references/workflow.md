# Workflow Reference

## Contents

1. Test-design sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Test-Design Sequence

1. Confirm the changed behavior, risk surface, and the boundaries that actually need test proof.
2. Choose the right layers for coverage instead of defaulting to whichever test harness already exists.
3. Run the relevant suites and record the exact evidence tied to the submitted revision.
4. Package the result so the build gate can see what is covered, what remains risky, and why.

## Decision Rules

- Prefer coverage at the boundary where failure would matter most.
- Treat missing reproduction paths as missing evidence, not a documentation nicety.
- Keep out-of-scope coverage explicit whenever environment limits prevent a full run.
- Escalate when the right test surface requires design or infrastructure decisions outside the assigned build scope.

## Acceptance Checklist

- The tested behavior and boundaries are explicit.
- Coverage includes critical failure paths, not just success cases.
- Executed suites and reproduction commands are recorded.
- Remaining risk is narrow and honest.

## Contract Notes

- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- Proactive triggers: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.

## Collaboration Notes

- `build/build-management` — delegating orchestrator; owns scope assignment, phase routing, and resubmission after test findings are returned.
- `build/gatekeeper-build` — downstream gate; validates that the test evidence matches the submitted build revision before the package can advance.
