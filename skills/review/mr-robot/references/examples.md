# Example Invocations

## Example 1

**User request:** run adversarial review on the invitation flow

**Output:**
- Scope: invitation creation, acceptance endpoint, and the tenant-assignment step.
- Exploit chain: a reused invitation token plus a missing tenant re-check allows a user to join the wrong tenant after the original invite has been revoked.
- Containment: bind the token to tenant and inviter state at acceptance time and invalidate previously issued links on role change.

## Example 2

**User request:** pressure-test this code path for abuse cases

**Output:**
- Scope: password-reset initiation and rate-limited verification endpoint.
- Finding set: one chain is confirmed (account enumeration through response timing); a second chain is conditional because the rate-limit tier is not visible in the supplied config.
- Delivery: adversarial packet that separates confirmed abuse paths from the unresolved runtime-control question.

## Example 3

**User request:** think like an attacker about the export worker

**Output:**
- Scope: background export request, object-store callback, and signed-download issuance.
- Major chain: a stale callback token plus missing ownership verification can turn a completed export into a cross-account download.
- Handoff: ask `review/security-review` to confirm whether the same flaw also exposes long-lived credential misuse outside the chained attack path.
