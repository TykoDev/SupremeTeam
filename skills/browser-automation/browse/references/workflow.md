# Workflow Reference

## Contents

1. Browser walkthrough sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Browser Walkthrough Sequence

1. Confirm the requested URL, environment, auth expectations, and any no-touch areas before beginning the walkthrough. Validate the target URL: require `http` or `https` scheme and refuse internal/loopback/metadata targets (localhost, 127.0.0.0/8, 169.254.169.254, RFC-1918 ranges, `*.internal`) and non-web schemes (`file:`, `chrome:`, etc.) unless the user has explicitly authorized an internal target — this prevents SSRF-style misuse where a supplied URL probes the internal network.
2. Open or reuse the browser state that matches the requested surface, then capture the starting URL, visible page identity, and session status.
3. Move through the requested flow one state at a time, anchoring observations in rendered UI, navigation changes, console signals, and screenshots.
4. Stop at the first meaningful blocker, permission wall, or destructive boundary instead of pushing through with guesses.
5. Package the walkthrough so another contributor can reproduce the same route and understand exactly where the flow succeeded or failed.

## Decision Rules

- Validate the target URL before navigating: require `http`/`https` and refuse internal, loopback, metadata, or non-web-scheme targets unless the user explicitly authorized them.
- Prefer visible browser evidence over assumed selectors or stale notes.
- Keep the walkthrough scoped to the requested flow instead of turning it into open-ended exploration.
- Record redirects, prompts, and branch points as first-class observations.
- Escalate before crossing a destructive boundary or a protected surface with missing authorization.

## Acceptance Checklist

- Starting page, session state, and requested flow are explicit.
- Important state changes are evidenced by UI, URL, or browser diagnostics.
- Blockers and branch points are preserved, not smoothed over.
- Next actions are clear: continue browsing, fix auth, pair another agent, or escalate.

## Contract Notes

- Before/After Evidence (screenshots): Pair each visual or browser fix with before and after captures that prove the effect on the surface under review.
- Proactive triggers: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- Shared severity: Report findings with the shared four-tier model (defined in the project's shared severity reference) so upstream and downstream packages interpret risk consistently.

## Collaboration Notes

- `browser-automation/open-browser` owns launching a visible session when none exists yet, including the Browser Acquisition ladder that reuses an installed browser before installing the Playwright browser.
- `browser-automation/pair-agent` owns safe collaborative takeover when another operator needs the live browser.
