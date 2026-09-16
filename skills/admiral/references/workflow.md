# Workflow Reference

## Contents

1. Intake and mode selection
2. Boundary sequencing
3. Rewind and idempotency rules
4. Delivery closure

## Intake And Mode Selection

1. Run the save startup check before new state is created: inspect `skillset-saves/_latest.md`, classify the directory as active/inactive/missing/unreadable/conflict, resume active reclaimable runs, or activate persistence for a new run.
2. If persistence activation fails, warn once, attempt read-only resume from any readable latest artifacts, and continue transiently only when no coherent resume boundary can be proven.
3. Run `harness/hooks/check_readiness.py --host auto` on a fresh intake, or with `--require-active-run` on a resume, so Python version, hook registration, and save state are visible in one place; a fresh intake has no run until `save_run.py create` publishes it. Record `RUNTIME_READINESS_CHECK`; warn and continue in degraded mode when hooks or Python are missing, and on a resume rerun the save startup check if no active save run is present.
4. Normalize the user request with `intake-brief.yaml` so scope, constraints, upstream artifacts, and requested endpoint are visible in one place.
5. Decide whether the run is full pipeline, partial pipeline, resume, create-skill, or create-team.
6. Detect whether the host supports agent mode or only skill mode, then re-check that mode at every boundary and active-session turn.
7. Reject any claimed resume path that cannot prove both approval lineage and package completeness for the next boundary.
8. After scope confirmation and before the first sub-orchestrator delegation, engage `session-memory` to checkpoint the normalized intake. This intake checkpoint is mandatory and unconditional — it is the first engagement of every run, so even a single-stage run engages `session-memory` plus the stage sub-orchestrator. Append each engaged skill to the run-state `skills_engaged` list as it is engaged.

## Boundary Sequencing

1. Use `stub-contract.md` to confirm which sub-orchestrator owns the next boundary and what package shape that boundary must return.
2. Start from the earliest incomplete approved stage, not from the most recent artifact found on disk.
3. Before each delegation, capture the package revision, expected outputs, escalation conditions, and the gate that will consume the result.
4. After each delegation, send the returned package through `gatekeeper-admiral` before any later stage is allowed to consume it.
5. Keep skill-maker as an on-demand utility path rather than inserting it into the normal design -> build -> review chain.

### Save Instructions Per Boundary

The path policy is `../../save-ownership.yaml`; admiral never writes a core run
file by hand and never creates a path outside its declared classes.

**On delegation** to any sub-orchestrator:
1. Checkpoint through `session-memory` (`python skills/harness/hooks/save_run.py checkpoint --run-id {run-id} --expect-revision <n> --set active_owner=<lead> --set phase_state=<PHASE>_ACTIVE`). The checkpoint publishes `_state.md`, `_lock.md`, and `_latest.md` atomically and appends `DELEGATION_SENT` to `_audit-trail.md`.
2. Include the canonical `### Save Context` block (below) in the delegation prompt.

**On package return** from a sub-orchestrator:
1. Generate a `submission_id` in the format `{run-id}_handoff-{N}_attempt-{M}_{ISO-timestamp}`.
2. Write the cross-stage handoff record at `skillset-saves/runs/{run-id}/delivery/reports/handoff_{boundary}.md` (frontmatter: `submission_id`, `revision`, `package_path`, `submission_status: PENDING`, `verdict: PENDING`). `delivery/` is admiral's own phase directory.
3. Checkpoint through `session-memory` with `--set phase_state=<PHASE>_GATE_PENDING --evidence <that record>` before the gate submission.

**On gatekeeper-admiral verdict**:
1. Update the handoff record with the actual verdict, its `verdict_id`, and `submission_status: VERDICT_RECORDED`. The gatekeeper's own durable record is `<phase>/verdict_{boundary}.cross-stage.json`, written beside the phase gatekeeper's `verdict_{boundary}.json`.
2. Route per verdict:
   - APPROVED: checkpoint into the next active state and advance to the next stage.
   - REVISE: checkpoint into the gate-revise state and forward the findings to the same sub-orchestrator.
   - ESCALATE: `save_run.py block --reason "<dispute>"` (`DISPUTED_AWAITING_USER`) and freeze advancement.
3. Every checkpoint refreshes `_latest.md` and appends the verdict to `_audit-trail.md`; neither file is written by hand.

### Save Context Delegation Template

Include this block in every sub-orchestrator delegation with values copied from the current run state. It is the canonical field set from `../../contracts/handoff-templates.md` (mirrored in `../../save-protocol.md`); neither file may drop a field the other carries. When persistence is inactive or read-only resume is in effect, keep the block but set `Persistence active: no` so downstream skills return inline and skip writes.

```markdown
### Save Context
- Run ID: {run-id}
- Phase: {phase}
- Save path: skillset-saves/runs/{run-id}/{phase}/
- Persistence active: {yes|no}
- Persistence probe result: {ok|reason}
- Context tier: {1|2|3}
- Artifact mode: {inline|file|reference}
- Session pin: {true|false}
- Execution mode: {agent|skill}
- Submission ID: {id}
- Revision: {revision}
- Owner: {owner}
- Expected artifact: {artifact}
- Evidence paths: {relative paths}
- Artifact hashes: {path: sha256|none yet}
- Risks: {known risks|none declared}
- Return boundary: {gate boundary for the returned package}
```

## Rewind And Idempotency Rules

- Reuse an existing verdict only when the package revision and boundary scope are unchanged.
- Rewind when upstream approvals drift, artifacts are mixed across revisions, or a saved package loses mandatory deliverables.
- Preserve superseded packages and verdicts as evidence; do not overwrite them into a false single history.
- Route every remediation cycle back to the same owning sub-orchestrator and stop after two failed revision attempts.

## Delivery Closure

- Consolidate only approved packages.
- Separate approved outputs from disputed items so the delivery package does not blur acceptance with open conflict.
- Carry forward next actions that the user or the next operator can execute without reconstructing the whole run.
- If the run included skill-maker, include the resulting package, score outcome, and any remaining improvement notes alongside the main delivery summary.

## Contract Notes

- Preamble Tier System: Use short progress preambles that scale from terse status to fuller context only when complexity or risk rises.
- Proactive triggers: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- YAGNI intake: ask only load-bearing decisions; record reversible defaults and reopen triggers for speculative branches that do not affect the next deliverable.

## Collaboration Notes

- `design/commander` owns design package assembly and design-stage revisions.
- `build/build-management` owns build package assembly and implementation-stage revisions.
- `review/code-chief` owns review package assembly and specialist review routing.
- `gatekeeper-admiral` owns cross-boundary acceptance decisions.
- `skill-maker` owns custom skill and coordinated-team generation when that mode is selected.
- `session-memory` provides cross-session checkpoints and durable learnings; engaged by admiral as the mandatory first action at intake (after scope confirmation, before the first delegation), and again at context tier 3+, before gate submissions, at session end, and on error recovery. The intake engagement is unconditional and is recorded once in `skills_engaged` (re-engagements do not duplicate the entry).
