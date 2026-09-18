---
name: setup-browser-cookies
description: >-
  Imports a user-owned, deliberately supplied authenticated session into an isolated
  browser profile under a credential-hygiene contract: provenance, off-tracked-path
  storage, restricted permissions, unconditional deletion. Use when the user wants a
  browser that is already signed in — import cookies, set up the browser session,
  prepare authenticated access, or verify a protected page loads as the intended
  account. Supplies the signed-in state; opening the window itself is `open-browser`,
  driving the page is `browse`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---

# Setup Browser Cookies

## Purpose

To the service receiving it, an imported cookie is indistinguishable from the account holder. That makes this a credential-handling skill that happens to involve a browser, and two rules bound everything else it does. Provenance comes first: the session is one the user owns or is authorized to act for and supplied deliberately — never harvested from a live profile, an OS keychain, a credential store, or a third party — and unclear provenance is a refusal rather than a caveat. Hygiene covers the bundle's whole short life: off every tracked path, permissions narrowed to the current user before it is read, raw values never logged or captured, and deletion wired to every exit path before the import begins, because a failed import leaves the credential on disk exactly as a successful one does.

## Use This Skill When

Use this skill to **prepare authenticated session state** so later browser work can reach protected surfaces:

- "set up the browser session" / "prepare the authenticated browser" — establish the logged-in state
- "import cookies for browser work" — load session cookies for the intended account and tenant
- "load the browser access state" — verify a protected page is reachable before automation runs

Route elsewhere to launch the workspace (`open-browser`), drive page interactions (`browse`), or share the session with another operator (`pair-agent`).

## Inputs

- Target domain or protected surface plus current project context.
- Cookie source, storage bundle, or session-token material and the intended account or tenant, plus evidence the user owns or is authorized to act for that account and supplied the state deliberately.
- Known constraints such as environment boundaries, expiry windows, and evidence requirements.

## Outputs

- Authenticated session bootstrap record naming target domain, account or tenant, profile location, cookie source and its provenance, expiry assumptions, and confirmation that the bundle was deleted after the import attempt.
- Reachability evidence for the protected surface, including target URL, observed auth state, and redacted session-storage or cookie checks.
- Session handoff instructions covering safe reuse, refresh triggers, and blocked access reasons.

## Workflow

1. **Confirm provenance and consent before touching the bundle.** Establish that the session belongs to the user or to an account they are authorized to act for, and that they intend this state to be imported for this task. Do not harvest the session yourself from a live browser profile, an OS keychain, a credential store, or another running session — the bundle is supplied deliberately by its owner, not extracted. Refuse a third party's session, and refuse when provenance is unclear, because an imported cookie is indistinguishable from the account holder to the protected service. This is the credential-hygiene contract's first clause, ahead of any loading step.
2. Confirm the target domain, intended account or tenant, cookie source, and whether the authenticated state belongs in a clean or reused browser profile.
3. Place the bundle outside every tracked path. It never lives under `skillset-saves/`, the repository, or any directory the Save Protocol writes to — a session cookie committed or synced is a live credential exported to everyone who can read that path. Keep it in an untracked working location (an OS temp directory, or a path the user names) for the life of the import only.
4. Restrict the bundle's permissions to the current user before reading it:

   ```bash
   chmod 600 "$BUNDLE"                     # POSIX: owner read/write only
   ```

   ```powershell
   # Windows (repo is Windows-primary; chmod is a no-op here):
   icacls "$Bundle" /inheritance:r /grant:r "$($env:USERNAME):(R,W)"
   ```

   `icacls /inheritance:r` drops inherited ACLs so no broader group retains access; `/grant:r` replaces any existing grant for the user rather than adding to it.
