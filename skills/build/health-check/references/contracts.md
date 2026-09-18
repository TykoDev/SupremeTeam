# Contract Reference

The full normative text of every contract `SKILL.md` lists under Required
Contracts. `SKILL.md` carries the operative rule so it binds at load time; this
file carries the reasoning, the refusal cases, and the escalation path each rule
depends on. Read it before the first request of a pass, because two of these
rules govern whether that request may be sent at all.

## Contents

1. Probe target authorization
2. Secrets handling
3. Runtime has no fallback
4. Observed signal only
5. Shared severity
6. Proactive triggers
7. Save-protocol adherence

## Probe Target Authorization

The probe target is named in the handoff — environment, revision, and base
address — and the pass runs against that target and no other. Non-production is
the default: a local instance, an ephemeral environment, or a dedicated test
deployment.

Probing a production or otherwise shared environment requires explicit owner
authorization recorded in the handoff **before the first request**, because an
authenticated probe performs real work against real data under a real identity
and is indistinguishable from ordinary traffic once it lands. There is no
after-the-fact version of this permission: the request has already been served,
logged, rate-counted, and possibly billed.

Against any shared target, bound the sweep before it starts:

| Bound | What it fixes |
| --- | --- |
| Request budget | The total number of requests the pass may send, counted and reported |
| Rate ceiling | The maximum request rate, so the probe cannot resemble a load test |
| Stop condition | The observation that ends the sweep early — a hard failure, a budget exhaustion, or a degraded signal already sufficient to report |

Stop at the bound rather than widening it to chase a signal. A sweep that grew
because the result was interesting is a sweep nobody authorized.

A smoke flow that creates product data — an order, a message, an account — is
acceptable only when the handoff accepted that side effect on that target.
Record every side effect in the report, including ones that were expected, so
the owner can reverse them.

When the handoff names no target, or names one the authorization does not cover,
run nothing and return the gap. An unverified environment is an honest result;
an unauthorized probe is an incident the health pass created.

## Secrets Handling

Credentials are referenced by name only. Service accounts, tokens, and keys are
read from the environment or the configured secret source at the moment of use,
never inlined into a command, a config edit, or a report, and never reproduced
in output — including the readiness gap list, which names the missing reference
(the environment variable, the secrets path in the deployment config) and never
its content.

Scrub every artifact **before** it joins the evidence bundle. Startup logs,
probe transcripts, and environment dumps routinely carry connection strings,
bearer tokens, and session identifiers, so replace each value with a typed
placeholder that preserves the diagnostic shape and attach only the scrubbed
copy:

| Original shape | Placeholder |
| --- | --- |
| `Authorization: Bearer eyJ…` | `Authorization: Bearer <token:redacted>` |
| `postgres://svc:pw@host:5432/db` | `postgres://<user:redacted>:<password:redacted>@host:5432/db` |
| `Set-Cookie: sid=…` | `Set-Cookie: sid=<session:redacted>` |
| `AWS_SECRET_ACCESS_KEY=…` | `AWS_SECRET_ACCESS_KEY=<key:redacted>` |

Scrubbing after the fact fails in a specific way: the unscrubbed copy has
already been written to the phase directory, hashed, and possibly checkpointed,
and deleting it later leaves the digest pointing at content that existed. Scrub
as the log is captured.

A credential found exposed in a log or a running configuration is reported as a
Critical finding by location and type, routed to `build/security-builder` for
rotation, and the environment is not called healthy until rotation is confirmed.

## Runtime Has No Fallback

`../../../gates.yaml` `fallback_values` lists 9 keys that accept a sanctioned
applicability record instead of evidence (`taste-review` adds three more of its
own, admissible only there). `runtime` is not one of them: `fallback_values`
carries no entry for it, and `boundaries.build-to-review` lists it under both
`required_evidence` and `artifact_evidence`.

Three consequences follow, and all three are frequently softened by accident:

1. An unverifiable runtime **hard-blocks** `build-to-review`. The package cannot
   be submitted, and saying so is the deliverable.
2. No applicability record helps. "Not applicable — no runtime surface changed"
   is not a sanctioned value for this key and fails the artifact-backing check.
3. A passing test suite is not a substitute. `../../../pipelines.yaml` attaches no
   condition to the `runtime-health` stage precisely so that a green `tests` key
   never stands in for a startup log.

State the block plainly. A report that describes an unverified runtime as a
caveat invites the phase lead to submit anyway and take the mechanical failure
at the gate.

## Observed Signal Only

Every health claim cites a probe response, a log entry, or a dependency check,
with the observation attached. Configuration that declares a dependency is not
evidence that the dependency is reachable, and a deployment manifest that
declares a readiness probe is not evidence that the probe ever returned healthy.

The practical test: for each sentence in the report, name the line of captured
output it rests on. A sentence with no such line is a belief, and it is reported
as one or removed.

## Shared Severity

Grade every finding Critical | Major | Minor | Info — the four-tier model
clause 3 of `../../../execution-contract.md` defines, and the same vocabulary
`../../../gates.yaml` `finding_policy` enforces mechanically at the boundary.
Critical blocks every gate until a verified fix or an explicit not-applicable
reason. Major blocks unless verified, not-applicable with a reason, or
explicitly deferred with a named owner and a reopen trigger. Minor is recorded
and Info is preserved as context.

## Proactive Triggers

Offer the next sensible action when the surrounding context clearly implies it
and the pass can advance safely without a prompt loop — a rerun after a
dependency route is fixed, a narrower readiness claim the evidence already
supports. Clause 2 of `../../../execution-contract.md` bounds the offer: it is
suppressed while the current step, the scope, or the approval lineage is
unresolved, which is exactly the state an unauthorized target creates.

## Save-Protocol Adherence

When a Save Context block arrives with `Persistence active: yes`, deliverables
are written to the provided save path; saving is mandatory, not optional.
Resolve each destination with
`python skills/scripts/output_paths.py --run-id <run-id> --phase build --kind <evidence|reports> --name <file>`
rather than composing it, and never create nested per-specialist directories or
phase-state files — no declared path class covers them
(`../../../save-ownership.yaml`). When Save Context is absent or persistence is
inactive, the same deliverables are returned inline.
