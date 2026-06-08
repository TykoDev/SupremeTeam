# Workflow Reference

## Contents

1. Authenticated-session setup sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Authenticated-Session Setup Sequence

1. Confirm the target domain, environment, and intended identity before importing any state.
2. Load cookies or browser state into the correct profile using a concrete mechanism (Playwright `context.addCookies()`, HAR import, or scoped-profile copy). Before importing: restrict file permissions on the bundle to the running process, never log or echo raw cookie values, redact them in all evidence and screenshots, and delete the bundle file after a successful import. Do not widen the session boundary to unrelated tenants or environments. Cookies are live credentials — handle them accordingly.
3. Reopen the protected surface and verify the resulting page, redirect chain, and visible account context.
4. Package the session state so the next browser task knows exactly what was loaded, how long it will remain valid, and what still limits reuse.

## Decision Rules

- Use a concrete, auditable import method (Playwright `context.addCookies()`, HAR import, or scoped-profile copy); never rely on ambient state injection.
- Restrict bundle file permissions before import; delete the bundle after successful import; never log or echo raw cookie values.
- Redact cookie material in all evidence, screenshots, and saved output.
- Prefer a clean profile when the origin of the cookie state is uncertain.
- Treat wrong-account and wrong-tenant landings as hard blockers.
- Treat an MFA challenge as a hard stop — surface it and wait for the user; do not attempt to automate past it.
- Verify the protected page directly instead of assuming imported cookies worked because no error was thrown.
- Record expiry and reuse constraints every time authenticated state is loaded.

## Acceptance Checklist

- Target domain and intended identity are explicit.
- Import mechanism is named (e.g., `context.addCookies()`, HAR import, or scoped-profile copy).
- Bundle file permissions were restricted before import and the bundle was deleted after import.
- No raw cookie values appear in logs, evidence, or screenshots.
- Protected landing page is verified with concrete evidence.
- MFA or re-authentication requirements are surfaced, not bypassed.
- Expiry or reuse caveats are recorded.
- The next browser task can tell whether the session is safe to reuse.

## Contract Notes

- Session tokens: Use scoped time-bounded session credentials for remote browser or host interactions.
- Cookie bundle security: Restrict permissions, never log raw values, redact in evidence, delete after import. Treat cookies as live credentials.
- Loading mechanism: Use a concrete auditable method — Playwright `context.addCookies()`, HAR import, or scoped-profile copy.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.

## Collaboration Notes

- `browser-automation/open-browser` owns launching the profile that receives the authenticated state, and acquires the browser via its Browser Acquisition ladder (reuse an installed browser before installing the Playwright browser).
- `browser-automation/browse` consumes the verified authenticated session for protected walkthroughs.
- `browser-automation/pair-agent` consumes the verified authenticated session only after the identity boundary is proven safe to share.
