# Workflow Reference

The build-confirmation sequence, the traceability matrix schema the completeness
report is built around, the status vocabulary that makes each row auditable, the
threshold that decides whether the package is complete, and how a resubmission
is re-judged. `SKILL.md` states the order; this file states the procedure.

## Contents

1. Build confirmation sequence
2. Traceability matrix schema
3. Status vocabulary
4. Completeness threshold
5. Report assembly
6. Resubmission handling
7. Decision rules
8. Acceptance checklist
9. Collaboration notes

## Build Confirmation Sequence

1. Establish the baseline: the approved decision set, the approved design revision, and the delivery slices the build claims to satisfy.
2. List the required build outputs for `build-to-review` and the owner of each, from `../../../gates.yaml` `evidence_owners`.
3. Build one matrix row per approved decision and bind each cell to a concrete artifact, a sanctioned waiver, or nothing.
4. Verify every binding against the package itself — path present, hash registered, revision matching — never against the summary that claims it.
5. Mark each row, attach a reason code to every unproven row, and preserve contradictions instead of reconciling them.
6. Publish the completeness report and route each gap to its owning specialist through `build/build-management`.

## Traceability Matrix Schema

One row per approved design decision. Six columns, in this order:

| Column | Content | Bound to |
| --- | --- | --- |
| `decision_id` | The approved design decision this row traces, by its id in the `decisions` artifact approved at `design-to-build` | The approved design revision |
| `changed_artifact` | Repository-relative path plus sha256, from the `implementation` change set | `build/bob-the-builder` |
| `test_evidence` | The `tests` log path plus the selector or test id that exercises this decision | `build/test-builder` |
| `security_evidence` | The finding id in the `security_evidence` findings record, or the sanctioned waiver for the key | `build/security-builder` |
| `status` | `proven` or `unproven` — the two values `../../../ownership.yaml` names for `build-traceability`, "proven and unproven status per row" | — |
| `reason` | Required on every `unproven` row: one reason code from the vocabulary below. On a row proven by waiver, the waiver reference | — |

Two notes on scope. The `runtime` key is package-level rather than
decision-level: it is checked once, as its own row with `decision_id: runtime`,
because a startup smoke log proves the package boots rather than proving any
single decision. A decision that legitimately touches no code — a documentation
decision, a deferred decision recorded for lineage — is still a row, marked
`proven` with its waiver reference rather than quietly omitted, because an
omitted row is indistinguishable from a decision nobody checked.

## Status Vocabulary

`status` carries exactly two values, because that is what `../../../ownership.yaml`
names for the `build-traceability` deliverable build-management authors from this
matrix: "proven and unproven status per row". `gates.yaml` checks `traceability`
for presence only — the key has no `evidence_types` entry — so the vocabulary is an
ownership contract, not a machine check. The nuance lives in `reason`, not in a
third status.

| Status | When |
| --- | --- |
| `proven` | Every required cell cites an artifact that is present, hashed, and revision-matched — or holds a typed applicability record for a waivable key, carrying the sanctioned wording in its `reason` |
| `unproven` | Any required cell fails that test |

Reason codes for an `unproven` row:

| Reason | Meaning | Typical fix owner |
| --- | --- | --- |
| `missing-artifact` | The evidence was never produced | The key's owner |
| `unbound-claim` | A summary cites evidence that is not in the package, or whose path is not in `artifact_hashes` | The key's owner |
| `revision-mismatch` | The evidence exists but was produced against a different revision | The key's owner |
| `contradicted` | Two artifacts disagree about version, scope, or lineage | `build/build-management` |
| `unsanctioned-waiver` | A bare string stands where an artifact or an applicability record is required — including a bare string with the sanctioned wording, which `check.py` refuses at schema 2 | The key's owner |
| `unverifiable` | The binding could not be checked because a required tool was unavailable | `build/build-management` |

## Completeness Threshold

The package is complete when **every row is `proven`**. There is no percentage.

This is not strictness for its own sake: `../../../gates.yaml`
`evidence_rules.required_evidence` requires every key at `build-to-review` to be
present and non-falsy, and `artifact_evidence` requires `tests` and `runtime` to
reference hashed paths. A package with one `unproven` row on a required key
fails the machine before a gatekeeper reads a word of it, so reporting it as
"95% complete" costs a REVISE cycle and tells the build owner nothing actionable.

Rows proven by waiver count toward completeness. Only `security_evidence` is
waivable at this boundary; `tests`, `runtime`, `implementation`,
`approved_design_revision`, and `traceability` carry no sanctioned fallback.

The report states the count both ways — rows proven, rows proven by waiver, rows
unproven — so the gatekeeper can see the shape of the package without recounting
the matrix.

## Report Assembly

The `completeness-report` artifact `../../../ownership.yaml` assigns to this skill
carries two evidence lines: promised scope versus delivered artifacts, and the
unresolved gaps. The matrix satisfies the first; the gap list satisfies the
second.

Resolve the destination with
`python skills/scripts/output_paths.py --run-id <run-id> --phase build --kind reports --name report_completeness.md`
and register its hash through a `session-memory` checkpoint —
`python skills/harness/hooks/save_run.py checkpoint --run-id <run-id> --owner cross-check-build-confirm --evidence <path>`.

`build/build-management` authors its own `traceability` key from this matrix
(`../../../gates.yaml`, `evidence_owners.build-to-review`), which is why the status
vocabulary is fixed to `proven` and `unproven`: the mapping travels into the
manifest without translation, and a translation step is where a row's meaning
quietly changes.

## Resubmission Handling

When the phase resubmits after a `REVISE`, re-run the matrix but re-judge only
the rows whose bound artifacts changed. Carry the prior status on unchanged
rows, mirroring how the gate treats `changed_evidence` with `--prior`
(`../../../gates.yaml` `revise_policy.delta_review`), and state explicitly which
previously unproven rows are now closed and which remain open.

`revise_policy.cycle_cap` is 2. A third cycle escalates to the build owner
rather than producing a third report, because a row unproven twice is usually a
scope problem rather than an evidence problem.

## Decision Rules

- Completeness claims must map to visible deliverables, row by row.
- Missing proof is a blocker even when the implementation looks finished locally.
- A sanctioned waiver is evidence present; blocking a correctly waived package is this pass failing, not the package.
- Contradictory build evidence stays visible until reconciled by the owner.
- Scope drift belongs with the build owner, not hidden inside the confirmation pass.
- Nothing in the package is edited here — the independence of this pass is what makes its result worth reading.

## Acceptance Checklist

- The baseline — approved decision set and approved design revision — is named.
- Every approved decision has a row; no decision is omitted as obviously fine.
- Every cell is bound to a path that exists, is hashed, and matches the package revision, or to a sanctioned waiver with its reference.
- Every `unproven` row carries a reason code and a named fix owner.
- Contradictions are recorded rather than resolved.
- The report states rows proven, rows proven by waiver, and rows unproven.
- The completeness report exists as a file, is hashed, and its path is registered.
- Downstream review readiness is stated narrowly and honestly.

## Collaboration Notes

This skill's collaboration surface is stated in `../SKILL.md` § Collaboration Surface.
