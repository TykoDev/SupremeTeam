# Workflow Reference

## Contents

1. Release sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Release Sequence

1. Resolve the entry mode first, then confirm the exact revision being landed, the target branch or environment, the release window, and the rollback path — from the deploy-readiness package in pipeline mode, or read directly from `setup-deploy`'s persisted artifacts in standalone mode, where no package names them.
2. Confirm the recorded go decision for this revision — the `human_go_required` evidence in the package in pipeline mode, or a named owner's decision recorded before the merge with the same four fields in standalone mode — then the separate code-review approval for the same revision. `preconditions.md` carries both shapes.
3. Capture the pre-release state so later comparisons can prove what changed.
4. Merge or land the approved revision without widening scope during the release step.
5. Run the deployment using the persisted configuration as it stands, then verify the target environment with live health signals and smoke paths.
6. Record whether the outcome is full success, partial success, rollback, or blocked follow-up.

## Decision Rules

- Do not merge a revision that no longer matches the approved reviewed surface.
- A recorded go decision and a current review approval are separate preconditions; neither one covers the other, and neither is satisfied by CI or artifact checks.
- The absence of a deploy-readiness package means standalone mode, never a waived precondition: the go decision is then obtained and recorded directly, and the result says no gate verdict stands behind the release.
- `deploy-config` belongs to `setup-deploy`; drift against it is reported as a blocker, never repaired here.
- Prefer reversible rollout steps over one-shot irreversible changes.
- Treat conflicting verification signals as a blocker until they are reconciled.
- Record partial deployment states explicitly instead of compressing them into success.

## Acceptance Checklist

- The entry mode is stated, and in standalone mode the result says no deploy-readiness package or gate verdict stands behind the release.
- The landed revision is explicit.
- The go decision and the review approval are both present, both name that revision, and both references travel with the result.
- The consumed deploy-config revision is named, and any drift against the live environment is reported rather than reconciled.
- Before and after evidence is captured, and the rollout timestamps are recorded.
- Verification covers both health signals and user-visible behavior, with observed values against their pass conditions.
- Rollback status or residual risk is recorded.

## Contract Notes

The contracts this workflow runs under are stated in `../SKILL.md` § Required Contracts.

## Collaboration Notes

This skill's collaboration surface is stated in `../SKILL.md` § Collaboration Surface.
