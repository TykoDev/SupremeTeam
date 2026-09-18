---
name: document-release
description: >-
  Drafts release notes, operational follow-up, and the documentation trail,
  redacts them, and holds publication for a named owner's approval of that exact
  draft. Use for "document the release", "update the launch notes", "write the
  release follow-up", or "capture what shipped" — even when the request is only
  "write up what we just released". Drafts, never publishes; defers the rollout
  to `land-and-deploy` and orchestration to
  `ship`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---


# Document Release

## Purpose

Release notes are the most widely read artifact a release produces and the least reversible: once a note is sent, a correction never reaches everyone who saw the original. This skill treats that asymmetry as its design constraint. It reconciles the write-up against what actually shipped rather than what was planned, strips the internal and customer detail that release notes are the classic carrier for, and stops at a draft — publication is an owner's decision, recorded against an exact draft revision and named channels, not a step this skill takes on its own.

## Use This Skill When

Use this skill to **leave a usable record of what shipped** — after the rollout, not during it:

- "document the release" / "capture what shipped" — record scope, changes, and impact
- "update the launch notes" — produce user- and operator-facing release notes
- "write the release follow-up" — capture operational follow-up and known issues
- "write up what we just released" — the retrospective ask, once the rollout is already done

Route elsewhere to perform the merge and rollout (`land-and-deploy`), orchestrate the whole release (`ship`), or set up durable deploy configuration (`setup-deploy`).

## Entry Routing

`../routing-doctrine.md` classes this skill a standalone tool, invokable directly at any time, and `../pipelines.yaml` also runs it as the `document` stage of the `release` pipeline. That stage carries no `when:` condition, so in a release run the notes are written every time rather than only when someone remembers to ask. The two entry paths differ in what the draft is written against, never in whether the approval before publication is required:

| Signal | Mode | What the draft is written against |
|--------|------|-----------------------------------|
| A `### Save Context` block, or an active run lock under `skillset-saves/` | **Pipeline** | The `release-record` `land-and-deploy` produced for the shipped revision, with the approved deploy-readiness package behind it. The draft goes to the run save path and travels with that record. |
| Neither present — a direct "write the release notes" | **Standalone** | Whatever the requester supplies: the revision, the change set, the audience. Nothing upstream is assumed, and the draft marks which facts were supplied rather than verified. |

Say which mode is active before drafting. In pipeline mode this stage submits nothing: `../gates.yaml` closes the `release` pipeline at `deploy-readiness`, which `ship` submits before the rollout stage runs, so notes written here neither gate anything nor stand in for the gate that already passed. What changes inside a run is the source of the facts and the destination of the draft — not the draft-only rule, which holds in both modes until a named owner approves that exact revision and the channels it may go to.

## Inputs

- Release scope, shipped revision, deployment outcome, and the audiences who need post-release documentation.
- Supporting material such as change summaries, rollout notes, verification results, known issues, screenshots, and operator follow-up items.
- Constraints such as regulated communications, customer commitments, embargoes, or incomplete rollout status.

## Outputs

`../ownership.yaml` grants `document-release` one artifact, `release-notes`, and lists `release-record` under `does_not_write`. The release record belongs to `land-and-deploy` and is read here as evidence. Everything below leaves this skill as a draft.

- Release notes draft tailored to the target audiences, with shipped changes, behavior differences, and known issues, marked DRAFT until a named owner approves publication.
- Operational follow-up record covering rollout status, verification evidence, owner assignments, and support/monitoring notes. This one stays internal and keeps the detail the external draft redacts.
- Redaction log naming what was removed or generalized from the external draft and where the unredacted fact is preserved, so redaction is reviewable instead of invisible.
- Publication-approval record naming the approving owner, the exact draft revision approved, and the channels approved — or naming the approver still outstanding when no approval exists.
- Documentation gap list for missing screenshots, customer commitments, regulatory language, or incomplete release facts.

## Workflow

1. Reconcile the intended release with the revision and rollout result that actually shipped so the documentation follows reality rather than plan.
2. Record user-facing changes, operational consequences, rollback notes, known issues, and any follow-up work that the release leaves behind.
3. Shape the release write-up for its consumers, including product, support, operators, and downstream teams who need a usable paper trail.
4. **Redact before any draft leaves internal circulation**, across seven categories: internal hostnames and environment names; internal service, queue, job, and dashboard identifiers; internal URLs **including their query parameters**; credentials, tokens, session ids, connection strings, and signed URLs; internal ticket ids and staff names; customer identifiers and any data drawn from a customer's records; and embargoed security-fix detail — CVE identifiers, affected version ranges, exploit conditions, and mitigation timing — until the embargo owner releases it. Apply every category to **screenshots and attachments as well as text**: an image carries window chrome, address bars, account names, and adjacent surfaces that no text pass ever sees, so it is cropped or re-captured rather than blurred. Move each removed fact into the internal follow-up record rather than deleting it, and list the removals in the redaction log. `references/redaction.md` carries the per-category checklist, the screenshot procedure, and what to do when a credential is found.
5. **Hold publication for a named owner's approval**: the draft is the deliverable, and publication is someone else's decision. Approval names the owner, the exact draft revision, and the channels approved; an approval of an earlier draft does not carry to a changed one. Absent that approval, return the draft and name the missing approver. **The approver is never the drafter.** This skill drafts, so it never approves its own output, and where a person wrote the draft the approval comes from someone else — the release owner, the embargo owner for security detail, or whoever owns the channel being published to. The control exists because the draft's author is the one reader who cannot see what they left in it; an author approving their own customer-facing text is a single point of failure on an irreversible send. If no second party is available, that is a missing approver to report, not a formality to waive.
6. Return a release documentation package with ship summary, open risks, owners, redaction log, publication-approval state, and the next communication or remediation action.

