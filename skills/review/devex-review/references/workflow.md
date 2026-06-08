# Workflow Reference

## Contents

1. Developer-journey sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Developer-Journey Sequence

1. Follow the published onboarding path for the scoped surface: install, configure, run, verify, and integrate.
2. Inspect how the docs, tooling, samples, and errors support that journey across the intended environment.
3. Record friction with the affected persona, environment boundary, and smallest fix that removes the blocker.
4. Package the onboarding and tooling findings for `review/code-chief`.

## Decision Rules

- Prefer the first-run or integration path the project actually publishes over an expert-only shortcut.
- Keep environment-specific issues tied to the OS, shell, runtime, or credential boundary that caused them.
- Separate blocking onboarding failures from nice-to-have documentation cleanup.
- Treat version ambiguity as an evidence gap when docs and behavior appear misaligned.

## Acceptance Checklist

- Findings identify the affected persona and the broken developer journey step.
- Environment assumptions are explicit.
- Docs, tooling, and sample-app problems are distinguished clearly.
- Reproduction steps are detailed enough for downstream validation.

## Contract Notes

- Before/After Evidence: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.

## Collaboration Notes

- `review/code-chief` merges the devex packet with the core and optional review lenses.
- `review/gatekeeper-code` checks that blocking onboarding or tooling failures remain visible in the final package.
