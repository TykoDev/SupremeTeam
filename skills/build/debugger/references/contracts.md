# Contract Reference

The full normative text of every contract `SKILL.md` lists under Required
Contracts. `SKILL.md` carries the operative rule so it binds at load time; this
file carries the reasoning, the ledger format, and the refusal cases each rule
depends on. Read it before the first probe is added and before any reproduction
that reaches for real data.

## Contents

1. Instrumentation teardown
2. Evidence redaction
3. Production-data boundary
4. Before/after evidence
5. Atomic commit per fix
6. Shared severity
7. Save-protocol adherence

## Instrumentation Teardown

Record every probe the moment it is added. A probe is anything that exists only
to observe the failure: a temporary log line, an extra trace, a widened timeout,
a debug-only branch, a disabled assertion, a scratch script, a pinned test
fixture. The ledger is opened with the first probe, not reconstructed at the
end.

| Ledger field | Content |
| --- | --- |
| `file` | The path the probe was added to, or the scratch file created |
| `probe` | What was added, in one line |
| `question` | The question it answers — a probe with no question is not a probe, it is a change |
| `added` | When, so the observer effect can be lined up against the timeline |
| `removed` | The removal, confirmed against the returned diff rather than from memory |

Before the fix is handed back, remove every ledger entry and prove the removal
against the returned diff: the delivered change set contains the repair and
nothing that existed only to observe the failure.

`Atomic commit per fix` is exactly why this is mandatory rather than tidy. A
clean, rollback-safe commit is the thing that makes a stray probe riding inside
it invisible at review — the reviewer reads a small, coherent fix and approves
it, and the widened timeout ships with it. Reconciliation is a diff read, not a
recollection: walk the returned diff and the ledger together, and hand back only
when each accounts for the other.

An observation that genuinely belongs in the product is promoted to a deliberate
logging change with its own justification and its own review, never left behind
as residue. The test is whether it would have been written on purpose.

## Evidence Redaction

Redact every log, stack trace, request or response payload, environment dump,
and configuration excerpt before it is attached to a debug report. Traces and
request logs routinely carry bearer tokens, session and cookie values, API keys,
connection strings, and personal data, and a debug report travels further than
the failure ever did — into a package, a gate record, a review thread, and an
archive that outlives the environment.

Replace each sensitive value with a typed placeholder that preserves the
diagnostic shape, so the causal chain still reads while the value stays out of
it:

| Original | Placeholder | What survives |
| --- | --- | --- |
| `Authorization: Bearer eyJhbGciOi…` | `Authorization: Bearer <token:redacted>` | that the header was present and well-formed |
| `user=alice@example.com` | `user=<email:redacted>` | that a user identifier was bound to the request |
| `account_id=7731004` | `account_id=<account-id:redacted>` | that the field participated in the failing path |
| `postgres://svc:pw@host/db` | `postgres://<user:redacted>:<password:redacted>@host/db` | the host and database, which are the diagnostic part |

Quote only the payload fields the root cause actually depends on. Describe
rather than paste a value that redaction would destroy — "the signature header
was 43 bytes where the verifier expects 44" says everything the diagnosis needs
without reproducing either value.

A credential found exposed in the evidence is reported as a Critical finding by
location and type and routed to `build/security-builder` for rotation.

## Production-Data Boundary

Reproducing against production data requires explicit owner authorization
recorded in the handoff, and the authorized path is read-only and de-identified
— a restored snapshot or a masked copy, never a write against the live store and
never a live session used as a fixture.

The order is fixed:

1. **Attempt the de-identified route first** and state what it could not
   surface. Most defects reproduce on masked data; the ones that do not are
   informative about the cause.
2. **When only live-shaped data reproduces the defect**, name the fields that
   force it — a specific encoding, a legacy row shape, a locale, a volume — and
   request the authorization *before* the replay rather than after.
3. **Keep the authorized replay bounded** to the records the causal chain needs,
   and record which records were read.

Absent authorization, record the reproduction gap and return it. An unauthorized
production replay is a larger incident than the defect being chased, and the
urgency of the defect is the argument that makes it feel reasonable — which is
why the rule does not bend for urgency.

## Before/After Evidence

Capture observable state before and after each intervention, from the same
command on the same revision, so improvements are verified instead of asserted.
Two captures taken from different commands, different environments, or different
revisions prove nothing about the intervention between them; they prove only
that two runs differed.

The falsification check belongs here too: the original failing scenario passes
after the fix, **and** it fails again when the fix is reverted. A fix that
cannot be un-fixed was probably not the cause.

## Atomic Commit Per Fix

Keep each fix isolated, explain what changed, and preserve easy rollback
boundaries even when several issues are found. One commit carrying three
unrelated repairs cannot be reverted for the one that turned out wrong, and it
is also the commit shape a leftover probe hides most easily inside — see
Instrumentation teardown.

## Shared Severity

Grade every finding Critical | Major | Minor | Info — the four-tier model
clause 3 of `../../../execution-contract.md` defines, and the same vocabulary
`../../../gates.yaml` `finding_policy` enforces mechanically at the boundary.
Critical blocks every gate until a verified fix or an explicit not-applicable
reason. Major blocks unless verified, not-applicable with a reason, or
explicitly deferred with a named owner and a reopen trigger. Minor is recorded
and Info is preserved as context.

## Save-Protocol Adherence

When a Save Context block arrives with `Persistence active: yes`, deliverables
are written to the provided save path; saving is mandatory, not optional.
Resolve each destination with
`python skills/scripts/output_paths.py --run-id <run-id> --phase build --kind <reports|evidence> --name <file>`
rather than composing it, and never create nested per-specialist directories or
phase-state files — no declared path class covers them
(`../../../save-ownership.yaml`). When Save Context is absent or persistence is
inactive, the same deliverables are returned inline.
