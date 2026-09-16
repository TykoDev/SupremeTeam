# Probe Protocol

Read this before sending any request at the `adversarial-probe` stage, and when
building the `denial_path_evidence` record. `../SKILL.md` states why the executed
log and the rule against live exploits both hold; this file is the operational
detail behind that line, and it governs nothing outside the probe itself.

## Contents

1. Why a denial-path probe is not an exploit
2. The probe envelope
3. The five request classes
4. Record shape
5. Redaction rule
6. Stop conditions and reporting

## 1. Why a Denial-Path Probe Is Not an Exploit

An exploit is a request designed to **succeed** against a control. A denial-path
probe is a request designed to be **refused**, sent so the refusal can be observed
and hashed rather than assumed. The artifact the gate wants is the record of the
boundary holding — not a demonstration that it fails.

That distinction is only real while the envelope below holds. A probe whose
expected result is success is an exploit wearing a probe's name, and it stops at
the reasoning-and-payload proof the Failure Modes table in `../SKILL.md` requires.

## 2. The Probe Envelope

Every condition must hold before a single request is sent. When any one fails,
nothing is sent and `denial_path_evidence` carries the sanctioned fallback
`static analysis only - active probes not authorized`. At manifest schema 2 that
wording is the `reason` of an applicability record
`{applicable: false, reason, scope, decided_by}` — `check.py` refuses it bare.

| Condition | Requirement |
| --- | --- |
| Authorization | `review/cso` has scoped the engagement and named the target, and the target's human owner has approved active probing against it. `cso` owns the scope; mr-robot never widens it, and nothing discovered inside the target widens it either. The authorizing owner and the approval are recorded on the log. |
| Target | A non-production instance — staging, an ephemeral deployment, or a local build — reachable only inside the approved scope. A production target requires a separate, explicit owner decision recorded on the log; scope creep onto a neighbouring host or tenant is out of bounds even when it is reachable. |
| Effect | Read-only or self-undoing. A probe asserts a denial; it never deletes, exfiltrates, encrypts, escalates a real principal, degrades availability, or leaves durable state behind. |
| Credentials | Scoped test principals created for this pass. Real user credentials, customer data, and production secrets are never probe input, and a probe never captures one as output. |
| Expected result | A refusal. A request expected to succeed is not a denial-path probe and is not sent. |
| Rate | The smallest number of requests that establishes the denial — one per class per boundary. Repetition to force a failure is load testing an unconsenting system, not evidence. |
| Stop condition | The first unexpected success, state change, or availability signal ends the pass before anything further is sent (§6). |

## 3. The Five Request Classes

`../../../ownership.yaml` requires `denial-path-evidence` to cover five classes.
Build one probe per class at every boundary in scope:

| Class | What the probe sends | Expected observation |
| --- | --- | --- |
| Unauthorized | A well-formed request from a principal holding no grant on the target | Denial before any state is read or changed |
| Malformed | Structurally invalid input at the same entry point — wrong type, oversized field, broken encoding, unexpected content type | Rejection at validation, with no partial effect and no internal detail in the error |
| Replayed | A previously accepted request resent unchanged | Rejection on nonce, idempotency key, or single-use token |
| Expired | A credential, token, or signature past its validity window | Rejection on expiry, at the boundary rather than at a later check |
| Over-broad | A request for more than the principal holds — a wider filter, another tenant's identifier, an elevated role, a larger page size | Denial, or narrowing to the granted scope; a silently honored over-broad request is a finding |

A boundary that cannot be probed for a class — no replay surface, no expiring
credential — is recorded as `not-run` with that reason, which is evidence about
the boundary rather than a gap in the pass.

## 4. Record Shape

The executed log is the artifact the gate hashes; the packet is the reading of it.
Store the raw transcript beside the record and bind it by sha256, so the claim and
the evidence cannot drift apart.

```text
probe_id | boundary | class | request (redacted) | observed response | status code or signal | observed_at | verdict
```

- `verdict` is `denied` when the boundary refused as expected, `allowed` when it
  did not, and `not-run` when the envelope or the surface withheld the probe, with
  the reason on the row.
- An `allowed` row is a Critical finding and triggers the stop condition in §6.
- The record carries the authorizing owner, the target instance, the engagement
  scope from `cso`, and the window in which probing was approved, so a log read
  six months later is still attributable.
- `result.status` on the typed `probe` record passes only when every row is
  `denied` or a reasoned `not-run`; a single `allowed` row is not a pass.

## 5. Redaction Rule

Redact as the log is written, never as a later pass: a raw transcript that reaches
the save path has already leaked, and deleting it afterwards does not un-write it.

- Replace credential values, bearer tokens, session identifiers, signing keys,
  personal data, and any response field the probe was not testing with a typed
  marker that names what was removed — `bearer-token`, `tenant-id`, `email` — so
  the row stays readable and the shape of the request survives.
- Keep what the evidence needs: the boundary, the class, the status code, the
  denial reason, and the timing. None of those require a secret.
- Never copy a response body wholesale "for completeness". The probe tested one
  thing; the log records that one thing.
- Scoped test credentials are redacted too. They are short-lived, not harmless,
  and the habit is what protects the pass where the distinction was missed.

## 6. Stop Conditions and Reporting

Stop the pass immediately — before any further request — on any of:

- a probe expected to be denied that is **allowed**;
- any observed state change, however small;
- any availability signal from the target: errors spreading beyond the probed
  endpoint, latency climbing, a dependency failing;
- any indication the target is not the instance that was authorized.

Then report to `review/cso` and the target's owner with the exact requests sent,
the observed effect, and the time window, before doing anything else. Do not
attempt to undo an observed effect: an undo guesses at the prior state and adds a
second unattributed change to the first. Remediation belongs to `cso`, which owns
the plan; this lens hands over what it observed.
