---
name: pair-agent
description: >-
  Pairs a remote collaborator to a browser session with a least-exposing scoped
  credential, delivered out-of-band and revoked on completion; a whole-browser CDP
  handle runs only against a dedicated isolated-profile browser. Use when the user asks
  to pair another agent, share a browser session safely, issue pairing access, set up
  remote browser access, or hand a live browser to another operator — even when they
  only say "let my teammate drive this browser". Shares an existing session only,
  not launch, auth, or page-driving.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---

# Pair Agent

## Purpose

Handing a browser to someone else is a scope decision disguised as a connection detail. The credential form is the blast radius: a CDP endpoint cannot be narrowed to one session or one origin — it is the whole browser, every tab, every origin's cookies and storage — while a scoped or single-use token authorizes one session and nothing more. So the form is chosen by exposure before anything is minted, a CDP handle is issued only against a browser launched for this pairing with an empty profile, the value travels out-of-band and never into the pairing record, and the window is closed by that form's own teardown rather than by an expiry, which closes nothing.

## Use This Skill When

Use this skill to **hand a live browser session to another operator** with least-privilege, scoped access:

- "pair another agent to the browser" / "issue pairing access" — grant short-lived, scoped session credentials
- "set up remote browser access" — connect a remote collaborator to the session safely
- "share a browser session safely" — avoid exposing a broader environment than necessary

Route elsewhere to launch the session first (`open-browser`), load authenticated state (`setup-browser-cookies`), or drive the page yourself (`browse`).

## Inputs

- Active browser session details, intended collaborator, and current project context.
- Pairing scope, expiry rules, and any environment or account restrictions.
- Known constraints such as protected environments, one-time access rules, or audit requirements.

## Outputs

- Pairing access record with session id, collaborator scope, credential form, expiry, permissions, and the concrete revocation path — never the credential value itself.
- Issuance evidence showing which browser session was shared, what access boundary was exposed, and (for a CDP handle) that the browser was a dedicated isolated-profile instance.
- Handoff note for the paired agent covering allowed targets, prohibited actions, and blocked setup reasons.

## Workflow

