# Example Invocations

## Example 1 — draft held, redaction logged

**User request:** document the release

**Output:**
- Shipped summary: reconciled against the release record at `rev-8f21c0a` — new billing summary view, retry-safe invoice export, and one fixed permission bug are live in production.
- Known issue: CSV export still fails for accounts with archived line items and is owned by the payments team.
- Redaction log: three rows — the reporting customer's account id (customer identity), the internal invoice-worker hostname (hosts), and the dashboard link whose query string carried a tenant id (internal URLs). Each fact is preserved in the internal follow-up record rather than deleted.
- Next move: the user-facing release note and the support brief stay DRAFT pending the release owner's approval of this exact revision and of the channels; nothing is published from here.

## Example 2 — approval names an earlier draft revision

**User request:** the release owner approved this yesterday, send it out

**Output:**
- Hold: the approval on file names draft revision 2; the current draft is revision 4. It is treated as no approval for this draft, and publication does not proceed.
- What changed between them: the known-issues section gained the archived-line-items defect, and the upgrade note now names a migration step. Both are exactly the kind of change a customer acts on, which is why approval attaches to a revision rather than to a document.
- Request: a fresh approval naming revision 4 and the channels it may go to, from the same named owner.
- Meanwhile: the draft stays marked DRAFT and the redaction log stays attached to it.

## Example 3 — a screenshot carries more than its subject

**User request:** update the launch notes, and use the screenshot from the staging walkthrough

**Output:**
- Rollout note: the feature is live in staging and half of production, so the launch notes explicitly call out the phased release state rather than implying general availability.
- Screenshot finding: the supplied image shows the internal staging host and a tenant id in the address bar, the signed-in support account in the profile menu, and a notification toast naming another customer.
- Action: re-captured against seeded demo data in a clean browser profile rather than blurred, because blur is reversible on text and an overlaid box leaves the original image underneath. Logged as one redaction row with the original kept internally.
- Operator follow-up: support must watch one alert tied to the new queue processor for the first 24 hours; the alert's internal identifier stays in the internal record and the external note describes it functionally.

## Example 4 — incomplete rollout facts, and a credential in the source material

**User request:** write the release follow-up

**Output:**
- Post-release record: deployment succeeded, one migration ran longer than expected, and rollback was not required.
- Evidence gap: the production smoke result for the export path could not be reached, so the draft marks that claim unverified and lists it in the documentation gap list instead of softening it into a statement.
- Credential exposure: the pasted deploy log carried a webhook secret. It is removed from the draft and reported to the secret's owner for rotation as a finding in its own right, because the draft had already been saved and shared by the time it was noticed.
- Approval boundary: both drafts are redacted of the migration's internal host and job names and wait on the named release owner's approval of this exact revision before anything is sent or published.
- Owner map: each follow-up item is assigned so the release trail does not end at ship time.

## Example 5 — an embargoed security fix, from source material to held draft

The embargo category end to end: what the release actually contained, what the
external draft is allowed to say, where the rest went, and who can lift it.

**User request:** write up what we just released

**Output:**
- Shipped summary: reconciled against the release record at `rev-5b02e9f` — a session-handling fix, two performance improvements to the search index, and a copy correction are live in production.
- **Embargo held.** The session-handling fix is the patch for CVE-2026-31844, reported by an external researcher under a coordinated-disclosure window that closes in 19 days. Every one of the four embargoed facts is withheld from the external draft: the CVE identifier, the affected version range (`4.2.0` through `4.7.3`), the exploit condition (a session token remaining valid across a privilege downgrade), and the mitigation timing. The timing is the one most easily overlooked and the most useful to an attacker — saying "patched in 4.7.4" tells anyone reading exactly which deployed versions are still vulnerable and for how long they have been.
- What the external draft says instead: "This release includes a security fix. We recommend updating." That is publishable under embargo, because it advises the action without describing the weakness. It carries no version range, no CVE, and no "fixed in" note.
- Where the detail went: the internal follow-up record carries all four facts, the researcher's report reference, and the coordinated-disclosure date. Nothing was deleted — the redaction log's embargo row points to that record, so the person preparing the post-embargo update is not re-deriving it from commit history.
- **Embargo owner named in the draft**: `security-lead` owns the window and is the only person who can release these facts. The draft says so explicitly, so a reader who wants the detail knows who to ask rather than inferring that nobody knows. That owner is distinct from the release owner who approves publication of this draft; the two approvals answer different questions and neither substitutes for the other.
- Redaction log: four rows in the embargo category, plus one internal URL (the advisory tracker link, whose query string carried the report id) — the external draft carries nothing in its place, and the description and original URL live in the internal record.
- Next move: the release note stays DRAFT pending the release owner's approval of this exact revision. Separately, a post-embargo revision is queued against the disclosure date, at which point `security-lead` releases the four facts and this draft is revised — a changed draft, so it needs its own fresh approval before it goes anywhere.
