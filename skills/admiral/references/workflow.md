# Workflow Reference

## Contents

1. Intake and mode selection
2. Boundary sequencing
3. Rewind and idempotency rules
4. Delivery closure

## Intake And Mode Selection

1. Run the save startup check before new state is created: inspect `skillset-saves/_latest.md`, classify the directory as active/inactive/missing/unreadable/conflict, resume active reclaimable runs, or activate persistence for a new run.
2. If persistence activation fails, warn once, attempt read-only resume from any readable latest artifacts, and continue transiently only when no coherent resume boundary can be proven.
3. Normalize the user request with `intake-brief.yaml` so scope, constraints, upstream artifacts, and requested endpoint are visible in one place.
4. Decide whether the run is full pipeline, partial pipeline, resume, create-skill, or create-team.
5. Detect whether the host supports agent mode or only skill mode, then re-check that mode at every boundary and active-session turn.
6. Reject any claimed resume path that cannot prove both approval lineage and package completeness for the next boundary.
7. After scope confirmation and before the first sub-orchestrator delegation, engage `session-memory` to checkpoint the normalized intake. This intake checkpoint is mandatory and unconditional — it is the first engagement of every run, so even a single-stage run engages `session-memory` plus the stage sub-orchestrator. Append each engaged skill to the run-state `skills_engaged` list as it is engaged.

## Boundary Sequencing

1. Use `stub-contract.md` to confirm which sub-orchestrator owns the next boundary and what package shape that boundary must return.
2. Start from the earliest incomplete approved stage, not from the most recent artifact found on disk.
3. Before each delegation, capture the package revision, expected outputs, escalation conditions, and the gate that will consume the result.
4. After each delegation, send the returned package through `gatekeeper-admiral` before any later stage is allowed to consume it.
5. Keep skill-maker as an on-demand utility path rather than inserting it into the normal design -> build -> review chain.

### Save Instructions Per Boundary

**On delegation** to any sub-orchestrator:
1. Update `_state.md` to the active state for that pipeline (e.g. `DESIGN_ACTIVE`, `BUILD_ACTIVE`, `REVIEW_ACTIVE`).
2. Append a `DELEGATION_SENT` entry to `_audit-trail.md`.
3. Include a `### Save Context` block in the delegation prompt with the run ID, save path, persistence status, context tier, artifact mode, standalone fallback ref, and skipped upstream stages.

**On package return** from a sub-orchestrator:
1. Generate a `submission_id` in the format `{run-id}_handoff-{N}_attempt-{M}_{ISO-timestamp}`.
2. Write `gatekeeper-admiral_handoff-{N}.md` with `submission_status: PENDING` and `verdict: PENDING`.
3. Update `_state.md` to the gate-pending state (e.g. `DESIGN_GATE_PENDING`) with `gatekeeper_verdict_pending: true`.
4. Invoke `session-memory` to checkpoint the current state before the gate submission.

**On gatekeeper-admiral verdict**:
1. Update `gatekeeper-admiral_handoff-{N}.md` with the actual verdict and `submission_status: VERDICT_RECORDED`.
2. Route per verdict:
   - APPROVED: update `_state.md` to the next active state, advance to next stage.
   - REVISE: update `_state.md` to the gate-revise state, forward findings to the same sub-orchestrator.
   - ESCALATE: update `_state.md` to `DISPUTED_AWAITING_USER`, freeze advancement.
3. Update `_latest.md` and append the verdict to `_audit-trail.md`.

### Save Context Delegation Template

Include this block in every sub-orchestrator delegation with values copied from the current run state. When persistence is inactive or read-only resume is in effect, keep the block but set `Persistence active: no` so downstream skills return inline and skip writes.

```markdown
### Save Context
- **Run ID**: {run-id}
- **Save path**: skillset-saves/runs/{run-id}/{pipeline}/
- **Persistence active**: {yes|no — current run state}
- **Persistence probe result**: {ok|failed|skipped}
- **Context tier**: {1|2|3|4}
- **Artifact mode**: {inline|reference|best-effort-inline}
- **Standalone fallback ref**: {path or "none"}
- **Skipped upstream stages**: {none or list}
- **Session pin**: {true|false}
- **Execution mode**: {agent|skill}
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

## Collaboration Notes

- `design/commander` owns design package assembly and design-stage revisions.
- `build/build-management` owns build package assembly and implementation-stage revisions.
- `review/code-chief` owns review package assembly and specialist review routing.
- `gatekeeper-admiral` owns cross-boundary acceptance decisions.
- `skill-maker` owns custom skill and coordinated-team generation when that mode is selected.
- `session-memory` provides cross-session checkpoints and durable learnings; engaged by admiral as the mandatory first action at intake (after scope confirmation, before the first delegation), and again at context tier 3+, before gate submissions, at session end, and on error recovery. The intake engagement is unconditional and is recorded once in `skills_engaged` (re-engagements do not duplicate the entry).