1. Verify the active browser session, intended collaborator, and allowed browser surface before sharing any bootstrap material. When no session exists yet, route to `open-browser`, which acquires the browser via its Browser Acquisition ladder (reuse an installed or cached browser before installing the Playwright browser; attaching to the user's running browser is opt-in).
2. **Choose the credential form by how much of the browser it exposes**, then mint it by that form's concrete procedure (the selection rule is in § Credential Forms below, the procedure in `references/workflow.md` § Credential Forms). A CDP endpoint is not scoped per session — it controls the whole browser, every origin's cookies and storage included — so it is only ever issued against a **dedicated, isolated-profile browser launched for this pairing**, never against a browser that also holds the user's own state. A scoped WebSocket or single-use access token is preferred whenever the collaborator needs one session rather than the whole browser.
3. Deliver the credential **out-of-band** — a direct secure channel, never pasted into shared chat, logs, screenshots, or the pairing record — so it cannot leak through conversation history, screen recordings, or log aggregation. The record names the credential and its revocation path; it never carries the value.
4. Confirm the collaborator can reach the intended browser surface without inheriting broader host or tenant access than approved.
5. **Revoke by the form's concrete teardown** (`references/workflow.md` § Credential Forms) at handoff completion or expiry; leave no open endpoint, token, or running isolated-profile browser after the window closes.
6. Return a pairing record with issued access scope, credential form, expiry, revocation path, and the next recommended browser handoff.

## Credential Forms

Three forms are available, and the choice is made by exposure before anything is minted: take
the narrowest form that still lets the collaborator do the work. How each one is issued and how
it is torn down is in `references/workflow.md` § Credential Forms.

| Form | What it exposes | Choose it when |
| --- | --- | --- |
| Single-use access token | One bootstrap connection, consumed on first use | The collaborator attaches once and the issuer can mint single-use material |
| Scoped WebSocket / session token | One browser context or session id, and nothing else | The collaborator needs one session for the handoff window — the preferred form |
| CDP / session handle | The whole browser: every tab, and every origin's cookies and storage in the profile — and it is **not** single-use: the `webSocketDebuggerUrl` stays re-readable from `/json/version` for as long as the port is reachable | Nothing narrower can do the work — and then only against a browser launched for this pairing with an empty, isolated profile |

A CDP endpoint cannot be narrowed after the fact, and there is no per-session revoke short of
ending the process. That is why it is never issued against the user's own browser or any profile
holding authenticated state outside the pairing's scope, and why its debug port stays on loopback
behind an identity-bound tunnel rather than bound to a broad interface.

"Revoke on completion" means running that form's teardown, not letting an expiry lapse — an
unrevoked endpoint or token is live until it is actually closed.

## Required Contracts

- **Credential form fits the exposure**: Pick the least-exposing form that still works (single-use or scoped token over a whole-browser CDP handle), and mint it by that form's procedure in `references/workflow.md` § Credential Forms.
- **CDP requires an isolated-profile browser**: A CDP endpoint controls the whole browser and every origin's cookies and storage, so it is issued only against a dedicated browser launched for the pairing with an empty profile — never the user's own browser (Workflow step 2, § Credential Forms).
- **One-time credentials over standing ones**: Where the form supports it, issue a credential that is consumed on first use, and prefer that form over one that stands until teardown. **A CDP handle is not that form.** Its `webSocketDebuggerUrl` is read from `/json/version`, and that whole HTTP endpoint stays reachable for as long as the port is — `/json/list` keeps leaking every open target's full URL as the collaborator navigates — so the URL can be re-read and re-used by anyone who reaches the port. Treat it as a standing credential whose only revocation is teardown: ending the browser process and deleting the isolated profile (`references/workflow.md` § Credential Forms). That is precisely why the CDP form is last on the ladder, why its port stays on loopback behind an identity-bound tunnel, and why it is never pointed at a profile holding state outside the pairing.
- **Session tokens are scoped and time-bounded**: Where a one-time form does not fit, the credential carries an explicit scope and an expiry sized to the pairing window, and is revoked at completion rather than left to lapse.
- **Credential delivery (out-of-band)**: Deliver scoped pairing credentials out-of-band over a direct secure channel — never in shared chat, logs, screenshots, or the pairing record — as detailed in Workflow step 3.
- **Revocation on completion**: Revoke the pairing credential by its form's teardown at handoff completion or expiry (Workflow step 5; the teardown per form is in `references/workflow.md` § Credential Forms); leave no open endpoint, token, or isolated-profile browser after the window closes.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../execution-contract.md` defines, so upstream and downstream packages read risk identically.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- `open-browser`
- `setup-browser-cookies`

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
| The only way to pair is a CDP endpoint on the browser that already holds the user's own authenticated state | Refuse to expose that browser. A CDP handle is whole-browser control across every origin's cookies and storage, so launch a dedicated isolated-profile browser for the pairing (§ Credential Forms) and pair against that, or fall back to a scoped token if the collaborator needs only one session. |
| A CDP debug port would have to be bound to a broad interface (`0.0.0.0`) for the collaborator to reach it | Do not widen the bind. Keep the port on loopback and reach it through an identity-bound tunnel or SSH port-forward; a network-exposed debug port is unauthenticated whole-browser control for anyone who can route to it. |
| The handoff window closed but the isolated-profile browser or its debug endpoint is still running | Treat the pairing as not revoked. Terminate the browser process and delete its temporary profile directory; an expiry that lapsed does not close a CDP endpoint — ending the process does. |
| A pairing credential is leaked, compromised, or sent to the wrong recipient | Immediately revoke the credential and any session it could have accessed, record the event, and re-issue fresh pairing material only after the target identity is reconfirmed. |
| The collaborator cannot connect due to firewall rules, network restrictions, or an unreachable host | Record the connectivity failure (blocked port, refused connection, DNS failure), do not retry with broader access, and ask the user whether a different delivery path or network setup is available. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Never write `_phase-state.md`. No class in the save-ownership policy declares that path, so it is not an orchestrator-owned file either — phase state is published only through `save_run.py checkpoint`, which keeps revision lineage and the audit trail coherent.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed browser-pairing sequence, the per-form issue-and-revoke procedures, and decision rules.
- `references/examples.md` for concrete pairing outputs, including out-of-band delivery, an actual CDP teardown, and the isolated-profile requirement in practice.
- `open-browser` for the Browser Acquisition ladder (reuse an existing browser before installing the Playwright browser) when the session to pair must first be launched.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
