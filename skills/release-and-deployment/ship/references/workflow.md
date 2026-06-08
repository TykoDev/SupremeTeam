# Workflow Reference

## Contents

1. Release sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Release Sequence

1. Confirm the release candidate, approvals, rollback path, and launch window.
2. Run the launch in explicit stages with go or no-go checks between packaging, rollout, and verification.
3. Record live verification evidence and preserve any partial-rollout state honestly.
4. Publish the release record with follow-up checks and rollback triggers.

## Decision Rules

- Shipping requires a candidate, a rollback path, and verification checkpoints.
- Launch sequencing should stop when evidence turns contradictory or incomplete.
- Partial rollout states must stay explicit rather than being normalized into success.
- Proactive next steps are useful only when they do not hide release risk.

## Acceptance Checklist

- Candidate, launch window, and rollback path are named.
- Verification checkpoints are explicit.
- Partial or paused rollout states are recorded honestly.
- Follow-up and rollback triggers are visible in the release record.

## Contract Notes

- Before/After Evidence: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- Proactive triggers: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.

## Collaboration Notes

- None required beyond the active task surface.
