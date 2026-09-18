# Workflow Reference

Read this for the request-by-request sequence behind `../SKILL.md`. Operation
mechanics — flags, results, exit codes, reclaim, rollback — live in
`run-record.md`.

## Contents

1. Continuity sequence
2. The four request kinds
3. Decision rules
4. Acceptance checklist
5. Contract notes
6. Collaboration notes

## Continuity Sequence

1. Determine whether the request is a checkpoint, a learning write, a resume, or a lookup against prior learnings. The four are enumerated below; only the first three write.
2. Write core run state only through `../../harness/hooks/save_run.py` operations, following `../../save-protocol.md` and `../../save-ownership.yaml`. Session-memory is the declared sole writer of that class: no other skill writes those six paths, and a skill that needs one changed asks for the write rather than making it.
3. Resolve every supplemental report destination with `python skills/scripts/output_paths.py --run-id <run-id> --phase <phase> --kind reports --name <file> --mkdir`, confirm the printed path is inside the run's phase directory, and write only there. Save only the durable state needed for safe continuation: current boundary, active artifacts, blockers, and the next intended action.
4. Normalize learnings into short searchable entries with evidence and confidence so later sessions can query them quickly.
5. On resume, reload only the verified artifacts and notes relevant to the immediate next step, then surface any drift or missing state.
6. Read `result` on every write before reporting an outcome. `ok`, `degraded`, and `refused` lead to three different reports, and a `degraded` write that is announced as a save is the one failure a later session cannot detect.

## The Four Request Kinds

| Kind | Trigger shape | Writes | Returns |
| --- | --- | --- | --- |
| Checkpoint | "save progress", a delegation boundary, a tier-3 escalation | `checkpoint` (or `create` on the first) plus a report file | Published revision, registered evidence hashes, next action |
| Learning write | "record a learning", an error-recovery return | A tagged entry in the phase learning report, referenced by the next checkpoint | The entry as written, with its layer, category, evidence, and confidence |
| Resume | "resume from saved state", a new session on a pinned run | Nothing until the restored state is verified | Verified state, drift, and the narrowed safe resume point |
| Lookup | "what did we learn about X", a pre-work query from another skill | Nothing — a lookup is read-only and never opens a run | Matching entries with evidence and confidence, or an explicit empty result |

A lookup searches the learning reports already written under the run's phase
directories. Grep them by subject, then by `layer:` or `failure-category:` when
the caller is routing a fix rather than recalling a fact:

```bash
grep -rn --include='report_learnings*.md' -i -B2 -A6 '<subject>' skillset-saves/runs/<run-id>/
```

Narrow a routing lookup by tag instead — `grep -rn 'failure-category: <cat>'` or
`grep -rn 'layer: <layer>'` over the same path. When several entries match, order
them newest phase first (the run's phase directories are written in pipeline
order), and within a phase by descending confidence; return every match rather
than the first, since a later entry usually revises an earlier one rather than
repeating it, and the caller needs to see both. Return each entry verbatim with
its evidence line; a paraphrase drops the file reference that makes the learning
checkable.

## Decision Rules

- Prefer short, evidence-backed continuity notes over verbose narrative.
- Treat missing artifact lineage as a resume blocker, not a guessable inconvenience.
- Keep learnings reusable by other skills rather than tied to one transient conversation turn.
- Never persist sensitive ephemeral tokens or secrets as durable state.
- Treat a corrupt canonical record as evidence to preserve, never as a file to overwrite with a fresh one.
- Report an empty lookup as empty rather than reconstructing a plausible answer.

## Acceptance Checklist

- Checkpoint names the active stage, blockers, and next action, and reports the revision the writer published.
- Every write reports the `result` it actually received, not the one it intended.
- Learnings include evidence or confidence context, and failure-derived learnings carry a layer and a failure category.
- Resume output distinguishes verified state from missing or stale state.
- Report destinations came from `output_paths.py` and resolve inside the run's phase directory.
- Saved material is durable, searchable, and safe to retain.

## Contract Notes

The contracts this workflow runs under are stated in `../SKILL.md` § Required Contracts.

## Collaboration Notes

- `admiral` is the primary invoker — calls session-memory after normalized intake before the first stage delegation, at context tier 3+ escalations, before every gatekeeper-admiral submission, at session end, and on error recovery.
- `design/commander`, `build/build-management`, and `review/code-chief` consume continuity records when long-running work spans sessions, and route any change to the core run record through session-memory instead of writing it.
- `review/cso` and the other phase leads checkpoint through session-memory at every delegation and return; the phase lead owns its own `reports/`, `artifacts/`, `evidence/`, and `packages/` paths, and session-memory owns the run record those checkpoints publish.
- Any specialist may request a checkpoint or a learning lookup via its orchestrator when context pressure rises or when prior findings would change its approach.
