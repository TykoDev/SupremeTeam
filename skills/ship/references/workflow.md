# Workflow Reference

## Contents

1. Release sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Release Sequence

Steps 1 to 3 run identically in both entry modes. Step 4 is where they diverge, because only
the pipeline route closes a gate.

1. Resolve the entry mode — a `### Save Context` block or an active run lock means pipeline mode; neither means standalone — and state it before any release work starts.
2. Confirm the release candidate, approvals, rollback path, and launch window, re-verifying the persisted deployment settings against this release rather than the last one.
3. Fix the verification plan and its pass conditions before the rollout, then run the launch in explicit stages with go or no-go checks between packaging, rollout, and verification, recording live verification evidence and preserving any partial-rollout state honestly.
4. Close the readiness boundary:
   - Pipeline — assemble the deploy-readiness package, self-check it, and submit it at the `deploy-readiness` boundary; delegate the rollout only once it is approved and the go decision is on file.
   - Standalone — assemble no package and seek no verdict. Return the readiness statement in its place: approved delivery revision, re-verified configuration and rollback path with the revision each was verified at, the verification plan with its pass conditions, and the named owner's recorded go decision. Say that no `deploy-readiness` verdict exists.
5. Publish the post-ship checklist with follow-up checks and rollback triggers once the rollout record returns from `land-and-deploy`.

## Decision Rules

- Shipping requires a candidate, the persisted deployment settings and rollback path from `setup-deploy`, and verification checkpoints written before the rollout.
- The release record belongs to `land-and-deploy`; a disagreement with it is a finding routed to that owner, not an amendment made here.
- Launch sequencing should stop when evidence turns contradictory or incomplete.
- Partial rollout states must stay explicit rather than being normalized into success.
- Proactive next steps are useful only when they do not hide release risk.
- The named owner's go decision is required in both entry modes; it is a judgment, not a mechanical check, so the absence of a gate never removes it.
- A second `REVISE` on the same package reaches `cycle_cap: 2` and escalates with both packets; the release stays held while that verdict or an `ESCALATE` stands.

## Acceptance Checklist

- Candidate, launch window, and rollback path are named.
- Verification checkpoints are explicit.
- Partial or paused rollout states are recorded honestly.
- Follow-up and rollback triggers are visible in the deploy-readiness package and the post-ship checklist.
- The entry mode is stated, and in standalone mode the result says no `deploy-readiness` verdict exists.

## Contract Notes

The contracts this workflow runs under are stated in `../SKILL.md` § Required Contracts.

## Collaboration Notes

This skill's collaboration surface is stated in `../SKILL.md` § Collaboration Surface.
