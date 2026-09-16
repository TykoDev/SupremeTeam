---
name: browse
description: >-
  Drives an existing browser session through a page-reading workflow, reading
  observable evidence instead of guessing selectors and redacting credentials from
  every capture. Use when the user asks to browse this site, test the page in a
  browser, walk through the interface, capture browser evidence, or verify a live
  flow — even when they only say "click through the app and check it". Drives an existing session only,
  not workspace launch, auth import, or session sharing.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---

# Browse

## Purpose

A walkthrough leaves behind two things that outlive the session: a claim about what the page did, and a pile of captures. Both are traps. A claim inferred from a remembered selector is a guess wearing the clothes of evidence, so every observation here is read off the live page with named tooling and attributed to the tool that produced it. And a capture is an export — headers, URLs, and screenshots carry session credentials out of the session and onto a path that survives it — so redaction happens before the write rather than after, and session-state material (HAR, storage state, cookie jar, profile directory) never reaches the save path at all. The target URL is validated before any of that begins, because a supplied address is an instruction to reach a network location.

## Use This Skill When

Use this skill to **drive and read a live page** through observable evidence, not selector guessing:

- "browse this site" / "walk through the interface" — navigate and capture what the page actually shows
- "test the page in a browser" — exercise a live flow and verify rendered behavior
- "capture the browser evidence" — record screenshots and page state as proof

Route elsewhere to launch a visible browser workspace first (`open-browser`), load authenticated session state (`setup-browser-cookies`), or hand the session to another operator (`pair-agent`).

## Inputs

- Target URL or product surface, requested flow, and current project context.
- Browser session state, screenshots, or runtime observations when they already exist.
- Constraints such as protected environments, destructive actions to avoid, or evidence requirements.

## Outputs

- Browser walkthrough record with target URL, interaction steps, observations, and final state.
- Evidence bundle with screenshots, accessibility snapshots, console/network notes, and form or input state needed to reproduce observations — every artifact redacted per the capture-redaction contract, and each attributed to the tool that produced it.
- Product-flow finding list or completion note that distinguishes verified behavior, blocked steps, and recommended next actions.

## Workflow

1. Establish the target surface, required browser state, and safe interaction boundary before opening or reusing a session. **Validate the target URL first**: require an `http` or `https` scheme and refuse internal or loopback targets (localhost, 127.0.0.0/8, 169.254.169.254, RFC-1918 ranges, `*.internal`) and non-web schemes (`file:`, `chrome:`, etc.) unless the user has explicitly authorized the internal target — this prevents SSRF-style misuse where a supplied URL probes the internal network. When no session exists yet, acquire the browser through `open-browser`'s Browser Acquisition ladder — reuse an installed or cached browser before installing the Playwright browser (attaching to the user's running browser is opt-in).
2. Read the live page with named tooling rather than guessing selectors from memory. `../mcp-tools.md` is this project's browser-automation source of truth: prefer the rows it confirms — `mcp__playwright:browser_snapshot` for the accessibility snapshot (the structural read: roles, names, states), `browser_take_screenshot` for the visual read, `browser_navigate` and the resulting URL for state changes, `browser_console_messages` and `browser_network_requests` / `browser_network_request` for diagnostics, `browser_click` and `browser_resize` to drive and to check responsive behavior. That registry is a cache, not a claim about live tools, so when a row is missing or the server is not exposed on this host, fall back to the Playwright library equivalents in `references/workflow.md` (`page.accessibility.snapshot()` or `locator.aria_snapshot()`, `page.screenshot()`, `page.on("console"/"response")`, `page.inner_text()`) — and name which path produced each capture.
3. Traverse the requested flow, recording concrete evidence for each important state change, blocker, or unexpected branch that appears in the browser.
4. **Redact every capture before it is written to the save path.** Replace the values of `Authorization`, `Proxy-Authorization`, `Cookie`, and custom auth headers with `<redacted>`; drop `Set-Cookie` and any token, refresh token, session id, or key in a response body; rewrite tokens and signed-URL signatures in captured URLs, keeping the parameter names; check each screenshot for a token-bearing address bar before saving it; strip password, OTP, and token values from accessibility snapshots and page text while keeping roles, names, and states. Never write a raw HAR, storage-state file, cookie jar, or profile directory to the save path at all. Redaction happens before the write, because an artifact cleaned afterwards has already been on disk — and a session credential in a tracked artifact outlives the session it came from. Full capture-by-capture table in `references/workflow.md`.
5. Return a browser automation record with visited pages, observed behavior, redacted evidence anchors, and the next recommended browser step.

