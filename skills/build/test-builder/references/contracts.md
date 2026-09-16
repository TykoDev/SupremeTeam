# Contract Reference

The full normative text of every contract `SKILL.md` lists under Required
Contracts. `SKILL.md` carries the operative rule so it binds at load time; this
file carries the reasoning, the record shapes, and the approval path each rule
depends on. Read it before quarantining anything, and before deciding what a
run that did not complete is allowed to claim.

## Contents

1. Evidence is the log
2. Quarantine record
3. Harness failure is not a test result
4. Shared severity
5. Proactive triggers
6. Save-protocol adherence

## Evidence Is The Log

`../../../gates.yaml` `evidence_type_rules.probe` is unambiguous about what the
`tests` key accepts at `build-to-review`: the test-runner log, as a hashed file
under the phase `evidence/` directory, carried by a typed record whose
`result.status` is `pass`. The same rule states the negative directly — a bare
count or claim is not evidence.

The practical consequence is an ordering rule. Capture the runner's own output
to a file as the suite runs, then hash the file, then describe it. Producing the
description first and the log afterwards invites a mismatch nobody notices: the
summary says 148 passed, the log says 147 passed and one skipped, and only the
log is hashed.

Bind the record to the source with `inputs`, a list of `{path, sha256}` entries
naming the implementation files the suite exercised. This is what makes stale
evidence fail loudly: when the implementation changes after the suite ran,
`check.py` reports input hash drift instead of accepting a green log that
describes code no longer in the package. A record without `inputs` passes the
mechanical check and loses that protection.

Artifacts are hashed byte-for-byte, so a log is never reformatted, trimmed, or
re-encoded after its hash is taken. A log too large to attach comfortably is
still attached; truncating it makes the evidence describe a run that did not
happen.

## Quarantine Record

Quarantining a test removes it from the pass/fail verdict. That silently mutates
effective coverage while the package still reads green, which is why it is an
owner decision rather than a testing convenience.

No test is quarantined without both of these:

1. **The build owner's recorded approval.** `build/build-management` owns scope
   for the phase; excluding a test narrows the scope it approved. Request the
   exclusion, name what stops being proven, and wait for the decision.
2. **A durable quarantine record**, one entry per excluded test:

| Field | Content |
| --- | --- |
| `test_id` | Module path plus test name, precise enough to re-run alone |
| `observed` | Failure rate and sample size from repeated identical runs, e.g. `2/5 over five consecutive runs` |
| `reason` | What is believed unstable, stated as a belief when it is one |
| `owner` | The named person or role accountable for the instability |
| `reopen_trigger` | The condition that ends the quarantine, e.g. `the session-expiry clock is injected rather than read from the host` |
| `coverage_lost` | The delivery slices and failure paths that become unverified |

The first five fields are deliberately the shape `../../../gates.yaml`
`finding_policy.major_deferral` requires of a deferred Major finding — owner and
reopen trigger — so the quarantine can travel into the package's findings record
unchanged instead of being restated in a weaker form.

A quarantine with no reopen trigger is a deletion with extra steps: nothing will
ever cause the test to return, and effective coverage has dropped with nobody
accountable. Refuse it and return the instability as an open Major finding
instead.

The probe record names the exclusion. `result.status: pass` then reads as "the
suite that ran passed", which is true, rather than "the suite passed", which is
not.

## Harness Failure Is Not A Test Result

A crashed runner, a misconfigured CI step, a missing interpreter, or an
unreachable test database produces no verdict in either direction. The
distinction matters because the two look identical in a terminal that ends
without a green line, and only one of them says anything about the code.

When the harness fails, record three things: the command attempted, the
discovery rung it came from, and the observed error text. Return that as an
infrastructure gap to `build/build-management`. Produce no `tests` evidence
until a clean run completes — an absent failure is not a pass, and
`evidence_type_rules` treats an unavailable or errored check as a data gap
rather than a clean result.

## Shared Severity

Grade every finding Critical | Major | Minor | Info — the four-tier model
clause 3 of `../../../execution-contract.md` defines, and the same vocabulary
`../../../gates.yaml` `finding_policy` enforces mechanically at the boundary.
Critical blocks every gate until a verified fix or an explicit not-applicable
reason. Major blocks unless verified, not-applicable with a reason, or
explicitly deferred with a named owner and a reopen trigger. Minor is recorded
and Info is preserved as context. An uncovered permission boundary graded
"medium" on a local scale arrives downstream as an unreadable risk.

## Proactive Triggers

Offer the next sensible action when the surrounding context clearly implies it
and the pass can advance safely without a prompt loop — a missing regression
case that follows directly from the changed surface, a suite worth re-running
after a fix. Clause 2 of `../../../execution-contract.md` bounds the offer: it is
suppressed while the current step, the scope, or the approval lineage is
unresolved, which is exactly the state a quarantine request or a harness failure
creates.

## Save-Protocol Adherence

When a Save Context block arrives with `Persistence active: yes`, deliverables
are written to the provided save path; saving is mandatory, not optional.
Resolve each destination with
`python skills/scripts/output_paths.py --run-id <run-id> --phase build --kind <evidence|reports> --name <file>`
rather than composing it, and never create nested per-specialist directories or
phase-state files — no declared path class covers them
(`../../../save-ownership.yaml`). When Save Context is absent or persistence is
inactive, the same deliverables are returned inline.
