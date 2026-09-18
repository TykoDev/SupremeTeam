# Contract Reference

The full normative text of every contract `SKILL.md` lists under Required
Contracts. `SKILL.md` carries the operative rule so it binds at load time; this
file carries the reasoning and the refusal cases each rule depends on. Read it
before selecting a stage, and before applying any fix inside a `security`
engagement.

## Contents

1. Stage selection before work
2. Authorized fixes only
3. Secrets handling
4. Proof, not assertion
5. Vendoring detection
6. Shared severity
7. Proactive triggers
8. Save-protocol adherence

## Stage Selection Before Work

`Phase` and `Return boundary` are read before anything is scanned or changed,
because the three stages owe three different deliverables and none substitutes
for another.

The design checkpoint is **forward-looking**: it names the trust boundaries the
design introduces or moves and the controls the build owes for each one, before
any code exists. Nothing can be graded at this point, and a seed that tries to
grade something has misread the stage.

The build checkpoint is **evidential**: it grades what the implementation
actually does against those seeded controls. It needs the seed as its baseline,
and without one it grades against an opinion formed on the spot.

The remediation stage is **bounded application**: `review/cso` has already
scoped, threat-modelled, and triaged, and the deliverable is the authorized
fixes plus proof each one closed what it was meant to close.

Confusing them produces two recognizable failures — a seed with no controls to
check, or a build checkpoint with no baseline to check against. An ambiguous or
missing handoff is returned to the delegating owner rather than guessed; one
question costs a round trip, and a guess costs the boundary its evidence.

## Authorized Fixes Only

In the `security` pipeline security-builder holds no gate. `review/cso` owns the
`security-review` boundary, sets the scope and the threat model, triages, and
submits the package. `../../../pipelines.yaml` places `remediation` as a
conditional stage of that pipeline, run when fixes are authorized.

Apply only the fixes `review/cso` authorized, and keep them inside the scoped
surface. A fix outside the set — however obviously correct — is recorded as a
finding with its recommended fix and returned for triage, not applied.

The reason is that the authorized set is what was reviewed. An engagement that
quietly widens delivers changes nobody triaged under a report that says
everything was triaged, and the widening is always locally reasonable: the
adjacent endpoint had the same flaw, the same helper was called from two places,
the fix was two lines. Escalate any fix that would change auth, tenancy, or
data-handling behavior beyond the scoped surface, because those three are where
a locally reasonable change alters the system's actual security model.

## Secrets Handling

A secret, token, API key, or credential encountered during dependency scanning
or config inspection — a token embedded in a lockfile, a credential in a
committed config, a key in a generated file — is never echoed, logged, or
included in any output or report.

Flag its presence as a Critical finding: location, type, and how it was
encountered, with the value withheld. Recommend immediate rotation. Treat the
build as not security-clean until rotation is confirmed **and** the credential is
removed from the source.

Both halves matter and the second is routinely skipped. Rotation without removal
leaves a dead credential in history that teaches the next reader the pattern is
acceptable; removal without rotation leaves a live credential in every copy
already taken.

## Proof, Not Assertion

Every claimed remediation is tied to a focused rerun, a scan record, or a direct
proof on the affected boundary. The proof exercises the exploit path, not the
code near it: a unit test on the sanitizer proves the sanitizer, while the
finding was that the sanitizer was never called.

`../../../gates.yaml` `finding_policy` enforces the same thing mechanically — a
Critical must be verified or not-applicable with a reason, and a Major must be
verified, not-applicable with a reason, or deferred with a named owner and a
reopen trigger. A finding marked closed with no rerun behind it fails at the
gate and costs a REVISE cycle, having already cost the reader their confidence
in the rest of the record.

Where a scanner produces the proof, record it with
`python skills/scripts/scan_record.py --out <path> --input <manifest> -- <scanner command>`
so the record carries the tool, the command, the exit code, the observed time,
and the inputs bound by sha256. A scan that could not run is recorded with
`--no-run`, which types the gap instead of narrating it;
`evidence_type_rules.scan` treats `unavailable` or `error` as a data gap and
never as a clean scan.

## Vendoring Detection

**`build/build-management` owns the classification rule; this section owns the
treatment.** Classify with
`../../build-management/references/contracts.md` § The Contracts → *Vendoring
detection*: a changed path is non-first-party when it sits under a vendor or
generated root, when its name or header marks it machine-produced, or when it
entered the diff through a package manager or codegen step rather than an
authored edit. Classifying by a local rule instead is how the same path ends up
first-party in the build record and vendored in the security record.

Having classified it, detect generated, vendored, or third-party imported content
and treat it with tighter review rules than first-party changes. These surfaces carry code nobody
on the team wrote, are regenerated or replaced wholesale, and are where a
transitive advisory lands without any first-party diff to notice it. Mark them
explicitly in the record and narrow the security claim to the boundaries
actually reviewed.

## Shared Severity

Grade every finding Critical | Major | Minor | Info — the four-tier model
clause 3 of `../../../execution-contract.md` defines, and the same vocabulary
`../../../gates.yaml` `finding_policy` enforces mechanically at the boundary.
Critical blocks every gate until a verified fix or an explicit not-applicable
reason. Major blocks unless verified, not-applicable with a reason, or
explicitly deferred with a named owner and a reopen trigger. Minor is recorded
and Info is preserved as context. The `findings` typed record carries the same
four values, so a local scale has to be translated at the boundary and a
translation is where a severity quietly drops.

## Proactive Triggers

Offer the next sensible action when the surrounding context clearly implies it
and the pass can advance safely without a prompt loop — a rerun after a
dependency is pinned, a seeded control worth checking now that the code exists.
Clause 2 of `../../../execution-contract.md` bounds the offer: it is suppressed
while the current step, the scope, or the approval lineage is unresolved, which
is exactly the state an ambiguous handoff or an unauthorized fix creates.

## Save-Protocol Adherence

When a Save Context block arrives with `Persistence active: yes`, deliverables
are written to the provided save path; saving is mandatory, not optional.
Resolve each destination with
`python skills/scripts/output_paths.py --run-id <run-id> --phase <design|build|security> --kind <reports|evidence> --name <file>`
rather than composing it, and never create nested per-specialist directories or
phase-state files — no declared path class covers them
(`../../../save-ownership.yaml`). When Save Context is absent or persistence is
inactive, the same deliverables are returned inline.