## Required Contracts

- **URL Validation**: Validate the target URL is `http`/`https` and not an internal or loopback target before navigating — full check and SSRF rationale in Workflow step 1.
- **Capture redaction**: Strip credentials from every capture *before* it is written — `Authorization` and `Cookie` header values, `Set-Cookie`, tokens in URLs and response bodies, credentials visible in screenshots — and never write session-state material (HAR, storage state, cookie jar, profile directory) to the save path at all. Workflow step 4 and the table in `references/workflow.md` carry the per-capture rules.
- **Before/After Evidence (screenshots)**: Pair each visual or browser fix with before and after captures that prove the effect on the surface under review.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../execution-contract.md` defines, so upstream and downstream packages read risk identically.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- `open-browser`
- `pair-agent`

## Review Expectations

- Anchor every conclusion to rendered-page evidence, not selector assumptions or expected behavior.
- Record destructive-action boundaries and user-data safeguards before clicking through sensitive flows.
- Keep the automation trace coherent enough that another agent can replay the same path or see exactly where it blocked.

## Skip Rule

Skip only when the requested surface, tool, or environment does not exist and a safe fallback is unavailable.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The requested flow lands on a login wall or expired session instead of the target page | Stop the walkthrough, record the redirect evidence, and route the user to authenticated session setup before continuing. |
| A modal, popup, file chooser, or permission prompt blocks the next interaction step | Capture the blocking UI state explicitly and avoid claiming the main flow was verified past that point. |
| The page mutates live data or triggers an irreversible action before the safe boundary is clear | Freeze at the last safe state, document the risk, and ask for approval before continuing past the destructive edge. |
| The rendered surface depends on browser features, geo rules, or anti-bot checks that the active environment cannot satisfy | Bound the missing capability, preserve the evidence gathered so far, and escalate instead of fabricating a complete walkthrough. |
| The page fails to load or the navigation times out | Record the timeout or load failure as a concrete observation, preserve any partial evidence (URL attempted, last known state), and stop the walkthrough rather than assuming the target state was reached. |
| The supplied URL targets an internal, loopback, or non-web address (e.g., localhost, RFC-1918, `file:`) | Refuse navigation, explain the restriction, and ask the user to confirm they intend to target an internal resource before proceeding. |
| A credential reaches a saved capture — a token in a request header dump, a `Set-Cookie` in a response body, an endpoint URL visible in a screenshot | Treat the session as compromised, not the file as untidy. Report at the Critical tier, have the session revoked and reissued, and remove the artifact; redaction after the write does not undo an exposure the artifact may already have carried into version control. |
| Neither the registered MCP browser tools nor the Playwright library is available on this host | Record that no page-reading tooling exists and stop. Do not substitute an HTTP fetch for a rendered-page observation — a response body is not evidence about what the browser displayed, and reporting it as such is the failure this skill is built to avoid. |
| The requested flow needs a capture type that cannot be redacted safely — a full HAR, a storage-state export, a video of an authenticated session | Do not write it to the save path. Capture the narrower artifact that answers the question (request summaries, a redacted snapshot, a cropped screenshot), and name what was deliberately not captured. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Never write `_phase-state.md`. No class in the save-ownership policy declares that path, so it is not an orchestrator-owned file either — phase state is published only through `save_run.py checkpoint`, which keeps revision lineage and the audit trail coherent.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the walkthrough sequence, the page-reading tool table (registered MCP surface plus Playwright library fallback), the capture-redaction table, and decision rules.
- `references/examples.md` for concrete browser navigation and evidence outputs, including a refused URL and an authorized local dev server.
- `../mcp-tools.md` for the confirmed browser tool rows this project treats as the browser-automation source of truth, and its staleness rules.
- `open-browser` for the Browser Acquisition ladder (reuse an existing browser before installing the Playwright browser) when a session must be launched.
- `setup-browser-cookies` for the authenticated state this skill consumes, including the bundle's provenance and disposal.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
