# Example Invocations

## Example 1

**User request:** unfreeze this area now that the hotfix is validated

**Output:**
- Governing record: payment hotfix freeze created during the incident window.
- Release check: rollback verification and canary health checks are both attached, so the payment boundary can reopen.
- Next safe action: resume planned edits in the payment service while leaving the release manifest freeze untouched.

## Example 2

**User request:** remove the guard on the billing configs

**Output:**
- Authority check: billing owner approval is present and matches the guarded config scope.
- Residual risk: production sync is still blocked until the checksum refresh finishes, so only local file edits are reopened.
- Record: partial unfreeze written with the still-protected sync job called out explicitly.

## Example 3

**User request:** lift the protection boundary around the release pipeline

**Output:**
- Governing record: release manifest freeze from the stabilization window.
- Decision: no-go because the final artifact verification step is still missing.
- Next safe action: finish artifact verification, attach the evidence, and re-run the unfreeze request.
