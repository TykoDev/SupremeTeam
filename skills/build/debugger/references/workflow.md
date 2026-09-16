# Workflow Reference

The build-debugging sequence, the instrumentation ledger that makes teardown
checkable, how the `debug-report` is assembled and hashed, and how a REVISE that
reaches this stage is handled. `SKILL.md` states the order; this file states the
procedure.

## Contents

1. Build-debugging sequence
2. Instrumentation ledger
3. Report assembly
4. REVISE handling
5. Decision rules
6. Acceptance checklist
7. Collaboration notes

## Build-Debugging Sequence

1. Confirm the failing boundary, the current revision, and the environments or tests that expose the defect.
2. Gather the evidence set from logs, traces, diffs, failing assertions, and runtime checks before choosing a theory, redacting each excerpt as it is collected.
3. Reproduce or narrow the failure until one repair path is supported and adjacent regression risk is visible, recording every probe in the instrumentation ledger as it is added.
4. Prove the candidate fix with a before/after capture from the same command on the same revision, and confirm the original scenario fails again when the fix is reverted.
5. Tear the instrumentation down and reconcile the ledger against the returned diff before anything is packaged.
6. Package the `debug-report` so build-management and the gate see the root cause, the repair scope, and the residual risk without re-investigating.

## Instrumentation Ledger

The ledger is the only thing that makes teardown checkable rather than
remembered. Open it with the first probe and keep it in the working notes, not
in the source tree.

```text
| file                         | probe                          | question                                   | added  | removed |
| ---------------------------- | ------------------------------ | ------------------------------------------ | ------ | ------- |
| worker/parser.py             | log payload keys before parse  | which key is absent on the failing payload | 14:02  | yes     |
| worker/settings.py           | pool timeout 5s -> 60s         | is the timeout the trigger or a symptom    | 14:19  | yes     |
| scripts/_repro_empty.py      | scratch reproduction driver    | smallest input that reproduces             | 14:31  | yes     |
```

Reconciliation is a diff read. Run the repository's own diff over the returned
change set — `git diff --stat` for the shape, then `git diff -- <path>` for each
ledger file — and confirm every ledger row is absent from it. Hand back only
when the ledger and the diff agree; a row marked removed that still appears in
the diff is a blocking defect in this pass, not a note for the reviewer.

## Report Assembly

`../../../ownership.yaml` assigns debugger the `debug-report` artifact and places
its boundary at "before returning a fix path to build-management". Three
evidence lines are required, and `implementation` is listed under
`does_not_write`, so the fix path returns for `build/bob-the-builder` to land
rather than shipping from here.

| Evidence line | What satisfies it |
| --- | --- |
| Reproduction steps | The exact command, environment, revision, and input that produce the failure, reproducible by a reader who has only the report |
| Isolated cause | The mechanism, stated as the specific code or configuration behavior that produces the symptom — with the falsification that survived, not just the theory that fit |
| Bounded fix path | The smallest change that addresses the mechanism, its blast radius, and the specialist that owns landing it |

Resolve the destination with
`python skills/scripts/output_paths.py --run-id <run-id> --phase build --kind reports --name report_debug-<slug>.md`,
write the report there, and register its hash through a `session-memory`
checkpoint —
`python skills/harness/hooks/save_run.py checkpoint --run-id <run-id> --owner debugger --evidence <path>`.
Captured before/after output belongs under the phase `evidence/` directory,
resolved with `--kind evidence`, and is cited from the report by path.

Artifacts are hashed byte-for-byte, so a report or capture is never reformatted
after its hash is taken.

## REVISE Handling

A `REVISE` reaches this stage only through `build/build-management`, which owns
resubmission for the phase; `build/gatekeeper-build` never routes to a
specialist directly. The packet arrives already grouped by owner in
`revise_packet.by_owner` (`../../../gates.yaml` `revise_policy.one_packet`).

Take only the findings routed here. Fix them in one pass, re-run the before/after
capture on the same revision, re-reconcile the ledger against the new diff, and
hand the updated report back once. `revise_policy.cycle_cap` is 2; a third cycle
escalates to the build owner rather than resubmitting, because two failed
repairs against the same finding mean the mechanism was not the one identified.

## Decision Rules

- Prefer the smallest explanation that accounts for all surviving evidence, not the first explanation that matches part of the symptom.
- Keep mitigation separate from confirmed root cause when the evidence is incomplete.
- Treat environment drift and data-shape differences as part of the debug boundary, not background noise.
- Escalate when the credible fix requires design, architecture, or scope changes outside the assigned build slice.
- Redact logs, traces, and payload excerpts as they are collected, not as a pass before delivery, so an unredacted copy never reaches the report in the first place.
- Treat production data as out of reach until the owner authorizes a read-only, de-identified path in writing.
- Treat incoherent symptom data as a blocking input defect, not as noise to reason around.
- Report an untested hypothesis as untested; absence of a tool never eliminates a theory.

## Acceptance Checklist

- Failure boundary and affected revision are explicit.
- Evidence sources and reproduction steps are named and independently runnable.
- Root cause or bounded suspect set is supported, with the falsification that survived.
- Candidate fix is tested against the real failure mode, and the original scenario fails again when the fix is reverted.
- Every instrumentation edit is removed and the removal is visible in the returned diff.
- Attached logs, traces, and payload excerpts are redacted, with placeholders preserving the diagnostic shape.
- The `debug-report` exists as a file, is hashed, and its path is registered.
- Remaining regression risk or escalation conditions are clear.

## Collaboration Notes

This skill's collaboration surface is stated in `../SKILL.md` § Collaboration Surface.
