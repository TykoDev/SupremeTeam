# Example Invocations

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
