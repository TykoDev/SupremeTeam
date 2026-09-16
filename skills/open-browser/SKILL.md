---
name: open-browser
description: >-
  Launches a visible browser workspace for guided interaction and debugging on live
  surfaces, reusing an available browser before installing one and handling the
  session credential by reference. Use when the user asks to open the browser
  workspace, launch a visible browser, inspect the page live, work in the browser
  directly, or prepare a session for reuse — even when they only say "pop open a
  browser so I can see it". CDP attachment is opt-in. Launches the session only,
  not page-driving, auth import, or operator pairing.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---

# Open Browser

## Purpose

A launch settles two things that cannot be taken back once the session exists: which browser it attached to, and where the session credential ended up. Attaching to the browser already running hands automation the user's live profile and every origin it is signed into, so that rung is opt-in and never the automatic default; acquisition starts at an installed browser with a clean profile, falls back to a cached one, and installs only as a last resort — with the rung used written into the session record, because nobody can tell afterwards which browser a session came from. The connection credential is handled by reference from the moment it exists — scoped, time-bounded, named rather than reproduced — since a token echoed into a record or caught in a screenshot stays live as long as the session does, and no later cleanup unpublishes it. This skill owns browser acquisition for the whole `browser-automation` set; the other three route here rather than installing browsers themselves.

## Use This Skill When

Use this skill to **put a controllable browser on screen** at a known target, with the acquisition route recorded:

- "open the browser workspace" / "launch a visible browser" — start a session someone can watch and another skill can reuse
- "inspect the page live" — get a real rendered surface rather than a fetched response
- "work in the browser directly" — establish the session before any interaction happens
- "pop open a browser so I can see it" — the same request phrased casually

Route elsewhere to drive the page once it is open (`browse`), load authenticated state into the profile (`setup-browser-cookies`), or hand the session to another operator (`pair-agent`).

## Inputs

- Target page, workspace, or environment plus current project context.
- Existing session information, browser profile constraints, or remote-host details.
- Constraints such as protected environments, display requirements, or evidence expectations.

## Outputs

- Visible browser session record with target URL, host/browser choice, profile boundary, acquisition rung, and the connection details follow-on automation needs — credentials named and located, never reproduced (see Session Credential Handling).
- Launch evidence showing the page loaded, the session is controllable, and any existing auth/profile state was intentionally reused or isolated.
- Fallback or escalation record when browser acquisition, display, or remote control cannot be established.

## Workflow

1. Confirm the requested target surface, browser host, display mode, and session boundary before launching or reusing a visible browser.
2. Analyze the environment for an already-available browser and resolve acquisition through the Browser Acquisition ladder (see below): by default start with an installed system browser (channel or executable path), then a cached Playwright browser, and only install the Playwright browser as the last resort. Attaching to the user's running browser over CDP (rung 1) is opt-in — never auto-attach without explicit confirmation. Record which rung satisfied acquisition.
3. Open the browser resolved in the previous step with the correct profile, target page, and scoped credentials so the rendered surface matches the intended environment.
4. Verify that the live session is actually usable by checking visible page identity, URL, auth state, and any immediate console or network blockers.
5. Return a visible browser session record with the acquisition rung used, launch method, active session state, takeover notes, and the next browser task to run.

## Browser Acquisition

`open-browser` owns browser acquisition for the whole `browser-automation` set. Reuse an already-available browser before downloading one; default acquisition starts at rung 2.

- **Rung 1 — Running browser over CDP (opt-in only).** Never probe or attach without explicit user confirmation; sharing the live profile and auth is never the automatic default.
- **Rung 2 — Installed system browser.** Launch via Playwright `channel` or a detected executable path. Prefer a clean, named profile for isolation.
- **Rung 3 — Cached Playwright browser.** Use a previously downloaded browser from the local cache — no network call needed.
- **Rung 4 — Install Playwright browser (last resort).** Only when rungs 1–3 all fail. Announce the install; escalate instead of forcing it in offline, locked, or frozen environments.

Record the rung used (`reused-cdp`, `system-channel`, `cached-playwright`, or `installed`) in the session record. Full cross-platform probe commands: see `references/workflow.md`.

## Required Contracts

