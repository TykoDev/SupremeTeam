# Workflow Reference

## Contents

1. Browser launch sequence
2. Browser acquisition ladder
3. Decision rules
4. Acceptance checklist
5. Collaboration notes

## Browser Launch Sequence

1. Confirm the target URL, environment, host, browser profile, and whether the session must start clean or reuse existing state.
2. Resolve the browser through the Browser Acquisition Ladder below (reuse an already-available browser before installing one) and record the rung used.
3. Launch the visible browser with the intended session boundary and capture the first rendered state, including URL, page title, and auth posture.
4. Check whether the live page is actually usable by watching for immediate console, network, certificate, or permission failures.
5. Package the session so another browser task can pick it up without rediscovering the launch context.

## Browser Acquisition Ladder

Analyze the environment and reuse an already-available browser before downloading one. By
default walk the rungs starting at **rung 2** and stop at the first that yields a usable
browser. **Rung 1 is opt-in:** attempt it only when the user has explicitly authorized
reusing their running browser. Record which rung satisfied acquisition (`reused-cdp`,
`system-channel`, `cached-playwright`, or `installed`).

### Rung 1 — Running browser / control extension (attach over CDP) — opt-in only

**Requires explicit user confirmation. Do not run these probes or attach to a running browser
unless the user has authorized reusing their real browser for this task; otherwise skip
straight to rung 2.** Attaching shares the user's live profile and auth, so it is never the
automatic default.

Once opted in, a browser already running with a DevTools/CDP endpoint (including one opened by
a browser-control extension) is the cheapest reuse. Probe the common debug ports and attach if
one answers:

```bash
# Linux/macOS — check for an open CDP endpoint (try 9222, then 9229, 9333):
for p in 9222 9229 9333; do
  curl -fsS "http://127.0.0.1:${p}/json/version" && echo "  <- CDP on ${p}" && break
done
```

```powershell
# Windows (PowerShell):
foreach ($p in 9222,9229,9333) {
  try { (Invoke-RestMethod "http://127.0.0.1:$p/json/version"); "<- CDP on $p"; break } catch {}
}
```

A JSON response with `webSocketDebuggerUrl` means a browser is attachable. Connect with
Playwright `chromium.connectOverCDP("http://127.0.0.1:<port>")`. This shares the live profile
and auth — only reuse it when shared state is acceptable for the task.

### Rung 2 — Installed system browser (channel or executable path)

Prefer launching an installed browser over downloading one. First honor an explicit override,
then probe the platform:

- **Env overrides:** `CHROME_PATH`, `BROWSER`, `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`.
- **Linux/macOS (`PATH`):**
  ```bash
  command -v google-chrome google-chrome-stable chromium chromium-browser microsoft-edge msedge firefox 2>/dev/null
  ```
- **macOS app bundles:** `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`,
  `/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge`,
  `/Applications/Firefox.app/Contents/MacOS/firefox`.
- **Windows — `where` + registry App Paths + common locations:**
  ```powershell
  where.exe chrome msedge 2>$null
  foreach ($exe in 'chrome.exe','msedge.exe') {
    foreach ($root in 'HKLM:','HKCU:') {
      $k = "$root\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\$exe"
      if (Test-Path $k) { (Get-ItemProperty $k).'(default)' }
    }
  }
  # Fallbacks:
  #   C:\Program Files\Google\Chrome\Application\chrome.exe
  #   C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe
  ```

Launch via the matching Playwright channel (`chrome`, `msedge`, `chromium`, `firefox`) or pass
the detected binary as `executablePath`. Use a clean, named profile when the task needs
isolation rather than the user's default profile.

### Rung 3 — Cached Playwright browser (already downloaded)

If a Playwright browser was downloaded previously, reuse it without a network call:

- Cache locations (when `PLAYWRIGHT_BROWSERS_PATH` is unset):
  - Linux: `~/.cache/ms-playwright`
  - macOS: `~/Library/Caches/ms-playwright`
  - Windows: `%USERPROFILE%\AppData\Local\ms-playwright`
- Confirm what is required vs. present without downloading:
  ```bash
  npx playwright install --dry-run    # lists target browsers and install state
  ls "${PLAYWRIGHT_BROWSERS_PATH:-$HOME/.cache/ms-playwright}" 2>/dev/null
  ```

If the needed browser directory exists, launch against it directly.

### Rung 4 — Install the Playwright browser (last resort)

Only when rungs 1–3 all fail, install the browser. This is a network and filesystem mutation:
announce it first, and in offline, locked, or frozen environments escalate instead of forcing
the download.

```bash
npx playwright install chromium          # or: chrome | msedge | firefox | webkit
# On Linux CI hosts missing system libraries: npx playwright install --with-deps chromium
```

Record that an install occurred and why reuse was not possible.

## Decision Rules

- Reuse an already-available browser before installing one: walk the acquisition ladder from rung 2 (or rung 1 when the user has opted in) and stop at the first usable rung.
- Rung 1 is opt-in: never probe for or attach to the user's running browser without explicit confirmation. Default acquisition starts at rung 2.
- Never silently download a browser when a usable one exists; never block on an install when reuse is possible.
- Treat installing the Playwright browser as a network/mutating action — announce it, and escalate (do not force it) in offline, locked, or frozen environments.
- Attaching to a running browser (rung 1, opt-in) inherits the user's live profile and auth; prefer a clean, named profile (rung 2/3) when the task needs isolation.
- Prefer a clean, named browser state over an ambiguous reused profile.
- Treat wrong-account or wrong-environment landings as hard blockers, not minor noise.
- Capture visible evidence as soon as the browser opens so later diagnosis has a starting point.
- Escalate tooling and host issues before routing work to browsing or paired collaboration.

## Acceptance Checklist

- The acquisition rung used is named (`reused-cdp`, `system-channel`, `cached-playwright`, or `installed`).
- Rung 1 (`reused-cdp`) was used only after explicit user opt-in; without it, acquisition started at rung 2.
- Probes for the available reuse rungs ran before any install, and an install happened only after they failed, with the reason recorded.
- The reuse-vs-clean-profile choice is explicit for the task.
- Launch target and environment are explicit.
- Visible browser state is captured immediately after launch.
- Session scope and expiry expectations are recorded.
- Any blockers are tied to concrete diagnostics.
- The next browser task is named clearly.

## Contract Notes

- Session tokens: Use scoped time-bounded session credentials for remote browser or host interactions.
- Proactive triggers: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.

## Collaboration Notes

- `open-browser` owns the Browser Acquisition Ladder for the whole `browser-automation` set; the other skills route acquisition here instead of installing browsers themselves.
- `browser-automation/browse` consumes a ready visible session to walk the interface.
- `browser-automation/pair-agent` consumes a known-good visible session when another operator needs access.