## Required Contracts

- **Draft only; publication requires named-owner approval**: Release notes leave this skill as a draft. Publication, customer email, status-page updates, changelog commits, in-product announcements, and any other external distribution require a named owner's explicit approval of the exact draft revision, recorded with the owner's identity, that revision, and the channels approved. Customer-facing text is irreversible once sent, so this approval is the control that a later correction cannot replace. An approval of an earlier draft never carries to a changed one, and no approval is inferred from the request to write the notes.
- **Redaction before external circulation**: Apply Workflow step 4 to every draft intended for an audience outside the team — text, screenshots, and attachments alike — and keep the redaction log with the draft so a reviewer can see what was withheld and why. Release notes are the most widely read artifact a release produces, which makes them the easiest place to leak infrastructure detail, customer identity, a live credential, or an unpatched vulnerability. Screenshots are the highest-risk carrier precisely because they are pasted in as illustrations rather than reviewed as content; `references/redaction.md` gives their checklist.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../execution-contract.md` defines, so upstream and downstream packages interpret risk consistently.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- None required beyond the active task surface.

## Review Expectations

- Reconcile every public or operator-facing claim against the shipped revision and rollout evidence.
- Separate customer-facing notes, operator runbook updates, and internal follow-up so each audience gets the right detail.
- Flag unknown rollout state or missing verification as documentation blockers instead of filling gaps with planned behavior.
- Confirm before handing off that the external draft carries its redaction log and its publication-approval state, because a draft that reads as finished is the one most likely to be published unreviewed.

## Skip Rule

Skip only when the requested surface, tool, or environment does not exist and a safe fallback is unavailable.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The release notes describe planned features or fixes that are not present in the revision that actually shipped | Rewrite the documentation around the shipped evidence and explicitly drop claims that outrun the release. |
| User-facing notes omit one breaking change, migration step, or operator action that downstream teams must know to use the release safely | Treat the release documentation as incomplete until the operational consequence is documented. |
| Known issues exist at ship time, but the documentation hides them or leaves ownership vague | Preserve the issue, assign an owner, and avoid presenting the release as cleaner than it is. |
| The rollout stopped partway through and the package mixes documentation for shipped and unshipped environments | Narrow the release notes to the actual deployment state and call out the version skew explicitly. When the release record disagrees with the observed rollout, return a finding to `land-and-deploy`, the owner of that record, rather than amending it here. |
| Publication is requested, or assumed, with no named owner approving the exact draft | Hold the draft, name the missing approver, and publish nothing; the absence of an objection is not an approval. |
| An approval exists but names an earlier draft revision than the one about to go out | Treat it as no approval for this draft and hold publication. Name the approved revision, the current one, and what changed between them, then request a fresh approval of the exact current revision. Approval attaches to a revision precisely because the change made after it is the one nobody signed off, and a one-word edit to a customer-facing note is exactly the kind of change that slips through on an inherited approval. |
| The draft carries internal hostnames, internal URLs with query parameters, credentials, customer identifiers, or embargoed security detail | Redact before the draft leaves internal circulation, preserve the fact in the internal follow-up record, and name the embargo owner when the detail is a security fix still under embargo. A credential found in a draft is treated as exposed: report it for rotation rather than only deleting it, because the draft has already been stored, synced, and possibly shared. |
| A screenshot or attachment is supplied for the external draft | Redact the image itself before it circulates: check window chrome, the address bar and its query string, account names, notification toasts, adjacent tabs, and terminal scrollback, then crop or re-capture against seeded demo data. Never blur or box over text — those are reversible or cosmetic depending on the format, and a reversible redaction reads as a completed one. |
| The release record, rollout result, or shipped revision is missing, empty, or contradicts the change summary | Refuse to write the narrative and name the gap. Documentation is the one artifact that outlives the release, so a plausible reconstruction of an unknown rollout becomes the record everyone trusts later; return the specific missing fact to the owner who holds it instead. |
| A verification result, screenshot, or environment the draft depends on cannot be reached | Mark the claim unverified in the draft rather than softening it into a statement, list it in the documentation gap list, and keep the draft honest about which parts rest on evidence and which do not. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Never write `_phase-state.md`. No class in the save-ownership policy declares that path, so it is not an orchestrator-owned file either — phase state is published only through `save_run.py checkpoint`, which keeps revision lineage and the audit trail coherent.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed release-documentation sequence and decision rules.
- `references/redaction.md` for the per-category redaction checklist, the screenshot and attachment procedure, the redaction-log shape, and the credential-exposure path.
- `references/examples.md` for concrete release-note and follow-up outputs.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/redaction.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
