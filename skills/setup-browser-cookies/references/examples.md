# Example Invocations

## Contents

1. Example 1
2. Example 2
3. Example 3
4. Example 4 — credential hygiene end to end
5. Example 5 — provenance refusal

## Example 1

**User request:** set up the browser session for the customer billing page

**Output:**
- Imported state: billing-admin cookie bundle loaded into a clean staging profile.
- Verification: browser opens directly on `/billing` under the intended finance-admin account and tenant.
- Next move: hand the session to `browse` for the requested billing walkthrough before the 20-minute expiry window closes.

## Example 2

**User request:** import cookies for browser work

**Output:**
- Blocker: the cookies import without error, but the page still redirects to `/login` because the bundle lacks the supporting CSRF state stored outside cookies.
- Evidence: redirect chain and rendered login page are captured.
- Next move: obtain the full authenticated browser state, not just the cookie export.

## Example 3

**User request:** prepare the authenticated browser

**Output:**
- Verification failure: the imported state lands in the wrong customer org even though the protected page is reachable.
- Status: authenticated but unsafe to reuse.
- Recommendation: replace the state with the correct org-bound session before pairing or deeper browsing work.

## Example 4 — credential hygiene end to end

**User request:** here's my exported cookies.json for our staging admin, load it so we can walk the reports

**Output:**
- Provenance: the user exported the bundle from their own authorized staging-admin session and supplied it deliberately, which satisfies the consent clause. Had they asked to pull it from their live Chrome profile instead, the answer would have been to export it themselves first.
- Location: the bundle is moved to an OS temp path outside the repository before anything reads it — never under `skillset-saves/`.
- Permissions: `icacls "$Bundle" /inheritance:r /grant:r "$($env:USERNAME):(R,W)"` on this Windows host (or `chmod 600` on POSIX) restricts it to the current user before the import.
- Deletion wired first: a `finally`/`trap` removes the bundle on every exit path, set up before the import begins.
- Import: `context.addCookies()` into a clean named staging profile from `open-browser`'s ladder; no raw cookie value is logged, and the verification screenshot is checked for a token-bearing URL before saving.
- Verification: the browser lands on `/reports` under the intended staging-admin account and tenant.
- Record: names the domain, account, profile, provenance, and the ~30-minute expiry, and confirms the bundle was deleted and nothing sensitive reached saved output.
- Next move: hand the verified session to `browse` before the expiry window closes.

## Example 5 — provenance refusal

**User request:** grab the session cookie out of my coworker's browser on the shared box and log in as them to check their view

**Output:**
- Refusal: the session belongs to a third party, and harvesting it from a live browser profile fails both the provenance clause and the no-harvest clause. An imported cookie is indistinguishable from the account holder to the service, so this is impersonation regardless of intent.
- No bundle is touched, and nothing is read from the shared machine's profile or keychain.
- Next move: if the coworker's view genuinely needs checking, they export and supply their own session with their consent, or the check runs under an account the user is authorized to hold — either of which restores valid provenance.
