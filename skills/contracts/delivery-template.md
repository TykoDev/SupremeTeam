# Delivery Template

## Contents

- Responsibility
- Field requirements at RUN_COMPLETE
- Template
- Worked example
- Enforcement
- Failure paths

## Responsibility

Use this template for the final delivery record of one bounded change. It
connects the requested goal to changed artifacts and proof without replacing the
underlying evidence. `admiral` writes it at `RUN_COMPLETE` as the
`delivery-package` artifact it owns in [`../ownership.yaml`](../ownership.yaml),
and resolves its destination with `python skills/scripts/output_paths.py --kind
reports --run-id <run> --phase delivery`.

## Field requirements at RUN_COMPLETE

Nothing in the record is silently omitted. A section that does not apply carries
an explicit non-applicability value with its reason, the same shape
[gates.yaml](../gates.yaml) requires of a waived evidence key. An empty heading
is an incomplete record, not an inapplicable one.

| Field or section | Status at `RUN_COMPLETE` | Rule |
|------------------|--------------------------|------|
| `run_id` | required | The single run id carried across the lifecycle. |
| `submission_id` | conditional | Required when any boundary was submitted; `none` when the run closed without a gate. |
| `revision` | required | The integer revision this record describes. |
| `parent_revision` | required | `none` only on revision 1. |
| `owner` | required | The delivery owner, `admiral` for a governed run. |
| `status` | required | One of `candidate`, `revised`, `approved`, `blocked`, `complete`. |
| `preamble_tier` | required | `0`, `1`, `2`, or `3` with the blast-radius rationale that placed the run at that tier, per clause 1 of [`../execution-contract.md`](../execution-contract.md). Tier 0 is a recorded selection, never an omission. |
| `evidence_paths` | required | Workspace-relative paths; `none` is valid only when the run produced no evidence and the reason is stated under Residual risks. |
| Goal | required | The outcome requested and who requested it. |
| Scope | required | Both `Included` and `Non-goals`. |
| Traceability | conditional | Required when the run carried requirements or recorded decisions; otherwise one row stating that the change carried none. |
| Stack lock | conditional | Required when a design phase ran, or when any runtime, framework, dependency, interface, or target changed; otherwise `unchanged from revision <n>`. |
| Changed artifacts | required | One row per changed path with owner, revision, and SHA-256. `none` only for a terminal record that changed nothing. |
| Tests and proof | required | Every check run, including those that returned `unavailable`. |
| Claims, gaps, and proof | required | All three collections are exposed even when a collection is empty. |
| Gate verdicts | conditional | Required when any boundary was submitted; the verdict id and revision come from the verdict file the gatekeeper wrote. |
| Disputes | required | `none` is a valid value. |
| Residual risks | required | `none observed` is a valid value; an unknown is never hidden behind a success label. |
| Next action | required | One safe, owner-assigned action, or `none` when the delivery is terminal. |
| Return | required | Outcome, revision, evidence paths, and verdict. |

Optional throughout: additional rows in any table, and additional prose under a
heading. No field above is optional, and no heading is removable.

## Template

````markdown
# Delivery Report: [change or artifact]

## Run identity

- run_id: [run id]
- submission_id: [submission id]
- revision: [revision]
- parent_revision: [parent revision or none]
- owner: [delivery owner]
- status: [candidate, revised, approved, blocked, or complete]
- preamble_tier: [0, 1, 2, or 3, with the blast-radius rationale]
- evidence_paths: [workspace-relative paths]

## Goal
[The outcome requested and the user or run that requested it.]

## Scope
- Included: [bounded work completed]
- Non-goals: [explicitly excluded work]

## Traceability

| Requirement or decision | Artifact or behavior | Evidence path | Status |
|-------------------------|----------------------|---------------|--------|
| [id and statement] | [what implements it] | [path] | [proven/unproven] |

## Stack lock

| Concern | Locked value | Evidence |
|---------|--------------|----------|
| Runtime and language | [version] | [path or command] |
| Framework and dependencies | [versions] | [manifest or command] |
| Host and deployment target | [target] | [path or decision] |
| Interfaces and data formats | [versions or schemas] | [path] |

