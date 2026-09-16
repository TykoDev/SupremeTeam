# Workflow Reference

## Contents

1. QA-only sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## QA-Only Sequence

1. Record the read-only boundary before anything is exercised: `python skills/harness/hooks/guard_state.py read-only --run-id <run> --owner <requester> --allow "<the run's own save path>"`. The run id is the active run in pipeline mode and the synthetic `qa-only-<YYYY-MM-DD>-<surface-slug>` in standalone mode; `read-only-boundary.md` carries both, with the allow glob for each.
2. Define the workflows and environments to test without changing the product surface.
3. Run the checks, collecting evidence for each defect. Each defect record must include: (a) numbered reproduction steps, (b) observed vs. expected behavior, (c) environment details (OS, runtime version, test data state, account/auth context), (d) severity rating using the shared four-tier model, (e) relevant logs, screenshots, or network traces. No mutations are made at any point.
4. Repeat ambiguous paths only to tighten evidence, never to mutate behavior. If a path cannot be reliably reproduced, record the unstable reproduction boundary and note confidence level.
5. For partial environment access, explicitly list which surfaces were tested and which could not be reached — report both. Do not imply coverage for untested surfaces.
6. Release the boundary once the evidence is written and before the run ends: `python skills/harness/hooks/guard_state.py release-read-only --run-id <run> --requester <requester>`. Confirm with `guard_state.py status`. An unreleased record keeps denying writes project-wide in later sessions, so the release belongs to the run that recorded it, not to whoever meets the block next.
7. Publish a defect report that another team can use directly for remediation, carrying the boundary record and its release alongside the findings. Delegated inside the `qa` pipeline, self-check the evidence with `check.py` and hand it to `qa`, which assembles and submits the `qa-review` package; standalone, return the report inline and state that no gate verdict was sought.

## Sample Defect Report Entry

| # | Workflow | Defect summary | Severity | Repro steps | Expected | Observed | Environment | Confidence |
|---|----------|----------------|----------|-------------|----------|----------|-------------|------------|
| 1 | Checkout | Payment fails silently on expired card | Critical | 1. Add item to cart. 2. Enter expired card. 3. Click Pay. | Error message shown | Spinner hangs indefinitely; no feedback | Chrome 124, staging v2.3.1 | Confirmed — 5/5 runs |
| 2 | Login | Session timeout not enforced after 30 min | Major | 1. Log in. 2. Wait 35 min idle. 3. Navigate. | Redirect to login | Remains logged in | Safari 17, staging v2.3.1 | Unstable — reproduced 3/5 runs |

## Decision Rules

- Keep the scope report-only; remediation belongs elsewhere.
- Record the boundary before the first probe and release it before the run ends; a run that skips either end is not a QA-only run.
- Mark untestable workflows explicitly instead of implying coverage.
- Prefer reproducible evidence over dramatic defect counts.
- Group symptoms when they point to one root cause.
- For partial environment access, always report the gap explicitly.
- `fixes_applied` at `qa-review` is always the sanctioned fallback for this skill — at schema 2, an applicability record whose `reason` is the verbatim `report-only run - no fixes applied`. A fix list there means the run belonged to `qa`.

## Acceptance Checklist

- Tested and untested workflows are explicit, including what could not be reached and why.
- Each defect has: reproduction steps, observed vs. expected, environment details, severity, and confidence level.
- No fix work is mixed into the report.
- The read-only boundary was recorded with a named owner, and its release is shown in the result.
- Severity and ownership hints are clear enough for handoff.

## Contract Notes

The contracts this workflow runs under are stated in `../SKILL.md` § Required Contracts.

## Collaboration Notes

This skill's collaboration surface is stated in `../SKILL.md` § Collaboration Surface.
