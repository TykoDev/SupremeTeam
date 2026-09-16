# Workflow Protocol

## Contents

- Responsibility
- States and transitions
- Approval, release, and safety edges
- Gate boundaries
- Gate table drift and what is compared
- Revision lineage
- Rewind rules
- Resume rules
- Enforcement
- Failure paths

## Responsibility

This contract defines the lifecycle state machine, revision lineage, and safe
behavior when work is rewound, resumed, or unable to proceed.

## States and transitions

| State | Owner | Enter when | Allowed next states |
|-------|-------|------------|---------------------|
| INTAKE | admiral | A request or resumable run is identified | DESIGN, BUILD, REVIEW, BLOCKED, ESCALATE, SAFETY |
| DESIGN | commander | The intake boundary is accepted | BUILD, REVISE, BLOCKED, ESCALATE, SAFETY |
| BUILD | build-management | The design contract is approved | REVIEW, REVISE, BLOCKED, ESCALATE, SAFETY |
| REVIEW | code-chief | A build or changed artifact is submitted | GATE, COMPLETE, REVISE, BLOCKED, ESCALATE, SAFETY |
| GATE | the boundary's gatekeeper | A phase boundary requests an approval decision | DESIGN, RELEASE, COMPLETE, REVISE, BLOCKED, ESCALATE, SAFETY |
| RELEASE | land-and-deploy | The gate approved an externally visible delivery | COMPLETE, REVISE, BLOCKED, ESCALATE, SAFETY |
| SAFETY | guard or freeze | A guarded, frozen, destructive, or externally visible action is requested | INTAKE, DESIGN, BUILD, REVIEW, GATE, RELEASE, REVISE, BLOCKED, ESCALATE |
| REVISE | current artifact owner | A finding or changed input names a correction boundary | DESIGN, BUILD, REVIEW, GATE, RELEASE, BLOCKED, ESCALATE, SAFETY |
| ESCALATE | admiral | Evidence, ownership, or approval cannot be resolved safely | INTAKE, REVISE, BLOCKED |
| BLOCKED | current run owner | A required input, permission, or decision is unavailable | INTAKE, DESIGN, BUILD, REVIEW, GATE, RELEASE, REVISE, ESCALATE, SAFETY |
| COMPLETE | admiral | The approved delivery boundary and required release verification are recorded | no normal transition; reopen through REVISE with a new revision |
| TASTE_ACTIVE | taste | Preference management begins with bounded scope and intent | TASTE_GATE_PENDING, BLOCKED, ESCALATE, SAFETY |
| TASTE_GATE_PENDING | taste | A taste package is ready for `taste-review` | COMPLETE, DESIGN, BUILD, REVIEW, RELEASE, TASTE_GATE_REVISE, BLOCKED, ESCALATE, SAFETY |
| TASTE_GATE_REVISE | taste | The taste gate returns a bounded correction | TASTE_ACTIVE, TASTE_GATE_PENDING, BLOCKED, ESCALATE, SAFETY |

The transition record names `from_state`, `to_state`, `run_id`, `revision`,
`owner`, `reason`, `evidence_paths`, and `next_action`. An invalid transition is
a protocol failure and returns `ESCALATE`; it is never silently coerced.

## Approval, release, and safety edges

`REVIEW -> GATE` is the normal review boundary. A `REVIEW -> COMPLETE` shorthand
is valid only when the same revision already contains a gatekeeper `APPROVED`
record; otherwise it passes through `GATE` first.

The exact external sequence is
`REVIEW -> GATE -> SAFETY -> GATE -> RELEASE -> COMPLETE`. A gate-approved
externally visible delivery may enter `SAFETY`; an explicit safety allow returns
to the source `GATE`, after which `GATE -> RELEASE` is allowed and
`RELEASE -> COMPLETE` requires release verification.

`GATE -> COMPLETE` applies to a delivery with no external release.
`GATE -> REVISE` handles missing proof, `GATE -> BLOCKED` handles missing
permission or required owner intent, and `GATE -> ESCALATE` handles conflicting
evidence or a failed validator. No gate failure is approval.

`GATE -> DESIGN` is the one gate edge that is an approval rather than a
correction: a design-shaped boundary whose package selects a design artifact
returns it to `DESIGN` for the phase to adopt. `redesign-review` is that case,
and `gates.yaml` guards it with `REDESIGN (design-shaped) -> GATE -> DESIGN with
the chosen variant, or COMPLETE`. It is the same shape as the
`TASTE_GATE_PENDING -> DESIGN` handoff this table already declares, where an
approved taste package returns its effective profile to a consuming pipeline. It
never substitutes for `GATE -> REVISE`: a package that failed still enters
`REVISE`.

`RELEASE -> COMPLETE` requires `land-and-deploy` to record the release result,
post-release verification, and rollback evidence. A changed package enters
`REVISE`; a deployment blocker enters `BLOCKED`; an uncertain rollout enters
`ESCALATE`.