5. Load the cookies or session state into the isolated profile using a concrete mechanism — Playwright's `context.addCookies()`, a HAR import, or a scoped-profile copy. Never log or echo raw cookie values, and redact them in any evidence, screenshots, or saved output. Acquire the browser through `open-browser`'s Browser Acquisition ladder — reuse an installed or cached browser before installing the Playwright browser (attaching to the user's running browser is opt-in) — and prefer a clean, named profile so imported state is not mixed with a reused live profile.
6. **Delete the bundle unconditionally when the import attempt ends — success or failure.** A failed import leaves the credential on disk exactly as a successful one does, so deletion is not conditioned on the outcome:

   ```bash
   trap 'shred -u "$BUNDLE" 2>/dev/null || rm -f "$BUNDLE"' EXIT
   ```

   ```powershell
   try { <# import #> } finally {
     try { Remove-Item -Force -ErrorAction Stop "$Bundle" } catch { }
     if (Test-Path "$Bundle") { throw "CREDENTIAL NOT DELETED: $Bundle still exists. Remove it manually before continuing." }
   }
   ```

   Wire the deletion to run on every exit path before the import begins, so an early return, an exception, or a verification failure cannot skip it. **Confirm the file is actually gone, and fail loudly when it is not.** `-ErrorAction SilentlyContinue` on its own swallows the failure — a bundle held open by the browser, or locked by an antivirus scanner, leaves a live credential on disk while the cleanup reports success. The existence check after the delete is what turns a silent miss into a visible one, and the failure-mode row below requires exactly that confirmation. The POSIX form needs the same treatment where `shred` and `rm` can both fail:

   ```bash
   trap 'shred -u "$BUNDLE" 2>/dev/null || rm -f "$BUNDLE"; [ -e "$BUNDLE" ] && echo "CREDENTIAL NOT DELETED: $BUNDLE" >&2' EXIT
   ```
7. Verify the authenticated landing state by checking redirects, visible account identity, tenant context, and whether the protected page is actually reachable.
8. Return a session bootstrap record with the loaded state boundary, verification result, expiry caveats, and the next browser task that can safely reuse the session — confirming the bundle was deleted and no raw cookie value reached any saved output.

## Required Contracts

- **Provenance and consent**: Import only a session the user owns or is authorized to act for and has deliberately supplied; never harvest one from a live profile, keychain, credential store, or another party's session, and refuse when provenance is unclear (Workflow step 1).
- **Session tokens**: Use scoped time-bounded session credentials for remote browser or host interactions.
- **Cookie bundle security**: Treat the cookie bundle as a live credential — keep it off every tracked path, restrict its permissions (`chmod 600` / `icacls`), never log raw values, and delete it unconditionally on any exit path — with the full handling in Workflow steps 3–6.
- **Loading mechanism**: Use a concrete, auditable import method (named in Workflow step 5) — never undocumented or ambient state injection.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../execution-contract.md` defines, so upstream and downstream packages read risk identically.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- `browse`
- `open-browser`
- `pair-agent`

## Review Expectations

- Prove the session belongs to the intended domain and account before using it on protected workflows.
- Redact or avoid exposing credential material while still recording enough evidence to debug auth failures.
- Mark expiry, tenant mismatch, or MFA blockers explicitly so later browser automation does not mistake auth drift for product failure.

## Skip Rule

Skip only when the requested surface, tool, or environment does not exist and a safe fallback is unavailable.

## Failure Modes

| Scenario | Response |
| --- | --- |
| Imported cookies load successfully but the browser still redirects back to login | Treat the auth setup as unverified, capture the redirect chain, and check for missing companion state such as local storage, CSRF tokens, or wrong environment cookies. |
| The authenticated surface opens under the wrong account, tenant, or role | Stop immediately, record the mismatched identity, and do not let later browser tasks reuse that session state. |
| The cookie bundle belongs to a different domain, environment, or subdomain than the requested protected surface | Reject the import as out of scope for the target page and require the correct state source before proceeding. |
| The bundle carries state for several tenants or several origins at once — a whole-profile export, a storage-state file spanning multiple domains, cookies for both staging and production | Reject it. Import exactly the origin and tenant the task needs, and nothing else. A multi-tenant bundle loads a credential for every tenant in it into one browser context, so any later navigation — a redirect, an embedded frame, a mis-typed URL — carries an authenticated identity the task never scoped and the user never considered. Ask for a per-origin export instead, or have the user narrow the existing one before it is supplied; do not narrow it by hand after import, because the wider credential has already been on disk and in the profile by then. The same applies to a bundle that mixes environments: staging and production are different tenants for this purpose, and an export holding both is the one most likely to be offered. |
| Session state is technically valid but expires too quickly to support the next browser task | Record the narrow expiry window and refresh or replace the state before handing it to browsing or pairing work. |
| The protected page requires an MFA challenge even after cookies are imported | Treat the session as requiring an interactive authentication step; pause, surface the MFA requirement explicitly, and do not attempt to proceed past the challenge automatically. |
| The session appears authenticated but expires within seconds or minutes of import | Record the short-lived state, do not pass it to downstream tasks as stable, and prompt the user to refresh or re-export the session bundle before continuing. |
| The session's provenance is unclear, or it belongs to a third party rather than the user | Refuse the import. An imported cookie acts as the account holder against the protected service, so importing a session the user does not own or is not authorized to use is impersonation regardless of intent. Ask the user to supply a session for an account they hold or are authorized to act for. |
| The user asks to pull the session directly from their live browser profile, an OS keychain, or a credential store | Do not harvest it. Explain that this skill imports a bundle the owner exports deliberately, not one extracted from an ambient store, and have the user produce the export themselves. Harvesting blurs consent and reaches state beyond the one session in scope. |
| The import fails, errors, or is interrupted before verification | Delete the bundle anyway. The deletion is wired to every exit path precisely so a failure cannot leave the credential on disk; confirm the file is gone before reporting the failure, and never leave a live credential behind as a side effect of an unsuccessful import. |
| The only place offered for the bundle is inside the repository or a `skillset-saves/` path | Refuse that location and move the bundle to an untracked working path first. A credential under a tracked or synced directory is exported to everyone who can read it, which outlives and outreaches the single session it was meant for. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Never write `_phase-state.md`. No class in the save-ownership policy declares that path, so it is not an orchestrator-owned file either — phase state is published only through `save_run.py checkpoint`, which keeps revision lineage and the audit trail coherent.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed authenticated-session setup sequence, the credential-hygiene rules (provenance, off-tracked-path storage, `chmod`/`icacls`, unconditional deletion), and decision rules.
- `references/examples.md` for concrete cookie-import and verification outputs, including the provenance refusal and the hygiene sequence end to end.
- `open-browser` for the Browser Acquisition ladder (reuse an existing browser before installing the Playwright browser) that launches the profile receiving the authenticated state.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
