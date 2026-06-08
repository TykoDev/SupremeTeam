# Admiral Stub Contract

## Scope

Admiral owns stage selection, cross-stage gate routing, persistence-aware resume behavior, and final delivery assembly.

## Stage Model

1. Design through commander
2. Build through build-management
3. Review through code-chief
4. Skill creation through skill-maker when requested (on-demand utility, not a sequential stage)

## Required Stage Inputs

- Design stage: user request, constraints, and mode selection
- Build stage: approved design package
- Review stage: approved build package plus design package for traceability
- Skill-creation stage: skill intent or team description with constraints

## Handoff Rules

- Admiral never edits a sub-orchestrator package.
- Every handoff record must capture approval state, revision count, and the current package revision identifier.
- Verdict vocabulary is limited to APPROVED, REVISE, and ESCALATE.
- Skill-creation verdicts map: SHIP → APPROVED, ITERATE → REVISE, BLOCKED → ESCALATE.
- Maximum revisions per cross-stage handoff: 2.

## Delivery Contract

- Deliver a unified package with table of contents, executive summary, traceability matrix, and prioritized next actions.
- Record unresolved disputes separately from approved deliverables.

## Persistence Contract

All pipeline participants MUST follow `save-protocol.md` when persistence is active. Saving is mandatory, not optional — every orchestrator, specialist, and gatekeeper must adhere to the write-ownership rules below without exception.

### Write Ownership

| Owner | Owns These Files |
|-------|-----------------|
| Admiral | `_index.md`, `_latest.md`, `_run-manifest.md`, `_lock.md`, `_state.md`, `_audit-trail.md`, `gatekeeper-admiral_handoff-{N}.md`, `admiral/delivery-package.md`, `admiral/intake.md`, `admiral/standalone-context.md`, `{pipeline}/_skip-record.md` |
| Sub-orchestrators (commander, build-management, code-chief) | `{pipeline}/_phase-state.md`, `{pipeline}/gatekeeper-verdict.md`, `{pipeline}/{package}.md`, `{pipeline}/delegation-log.md` |
| Specialists (researcher, planner, architect, bob-the-builder, etc.) | `{phase-dir}/deliverable_{name}.md`, `{phase-dir}/review-packet.md` (design specialists only) |
| Gatekeepers | Do NOT write to `skillset-saves/` — return verdicts to the invoking orchestrator, which captures them |

### Enforcement Rules

- Every orchestrator MUST include a `### Save Context` block in every specialist delegation when persistence is active.
- Every specialist MUST write deliverables to the save path specified in Save Context when `Persistence active: yes`.
- Every specialist MUST skip all save operations when Save Context is absent or `Persistence active: no`.
- Before starting a new run, classify `skillset-saves/` as active/inactive/missing/unreadable/conflict and resume an active reclaimable run before creating new state.
- Attempt persistence activation when no active run exists and file-system writes are available; activation failure downgrades to read-only resume or transient mode with one warning.
- Reuse saved artifacts only after lineage and package-shape validation.
- Rewind to the earliest affected stage when an approved upstream artifact changes or fails validation.

### Save Context Schema

Every `### Save Context` block delivered to a sub-orchestrator or specialist MUST include these fields. Sub-orchestrators propagate the same fields when they delegate further:

| Field | Values | Notes |
|-------|--------|-------|
| `Run ID` | `{run-id}` | Stable for the entire run |
| `Save path` | `skillset-saves/runs/{run-id}/{pipeline}/` | Forward slashes, workspace-relative |
| `Persistence active` | `yes` \| `no` | MUST reflect actual write-probe result |
| `Persistence probe result` | `ok` \| `failed` \| `skipped` | New field — never omit |
| `Context tier` | `1` \| `2` \| `3` \| `4` | Feeds artifact-mode decisions |
| `Artifact mode` | `inline` \| `reference` \| `best-effort-inline` | Per save-protocol Section 5 |
| `Standalone fallback ref` | path \| `none` | Standalone context when persistence is off |
| `Skipped upstream stages` | `none` \| list | Skip lineage |
| `Session pin` | `true` \| `false` | New field — true while run is `*_ACTIVE` and lock held |
| `Execution mode` | `agent` \| `skill` | New field — current mode after the per-boundary re-probe |

A specialist that receives a Save Context block with `Persistence active: no` MUST treat every save call as a no-op and surface its deliverable inline in the response. A specialist that receives `Session pin: true` MUST honor admiral routing and not spawn parallel skills.

### Session-Memory Integration

- Admiral invokes `session-memory` at context tier 3+ escalations, before gatekeeper-admiral submissions, at session end, and on error recovery.
- Sub-orchestrators reference session-memory checkpoints during cross-session resume.
- See `save-protocol.md` for the complete directory structure, file formats, and resume protocol.

## Agent Contract

- Detect execution mode (agent or skill) at intake and record in state.
- In agent mode, manage state programmatically and delegate to sub-agents.
- In skill mode, provide instructions for the host agent to follow.
- Both modes use the same pipeline stages, handoff contracts, and save-protocol structure.
