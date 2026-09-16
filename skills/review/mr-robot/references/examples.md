# Example Invocations

Four passes, each rendered in the full packet shape `../SKILL.md` mandates:
Outcome, Evidence, Findings, Open risks, Next action, Revision, in that order and
with no verdict, because this lens owns no gate — `cso` issues the
`security-review` verdict (`../../../execution-contract.md`, clause 6). The graded
passes carry the shape too, not just the clean one: the attacker model and the
probe envelope live in the Outcome and Evidence lines, and a chain reported
without them is a claim with no stated reach. Severities are the shared four
tiers — `Critical | Major | Minor | Info` — and nothing else; "exploit chain"
names the form of a finding, never its grade.

## Example 1

**User request:** run adversarial review on the invitation flow

**Output:**
- Outcome: mr-robot, `penetration-review` stage, r2, 2 findings: 1 Critical, 0 Major, 1 Minor, 0 Info. Attacker model: unauthenticated external, holding a revoked invitation link.
- Evidence: invitation creation, the acceptance endpoint, and the tenant-assignment step traced from the public route through to the membership write; the token's issuance and revocation paths read against each other. No active probes were run at this stage, so `denial_path_evidence` carries `static analysis only - active probes not authorized` as the `reason` of an applicability record `{applicable: false, reason, scope, decided_by}`, never as a bare string.
- Findings:
  - `MR-01` | Critical | public acceptance endpoint → reused invitation token → missing tenant re-check → tenant membership | confirmed | a holder of a revoked link joins the wrong tenant; blast radius is one tenant's data per stale link | bind the token to tenant and inviter state at acceptance, and invalidate previously issued links on role change.
  - `MR-02` | Minor | acceptance endpoint error path → invite-id enumeration | confirmed | the error distinguishes "unknown invite" from "expired invite", which narrows an enumeration attempt but closes no chain on its own | return one indistinguishable response for both cases.
- Open risks: whether a revoked link survives a role change is read from the revocation code rather than observed, because no probe window was authorized; one executed denial-path run against the acceptance endpoint would settle it.
- Next action: `review/cso` decides whether `MR-01` warrants an authorized probe window before the gate.
- Revision: r2.

## Example 2

**User request:** how would someone break this password-reset flow

**Output:**
- Outcome: mr-robot, `penetration-review` stage, r1, 2 findings: 0 Critical, 2 Major, 0 Minor, 0 Info. Attacker model: unauthenticated external, assumed because no profile was supplied.
- Evidence: reset initiation and the rate-limited verification endpoint traced from the public route to the token store; the supplied rate-limit configuration read for the tier it declares. The verification endpoint's per-account tier is not present in that configuration and was not inferred.
- Findings:
  - `MR-03` | Major | reset initiation endpoint → response-timing difference → user enumeration | confirmed | response timing differs between known and unknown accounts, so the initiation endpoint enumerates users; blast radius is the full account namespace | equalize the response path and move the work behind a queue.
  - `MR-04` | Major | verification endpoint → per-IP-only rate limit → credential stuffing | conditional | the chain closes only if the rate-limit tier is per-account rather than per-IP, and that tier is not visible in the supplied config | recorded conditional with the missing evidence named, not promoted on suspicion; confirm the tier, then scope the limit per account.
- Open risks: `MR-04`'s missing link is the effective rate-limit tier. The deployed limiter configuration, or one executed burst against a test principal, would settle it; neither was available to this pass.
- Next action: `review/cso` requests the limiter configuration from the target owner before grading `MR-04` further.
- Revision: r1.

## Example 3

**User request:** run the denial-path probes on the export service

**Output:**
- Outcome: mr-robot, `adversarial-probe` stage, r4, 1 finding: 1 Critical, 0 Major, 0 Minor, 0 Info. Attacker model: authenticated tenant principal holding another account's export id.
- Evidence: background export request, object-store callback, and signed-download issuance, at the `adversarial-probe` stage under `review/cso`. Envelope cleared: staging instance, owner-approved window, scoped test principals. `evidence/denial-path-probes.log`, redacted at write time and hashed into the manifest; rows `p-01` through `p-06` recorded `denied` across the unauthorized, malformed, replayed, and expired classes at the request and callback boundaries. The pass stopped at `p-07` and sent nothing further.
- Findings:
  - `MR-05` | Critical | signed-download boundary → over-broad export id → another account's export | confirmed by probe | the boundary returned 200 for an over-broad request carrying another account's export id; probe row `p-07 | download | over-broad | GET /d/<export-id> auth=<bearer-token> | 200, body withheld | 200 | 2026-05-02T09:41:07Z | allowed`; blast radius is every export whose id can be guessed or leaked | scope the signature to the issuing principal and re-check ownership at download.
- Open risks: rows `p-08` onward were never sent, so the callback boundary's behavior under an over-broad id is unprobed — stopping at the first unexpected success is the protocol, and it leaves that gap deliberately.
- Next action: reported to `review/cso` and the target owner at the moment of the unexpected success; `cso` decides whether a fresh window reopens the sequence after the fix.
- Revision: r4.

## Example 4 — clean pass, probes withheld

**User request:** think like an attacker about the new webhook receiver

**Output:**
- Outcome: mr-robot clean — 0 reachable chains across the receiver, signature verification, and the dispatch path, attacker model: unauthenticated external with the published endpoint and no valid signing key.
- Evidence: four entry points enumerated and worked — unsigned delivery, replayed delivery, oversized body, and forged source host; signature verification is constant-time and precedes parsing; the dispatch path holds no privileged transition. Active probes were not authorized for this stage, so `denial_path_evidence` carries `static analysis only - active probes not authorized` as the `reason` of an applicability record `{applicable: false, reason, scope, decided_by}`, and no request was sent.
- Findings: (none).
- Open risks: the denial behavior is read from code rather than observed, and the assumed attacker model excludes an insider holding a valid signing key.
- Next action: none from this lens; an authorized probe window would convert the open risk above into evidence.
- Revision: r2.
