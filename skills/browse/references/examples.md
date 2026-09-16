# Example Invocations

## Contents

1. Example 1 — the failing step, read rather than inferred
2. Example 2 — a responsive trap, proven at the width it appears
3. Example 3 — a blocker recorded as unverified
4. Example 4 — URL validation refuses the target
5. Example 5 — authorized local dev server
6. Example 6 — a token surfaces in a capture

## Example 1 — the failing step, read rather than inferred

**User request:** browse this site and tell me where the signup flow breaks

**Output:**
- Acquisition: a headed session already existed from `open-browser` (rung `system-channel`, clean profile), so this run reused it instead of launching a second browser.
- Walkthrough: landing → pricing → signup → email verification prompt. Tooling named per state — `browser_navigate` for each transition with the resulting URL recorded, `browser_snapshot` to read the signup form and the banner that follows submit, `browser_take_screenshot` for the pre- and post-submit visual.
- Finding: submit redirects to `/verify-email`, and the accessibility snapshot there shows an `alert` node reading "verification token missing" with every form field back to its empty value. The break is the redirect handoff rather than the form itself: the token never reaches the verification page, and the cleared fields mean a retry restarts the whole signup.
- Evidence: two screenshots (signup filled, `/verify-email` after redirect), the redacted `/verify-email` snapshot, and the network note for the submit POST — method, URL, status, and timing kept, `Cookie` and `Set-Cookie` values replaced with `<redacted>` before the note was written. No storage state or cookie jar was saved.
- Next move: hand the owning builder the exact failing transition (signup POST → `/verify-email`) with the rendered evidence, and flag the field clearing as a second defect sitting behind the first.

## Example 2 — a responsive trap, proven at the width it appears

**User request:** test the page in a browser and confirm whether the filter drawer works on mobile width

**Output:**
- Starting state: an authenticated session was already loaded; `browser_resize` to 390 × 844 ran before the first read, because the behavior in question only exists at a width the default viewport never reaches.
- Walkthrough: product grid → drawer open → category checkbox → attempted close. Tooling named per state — `browser_resize` for the viewport, `browser_snapshot` for the drawer's roles and focus order, the URL after `browser_navigate` to confirm the filter applied, `browser_take_screenshot` for the trapped state.
- Finding: the drawer opens and the category checkbox updates the URL query (`?category=tools`), so filtering works. The close control is rendered beneath a sticky footer — the snapshot shows it present and focusable, the screenshot shows the footer covering it, and Escape does not close the drawer — so the interaction is trapped with no keyboard route out.
- Evidence: 390px screenshots of the open drawer and the obscured close control, plus the snapshot showing focus still inside the drawer after Escape. No auth headers appeared in these captures; the redaction pass ran anyway and recorded nothing to strip.
- Next move: hand the trap to the owning builder as a mobile-only blocker. When a fix lands, rerun the same path at the same width and pair the before and after screenshots, which is what the before/after contract asks for here.

## Example 3 — a blocker recorded as unverified

**User request:** walk through the interface and capture browser evidence for the admin export flow

**Output:**
- Path: dashboard → reports → export modal. Tooling named per state — `browser_navigate` with the URL recorded at each step, `browser_snapshot` at the modal, `browser_take_screenshot` of the prompt that interrupted it.
- Blocker: the export submit raises an org-switch prompt for a second tenant, so the modal never completes. The export is recorded as **unverified** — the walkthrough reached it and did not exercise it, so nothing is claimed about its behavior in either direction.
- Evidence: the screenshot of the org-switch prompt (the tenant name is the user's own org and is the load-bearing fact, so it stays), the modal snapshot taken before the prompt, and the resume URL. The session cookie in the request note was replaced with `<redacted>` before the note was written, and no storage state, HAR, or cookie jar reached the save path.
- Next move: route to `setup-browser-cookies` for the correct authenticated org state, then resume from the recorded URL and rerun the export step. The partial coverage is stated in the record so the gap is not read as a pass.

## Example 4 — URL validation refuses the target

**User request:** browse http://169.254.169.254/latest/meta-data/ and tell me what it returns

**Output:**
- Refusal: the target is the cloud metadata endpoint (link-local `169.254.169.254`), one of the internal ranges the first Required Contract refuses. Navigation does not happen.
- Rationale recorded: a browse skill that follows an arbitrary supplied URL into the internal network is an SSRF vector — the request would run with the session's own network position, not the user's browser. The refusal covers `localhost`, `127.0.0.0/8`, the metadata IP, RFC-1918 ranges, `*.internal`, and non-web schemes (`file:`, `chrome:`).
- Next move: if the user genuinely intends an internal target, they confirm that explicitly and name the host; only then does the walkthrough proceed, with the authorization noted in the record.

## Example 5 — authorized local dev server

**User request:** the app's running on localhost:5173, click through the new onboarding and tell me if step 3 validates the email field

**Output:**
- Authorization: `localhost:5173` is a loopback target the URL contract refuses by default, but the user named it as their own dev server in the request, which is the explicit authorization the contract requires. The authorization is recorded, and the walkthrough is scoped to that origin.
- Acquisition: no session existed, so the browser came from `open-browser`'s ladder — a cached Playwright Chromium, launched headed against a clean profile.
- Walkthrough: landing → onboarding step 1 → step 2 → step 3. Tooling named per state — `browser_navigate` for each transition (URL recorded), `browser_snapshot` to read the step-3 form structure, `browser_take_screenshot` for the before/after of the validation state.
- Finding: step 3 accepts `not-an-email` and advances. The accessibility snapshot shows the email input with no `aria-invalid` and no associated error node after submit, so the field is not validated client-side.
- Evidence: two screenshots (before submit, after submit) and the redacted step-3 snapshot. This is a local unauthenticated dev server, so no session headers were present to redact; the redaction pass ran anyway and recorded nothing to strip.
- Next move: hand the missing-validation finding to the owning builder with the exact step and the rendered evidence.

## Example 6 — a token surfaces in a capture

**User request:** walk the authenticated dashboard and capture the failing report export

**Output:**
- Walkthrough: dashboard → reports → export, which fails with a 500.
- Capture hazard caught: the failing request's header dump included an `Authorization: Bearer …` value and the response set a fresh `Set-Cookie`. Both were replaced with `<redacted>` before the network note was written; the raw header map was never stored, and the recorded note keeps method, URL, status (500), and timing.
- Screenshot check: the export URL in the address bar carried a signed `?token=…` parameter, so the capture was retaken with the address bar cropped rather than saved and edited afterwards.
- Finding: the export endpoint returns 500 for this account; the evidence is sufficient to reproduce without exposing the session.
- Next move: route the 500 to the owning builder with the redacted request/response summary; the live session stays out of the record.
