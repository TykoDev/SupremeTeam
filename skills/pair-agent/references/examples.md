# Example Invocations

## Contents

1. Example 1 — Scoped session token, the preferred form
2. Example 2 — CDP refused against the user's own profile
3. Example 3 — Pairing verified and handed on to `browse`
4. Example 4 — CDP handoff, isolated profile, real teardown
5. Example 5 — Revocation on a leaked credential

## Example 1 — Scoped session token, the preferred form

**User request:** pair another agent to the browser so they can inspect the staging admin flow

**Output:**
- Pairing target: existing staging admin browser session opened on the release-preview host.
- Form chosen: a scoped session token, not a CDP handle — the collaborator needs one browser context, not the whole browser, so the least-exposing form applies.
- Issue: token requested from the automation service bound to the staging session id with a 15-minute expiry; token id and expiry recorded.
- Delivery: the token value is sent over the team's out-of-band secure channel. The pairing record names the token id and the issuer's revoke endpoint, never the value.
- Revocation: call the issuer's invalidate endpoint for that token id at handoff close, and immediately if the collaborator lands in the wrong tenant or requests host-level access; confirm a reconnect is refused.

## Example 2 — CDP refused against the user's own profile

**User request:** set up remote browser access for a second operator

**Output:**
- Blocker: the browser session exists, but the only available credential is a CDP handle against the user's own persistent profile — the whole-browser form, pointed at a profile holding every origin's cookies. `../SKILL.md` § Credential Forms admits a CDP handle only against a dedicated isolated-profile browser, so this is refused by form, not by judgment.
- Status: pairing denied.
- Next move: relaunch through `open-browser` with a dedicated empty profile, capturing the path rather than inlining it (`USER_DATA_DIR="$(mktemp -d)"`, then `--user-data-dir="$USER_DATA_DIR"`) so the teardown has something to delete, then retry with the **CDP / session handle** form — the `webSocketDebuggerUrl` from `/json/version`, delivered over a tunnel bound to the collaborator's identity. That handle is not single-use: it stays re-readable until the browser process ends, so the tunnel bounds who can reach it and teardown is the only revocation. If an isolated browser cannot be launched on this host, no form fits and the pairing stays denied; the answer is a narrower session, never a broader credential.

## Example 3 — Pairing verified and handed on to `browse`

**User request:** share a browser session safely

**Output:**
- Verification: collaborator reached the intended customer-support dashboard and nothing outside that browser workspace was exposed.
- Evidence: landing URL, credential form, scope summary, expiry, and the concrete revocation path are recorded in the pairing record; the credential value is not.
- Next move: hand the paired session to `browse` for the requested walkthrough.

## Example 4 — CDP handoff, isolated profile, real teardown

**User request:** the collaborator's tooling only speaks CDP, give them a debug endpoint to the session

**Output:**
- Form forced by the tool: a CDP endpoint, which is whole-browser control across every origin's cookies and storage — so it is not issued against the user's own browser.
- Issue: a dedicated browser is launched for the pairing with an empty isolated profile and a loopback-bound debug port, capturing both handles the teardown will need —
  `USER_DATA_DIR="$(mktemp -d)"`, then
  `chrome --user-data-dir="$USER_DATA_DIR" --remote-debugging-port=9222 --remote-debugging-address=127.0.0.1 about:blank &` and `BROWSER_PID=$!` —
  and the `webSocketDebuggerUrl` from `http://127.0.0.1:9222/json/version` is what the collaborator receives.
- **What is shared is not consumed.** That URL is *not* single-use: `/json/version` answers it again on every request, and `/json/list` keeps exposing every target's full URL for as long as the port is reachable. Treating it as spent after the collaborator's first connection is the error this example exists to rule out, because a run that believes the handle is already consumed skips the process termination below and leaves whole-browser control live. The tunnel bounds *who* can reach it; only teardown ends it (`../SKILL.md` § Credential Forms, `workflow.md` § CDP / session handle).
- Delivery: the endpoint URL goes over an SSH port-forward bound to the collaborator's identity, out-of-band; it is never pasted into chat or the record, and the debug port is never bound to `0.0.0.0`.
- Scope check: because the profile is empty and dedicated, the whole-browser reach of CDP exposes only this pairing's state — the user's real cookies and storage are in a different browser entirely.
- Revocation: at handoff close the pairing browser process is terminated (closing the endpoint is closing the browser) and its temporary profile directory is deleted, both using the handles captured at issue — `kill "$BROWSER_PID"`, then `rm -rf "${USER_DATA_DIR:?}"`, then a `test -d` to confirm the directory is actually gone. The guard and the check are not ceremony: `rm -rf "$USER_DATA_DIR"` on a path that was never captured expands to `rm -rf ""` and exits 0, so the teardown reports success while the profile keeps this pairing's cookies. The expiry is a backstop; ending the process is the revoke.

## Example 5 — Revocation on a leaked credential

**User request:** I think the pairing token ended up in a screenshot we posted

**Output:**
- Trigger: a scoped token was exposed in shared output, which is an immediate revocation event, not something to watch.
- Action: call the issuer's invalidate endpoint for that token id at once, before checking anything else, and confirm a reconnect attempt is refused. If the leaked credential had been a CDP endpoint, the equivalent is terminating the pairing browser and deleting its profile.
- Reissue: mint fresh pairing material only after the target collaborator's identity is reconfirmed, and deliver it out-of-band.
- Record: the leak, the revocation, and the reissue are noted so the exposure window is auditable.
