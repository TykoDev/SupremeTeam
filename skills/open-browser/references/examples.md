# Example Invocations

## Contents

1. Example 1
2. Example 2
3. Example 3
4. Example 4 — Acquisition by reuse (no install)
5. Example 5 — Install fallback (last resort)
6. Example 6 — Offline / locked environment (escalate, don't install)
7. Example 7 — Remote host session, credential recorded by reference

## Example 1

**User request:** open the browser workspace for staging so I can watch the checkout flow live

**Output:**
- Launch state: visible browser opened against the staging storefront with a clean profile and no authenticated user loaded.
- Evidence: starting URL, page title, and a screenshot of the landing state are recorded immediately after launch.
- Next move: run `browse` against the checkout path or load authenticated session state first if the flow requires login.

## Example 2

**User request:** launch a visible browser on the admin page

**Output:**
- Blocker: the visible session lands on the SSO challenge instead of the admin dashboard because the provided session token already expired.
- Evidence: redirect URL and the rendered challenge page are recorded. The expired token is referenced by issuer and expiry timestamp only — the value itself appears nowhere in the record, and the challenge-page screenshot was checked for a token-bearing URL in the address bar before it was saved.
- Next move: refresh the scoped browser credentials, then relaunch the session.

## Example 3

**User request:** inspect the page live

**Output:**
- Live session: browser opens successfully on the target release preview, but the console shows a CSP error that prevents the main app bundle from rendering.
- Status: visible browser session exists, rendered surface blocked.
- Recommendation: route the diagnostics to the owning builder before using the session for deeper walkthrough work.

## Example 4 — Acquisition by reuse (no install)

**User request:** open a browser and walk the dashboard

**Output:**
- Acquisition: rung 1 skipped (no opt-in to reuse a running browser); rung 2 detected an installed Microsoft Edge via `App Paths\msedge.exe`. Launched with Playwright `channel: "msedge"` and a clean named profile.
- Acquisition rung: `system-channel` (no Playwright download needed).
- Evidence: starting URL, page title, and a landing screenshot captured immediately after launch.
- Next move: run `browse` against the dashboard flow.

## Example 5 — Install fallback (last resort)

**User request:** open a visible browser for the CI smoke check

**Output:**
- Acquisition: rung 1 skipped (no opt-in); rung 2 (no system Chrome/Edge/Firefox on PATH, registry, or app bundles) and rung 3 (empty `~/.cache/ms-playwright`) found nothing reusable.
- Action: announced the install, then ran `npx playwright install chromium` as the last resort.
- Acquisition rung: `installed` — reason recorded (no reusable browser present in the CI host).
- Next move: launch against the freshly installed Chromium and capture the landing state.

## Example 6 — Offline / locked environment (escalate, don't install)

**User request:** launch a browser on the airgapped build host

**Output:**
- Acquisition: rung 1 skipped (no opt-in); rungs 2–3 found no reusable browser, and the host is offline/locked so rung 4 install is not permitted.
- Status: blocked — no usable browser could be acquired.
- Evidence: per-rung probe results preserved (empty PATH/registry probe, empty Playwright cache; rung 1 not attempted — no opt-in).
- Escalation: route to a host with an installed browser or a permitted install path instead of forcing a download.

## Example 7 — Remote host session, credential recorded by reference

**User request:** open a browser on the remote grid host so QA can watch the run

**Output:**
- Acquisition: rung 1 skipped (no opt-in); the grid host exposes a managed browser endpoint, so acquisition resolves to `system-channel` against the grid's own installed Chrome with a clean named profile.
- Credential scope: a grid session token bound to one session id, one target origin, and the automation role — not the tenant-wide API key that was also offered. The wider key was declined and the narrowing recorded.
- Lifetime: 20 minutes, sized to launch plus verification, set at issue time by the grid's own expiry rather than assumed.
- Storage: held in the launching process environment for the life of the session; nothing written under the save path.
- Session record: names the issuer, the session id, the expiry timestamp, and the revoke endpoint. The token value appears nowhere — not in the record, not in the handoff note, not in the console transcript.
- Screenshot check: the landing capture was taken with the address bar showing the target URL only; the endpoint URL carrying the token was never rendered in frame.
- Next move: QA watches read-only. If QA needs to drive, the handoff goes to `pair-agent` for a scoped credential delivered out-of-band — the connection details are not pasted into shared output.