The safety edge may be entered from any non-terminal state before the action it
protects. Select `guard` when intent and the write boundary must be checked
together; select `freeze` when a path boundary must be locked. On an explicit
allow, `SAFETY` returns to its source state. On a denial it transitions to
`BLOCKED`; on ambiguous intent, an invalid boundary, or an unavailable check it
transitions to `ESCALATE`. A safety denial never advances to `RELEASE` or
`COMPLETE`.

## Gate boundaries

The states above and the boundaries in the canonical
[`../gates.yaml`](../gates.yaml) are one system: every `GATE` entry names the
boundary it validates, and every boundary guards a specific transition.

| Boundary | Guards | Submitter | Validator |
| --- | --- | --- | --- |
| `design-to-build` | `DESIGN -> BUILD` | commander | gatekeeper-design, then gatekeeper-admiral |
| `redesign-review` | `REDESIGN (design-shaped) -> GATE -> DESIGN or COMPLETE` | redesign | gatekeeper-design, then gatekeeper-admiral |
| `build-to-review` | `BUILD -> REVIEW` | build-management | gatekeeper-build, then gatekeeper-admiral |
| `review-to-delivery` | `REVIEW -> GATE -> COMPLETE` | code-chief | gatekeeper-code, then gatekeeper-admiral |
| `security-review` | security pipeline to `GATE -> COMPLETE` | cso | gatekeeper-admiral |
| `investigation-review` | investigation to the owning phase | investigate | gatekeeper-admiral |
| `qa-review` | testing pipeline to `GATE -> COMPLETE` | qa | gatekeeper-admiral |
| `taste-review` | `TASTE_ACTIVE -> TASTE_GATE_PENDING -> COMPLETE` or consuming pipeline | taste | gatekeeper-admiral |
| `skill-maker-to-delivery` | skill-maker pipeline to `GATE -> COMPLETE` | skill-maker | gatekeeper-admiral |
| `deploy-readiness` | `GATE -> RELEASE` | ship | gatekeeper-admiral |

The phase gatekeeper validates inside its sub-pipeline; `gatekeeper-admiral`
validates the same boundary as the cross-stage handoff. The taste pipeline uses
its explicit `TASTE_*` states: approval at
`TASTE_GATE_PENDING` transitions either to `COMPLETE` for preference-only work
or returns the immutable effective-profile handoff to the applicable consuming
pipeline; revision returns to `TASTE_GATE_REVISE` and then `TASTE_ACTIVE`.
The redesign, security, investigation, qa, skill-creation, and release pipelines run
inside this state machine, not beside it: their work occupies `DESIGN`-shaped or `BUILD`-shaped
states in their own phase directory and meets the gate at the boundary named
above. `gates.yaml` is the single source of truth for each boundary's required
evidence; a boundary or key added there must be reflected here and in
`docs/gatekeepers.md`.

## Gate table drift and what is compared

The boundary table above is drift-tested. `GateSpecContractTests.test_documented_boundary_table_matches_gate_spec`
in [`../harness/gatekeeper/test_gate_manifests.py`](../harness/gatekeeper/test_gate_manifests.py)
reads the table, extracts the backticked name in each row's first cell, and
requires that set to equal the boundary set in `gates.yaml` exactly. A boundary
added to `gates.yaml` and not added here fails that test, and so does a row here
naming a boundary the spec does not define. The same test holds
`docs/gatekeepers.md` to the stricter standard of matching every required
evidence key, and a companion test holds the four gatekeeper skills to it.

Only the first cell is compared. The rest of the table is not:

| Column | Compared against gates.yaml | Consequence |
|--------|-----------------------------|-------------|
| Boundary | Yes, as a name set | A missing or invented boundary fails the test. |
| Guards | No | The wording may drift silently; it is prose in this contract's state vocabulary. |
| Submitter | No | Verified equal to the `submitter` field of every boundary as of this revision, but nothing keeps it so. |
| Validator | No | Derived from the phase-gatekeeper assignment, which `gates.yaml` does not carry. |

The Guards column is a deliberate paraphrase, not a copy. Two kinds of
difference exist today and both are intentional:

- Four cells abbreviate the spec wording. `redesign-review` drops "with the
  chosen variant"; `security-review`, `investigation-review`, and `qa-review`
  render the spec's arrow form as prose and shorten the pipeline names
  ("testing pipeline" for the spec's "testing-and-qa pipeline",
  "the owning phase" for the spec's "the owning phase (DESIGN, BUILD, or
  REVIEW)").
