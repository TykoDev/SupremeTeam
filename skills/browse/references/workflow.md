# Workflow Reference

## Contents

1. [Browser walkthrough sequence](#browser-walkthrough-sequence)
2. [Page-reading tooling](#page-reading-tooling)
3. [Capture redaction](#capture-redaction)
4. [Decision rules](#decision-rules)
5. [Acceptance checklist](#acceptance-checklist)
6. [Contract notes](#contract-notes)
7. [Collaboration notes](#collaboration-notes)

## Browser Walkthrough Sequence

1. Confirm the requested URL, environment, auth expectations, and any no-touch areas before beginning the walkthrough. Validate the target URL: require `http` or `https` scheme and refuse internal/loopback/metadata targets (localhost, 127.0.0.0/8, 169.254.169.254, RFC-1918 ranges, `*.internal`) and non-web schemes (`file:`, `chrome:`, etc.) unless the user has explicitly authorized an internal target — this prevents SSRF-style misuse where a supplied URL probes the internal network.
2. Open or reuse the browser state that matches the requested surface, then capture the starting URL, visible page identity, and session status with the tooling below.
3. Move through the requested flow one state at a time, anchoring observations in rendered UI, navigation changes, console signals, and screenshots.
4. Stop at the first meaningful blocker, permission wall, or destructive boundary instead of pushing through with guesses.
5. Redact every capture before it is written to the save path, then package the walkthrough so another contributor can reproduce the same route and understand exactly where the flow succeeded or failed.

## Page-Reading Tooling

`../../mcp-tools.md` is this project's browser-automation source of truth. Read
it first and use the rows it confirms; it is a cache, not a claim about live
tools, so when a row is missing, the registry is stale, or the server is not
exposed on the active host, fall back to the library calls below and record which
path was used. Never assert a capture that no tool actually produced.

### Preferred: the registered MCP surface

| Need | Tool | Note |
| --- | --- | --- |
| Navigate | `mcp__playwright:browser_navigate` | records the resulting URL, which is the primary state-change signal |
| Accessibility snapshot | `mcp__playwright:browser_snapshot` | the structural read — roles, names, and states. Prefer it over a screenshot for verifying text and structure, and over any selector recalled from memory |
| Screenshot | `mcp__playwright:browser_take_screenshot` | the visual read; pairs with the snapshot, never replaces it |
| Interact | `mcp__playwright:browser_click` | drive from a snapshot reference rather than a guessed selector |
| Viewport | `mcp__playwright:browser_resize` | for responsive checks; record the width alongside the observation |
| Tabs | `mcp__playwright:browser_tabs` | for flows that open a new context |
| Console signals | `mcp__playwright:browser_console_messages` | client-side errors in the reader's own words |
| Network signals | `mcp__playwright:browser_network_requests`, `mcp__playwright:browser_network_request` | request list, then one response body when a specific call is in question |

### Fallback: the Playwright library

Use when the MCP surface is unavailable. Python shown; the Node API is the same
shape.

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=False)   # acquisition: open-browser's ladder
    context = browser.new_context()

    console, network = [], []
    page = context.new_page()
    page.on("console", lambda m: console.append({"type": m.type, "text": m.text}))
    page.on("response", lambda r: network.append({"url": r.url, "status": r.status}))

    page.goto("https://example.test/signup", wait_until="domcontentloaded")

    page.screenshot(path="01-landing.png", full_page=True)   # visual read
    tree = page.accessibility.snapshot(interesting_only=True) # structural read
    aria = page.locator("body").aria_snapshot()               # newer Playwright equivalent
    text = page.inner_text("body")
    url  = page.url                                           # state-change signal
```

- `page.accessibility.snapshot()` is the structural read on older Playwright
  builds; `locator.aria_snapshot()` is the current equivalent. Use whichever the
  installed version exposes and name it in the record.
- For a full HAR of the flow, open the context with
  `browser.new_context(record_har_path="flow.har")` and close it before reading
  the file — a HAR captures request and response headers in full, which makes
  redaction mandatory rather than advisable.
- Acquisition of the browser itself is never decided here:
  `open-browser` owns the ladder (reuse an installed or cached
  browser before installing the Playwright browser; CDP attachment is opt-in).

## Capture Redaction

This skill runs against authenticated sessions and writes its captures to a
tracked save path, so every capture is a potential credential export. A session
cookie or bearer token in a saved artifact is a live credential for whoever reads
the repository — a longer-lived exposure than the browser session it came from,
because the artifact outlives the session.

Redact **before** the artifact is written, not afterwards. A capture written raw
and cleaned later has already been on disk, and may already have been read,
synced, or committed.

| Capture | What is redacted | How |
| --- | --- | --- |
| Network requests | `Authorization`, `Proxy-Authorization`, `Cookie`, `X-API-Key` and equivalent custom auth headers | record method, URL, status, and timing; replace each header value with `<redacted>`; never store the raw header map |
| Network responses | `Set-Cookie`; any body field naming a token, refresh token, session id, or key | store the status and the fields the finding actually needs; replace the rest with `<redacted>` |
| URLs | tokens, session ids, signed-URL signatures, and one-time codes in query strings or fragments | rewrite the parameter value to `<redacted>` and keep the parameter name, so the shape of the request stays legible |
| Screenshots | any token-bearing URL in the address bar or DevTools pane; visible one-time codes; personal data not needed for the finding | check the frame before saving; crop or mask, and retake rather than annotate over a leak |
| Accessibility snapshots and page text | values of password, OTP, and token fields; personal data outside the finding's scope | replace values with `<redacted>`, keep roles, names, and states — the structure is what the walkthrough needs |
| Console transcripts | tokens and credentials that applications routinely log at debug level | filter on save; do not paste a raw console dump into the record |
| HAR files | everything above, across every entry | a raw HAR is never written to the save path. Post-process it, or capture request/response summaries instead |

Session-state artifacts — storage-state JSON, cookie jars, profile directories —
are not evidence and are never written to the save path at all.
`setup-browser-cookies` owns that material and its disposal.

When a credential does reach a saved artifact, treat it as compromised: report it
at the shared severity model's Critical tier, have the session revoked and
reissued, and remove the artifact. Redaction after the fact does not undo the
exposure.

## Decision Rules

- Validate the target URL before navigating: require `http`/`https` and refuse internal, loopback, metadata, or non-web-scheme targets unless the user explicitly authorized them.
- Prefer visible browser evidence over assumed selectors or stale notes; prefer the accessibility snapshot over a screenshot for anything about text or structure.
- Name the tooling that produced each capture, and say whether it came from the registered MCP surface or the library fallback.
- Redact every capture before it is written, and never write session-state material to the save path.
- Keep the walkthrough scoped to the requested flow instead of turning it into open-ended exploration.
- Record redirects, prompts, and branch points as first-class observations.
- Escalate before crossing a destructive boundary or a protected surface with missing authorization.

## Acceptance Checklist

- Starting page, session state, and requested flow are explicit.
- The target URL passed validation, or the user's explicit authorization for an internal target is recorded.
- Important state changes are evidenced by UI, URL, or browser diagnostics, each attributed to the tool that produced it.
- Every saved capture is redacted: no `Authorization` or `Cookie` header value, no `Set-Cookie`, no token in a URL, no credential visible in a screenshot.
- No session-state file, cookie jar, or profile directory was written to the save path.
- Blockers and branch points are preserved, not smoothed over.
- Next actions are clear: continue browsing, fix auth, pair another agent, or escalate.

## Contract Notes

The contracts this workflow runs under are stated in `../SKILL.md` § Required Contracts.

## Collaboration Notes

- `open-browser` owns launching a visible session when none exists yet, including the Browser Acquisition ladder that reuses an installed browser before installing the Playwright browser, and the handling rules for the session credential itself.
- `setup-browser-cookies` owns the authenticated state this skill consumes, including the cookie bundle's provenance, permissions, and deletion.
- `pair-agent` owns safe collaborative takeover when another operator needs the live browser.
