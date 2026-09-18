# Workflow Reference

## Contents

1. Pairing sequence
2. Credential forms — issue and revoke, per form
3. Decision rules
4. Acceptance checklist
5. Contract notes
6. Collaboration notes

## Pairing Sequence

1. Confirm the active browser session, target collaborator, approved environment, and maximum allowed access before issuing anything.
2. Choose the credential form by how much of the browser it exposes (§ Credential Forms), preferring a scoped or single-use token over a whole-browser CDP handle, and mint it by that form's procedure.
3. Deliver the credential **out-of-band** — a direct secure channel only, never shared chat, logs, screenshots, or the pairing record — so it cannot leak through conversation history, screen recordings, or log aggregation.
4. Verify the collaborator's landing state and record the concrete revocation instructions alongside the pairing result.
5. Revoke by the form's teardown on handoff completion or expiry; do not leave an open endpoint, token, or isolated-profile browser after the window closes.

## Credential Forms

Issue-and-revoke procedure per form. Which form fits which exposure is decided in
`../SKILL.md` § Credential Forms; this section is what to run once that choice is made.

### CDP / session handle (standing until teardown)

**Issue.** Launch a dedicated browser with an isolated profile and a debug port bound to
loopback:

```bash
USER_DATA_DIR="$(mktemp -d)"
chrome --user-data-dir="$USER_DATA_DIR" --remote-debugging-port=9222 --remote-debugging-address=127.0.0.1 about:blank &
BROWSER_PID=$!
```

```powershell
$UserDataDir = Join-Path $env:TEMP ([guid]::NewGuid().Guid)
New-Item -ItemType Directory -Path $UserDataDir | Out-Null
$Browser = Start-Process chrome -PassThru -ArgumentList "--user-data-dir=$UserDataDir", "--remote-debugging-port=9222", "--remote-debugging-address=127.0.0.1", "about:blank"
$BrowserPid = $Browser.Id
```

**Capture both the profile path and the process id here, and keep them for the
teardown below — they are the only two handles that can revoke this pairing.**
`--user-data-dir="$(mktemp -d)"` discards the path the moment the browser starts, and
the revoke step then has nothing to delete: `rm -rf "$USER_DATA_DIR"` on an unset
variable expands to `rm -rf ""`, which **exits 0**. The teardown reports success while
the profile — holding this pairing's cookies and storage — survives on disk. Losing the
path is losing the ability to revoke.

Read the `webSocketDebuggerUrl` from `http://127.0.0.1:9222/json/version` and hand
**that** to the collaborator, over an SSH-forwarded port or a tunnel bound to their identity — not
a broad network-exposed port. Never bind the debug port to `0.0.0.0`.

This handle is **not single-use**, and nothing about reading it consumes it. `/json/version`
answers again on every request, so the same URL can be re-read and re-connected by anyone who
reaches the port, for as long as the process lives. The tunnel is what limits *who* reaches it;
teardown is what ends it. Do not describe a CDP handle as one-time or as consumed on first
use — that is the single-use access token below, a different form with a different revocation.

**The whole HTTP endpoint is reachable, not just `/json/version`.** Anyone who can
reach the forwarded port can also read:

- `/json/list` (and `/json`) — every open target's **full URL, including query parameters**, plus its title and its own debugger URL. Session ids, one-time tokens, and reset links routinely live in query strings, so this list leaks them for as long as the port is reachable, and it keeps leaking as the collaborator navigates.
- `/json/new` and `/json/close` — open and close targets, so the endpoint is not read-only even before the WebSocket is used.
- `/json/protocol` and `/json/version` — the browser build and protocol surface.

Two consequences. The tunnel must be bound to the collaborator's identity alone —
this is the whole reason a broad port is refused, not merely a hardening
preference — and the isolated profile matters for what is *visible* here as much
as for what is attackable: a dedicated empty-profile browser means `/json/list`
shows only the pairing's own targets, while the user's own browser would expose
every tab they have open. The leak lasts until teardown, so the revoke below is
what ends it.

**Revoke.** Terminate the browser process — closing the endpoint is closing the browser — and
delete the temporary profile directory:

```bash
kill "$BROWSER_PID"
rm -rf "${USER_DATA_DIR:?profile path was not captured at issue time - find and delete it by hand}"
test -d "$USER_DATA_DIR" && echo "TEARDOWN FAILED: profile still present" || echo "profile deleted"
```

```powershell
Stop-Process -Id $BrowserPid
Remove-Item -Recurse -Force $UserDataDir
if (Test-Path $UserDataDir) { Write-Error "TEARDOWN FAILED: profile still present" }
```

Both forms use the `$USER_DATA_DIR` / `$UserDataDir` assigned at issue time. The
`${VAR:?...}` guard makes an unset path fail loudly instead of deleting nothing and
returning 0, and the trailing check confirms the directory is actually gone — a
revoke that was not verified is not a revoke.

There is no per-session revoke short of ending the process, which is the other reason a CDP
handle never runs against a shared profile.

### Scoped WebSocket / session token

**Issue.** Request the token from the issuing service — or the thin broker in front of the
browser — bound to the specific session id, with an expiry sized to the handoff window.
Record the token id and the expiry in the pairing record; deliver the value out-of-band.

**Revoke.** Call the issuer's revoke/invalidate endpoint for that token id at completion, then
confirm a subsequent connect attempt is refused. Expiry is the backstop; revocation is the act.

### Single-use access token

**Issue.** Mint it single-use against the session id and deliver it out-of-band; it authorizes
one bootstrap connection and is consumed on first use.

**Revoke.** It self-invalidates on use — still confirm it cannot be redeemed a second time. If
the collaborator never connected before the window closed, revoke it explicitly at the issuer
rather than leaving an unredeemed token alive.

## Decision Rules

- Pair to a known live session, not to a guessed hostname or remembered browser state.
- Prefer the narrowest possible scope for both bootstrap and ongoing access; prefer a scoped or single-use token to a CDP handle.
- Never issue a CDP endpoint against a browser holding the user's own state, and never bind a debug port to a broad interface — isolated profile, loopback, identity-bound tunnel.
- Deliver credentials out-of-band only — never in shared chat, logs, screenshots, or the pairing record.
- Revoke by the form's teardown as soon as the handoff is complete or the expiry passes; a lapsed expiry does not close a CDP endpoint — ending the process does.
- Treat leaked or wrong-recipient credential events as immediate revocation triggers, not operational noise.
- Treat wrong-environment and connectivity-failure events as hard blockers requiring human confirmation before retry.

## Acceptance Checklist

- Target collaborator and browser session are explicit.
- The credential form fits the exposure, and a CDP handle (if used) runs against a dedicated isolated-profile browser, not the user's own.
- Pairing credential is scoped to the specific session, time-limited, and delivered out-of-band — its value is absent from the pairing record.
- Bootstrap and ongoing access scopes are both recorded.
- Landing state is verified after pairing.
- Expiry and the concrete revocation path (endpoint teardown, issuer invalidate call) are present.
- Credential was revoked by its form's teardown at handoff close — for CDP, the browser process ended and its profile directory deleted — not merely left to expire.
- Any unsafe broadening attempt is surfaced explicitly.

## Contract Notes

The contracts this workflow runs under are stated in `../SKILL.md` § Required Contracts.

## Collaboration Notes

- `open-browser` owns creating the visible session to be paired, via its Browser Acquisition ladder (reuse an installed browser before installing the Playwright browser).
- `setup-browser-cookies` owns authenticated state when the paired session must start on a protected surface.
