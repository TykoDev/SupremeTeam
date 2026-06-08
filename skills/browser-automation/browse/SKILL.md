---
name: browse
description: >-
  Automates browser interactions through a structured page-reading workflow that
  emphasizes observable evidence instead of selector guessing. Use when the user
  asks to browse this site, test the page in a browser, walk through the interface,
  capture browser evidence, or verify how a live flow behaves on an actual rendered
  surface — even when they only say "click through the app and check it". Drives an
  existing browser session; defers launching a visible workspace to
  `browser-automation/open-browser`, loading authenticated session state to
  `browser-automation/setup-browser-cookies`, and sharing the session with another
  operator to `browser-automation/pair-agent`.
version: 1.0.0
---

# Browse

## Purpose

Automate browser interactions through a structured page-reading workflow that emphasizes observable evidence instead of selector guessing.

## Use This Skill When

Use this skill to **drive and read a live page** through observable evidence, not selector guessing:

- "browse this site" / "walk through the interface" — navigate and capture what the page actually shows
- "test the page in a browser" — exercise a live flow and verify rendered behavior
- "capture the browser evidence" — record screenshots and page state as proof

Route elsewhere to launch a visible browser workspace first (`browser-automation/open-browser`), load authenticated session state (`browser-automation/setup-browser-cookies`), or hand the session to another operator (`browser-automation/pair-agent`).

## Inputs

- Target URL or product surface, requested flow, and current project context.
- Browser session state, screenshots, or runtime observations when they already exist.
- Constraints such as protected environments, destructive actions to avoid, or evidence requirements.

## Outputs

- Browser walkthrough record with target URL, interaction steps, observations, and final state.
- Evidence bundle with screenshots, accessibility snapshots, console/network notes, and form or input state needed to reproduce observations.
- Product-flow finding list or completion note that distinguishes verified behavior, blocked steps, and recommended next actions.

## Workflow

1. Establish the target surface, required browser state, and safe interaction boundary before opening or reusing a session. **Validate the target URL first**: require an `http` or `https` scheme and refuse internal or loopback targets (localhost, 127.0.0.0/8, 169.254.169.254, RFC-1918 ranges, `*.internal`) and non-web schemes (`file:`, `chrome:`, etc.) unless the user has explicitly authorized the internal target — this prevents SSRF-style misuse where a supplied URL probes the internal network. When no session exists yet, acquire the browser through `browser-automation/open-browser`'s Browser Acquisition ladder — reuse an installed or cached browser before installing the Playwright browser (attaching to the user's running browser is opt-in).
2. Read the live page through visible structure, URL changes, console or network signals, and page text instead of guessing selectors from memory.
3. Traverse the requested flow, recording concrete evidence for each important state change, blocker, or unexpected branch that appears in the browser.
4. Return a browser automation record with visited pages, observed behavior, evidence anchors, and the next recommended browser step.

## Required Contracts

- **URL Validation**: Validate the target URL is `http`/`https` and not an internal or loopback target before navigating — full check and SSRF rationale in Workflow step 1.
- **Before/After Evidence (screenshots)**: Pair each visual or browser fix with before and after captures that prove the effect on the surface under review.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Shared severity**: Report findings with the shared four-tier model (defined in the project's shared severity reference) so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- `browser-automation/open-browser`
- `browser-automation/pair-agent`

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

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Do not create or manage `_phase-state.md` — that is the delegating orchestrator's responsibility.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed browser walkthrough sequence and decision rules.
- `references/examples.md` for concrete browser navigation and evidence outputs.
- `browser-automation/open-browser` for the Browser Acquisition ladder (reuse an existing browser before installing the Playwright browser) when a session must be launched.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
