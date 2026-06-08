---
name: open-browser
description: >-
  Launches a visible browser workspace for guided interaction, debugging, and
  collaborative automation on live product surfaces. Reuses an already-available
  browser (installed system browser or cached Playwright browser) before installing
  one; attaching to a running browser over CDP is opt-in only. Use when the user
  asks to open the browser workspace, launch a visible browser, inspect the page
  live, or prepare a live session for reuse — even when they only say "pop open a
  browser so I can see it". Defers page interactions to `browser-automation/browse`,
  authenticated state to `browser-automation/setup-browser-cookies`, and session
  sharing to `browser-automation/pair-agent`.
version: 1.0.0
---

# Open Browser

## Purpose

Launch a visible browser workspace for guided interaction, debugging, and collaborative automation on live product surfaces.

## Use This Skill When

- open the browser workspace
- launch a visible browser
- inspect the page live
- work in the browser directly

## Inputs

- Target page, workspace, or environment plus current project context.
- Existing session information, browser profile constraints, or remote-host details.
- Constraints such as protected environments, display requirements, or evidence expectations.

## Outputs

- Visible browser session record with target URL, host/browser choice, profile boundary, and connection details needed by follow-on automation.
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

- **Browser acquisition (reuse before install)**: Analyze the environment and reuse an already-available browser — an installed system browser or a cached Playwright browser — before installing one. Attaching to the user's running browser over CDP (rung 1) is opt-in and requires explicit confirmation; never auto-attach to the user's real browser. Install the Playwright browser only as the last resort, and escalate the install (do not force it) in offline, locked, or frozen environments. Record the acquisition rung used. See `references/workflow.md` for the concrete probes.
- **Session tokens**: Use scoped time-bounded session credentials for remote browser or host interactions.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- `browser-automation/browse`
- `browser-automation/pair-agent`

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
| The browser opens successfully but immediate console, certificate, or CSP failures block the rendered surface | Return the session as blocked with the exact diagnostics rather than claiming the visible workspace is ready. |
| All acquisition rungs fail and the Playwright browser cannot be installed (offline, locked, or frozen environment, or no network) | Preserve the per-rung probe evidence, do not fake a session, and escalate to a host with an available browser or a permitted install path instead of forcing a download. |
| A running browser is detected but the user has not opted in to reusing it | Do not probe for or attach to it. Skip rung 1, acquire via an installed or cached browser (rung 2/3), and only attach to the running browser after explicit confirmation. |
| The user opted in to reusing their running browser over CDP, but its live profile or auth is wrong for a task that required a clean, isolated session | Treat it as a context mismatch: stop, record it, and re-acquire a fresh named profile via rung 2 or 3 before continuing. |
| An installed browser is detected but its version or channel is incompatible with the automation, so it launches but cannot be driven | Record the incompatible binary, fall through to the next acquisition rung (cached or installed Playwright browser), and note why the system browser was rejected. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Do not create or manage `_phase-state.md` — that is the delegating orchestrator's responsibility.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed browser-launch sequence, the Browser Acquisition Ladder with concrete cross-platform probe commands, and decision rules.
- `references/examples.md` for concrete visible-session launch outputs, including acquisition-by-reuse and install-fallback cases.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
