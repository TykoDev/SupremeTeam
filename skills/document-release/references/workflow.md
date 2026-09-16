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
4. Redact the external draft across all seven categories — internal hostnames and environment names, internal service and job identifiers, internal URLs including their query parameters, credentials and tokens, internal identifiers and staff names, customer identifiers, and embargoed security detail — applying each to screenshots and attachments as well as text, and log every removal against where the fact is preserved internally. `redaction.md` carries the per-category checklist and the image procedure.
5. Hold the draft for a named owner's approval of that exact revision and the channels it may go to; publish nothing without it.
6. Package the outcome so support, product, and future responders can reconstruct the release state without guesswork.

## Decision Rules

- Prefer release truth over release polish when the rollout is messy or partial.
- Keep user-facing notes, operator notes, and known issues clearly separated.
- Treat unowned follow-up work as incomplete release documentation, not optional extras.
- Escalate when legal, customer, or compliance constraints limit what can be documented publicly.
- Publication is an owner's decision, not a documentation step; the draft is where this skill stops.
- Approval attaches to a draft revision: an approval naming an earlier revision is no approval for the current one, and a fresh one is requested rather than inherited.
- Screenshots and attachments are redacted by cropping or re-capture, never by blur or an overlaid box; both look redacted and are not.
- A credential found in a draft is an exposure to report for rotation, not only a string to delete.
- The release record belongs to `land-and-deploy`: disagreement with it is a finding for that owner, not an edit made here.

## Acceptance Checklist

- Shipped revision and rollout scope are explicit.
- User-facing and operator-facing changes are documented.
- Known issues and follow-up owners are named.
- The release narrative matches the actual ship state.
- The external draft is redacted across text, screenshots, and attachments, and its redaction log is attached.
- Publication approval names the owner, the approved draft revision, and the channels — or the missing approver is named.
- Next communication or remediation steps are clear.

## Contract Notes

The contracts this workflow runs under are stated in `../SKILL.md` § Required Contracts.

## Collaboration Notes

This skill's collaboration surface is stated in `../SKILL.md` § Collaboration Surface.
