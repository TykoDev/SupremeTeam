# Workflow Protocol

## Contents

- Responsibility
- States and transitions
- Approval, release, and safety edges
- Gate boundaries
- Revision lineage
- Rewind rules
- Resume rules
- Failure rules

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
| GATE | the boundary's gatekeeper | A phase boundary requests an approval decision | RELEASE, COMPLETE, REVISE, BLOCKED, ESCALATE, SAFETY |
| RELEASE | land-and-deploy | The gate approved an externally visible delivery | COMPLETE, REVISE, BLOCKED, ESCALATE, SAFETY |
| SAFETY | guard or freeze | A guarded, frozen, destructive, or externally visible action is requested | INTAKE, DESIGN, BUILD, REVIEW, GATE, RELEASE, REVISE, BLOCKED, ESCALATE |
| REVISE | current artifact owner | A finding or changed input names a correction boundary | DESIGN, BUILD, REVIEW, GATE, RELEASE, BLOCKED, ESCALATE, SAFETY |
| ESCALATE | admiral | Evidence, ownership, or approval cannot be resolved safely | INTAKE, REVISE, BLOCKED |
| BLOCKED | current run owner | A required input, permission, or decision is unavailable | INTAKE, DESIGN, BUILD, REVIEW, GATE, RELEASE, REVISE, ESCALATE, SAFETY |
| COMPLETE | admiral | The approved delivery boundary and required release verification are recorded | no normal transition; reopen through REVISE with a new revision |

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
| `build-to-review` | `BUILD -> REVIEW` | build-management | gatekeeper-build, then gatekeeper-admiral |
| `review-to-delivery` | `REVIEW -> GATE -> COMPLETE` | code-chief | gatekeeper-code, then gatekeeper-admiral |
| `security-review` | security pipeline to `GATE -> COMPLETE` | cso | gatekeeper-admiral |
| `investigation-review` | investigation to the owning phase | investigate | gatekeeper-admiral |
| `qa-review` | testing pipeline to `GATE -> COMPLETE` | qa | gatekeeper-admiral |
| `skill-maker-to-delivery` | skill-maker pipeline to `GATE -> COMPLETE` | skill-maker | gatekeeper-admiral |
| `deploy-readiness` | `GATE -> RELEASE` | ship | gatekeeper-admiral |

The phase gatekeeper validates inside its sub-pipeline; `gatekeeper-admiral`
validates the same boundary as the cross-stage handoff. The security,
investigation, qa, skill-creation, and release pipelines run inside this state
machine, not beside it: their work occupies `DESIGN`-shaped or `BUILD`-shaped
states in their own phase directory and meets the gate at the boundary named
above. `gates.yaml` is the single source of truth for each boundary's required
evidence; a boundary or key added there must be reflected here and in
`docs/gatekeepers.md`.

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
revision cycles at two before escalating the dispute to the user.

## Resume rules

On resume, verify the run pointer, lock, owner, revision, referenced artifacts,
hashes, and evidence before selecting a state. Resume from the next incomplete
boundary, not from memory. If the state is stale, conflicting, corrupt, or
evidence-incomplete, enter `ESCALATE` or `BLOCKED` and preserve the diagnosis.

## Failure rules

- Missing or malformed input: record the exact gap and enter `REVISE` or `BLOCKED`.
- Conflicting evidence: preserve both sources, identify the disputed claim, and
  enter `ESCALATE` unless an owner resolves it.
- Unavailable tool, host, permission, or validator: report the failed probe and
  enter `ESCALATE`; absence of output is not proof.
- Write failure: preserve readable inline evidence, keep the prior revision, and
  enter `BLOCKED` unless a safe transient return is explicitly allowed.
- Destructive or externally visible action without current owner intent: deny
  the action and remain `BLOCKED`.

`COMPLETE` is a claim about the recorded boundary, not a reason to discard
lineage. Any post-completion change starts a new revision and re-enters through
`REVISE`.