- One cell uses different state names. `gates.yaml` guards `taste-review` with
  "TASTE -> GATE -> COMPLETE or consuming pipeline"; this table writes the same
  edge as `TASTE_ACTIVE -> TASTE_GATE_PENDING -> COMPLETE` or consuming
  pipeline. `TASTE` in the spec is the phase name; `TASTE_ACTIVE` and
  `TASTE_GATE_PENDING` are the explicit states this contract declares in States
  and transitions, and `GATE` in the spec is the moment `TASTE_GATE_PENDING`
  submits. The two say the same thing in two vocabularies, and this contract
  keeps its own because its state machine is what the rewind and resume rules
  operate on.

Where a reader needs the exact guarded transition for a gate decision,
`gates.yaml` is authoritative and this column is a reading aid.

## Revision lineage

Keep one `run_id` across a lifecycle. Each accepted state change or artifact
change increments the integer revision and records its `parent_revision`.
Preserve superseded artifacts, hashes, verdicts, and evidence paths. A handoff
may reference only its own revision or an explicitly named predecessor. Mixed,
missing, or stale revisions invalidate dependent verdicts.

## Rewind rules

When an upstream artifact or evidence item changes, find the earliest boundary
that depended on it. Rewind there, invalidate only dependent verdicts, and keep
unaffected evidence. Do not merge two histories or advance past an unresolved
load-bearing gap. A failed review normally enters `REVISE` at the smallest
owner-controlled boundary; a changed design rewinds to `DESIGN`. Cap cross-stage
revision cycles at two before escalating the dispute to the user. A `REVISE` is
one packet: every finding from the pass grouped by owner
(`gates.yaml` `revise_policy`); the lead fixes owner groups in parallel,
resubmits once, and the gate re-judges only the keys whose evidence changed.

## Resume rules

On resume, verify the run pointer, lock, owner, revision, referenced artifacts,
hashes, and evidence before selecting a state. Resume from the next incomplete
boundary, not from memory. If the state is stale, conflicting, corrupt, or
evidence-incomplete, enter `ESCALATE` or `BLOCKED` and preserve the diagnosis.

## Enforcement

| Rule | Backing |
|------|---------|
| Every boundary name in the gate table exists in `gates.yaml`, and every boundary in `gates.yaml` appears here | Machine-checked by `GateSpecContractTests.test_documented_boundary_table_matches_gate_spec`. |
| A boundary's required evidence is present, artifact-backed, and hash-matched before approval | Machine-checked by [`../harness/gatekeeper/check.py`](../harness/gatekeeper/check.py) at submission. |
| Mixed or stale revisions invalidate dependent verdicts | Machine-checked: `check.py` reports `mixed_revisions` and `stale verdict revision` and exits non-zero. |
| An unchanged revision whose artifact hashes moved is drift | Machine-checked: `check.py` reports `idempotency_drift`. |
| A `REVISE` is one packet with a cycle cap of two | Partly machine-checked: `validate_manifests.py` requires `revise_policy` to declare `self_check`, `one_packet`, `parallel_fix`, `delta_review`, and `cycle_cap: 2`; whether a given run honors the packet discipline is judgement. |
| One run pointer, one lock, one owner, monotonic revisions on resume | Machine-checked by `../harness/hooks/save_run.py` and exercised in `../validation/test_save_contracts.py`: a revision conflict, a competing session pin, a wrong owner, and an interrupted checkpoint are all refused. |
| The state table and the allowed-transition sets | Partly machine-checked: `../validation/test_orchestration.py` `GuardedTransitionTests` parses this table and requires every `gates.yaml` `guards` string to name only states it declares and to walk only edges it allows. Whether a *run* takes an allowed edge is still judgement. |
| The approval, release, and safety edges | Judgement. No parser reads that prose, and an invalid transition is caught only by the owner applying this contract. |
| The Guards, Submitter, and Validator columns | Judgement. See Gate table drift and what is compared. |
| Rewind rules, resume rules, and the failure paths below | Judgement, with the exception of the lock and revision mechanics named in this table. |

## Failure paths

- Missing or malformed input: record the exact gap and enter `REVISE` or `BLOCKED`.
- Conflicting evidence: preserve both sources, identify the disputed claim, and
  enter `ESCALATE` unless an owner resolves it.
- Unavailable tool, host, permission, or validator: report the failed probe and
  enter `ESCALATE`; absence of output is not proof.
- Write failure: preserve readable inline evidence, keep the prior revision, and
  enter `BLOCKED` unless a safe transient return is explicitly allowed.
- Destructive or externally visible action without current owner intent: deny
  the action and remain `BLOCKED`.
- A rule in this contract conflicts with `gates.yaml`: the spec decides the
  boundary contract and this document decides the state machine. Where the two
  overlap, the spec wins on required evidence, submitter, and the guarded
  transition; this contract wins on state names, allowed transitions, rewind,
  and resume.
- A state is reachable here but has no owner on the roster: the transition is
  invalid. Enter `ESCALATE` rather than assigning the nearest available owner.

`COMPLETE` is a claim about the recorded boundary, not a reason to discard
lineage. Any post-completion change starts a new revision and re-enters through
`REVISE`.
