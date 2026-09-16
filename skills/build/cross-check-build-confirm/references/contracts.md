# Contract Reference

The full normative text of every contract `SKILL.md` lists under Required
Contracts. `SKILL.md` carries the operative rule so it binds at load time; this
file carries the reasoning and the boundary cases each rule depends on. Read it
before marking the first row, and before deciding whether a waived cell blocks a
package.

## Contents

1. Read-only boundary
2. Waived is present
3. Binding, not claiming
4. Contradictions stay visible
5. Shared severity
6. Save-protocol adherence

## Read-Only Boundary

This pass observes the package; it does not change it. Two facts fix that:
`../../../ownership.yaml` lists `implementation` under this skill's
`does_not_write`, and the declared tool surface grants no edit capability.

A gap discovered here is routed to `build/build-management`, which re-delegates
it to the specialist that owns the missing evidence — `build/bob-the-builder`
for an implementation artifact, `build/test-builder` for the `tests` log,
`build/health-check` for the `runtime` log, `build/security-builder` for the
findings record.

The reason is not procedural tidiness. This is the only independent check the
package gets between assembly and the gate, and independence is destroyed by a
single convenient edit: a pass that repairs what it finds is afterwards
reviewing its own work, and its "complete" carries no more information than the
build owner's own belief. The temptation is strongest on the smallest gaps — a
missing hash line, an unattached log — which is exactly where the habit forms.

Writing the completeness report itself is not an exception: that report is this
skill's own artifact, not part of the package under review.

## Waived Is Present

A cell holding a typed applicability record `{applicable: false, reason, scope,
decided_by}`, whose `reason` carries the sanctioned wording from
`../../../gates.yaml` `fallback_values`, **is evidence present**. The row is
proven by waiver and the package is not blocked.

The record is the waiver, not the wording. A bare string carrying that same
sanctioned wording is refused at schema 2: `skills/harness/gatekeeper/check.py`
matches it against `fallback_values` and then fails the package with `bare
fallback string not accepted at schema 2: <key> (use an applicability record)`.
`gates.yaml` `evidence_rules.manifest_schema_2` states the same rule.

Blocking a package whose waiver is a well-formed applicability record is a defect
in this pass, not a strict reading of it. `check.py` accepts that record and moves
on, so a completeness report that marks the same cell unproven contradicts the
machine the package is about to face and burns a REVISE cycle on nothing.

For a bare fallback string the direction reverses. The machine fails it, so
marking that cell unproven *agrees* with the machine, and passing the row is what
would cost the cycle. Artifact-backing is not the reason either way: at
`build-to-review` `artifact_evidence` lists only `tests` and `runtime`, so
`security_evidence` was never subject to that check.

What is waivable at `build-to-review` is narrow, and it is worth stating exactly:

| Key | Waivable here | Sanctioned value |
| --- | --- | --- |
| `security_evidence` | Yes | A typed applicability record whose `reason` reads `no trust-boundary change - security-builder not engaged`; the bare string is refused at schema 2 |
| `tests` | No | `fallback_values` carries no entry; a run that never happened cannot be waived |
| `runtime` | No | `fallback_values` carries no entry; an unverifiable runtime hard-blocks the boundary |
| `implementation` | No | Not waivable; a build with no implementation has nothing to confirm |
| `approved_design_revision` | No | Not waivable; without an approved upstream revision there is no baseline |
| `traceability` | No | Every submission carries the mapping |

Two checks apply to any waiver before the row is marked proven:

1. **Sanctioned for that key.** Only the exact strings under `fallback_values`
   count. Any other bare string is `unproven`, not waived — "N/A", "not
   relevant", and "see notes" are unproven cells wearing a waiver's clothes.
2. **Sanctioned at that boundary.** A boundary's `no_fallback` list removes a
   key's fallback there even when a global one exists.

Record the waiver reference on the row so the gatekeeper can audit the decision
rather than rediscover it.

## Binding, Not Claiming

A row is proven only when three things hold of the cited evidence:

1. **The path exists in the package.** Not in a summary, not in a sibling
   report — in the package, at the manifest-relative path the cell names.
2. **Its hash is registered.** The path appears in the manifest's
   `artifact_hashes` map, which is what makes it a shipped file rather than a
   reference to one.
3. **Its revision matches the package revision.** Evidence produced against an
   earlier revision describes code the package no longer contains; the gate
   reports this as input hash drift, and this pass is the cheaper place to
   catch it.

A package summary asserting that an artifact is attached is a claim about
evidence. Distinguishing the claim from the evidence is the entire value of this
pass — everything else in the report could be reconstructed by reading the build
owner's own notes.

## Contradictions Stay Visible

When two artifacts disagree — a manifest listing one image digest while the
deployment notes cite another, a test log timestamped before the implementation
commit, a security record naming a module the change set never touched — record
the disagreement, mark the affected rows `unproven` with reason `contradicted`,
and narrow the completeness statement.

Choosing the more plausible of the two silently converts an open question into
an unlogged decision. The reviewer downstream then inherits a clean report and
no way to know a judgement was made inside it. Reconciliation belongs to
`build/build-management`, which owns the package and can ask the owners.

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
Resolve the destination with
`python skills/scripts/output_paths.py --run-id <run-id> --phase build --kind reports --name report_completeness.md`
rather than composing it, and never create nested per-specialist directories or
phase-state files — no declared path class covers them
(`../../../save-ownership.yaml`). When Save Context is absent or persistence is
inactive, the same deliverables are returned inline.
