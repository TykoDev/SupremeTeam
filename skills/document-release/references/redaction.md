# Redaction Reference

Read this before any draft leaves internal circulation. SKILL.md Workflow step 4 names the seven
categories; this file carries the checklist per category, the screenshot and attachment
procedure that a text pass cannot cover, the redaction-log shape, and what to do when a
credential turns up in a draft.

## Contents

1. The rule, and why it is applied before review rather than after
2. Category checklist — text
3. Category checklist — screenshots and attachments
4. The redaction log
5. Credentials found in a draft
6. Embargoed security detail

## 1. The Rule, and Why It Is Applied Before Review Rather Than After

Redact the draft before it circulates, not before it publishes. A draft shared for review has
already left the boundary: it sits in a document store, a chat thread, and several mailboxes,
and no later edit reaches those copies. Nothing is deleted in the process — every removed fact
moves into the internal follow-up record, which keeps the detail the external draft cannot, so
redaction costs the team nothing and the log makes it reviewable instead of invisible.

## 2. Category Checklist — Text

| Category | What to remove | Replace with |
| --- | --- | --- |
| Hosts and environments | Internal hostnames, environment names, internal IPs and ports, cluster and region names | The user-visible service name, or nothing |
| Internal identifiers | Service, queue, topic, job, cron, dashboard, and alert identifiers | A functional description: "the invoice export job" |
| Internal URLs | The whole URL, **including the query string** — a link to an internal tool leaks the host, the path structure, and frequently ids, filters, tokens, and account references inside its parameters | A description of where the information lives, for the internal record only |
| Credentials | API keys, bearer and refresh tokens, session ids, connection strings, webhook secrets, and signed URLs — a signed URL is a credential with an expiry, not a link | Removal plus rotation; see section 5 |
| People and tickets | Internal ticket ids, staff names, internal team handles and channel names | The owning team's public-facing name, or nothing |
| Customer identity | Customer identifiers, account names, tenant ids, and any value drawn from a customer's records — including the one whose bug report prompted the fix | A generic description of the affected condition |
| Embargoed security detail | See section 6 | A neutral statement that a security fix is included |

Two habits catch most of what a category pass misses. Read the draft as an outsider with no
internal context and mark every proper noun whose meaning depends on internal knowledge. And
check error messages, log excerpts, sample payloads, and code snippets specifically: they are
pasted in verbatim far more often than prose is, and they carry hosts, ids, and tokens inline.

## 3. Category Checklist — Screenshots and Attachments

Images are the highest-risk carrier because they are pasted in as illustrations rather than
reviewed as content, and every text pass runs straight past them. Check each image for:

- **Window chrome** — tab titles, the bookmark bar, the browser profile name and avatar, the
  extension row, the window title bar and its file path.
- **The address bar** — the internal host, the path structure, and the query string, which is
  where ids, tokens, filters, and impersonation parameters live.
- **Identity** — the signed-in account name, email, avatar, and any org or tenant switcher.
- **Surrounding surfaces** — notification toasts, adjacent panels, sidebars listing other
  customers, search history, autocomplete dropdowns, and recent-item lists.
- **Terminals** — scrollback above the region of interest, the prompt itself (user, host,
  working directory), and environment variables echoed earlier in the session.
- **Incidental context** — clock and timezone, calendar entries, and anything that places a
  person or a facility.

Then fix it one of two ways, never a third:

1. **Crop** to the region that carries the point, when the sensitive content is outside it.
2. **Re-capture** against seeded demo data in a clean profile, when it is inside the region.
   This is the default for anything showing customer data.

Do not blur, pixelate, or draw a box over the content. Blur and pixelation are reversible on
text, and a box drawn in a document format that keeps the original image underneath is not a
redaction at all — both produce a draft that reads as redacted and is not. The same rule governs
attachments: logs, exports, HAR files, and config samples are re-generated from a scrubbed
environment or left off the external draft entirely. Strip image metadata as well, since EXIF and
authoring fields carry device, account, and location detail the picture itself does not.

## 4. The Redaction Log

The log travels with the draft, so a reviewer can see what was withheld and why without hunting
for it. One row per removal:

| # | Location | Category | What was removed | Where the fact is preserved |
| --- | --- | --- | --- | --- |
| 1 | Notes, "Known issues" | Customer identity | The reporting customer's account id | Internal follow-up record, section 3 |
| 2 | Screenshot `export-flow.png` | Hosts, internal URLs | Address bar showing the internal host and a tenant id in the query string | Re-captured against demo data; original kept internally |
| 3 | Notes, "Fixed" | Embargo | CVE id and affected version range | Internal follow-up record; embargo owner `security-lead` |

A draft that circulates without its log is incomplete, because the absence of a log is
indistinguishable from an absence of anything to redact.

## 5. Credentials Found in a Draft

A credential in a draft is exposed, not merely present: by the time it is noticed, the draft has
been saved, synced, and often shared. Remove it, then report it for rotation to the owner of the
secret, naming where it appeared and roughly how long it sat there. Record the exposure as a
finding in its own right rather than folding it into the redaction log as a routine removal —
the log says what the external draft no longer carries, while rotation is work somebody else has
to do. Treat signed URLs, webhook secrets, and long-lived session ids the same way.

## 6. Embargoed Security Detail

Until the embargo owner releases it, an external draft carries no CVE identifier, no affected
version range, no exploit condition, and no mitigation timing — the timing alone tells an
attacker which releases are still vulnerable. A neutral statement that a security fix is
included is publishable; the detail behind it moves to the internal follow-up record with the
embargo owner named, so the person who can lift the embargo is identified in the draft rather
than searched for later.
