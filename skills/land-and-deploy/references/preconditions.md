# Preconditions Reference

Read this before the merge. Two independent preconditions gate every landing, in both entry
modes, and neither is satisfied by CI, artifact validation, or a green pipeline. This file
gives the shape of each, where it lives per mode, and how a mismatch is handled.

## Contents

1. The two preconditions and why they are separate
2. The recorded go decision
3. The current review approval
4. Revision mismatch and drift
5. What the release record carries forward

## 1. The Two Preconditions and Why They Are Separate

They answer different questions and are resolved by different people:

| Precondition | Question it answers | Typical owner |
| --- | --- | --- |
| Recorded go decision | Does the owner want this live, now? | Release owner, service owner, on-call lead |
| Current review approval | Is this change sound? | The named reviewer of that revision |

One satisfied precondition never covers the other. A thoroughly reviewed change still needs
someone to choose this moment; an urgently wanted change still needs someone to have read it.
Automated signals — CI status, artifact checks, a passing build, a green dashboard — are
readiness inputs to both decisions and a substitute for neither.

## 2. The Recorded Go Decision

Four fields, in both modes:

| Field | Content |
| --- | --- |
| Approver identity | A named person or named role holder, never "the team" or "approved" |
| Approval reference | The record the decision lives in: a ticket, a chat permalink, a sign-off entry |
| Exact revision | The commit or release identifier being landed, not a branch name |
| Decision timestamp | When the decision was made, so staleness is visible |

**Pipeline mode.** The decision is the `human_go_required` evidence inside `ship`'s approved
deploy-readiness package. `../../gates.yaml` sanctions no fallback value for that key, so it
cannot be waived by an applicability record, and `../../pipelines.yaml` starts this stage only
`when: human go decision recorded` — an absent decision means the stage has not started, not
that it started with a caveat.

**Standalone mode.** No package exists, so the decision stands alone and is obtained before the
merge rather than read from an artifact. Quote the four fields back against the exact revision
and proceed only on an explicit go. These are all absent decisions, not weak ones: silence, an
approval of an earlier release, a general "yes, ship it" naming no revision, and an approval
given before the last commit landed. The result then states that the release proceeded on a
recorded decision with no gate verdict behind it, so nobody downstream reads it as gated.

## 3. The Current Review Approval

A named reviewer approved the exact revision being merged, the approval is still current for it,
and its reference travels with the release: a review link, a sign-off record, or an equivalent
durable pointer. "Current" means the approved surface and the surface being merged are the same
— an approval that predates a later commit on the branch is stale, regardless of how small the
commit looks.

## 4. Revision Mismatch and Drift

Any disagreement between the approved revision, the reviewed revision, and the revision about to
merge stops the flow before the merge. Name the divergence precisely — the last approved commit,
the extra commits, and which precondition each one invalidates — and require the specific repair:

- The branch moved after review: a fresh review boundary, or a release target narrowed back to
  the reviewed revision.
- The go decision names an earlier revision: a new decision for this revision at this time, from
  a named owner. Re-dating the old one is not a decision.
- The live environment differs from the persisted `deploy-config` the flow is about to use: stop
  and report the drift as a release blocker owned by `setup-deploy`. It is never reconciled from
  inside the rollout; one writer per configuration is what makes the next rollout reproducible.

## 5. What the Release Record Carries Forward

Both precondition references travel into the release record — the go decision's approver and
reference, and the review approval's reference — alongside the consumed `deploy-config`
revision, the release result with its timestamps, and the post-release verification evidence.
That is what lets a release be audited back to the people who approved it, months later, by
someone who was not there.
