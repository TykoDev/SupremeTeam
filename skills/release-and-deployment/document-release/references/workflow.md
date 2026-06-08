# Workflow Reference

## Contents

1. Release-documentation sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Release-Documentation Sequence

1. Confirm the shipped revision, rollout status, and which audiences need a record of the release.
2. Gather the evidence set from deployment results, verification notes, issue lists, and operator follow-up items.
3. Write the release narrative around what actually changed for users, operators, and downstream teams.
4. Package the outcome so support, product, and future responders can reconstruct the release state without guesswork.

## Decision Rules

- Prefer release truth over release polish when the rollout is messy or partial.
- Keep user-facing notes, operator notes, and known issues clearly separated.
- Treat unowned follow-up work as incomplete release documentation, not optional extras.
- Escalate when legal, customer, or compliance constraints limit what can be documented publicly.

## Acceptance Checklist

- Shipped revision and rollout scope are explicit.
- User-facing and operator-facing changes are documented.
- Known issues and follow-up owners are named.
- The release narrative matches the actual ship state.
- Next communication or remediation steps are clear.

## Contract Notes

- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- Proactive triggers: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.

## Collaboration Notes

- None required beyond the active task surface.
