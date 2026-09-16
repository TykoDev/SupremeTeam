# Investigate Stub Contract

## Scope

Investigate owns the investigation pipeline boundary from an unexplained failure
through the `investigation-review` gate and the return of a bounded fix path to
the phase that owns the code. It runs when the failure mechanism is unknown; a
reproduced build-phase failure whose mechanism is already known belongs to
`build/debugger`.

## Stage Order

1. Investigate (scope and reproduction: the executed log, its environment and inputs)
2. Investigate (evidence chain: the observed trace from symptom to mechanism)
3. Investigate (mechanism: the surviving explanation and the hypotheses it displaced)
4. Investigate (bounded fix path: the smallest change and the phase that owns it)
5. Admiral (return to the owning phase, once the boundary approves the package)

## Required Inputs

- Symptom boundary, timing, impact, and the expected healthy behavior
- The phase that owns the affected code, so the fix path has a destination
- Logs, traces, captures, and configuration snapshots, plus the access needed to execute a reproduction
- Evidence-retention and environment constraints that bound what can be observed

## Gate Contract

The per-key table, the backing each key requires, and the self-check command are
stated once, in `references/workflow.md` — "Boundary contract" and "Manifest
assembly and self-check". This contract records only what a caller needs to know
before delegating.

- Investigate is the only owner that submits `investigation-review`, and the only owner of every evidence key at it, so a gap has no second owner to route to.
- Two keys are artifact-backed; four are stated in the package. No key at this boundary is waivable.
- An unreproducible failure returns `ESCALATE` with the uncertainty stated, never a package missing a key.
- The submitter self-checks the manifest mechanically before submitting, so a package that fails the machine is never sent.
- Maximum revisions per boundary: 2. All keys share one owner, so a REVISE packet is resolved in a single pass and resubmitted once with `--prior`; a third cycle escalates.

## Package Shape

- Executed reproduction log with environment and inputs
- Evidence chain from symptom to mechanism, each link naming its source and capture
- Mechanism statement with displaced hypotheses and a confidence level
- Bounded fix path with its owning phase and acceptance signal
- Residual uncertainty with the observation that would change the conclusion
- `investigation/manifest.json` at schema 2 (`boundary: investigation-review`, `owner: investigate`)

## Downstream Expectations

- `admiral` routes the approved package back to the owning phase; that phase schedules the change through its own pipeline and gates it at its own boundary.
- Investigate hands over a path, not a build: `ownership.yaml` records `implementation` and `review-verdict` among the artifacts it never writes.
- A fix path that outgrows the mechanism is narrowed before handoff rather than carried into the owning phase as scope.
