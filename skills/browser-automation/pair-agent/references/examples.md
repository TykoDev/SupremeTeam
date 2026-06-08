# Example Invocations

## Example 1

**User request:** pair another agent to the browser so they can inspect the staging admin flow

**Output:**
- Pairing target: existing staging admin browser session opened on the release-preview host.
- Access issued: one-time bootstrap key plus a session token limited to the staging browser context with a 15-minute expiry.
- Revocation note: revoke immediately if the collaborator lands in the wrong tenant or requests host-level access.

## Example 2

**User request:** set up remote browser access for a second operator

**Output:**
- Blocker: the browser session exists, but the only available credential would expose a persistent shared profile.
- Status: pairing denied.
- Next move: relaunch the browser with a narrower scoped profile, then retry pairing.

## Example 3

**User request:** share a browser session safely

**Output:**
- Verification: collaborator reached the intended customer-support dashboard and nothing outside that browser workspace was exposed.
- Evidence: landing URL, scope summary, expiry, and revocation path are recorded in the pairing record.
- Next move: hand the paired session to `browse` for the requested walkthrough.
