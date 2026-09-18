# Workflow Reference

## Contents

1. Authenticated-session setup sequence
2. Credential-hygiene contract
3. Decision rules
4. Acceptance checklist
5. Collaboration notes

## Authenticated-Session Setup Sequence

1. Confirm provenance and consent first: the session is one the user owns or is authorized to act for and has deliberately supplied. Refuse a harvested or third-party session, or one whose origin is unclear, before any other step.
2. Confirm the target domain, environment, and intended identity before importing any state.
3. Place the bundle on an untracked working path — never under `skillset-saves/`, the repository, or any Save-Protocol directory.
4. Restrict the bundle's permissions to the current user (`chmod 600` on POSIX; `icacls "$Bundle" /inheritance:r /grant:r "$($env:USERNAME):(R,W)"` on Windows, which is this repo's primary platform where `chmod` is a no-op).
5. Load cookies or browser state into the correct profile using a concrete mechanism (Playwright `context.addCookies()`, HAR import, or scoped-profile copy). Never log or echo raw cookie values, redact them in all evidence and screenshots, and do not widen the session boundary to unrelated tenants or environments.
6. Delete the bundle unconditionally on every exit path — success, failure, or interruption — wiring the deletion (`trap ... EXIT`, or a `finally` block) before the import begins so no path skips it.
7. Reopen the protected surface and verify the resulting page, redirect chain, and visible account context.
8. Package the session state so the next browser task knows exactly what was loaded, how long it will remain valid, and what still limits reuse.

## Credential-Hygiene Contract

The clauses below are not optional hardening; they are the contract this skill
exists to hold, because an imported session cookie is a live credential that acts
as the account holder against the protected service.

- **Provenance and consent.** Import only a session the user owns or is authorized to use and supplied deliberately. Do not extract one from a live browser profile, an OS keychain, a credential manager, or another running session; do not import a third party's session; refuse when provenance is unclear.
- **Off every tracked path.** The bundle never lives under `skillset-saves/`, the repository, or a synced directory. A credential on a tracked path is exported to everyone who can read it and outlives the session it came from.
- **Least-privilege permissions before read.** `chmod 600`, or `icacls` with `/inheritance:r /grant:r` so inherited ACLs are dropped and no broader group keeps access.
- **Never in the clear.** No raw cookie value in a log, an echo, an evidence file, a screenshot, or any saved output. Redact in place; keep only what a later reader needs to debug auth, never the secret.
- **Unconditional deletion.** Delete on success, on failure, and on interruption. Deletion conditioned on success leaves the credential on disk for exactly the failure paths that most need it gone.

## Decision Rules

- Verify provenance and consent before importing; refuse a harvested, third-party, or unexplained session.
- Use a concrete, auditable import method (Playwright `context.addCookies()`, HAR import, or scoped-profile copy); never rely on ambient state injection.
- Keep the bundle off every tracked path; restrict its permissions before import; delete it on every exit path, not only on success; never log or echo raw cookie values.
- Redact cookie material in all evidence, screenshots, and saved output.
- Prefer a clean profile when the origin of the cookie state is uncertain.
- Treat wrong-account and wrong-tenant landings as hard blockers.
- Treat an MFA challenge as a hard stop — surface it and wait for the user; do not attempt to automate past it.
- Verify the protected page directly instead of assuming imported cookies worked because no error was thrown.
- Record expiry and reuse constraints every time authenticated state is loaded.

## Acceptance Checklist

- Provenance and consent are established: the session is the user's own or authorized, and deliberately supplied — not harvested or third-party.
- Target domain and intended identity are explicit.
- The bundle sat on an untracked path, never under `skillset-saves/` or the repository.
- Import mechanism is named (e.g., `context.addCookies()`, HAR import, or scoped-profile copy).
- Bundle permissions were restricted before import (`chmod 600` / `icacls`) and the bundle was deleted on every exit path, not only on success.
- No raw cookie values appear in logs, evidence, or screenshots.
- Protected landing page is verified with concrete evidence.
- MFA or re-authentication requirements are surfaced, not bypassed.
- Expiry or reuse caveats are recorded.
- The next browser task can tell whether the session is safe to reuse.

## Contract Notes

The contracts this workflow runs under are stated in `../SKILL.md` § Required Contracts.

## Collaboration Notes

- `open-browser` owns launching the profile that receives the authenticated state, and acquires the browser via its Browser Acquisition ladder (reuse an installed browser before installing the Playwright browser).
- `browse` consumes the verified authenticated session for protected walkthroughs.
- `pair-agent` consumes the verified authenticated session only after the identity boundary is proven safe to share.