- **Browser acquisition (reuse before install)**: Walk the ladder in §Browser Acquisition above and record the rung used; concrete probes in `references/workflow.md`.
- **Session credentials (scoped, time-bounded, never echoed)**: Handling rules below — the scope, the storage rule, and the prohibition on reproducing a token anywhere the session record can be read.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../execution-contract.md` defines, so upstream and downstream packages read risk identically.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Session Credential Handling

Launching a remote or hosted browser needs a credential — a CDP endpoint URL, a WebSocket token, a grid or host access token — and the session record this skill produces is exactly the artifact a later reader will search for it in. "Scoped and time-bounded" is not a property a credential has on its own; it is three decisions made at issue time and one rule about where the value may appear.

**Scope** — the smallest surface that still lets the session work: one browser session or one profile, one target origin or host, one automation role. A credential that also reaches the wider tenant, the host shell, or other origins in the same profile is out of scope regardless of how briefly it lives, and the launch is narrowed rather than the scope widened.

**Lifetime** — bounded at issue time by the issuing system's own expiry, sized to the launch-and-verify window rather than to the working day. A credential with no expiry mechanism is treated as long-lived, which is an escalation, not a default (see the Failure Modes row on long-lived secrets).

**Storage** — held in the process environment or an untracked file outside the repository for the life of the session, never committed, and never written into the save path. A session record is a tracked deliverable; treat everything in it as readable by anyone who can read the repo.

**Never reproduce the value.** The session record, handoff notes, logs, console transcripts, and screenshots carry a *reference* — which credential, which system issued it, when it expires, how to revoke it — and never the secret itself. Before capturing a launch screenshot, confirm no address bar, DevTools panel, or terminal pane in frame contains a token-bearing URL; a CDP endpoint pasted into the address bar is a credential rendered as a picture. Redact any token that reaches an evidence artifact, and treat a leak into a saved artifact as a revoke-and-reissue event, not an editing problem.

Delivering a credential to another operator is not this skill's job. `pair-agent` owns issue, out-of-band delivery, and revocation for a paired session; route the handoff there rather than pasting connection details into shared output.

## Collaboration Surface

- `browse`
- `pair-agent`

## Review Expectations

- Confirm the browser is actually visible and controllable at the requested target rather than only reporting a launched process.
- Preserve profile isolation and opt-in rules when attaching to an existing user browser or protected account.
- Capture enough session coordinates for `browse`, `pair-agent`, or setup-cookie workflows to continue without rediscovery.

## Skip Rule

Skip only when the requested surface, tool, or environment does not exist and a safe fallback is unavailable.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The browser launches but lands in the wrong profile, environment, or account context | Stop at the landing state, record the mismatch, and avoid treating the session as reusable until the context is corrected. |
| A visible browser cannot open because the host lacks the required binary, display path, or remote session support | Preserve the launch failure evidence and escalate to a different browser host or tooling path instead of faking a live session. |
| Scoped session tokens or browser state expire before the live page becomes usable | Treat the launch as incomplete, refresh the session boundary, and re-verify from a clean landing page. |
| The only credential available for the remote browser or host has no expiry mechanism, or grants more than the target session | Do not launch against it as a matter of routine. Record the over-broad scope as a finding and escalate for a scoped alternative; a long-lived or host-wide credential is a deliberate, owner-approved exception, not a fallback. |
| A token-bearing URL or credential value has already reached the session record, a log, or a screenshot | Treat it as compromised. Have the issuing system revoke it and reissue, then redact the artifact — redaction alone does not undo the exposure, because the artifact may already have been read or synced. |
| Another operator asks for the connection details so they can drive the session | Do not paste them into shared output. Route the handoff to `pair-agent`, which issues a scoped credential, delivers it out-of-band, and owns the revocation. |
| The browser opens successfully but immediate console, certificate, or CSP failures block the rendered surface | Return the session as blocked with the exact diagnostics rather than claiming the visible workspace is ready. |
| All acquisition rungs fail and the Playwright browser cannot be installed (offline, locked, or frozen environment, or no network) | Preserve the per-rung probe evidence, do not fake a session, and escalate to a host with an available browser or a permitted install path instead of forcing a download. |
| A running browser is detected but the user has not opted in to reusing it | Do not probe for or attach to it. Skip rung 1, acquire via an installed or cached browser (rung 2/3), and only attach to the running browser after explicit confirmation. |
| The user opted in to reusing their running browser over CDP, but its live profile or auth is wrong for a task that required a clean, isolated session | Treat it as a context mismatch: stop, record it, and re-acquire a fresh named profile via rung 2 or 3 before continuing. |
| An installed browser is detected but its version or channel is incompatible with the automation, so it launches but cannot be driven | Record the incompatible binary, fall through to the next acquisition rung (cached or installed Playwright browser), and note why the system browser was rejected. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Never write `_phase-state.md`. No class in the save-ownership policy declares that path, so it is not an orchestrator-owned file either — phase state is published only through `save_run.py checkpoint`, which keeps revision lineage and the audit trail coherent.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed browser-launch sequence, the Browser Acquisition Ladder with concrete cross-platform probe commands, and decision rules.
- `references/examples.md` for concrete visible-session launch outputs, including acquisition-by-reuse and install-fallback cases.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