Do not introduce a new runtime, framework, dependency, interface, or target
without recording the decision and its owner here. The registry slug and overlay
digest come from [`../tech-stacks/registry.yaml`](../tech-stacks/registry.yaml).

## Changed artifacts

| Path | Change | Owner | Revision | SHA-256 |
|------|--------|-------|----------|---------|
| [workspace-relative path] | [added, changed, or removed] | [owner] | [n] | [digest] |

## Tests and proof

| Check | Command or method | Result | Evidence |
|-------|-------------------|--------|----------|
| [test or validation] | `[command]` | [pass, fail, or unavailable] | [path or output] |

## Claims, gaps, and proof

Use the canonical [Evidence Standards](evidence-standards.md) records so every
delivery claim has a scope, trust level, evidence path, and proof. Expose all
three collections here:

```yaml
claims: [claim records or ids]
gaps: [gap records or none]
proof: [proof records or paths]
```

## Gate verdicts

| Boundary | Verdict | Verdict id | Revision |
|----------|---------|------------|----------|
| [boundary from gates.yaml] | [APPROVED/REVISE/ESCALATE] | [verdict_id] | [n] |

## Disputes

[Open decisions, conflicting evidence, or "none". Name the decision owner and
the revision that introduced each dispute.]

## Residual risks

[Known gaps, denied checks, operational risks, and their severity. Do not hide
unknowns behind a success label.]

## Next action

[One safe, owner-assigned action, or "none" when the delivery is terminal.]

## Return

- Outcome: [completed, revised, blocked, or escalated]
- Revision: [revision]
- Evidence paths: [paths]
- Verdict: [APPROVED, REVISE, or ESCALATE]
````

## Worked example

One filled instance of the template above, for a documentation-only change that
passed `review-to-delivery` on its second revision. The SHA-256 values are
illustrative digests of the correct length and shape; a real record carries the
digests the run actually computed.

````markdown
# Delivery Report: gate-boundary table reconciled with gates.yaml

## Run identity

- run_id: run-2026-09-14-contracts
- submission_id: run-2026-09-14-contracts-r2
- revision: 2
- parent_revision: 1
- owner: admiral
- status: complete
- preamble_tier: 1 — documentation-only change inside skills/contracts/, no
  runtime, no product source, and no externally visible surface; blast radius is
  the contract layer's own readers, and the two parsing tests bound it.
- evidence_paths: skillset-saves/runs/run-2026-09-14-contracts/review/evidence/

## Goal
Reconcile the boundary table in `skills/contracts/workflow-protocol.md` with
`skills/gates.yaml` after a boundary rename, requested by the run owner at
intake.

## Scope
- Included: the boundary table, its guards column, and the two documentation
  mirrors the manifest validator checks.
- Non-goals: gates.yaml itself, the gatekeeper skills' own tables, and any
  change to required evidence keys.

## Traceability

| Requirement or decision | Artifact or behavior | Evidence path | Status |
|-------------------------|----------------------|---------------|--------|
| REQ-1 every boundary name in the contract table exists in gates.yaml | workflow-protocol.md gate table | review/evidence/test-gate-manifests.txt | proven |
| DEC-1 the guards column stays in this contract's state vocabulary | workflow-protocol.md reconciliation note | review/evidence/test-gate-manifests.txt | proven |

## Stack lock

| Concern | Locked value | Evidence |
|---------|--------------|----------|
| Runtime and language | unchanged from revision 1 (Python 3.13) | `python skills/scripts/check_runtime.py` |
| Framework and dependencies | unchanged from revision 1 (stdlib only) | skills/runtime-manifest.yaml |
| Host and deployment target | unchanged from revision 1 (no deployment target) | intake/report_grilling.md |
| Interfaces and data formats | unchanged from revision 1 | skills/gates.yaml |

## Changed artifacts

| Path | Change | Owner | Revision | SHA-256 |
|------|--------|-------|----------|---------|
| skills/contracts/workflow-protocol.md | changed | admiral | 2 | 2c14ad6a4981245ae4b25380d6351d1654b7e09d3e160a882ce4f0699ebf7d8c |

## Tests and proof

