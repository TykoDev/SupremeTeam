# Example Invocations

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
- Evidence: redirect URL and the rendered challenge page are recorded.
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
