# Workflow Reference

## Contents

1. Release sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Release Sequence

1. Confirm the exact revision being landed, the target branch or environment, the release window, and the rollback path.
2. Capture the pre-release state so later comparisons can prove what changed.
3. Merge or land the approved revision without widening scope during the release step.
4. Run the deployment using durable configuration, then verify the target environment with live health signals and smoke paths.
5. Record whether the outcome is full success, partial success, rollback, or blocked follow-up.

## Decision Rules

- Do not merge a revision that no longer matches the approved reviewed surface.
- Prefer reversible rollout steps over one-shot irreversible changes.
- Treat conflicting verification signals as a blocker until they are reconciled.
- Record partial deployment states explicitly instead of compressing them into success.

## Acceptance Checklist

- The landed revision is explicit.
- Deploy configuration is durable and reproducible.
- Before and after evidence is captured.
- Verification covers both health signals and user-visible behavior.
- Rollback status or residual risk is recorded.

## Contract Notes

- Deploy config persistence: Store verified deployment configuration in a durable project location so later release flows can reuse it safely.
- Before/After Evidence: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.

## Collaboration Notes

- None required beyond the active task surface.