| Check | Command or method | Result | Evidence |
|-------|-------------------|--------|----------|
| gate table mirrors gates.yaml | `python -m unittest discover -s skills/harness/gatekeeper -p "test_*.py"` | pass | review/evidence/test-gate-manifests.txt |
| manifest cross-references | `python skills/scripts/validate_manifests.py` | pass | review/evidence/validate-manifests.json |
| rendered preview of the changed table | not run | unavailable | review/evidence/render-gap.md |

## Claims, gaps, and proof

```yaml
claims:
  - id: claim-1
    statement: every boundary name in the contract table resolves in gates.yaml
    scope: skills/contracts/workflow-protocol.md gate table, revision 2
    specificity: exact
    trust: observed
    evidence_paths: [review/evidence/test-gate-manifests.txt]
    proof: GateSpecContractTests.test_documented_boundary_table_matches_gate_spec
gaps:
  - id: gap-1
    missing_fact: whether the guards column reads correctly when rendered
    boundary: no renderer was available in this run
    impact: claim-1 is unaffected; presentation is unproven
    next_check: render the file and attach the capture
proof:
  - claim_id: claim-1
    method: unittest discovery over skills/harness/gatekeeper
    result: pass
    evidence_paths: [review/evidence/test-gate-manifests.txt]
```

## Gate verdicts

| Boundary | Verdict | Verdict id | Revision |
|----------|---------|------------|----------|
| review-to-delivery | APPROVED | verdict-review-to-delivery-r2 | 2 |

## Disputes

none

## Residual risks

Presentation of the changed table is unrendered (gap-1), severity low: the
parsing test reads the source text, not the rendered output, so a rendering
defect would not be caught by this run.

## Next action

none

## Return

- Outcome: completed
- Revision: 2
- Evidence paths: skillset-saves/runs/run-2026-09-14-contracts/review/evidence/
- Verdict: APPROVED
````

## Enforcement

No script parses this template and no test opens this file. Every rule above is
judgement, including the field table. Three facts bound that:

- `preamble_tier` is the only correctly shaped realization of clause 1 of
  [`../execution-contract.md`](../execution-contract.md) in this layer. The
  clause text itself is machine-checked: `../validation/test_catalog_contracts.py`
  (`ExecutionContractTests`) requires all six clauses verbatim in every bound
  orchestrator and gatekeeper. The recorded tier value in a delivery report is
  checked by nothing.
- The sibling field `Preamble tier` in
  [handoff-templates](handoff-templates.md)'s Save Context block is compared by
  `SaveContextParityTests`, but only across the copies that comparator
  recognizes — a file carrying the block's `Run ID` anchor line, which is 10 of
  the 89 files under `skills/` that contain the words "Save Context". It checks
  that the field name is present, never that a value was filled in, and this
  template is one of the 79 it skips.
- `Changed artifacts` digests, `Gate verdicts`, and the claims, gaps, and proof
  collections restate records that are enforced at the gate by
  [`check.py`](../harness/gatekeeper/check.py) — artifact hashes, verdict
  revision lineage, artifact-backed evidence. The restatement in this report is
  not compared against those records by anything.

A delivery report that contradicts the gate submission it describes is a defect
in the report: the submission and the verdict file are authoritative.

## Failure paths

- A required field cannot be filled. Record the field with the reason it is
  unknown and open a matching `gap` record. An omitted heading is not an empty
  value; it is an incomplete record and the delivery stays `blocked`.
- A check could not run. Record `unavailable` in Tests and proof with the failed
  probe. An unavailable check is never recorded as `pass` and never supports an
  `approved` status.
- A hash cannot be computed because the path is unreadable. Record the path, the
  read error, and the prior revision's digest, and enter `BLOCKED` under
  [workflow-protocol](workflow-protocol.md) rather than shipping a row with an
  empty digest.
- No gate was submitted but the change is externally visible. The record cannot
  carry `status: complete`; it carries `blocked` with the missing boundary named.
- This record and a gate verdict disagree about a revision or a digest. The
  verdict file wins, the report is corrected, and the correction is itself a new
  revision under the rewind rules in [workflow-protocol](workflow-protocol.md).
- The template and [evidence-standards](evidence-standards.md) appear to
  conflict about a claim record's fields. Evidence Standards is canonical for
  the record shape; this template only states where the collections appear.
