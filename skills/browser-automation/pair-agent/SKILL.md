---
name: pair-agent
description: >-
  Pairs a remote collaborator to a browser session using short-lived setup access
  and scoped session credentials. Use when the user asks to pair another agent to
  the browser, set up remote browser access, share a browser session safely, issue
  pairing access, or hand a live browser to another operator without exposing a
  broader environment than necessary — even when they only say "let my teammate
  drive this browser". Shares an existing session; defers launching the workspace
  to `browser-automation/open-browser`, loading authenticated state to
  `browser-automation/setup-browser-cookies`, and driving the page to
  `browser-automation/browse`.
version: 1.0.0
---

# Pair Agent

## Purpose

Pair a remote collaborator to a browser session using short-lived setup access and scoped session credentials.

## Use This Skill When

Use this skill to **hand a live browser session to another operator** with least-privilege, scoped access:

- "pair another agent to the browser" / "issue pairing access" — grant short-lived, scoped session credentials
- "set up remote browser access" — connect a remote collaborator to the session safely
- "share a browser session safely" — avoid exposing a broader environment than necessary

Route elsewhere to launch the session first (`browser-automation/open-browser`), load authenticated state (`browser-automation/setup-browser-cookies`), or drive the page yourself (`browser-automation/browse`).

## Inputs

- Active browser session details, intended collaborator, and current project context.
- Pairing scope, expiry rules, and any environment or account restrictions.
- Known constraints such as protected environments, one-time access rules, or audit requirements.

## Outputs

- Pairing access record with session id, collaborator scope, expiry, permissions, and revocation path.
- Issuance evidence showing which browser session was shared and what access boundary was exposed.
- Handoff note for the paired agent covering allowed targets, prohibited actions, and blocked setup reasons.

## Workflow

1. Verify the active browser session, intended collaborator, and allowed browser surface before sharing any bootstrap material. When no session exists yet, route to `browser-automation/open-browser`, which acquires the browser via its Browser Acquisition ladder (reuse an installed or cached browser before installing the Playwright browser; attaching to the user's running browser is opt-in).
2. Issue a **scoped, time-limited pairing credential** — for example a one-time CDP/session handle, a scoped WebSocket token, or a single-use access token bound to the specific session ID and expiring after the handoff window. Deliver it **out-of-band** (not pasted into shared chat, logs, or screenshots) — use a direct secure channel. This prevents credential leakage through conversation history, shared screen recordings, or log aggregation.
3. Confirm the collaborator can reach the intended browser surface without inheriting broader host or tenant access than approved.
4. Revoke the pairing credential on handoff completion or expiry; do not leave open tokens after the collaboration window closes.
5. Return a pairing record with issued access scope, expiry, revocation path, and the next recommended browser handoff.

## Required Contracts

- **Setup keys (one-time)**: Use short-lived one-time pairing keys for remote session bootstrap before issuing longer-lived tokens.
- **Session tokens**: Use scoped time-bounded session credentials for remote browser or host interactions.
- **Credential delivery (out-of-band)**: Deliver scoped pairing credentials out-of-band over a direct secure channel — never in shared chat, logs, or screenshots — as detailed in Workflow step 2.
- **Revocation on completion**: Revoke the pairing credential at handoff completion or expiry (Workflow step 4); leave no open tokens after the collaboration window closes.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- `browser-automation/open-browser`
- `browser-automation/setup-browser-cookies`

## Review Expectations

- Verify the collaborator receives only the intended browser surface, lifetime, and permissions before sharing credentials.
- Record revocation and audit details so access can be closed or explained after the pairing window.
- Block or narrow sharing when the active session contains protected accounts outside the requested scope.

## Skip Rule

Skip only when the requested surface, tool, or environment does not exist and a safe fallback is unavailable.

## Failure Modes

| Scenario | Response |
| --- | --- |
| No active browser session exists or the target session no longer matches the requested environment | Refuse to pair against an ambiguous session, record the missing or stale session state, and route back to browser launch first. |
| A one-time setup key expires, is reused, or is sent to the wrong collaborator | Revoke the attempt, record the invalid bootstrap event, and issue fresh pairing material only after the target identity is reconfirmed. |
| The collaborator attaches successfully but lands with broader tenant, account, or host access than the request allows | Treat the pairing as unsafe, revoke access, and reopen the session with narrower scope before another handoff. |
| The browser can be paired only by exposing long-lived secrets or persistent host access | Escalate instead of converting a short-lived pairing task into durable credential sprawl. |
| A pairing credential is leaked, compromised, or sent to the wrong recipient | Immediately revoke the credential and any session it could have accessed, record the event, and re-issue fresh pairing material only after the target identity is reconfirmed. |
| The collaborator cannot connect due to firewall rules, network restrictions, or an unreachable host | Record the connectivity failure (blocked port, refused connection, DNS failure), do not retry with broader access, and ask the user whether a different delivery path or network setup is available. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Do not create or manage `_phase-state.md` — that is the delegating orchestrator's responsibility.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed browser-pairing sequence and decision rules.
- `references/examples.md` for concrete pairing and revocation outputs.
- `browser-automation/open-browser` for the Browser Acquisition ladder (reuse an existing browser before installing the Playwright browser) when the session to pair must first be launched.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
