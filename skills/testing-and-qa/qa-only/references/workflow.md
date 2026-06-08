# Workflow Reference

## Contents

1. QA-only sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## QA-Only Sequence

1. Define the workflows and environments to test without changing the product surface.
2. Run the checks, collecting evidence for each defect. Each defect record must include: (a) numbered reproduction steps, (b) observed vs. expected behavior, (c) environment details (OS, runtime version, test data state, account/auth context), (d) severity rating using the shared four-tier model, (e) relevant logs, screenshots, or network traces. No mutations are made at any point.
3. Repeat ambiguous paths only to tighten evidence, never to mutate behavior. If a path cannot be reliably reproduced, record the unstable reproduction boundary and note confidence level.
4. For partial environment access, explicitly list which surfaces were tested and which could not be reached — report both. Do not imply coverage for untested surfaces.
5. Publish a defect report that another team can use directly for remediation.

## Sample Defect Report Entry

| # | Workflow | Defect summary | Severity | Repro steps | Expected | Observed | Environment | Confidence |
|---|----------|----------------|----------|-------------|----------|----------|-------------|------------|
| 1 | Checkout | Payment fails silently on expired card | High | 1. Add item to cart. 2. Enter expired card. 3. Click Pay. | Error message shown | Spinner hangs indefinitely; no feedback | Chrome 124, staging v2.3.1 | Confirmed — 5/5 runs |
| 2 | Login | Session timeout not enforced after 30 min | Medium | 1. Log in. 2. Wait 35 min idle. 3. Navigate. | Redirect to login | Remains logged in | Safari 17, staging v2.3.1 | Unstable — reproduced 3/5 runs |

## Decision Rules

- Keep the scope report-only; remediation belongs elsewhere.
- Mark untestable workflows explicitly instead of implying coverage.
- Prefer reproducible evidence over dramatic defect counts.
- Group symptoms when they point to one root cause.
- For partial environment access, always report the gap explicitly.

## Acceptance Checklist

- Tested and untested workflows are explicit, including what could not be reached and why.
- Each defect has: reproduction steps, observed vs. expected, environment details, severity, and confidence level.
- No fix work is mixed into the report.
- Severity and ownership hints are clear enough for handoff.

## Contract Notes

- Reproduction Evidence: Capture reproduction steps and observed-vs-expected state for each defect. No interventions or changes are made — this skill is strictly read-only.
- Partial-access transparency: Explicitly list what was tested and what could not be reached.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.

## Collaboration Notes

- None required beyond the active task surface.
