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

The authoritative path policy is `../save-ownership.yaml`; this table summarizes it.

| Owner | Owns These Paths |
|-------|------------------|
| `session-memory`, only through `harness/hooks/save_run.py` | `skillset-saves/_latest.md`, `runs/{run-id}/_state.md`, `_lock.md`, `_audit-trail.md`, `_journal.json`, `_history/` |
| Admiral | `runs/{run-id}/intake/report_grilling.md`, `intake/intake-brief.md`, `delivery/reports/handoff_{boundary}.md` (one cross-stage handoff record per boundary), `delivery/reports/delivery-package.md` |
| Phase leads (commander, build-management, code-chief; cso, investigate, qa, taste, skill-maker, ship for their pipelines) | `runs/{run-id}/{phase}/manifest.json`, `reports/`, `artifacts/`, `evidence/`, `packages/` |
| Specialists | Only the report, artifact, or evidence file named in their delegation, at the destination it names (resolved with `scripts/output_paths.py`) |
| Gatekeepers | `runs/{run-id}/{phase}/verdict_{boundary}.json` (phase gatekeeper) and `verdict_{boundary}.cross-stage.json` (gatekeeper-admiral), written through `harness/gatekeeper/check.py --verdict-out`; never the submission |
| `taste`, only through `taste/taste_prefs.py` | `skillset-saves/preferences/*` |

Phase state, the active owner, skips, and the next action live in the run record and are published only through `save_run.py checkpoint` (`--set key=value`, `--next-action`). Nested per-specialist directories, phase-state files, and hand-written pointers belong to no declared class and are write-ownership violations.

### Enforcement Rules

- Every orchestrator MUST include a `### Save Context` block in every specialist delegation when persistence is active.
- Every specialist MUST write deliverables to the save path specified in Save Context when `Persistence active: yes`.
- Every specialist MUST skip all save operations when Save Context is absent or `Persistence active: no`.
- Before starting a new run, classify `skillset-saves/` as active/inactive/orphaned/missing/unreadable/conflict and resume an active reclaimable run before creating new state.
- Attempt persistence activation (`save_run.py create`) when no active run exists and file-system writes are available; activation failure downgrades to read-only resume or transient mode with one warning.
- Reuse saved artifacts only after lineage and package-shape validation.
- Rewind to the earliest affected stage when an approved upstream artifact changes or fails validation.

### Save Context Schema

Every `### Save Context` block delivered to a sub-orchestrator or specialist MUST carry the canonical field set from `../contracts/handoff-templates.md` (mirrored in `../save-protocol.md`); neither file may drop a field the other carries. Sub-orchestrators propagate the same fields when they delegate further:

| Field | Values | Notes |
|-------|--------|-------|
| `Run ID` | `{run-id}` | Stable for the entire run |
| `Phase` | `{phase}` | The declared phase directory |
| `Save path` | `skillset-saves/runs/{run-id}/{phase}/` | Forward slashes, workspace-relative |
| `Persistence active` | `yes` \| `no` | MUST reflect the actual `save_run.py create` probe result |
| `Persistence probe result` | `ok` \| reason | Never omit |
| `Context tier` | `1` \| `2` \| `3` | Feeds artifact-mode decisions |
| `Artifact mode` | `inline` \| `file` \| `reference` | How the deliverable returns |
| `Session pin` | `true` \| `false` | True while the run is active and the lock is held |
| `Execution mode` | `agent` \| `skill` | Current mode after the per-boundary re-probe |
| `Submission ID` | `{id}` | Idempotency key for the boundary |
| `Revision` | `{revision}` | The run revision being worked |
| `Owner` | `{owner}` | The delegate that may write |
| `Expected artifact` | `{artifact}` | The one artifact the delegate returns, at its resolved destination |
| `Evidence paths` | relative paths | Existing evidence the delegate may rely on |
| `Artifact hashes` | `path: sha256` \| `none yet` | Hashes already registered |
| `Risks` | known risks \| `none declared` | Carried forward, never dropped |
| `Return boundary` | gate boundary | Where the returned package is validated |

A specialist that receives a Save Context block with `Persistence active: no` MUST treat every save call as a no-op and surface its deliverable inline in the response. A specialist that receives `Session pin: true` MUST honor admiral routing and not spawn parallel skills.

### Session-Memory Integration

- Admiral engages `session-memory` first at intake (mandatory, after scope confirmation and before the first delegation), then at context tier 3+ escalations, before every gatekeeper-admiral submission, at session end, and on error recovery.
- Sub-orchestrators reference session-memory checkpoints during cross-session resume.
- See `save-protocol.md` for the complete directory structure, file formats, and resume protocol.

## Agent Contract

- Detect execution mode (agent or skill) at intake and record in state.
- In agent mode, manage state programmatically and delegate to sub-agents.
- In skill mode, provide instructions for the host agent to follow.
- Both modes use the same pipeline stages, handoff contracts, and save-protocol structure.
