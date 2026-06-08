---
name: setup-browser-cookies
description: >-
  Imports or prepares authenticated browser session state so later browser work can
  operate on protected surfaces safely. Use when the user asks to set up the browser
  session, import cookies for browser work, prepare the authenticated browser, load
  the browser access state, or verify that a protected page can be reached with the
  intended account and tenant — even when they only say "log the browser into our
  app". Prepares authenticated state; defers launching the workspace to
  `browser-automation/open-browser`, driving the page to `browser-automation/browse`,
  and sharing the session to `browser-automation/pair-agent`.
version: 1.0.0
---

# Setup Browser Cookies

## Purpose

Import or prepare authenticated browser session state so later browser work can operate on protected surfaces safely.

## Use This Skill When

Use this skill to **prepare authenticated session state** so later browser work can reach protected surfaces:

- "set up the browser session" / "prepare the authenticated browser" — establish the logged-in state
- "import cookies for browser work" — load session cookies for the intended account and tenant
- "load the browser access state" — verify a protected page is reachable before automation runs

Route elsewhere to launch the workspace (`browser-automation/open-browser`), drive page interactions (`browser-automation/browse`), or share the session with another operator (`browser-automation/pair-agent`).

## Inputs

- Target domain or protected surface plus current project context.
- Cookie source, storage bundle, or session-token material and the intended account or tenant.
- Known constraints such as environment boundaries, expiry windows, and evidence requirements.

## Outputs

- Authenticated session bootstrap record naming target domain, account or tenant, profile location, cookie source, and expiry assumptions.
- Reachability evidence for the protected surface, including target URL, observed auth state, and redacted session-storage or cookie checks.
- Session handoff instructions covering safe reuse, refresh triggers, and blocked access reasons.

## Workflow

1. Confirm the target domain, intended account or tenant, cookie source, and whether the authenticated state belongs in a clean or reused browser profile.
2. Load the browser cookies or session state into the isolated profile using a concrete mechanism — for example Playwright's `context.addCookies()`, a HAR import, or a scoped-profile copy. Before importing: restrict file permissions on the cookie bundle (readable only by the process), never log or echo raw cookie values, redact them in any evidence, screenshots, or saved output, and delete the bundle file after a successful import. Acquire that browser through `browser-automation/open-browser`'s Browser Acquisition ladder — reuse an installed or cached browser before installing the Playwright browser (attaching to the user's running browser is opt-in) — and prefer a clean, named profile so imported state is not mixed with a reused live profile. Cookies are live credentials; a leaked bundle grants session access to the protected service.
3. Verify the authenticated landing state by checking redirects, visible account identity, tenant context, and whether the protected page is actually reachable.
4. Return a session bootstrap record with the loaded state boundary, verification result, expiry caveats, and the next browser task that can safely reuse the session.

## Required Contracts

- **Session tokens**: Use scoped time-bounded session credentials for remote browser or host interactions.
- **Cookie bundle security**: Treat the cookie bundle as a live credential — restrict it, never log raw values, and delete it after import — with the full handling in Workflow step 2.
- **Loading mechanism**: Use a concrete, auditable import method (named in Workflow step 2) — never undocumented or ambient state injection.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- `browser-automation/browse`
- `browser-automation/open-browser`
- `browser-automation/pair-agent`

## Review Expectations

- Prove the session belongs to the intended domain and account before using it on protected workflows.
- Redact or avoid exposing credential material while still recording enough evidence to debug auth failures.
- Mark expiry, tenant mismatch, or MFA blockers explicitly so later browser automation does not mistake auth drift for product failure.

## Skip Rule

Skip only when the requested surface, tool, or environment does not exist and a safe fallback is unavailable.

## Failure Modes

| Scenario | Response |
| --- | --- |
| Imported cookies load successfully but the browser still redirects back to login | Treat the auth setup as unverified, capture the redirect chain, and check for missing companion state such as local storage, CSRF tokens, or wrong environment cookies. |
| The authenticated surface opens under the wrong account, tenant, or role | Stop immediately, record the mismatched identity, and do not let later browser tasks reuse that session state. |
| The cookie bundle belongs to a different domain, environment, or subdomain than the requested protected surface | Reject the import as out of scope for the target page and require the correct state source before proceeding. |
| Session state is technically valid but expires too quickly to support the next browser task | Record the narrow expiry window and refresh or replace the state before handing it to browsing or pairing work. |
| The protected page requires an MFA challenge even after cookies are imported | Treat the session as requiring an interactive authentication step; pause, surface the MFA requirement explicitly, and do not attempt to proceed past the challenge automatically. |
| The session appears authenticated but expires within seconds or minutes of import | Record the short-lived state, do not pass it to downstream tasks as stable, and prompt the user to refresh or re-export the session bundle before continuing. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Do not create or manage `_phase-state.md` — that is the delegating orchestrator's responsibility.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed authenticated-session setup sequence and decision rules.
- `references/examples.md` for concrete cookie-import and verification outputs.
- `browser-automation/open-browser` for the Browser Acquisition ladder (reuse an existing browser before installing the Playwright browser) that launches the profile receiving the authenticated state.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
