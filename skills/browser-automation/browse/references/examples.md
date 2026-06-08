# Example Invocations

## Example 1

**User request:** browse this site and tell me where the signup flow breaks

**Output:**
- Walkthrough: landing page -> pricing -> signup -> email verification prompt.
- Evidence: the flow redirects to `/verify-email` after submit, then shows a missing-token error banner with the original form data cleared.
- Next move: hand the issue to the owning builder or investigator with the exact failing step and rendered evidence.

## Example 2

**User request:** test the page in a browser and confirm whether the filter drawer works on mobile width

**Output:**
- Starting state: product grid at 390px viewport with an authenticated session already loaded.
- Evidence: the drawer opens, the category checkbox updates the URL query, but the close button is hidden beneath a sticky footer and traps the interaction.
- Next move: capture before and after screenshots if a UI fix is applied, then rerun the same mobile path.

## Example 3

**User request:** walk through the interface and capture browser evidence for the admin export flow

**Output:**
- Path: dashboard -> reports -> export modal.
- Blocker: the browser hits an org-switch prompt before the modal can complete, so the export itself is unverified.
- Recommendation: set up the correct authenticated org state first, then resume from the recorded starting URL.
