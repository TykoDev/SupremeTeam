# Admiral Agent Protocol

## Contents

- [Overview](#overview)
- [Execution Mode Detection](#execution-mode-detection)
- [Startup Save Activation](#startup-save-activation)
  - [Per-Boundary Re-Probe](#per-boundary-re-probe)
  - [Write-Capability Probe](#write-capability-probe)
  - [Session Pin](#session-pin)
- [Agent Mode Execution Flow](#agent-mode-execution-flow)
  - [Stage 0: Intake](#stage-0-intake)
  - [Stage 1-4: Pipeline Execution](#stage-1-4-pipeline-execution)
  - [Skill-Creation Utility Path](#skill-creation-utility-path)
  - [Final Consolidation](#final-consolidation)
- [Sub-Agent Delegation Protocol](#sub-agent-delegation-protocol)
  - [Handoff Prompt Structure](#handoff-prompt-structure)
  - [Structured Response Format](#structured-response-format)
  - [Error Handling](#error-handling)
- [Skill Mode Execution Flow](#skill-mode-execution-flow)
- [Platform-Specific Behavior](#platform-specific-behavior)
- [State Machine Extensions For Agent Mode](#state-machine-extensions-for-agent-mode)

## Overview

This document defines how Admiral operates in agent mode: autonomous execution with programmatic state management and sub-agent delegation. Agent mode activates when the host platform provides tool access and sub-agent delegation capabilities. When those capabilities are absent, Admiral falls back to skill mode.

Both modes share identical pipeline stages, handoff contracts, gatekeeper verdicts, and save-protocol structure. Agent mode adds programmatic control; skill mode provides the same behavior through instruction following.

---

## Execution Mode Detection

At intake, detect execution mode before any pipeline work:

1. Check for sub-agent capability.
2. Check for file-system read and write capability.
3. Check for command execution.

If all three are available -> **agent mode**.
If any is missing -> **skill mode**.

Record the detected mode in the run state record:

```yaml
execution_mode: "agent" | "skill"
execution_mode_detected_at: "{ISO 8601}"
agent_platform: "copilot" | "codex" | "claude" | "other"
tools_verified: [list of confirmed tool categories]
```

## Startup Save Activation

Before Admiral creates a new run or accepts a fresh-looking request, inspect `skillset-saves/` per `../../save-protocol.md` Section 4.0:

1. Read `_latest.md` when present, then read the latest run's `_state.md` and `_lock.md`. Treat `_latest.md` as a pointer only — if it is missing or stale, scan `runs/*/_state.md` directly rather than concluding no run exists.
2. Classify the save directory as `active`, `inactive`, `orphaned`, `missing`, `unreadable`, or `conflict`.
3. If the directory is `active`, run the resume protocol and continue from the earliest incomplete boundary.
4. If the directory is `orphaned` (a non-terminal run exists under `runs/` but `_latest.md` is missing, unreadable, or points at a missing/terminal run), rebuild `_latest.md` to point at the most recent non-terminal run, append `LATEST_POINTER_REBUILT`, then run the resume protocol. Never fork a fresh run over a recoverable orphan.
5. If the directory is `conflict`, stop and warn that another fresh session owns the run unless the lock is stale and reclaimable.
6. If the directory is `inactive` or `missing`, create `skillset-saves/`, run the write-capability probe, and initialize a new run only after activation succeeds.
7. If activation fails, warn once, attempt read-only resume from any readable latest artifacts, and continue in transient mode only when no coherent boundary can be proven.

This check runs at initial intake, on explicit resume, and at the start of every turn while `session_pin: true`. It prevents a plan-mode or post-compaction turn from accidentally bypassing an active saved run.

### Per-Boundary Re-Probe

Mode is not static. Hosts can gain or lose capabilities mid-session — most commonly when Claude Code exits plan mode (skill -> agent) or when a tool surface is revoked (agent -> skill). Admiral MUST re-probe before every boundary delegation and on every resume:

1. Re-run the three-capability probe above.
2. Compare the result to `execution_mode` in `_state.md`.
3. If they differ:
   - Update `execution_mode` and `execution_mode_detected_at` in `_state.md`.
   - Append `MODE_RECHECK` to `_audit-trail.md` with `cached={old}`, `detected={new}`, `action={upgrade|downgrade}`.
   - Continue the delegation under the new mode in place. Do not abort, do not force the user to retry.
4. If they match, log a cache hit only.

**Upgrade path (skill -> agent)**: The first boundary after the host gains capabilities switches automatically. The handoff prompt is re-emitted as a programmatic delegation rather than instruction text. The cached `agent_platform` is overwritten with the freshly detected value.

**Downgrade path (agent -> skill)**: The current boundary completes in skill mode by emitting instruction text in place of the programmatic call. Subsequent boundaries continue in skill mode until a re-probe shows the capability returned.

### Write-Capability Probe

Before the first save and at every heartbeat refresh, run the write-capability probe defined in `save-protocol.md` after the startup classification above:

1. Write a short ASCII payload to `skillset-saves/_probe-{run-id}.tmp`.
2. Read it back and verify byte equality.
3. Delete the probe file.
4. Record the result in `_state.md` (`persistence_active`, `persistence_probe_result`) and append `PERSISTENCE_PROBE` to `_audit-trail.md`.

If the probe fails at intake or activation, set `Persistence active: no`, surface a single user-visible warning, attempt read-only resume from any readable latest artifacts, and continue in transient mode only if no coherent resume boundary exists. If a heartbeat probe fails mid-run, downgrade `persistence_active` to `no`, warn once, emit `RESUME_FALLBACK` when readable state exists, and stop emitting save calls — do not pretend writes succeeded.

### Session Pin

Hosts that support continuous turns (Claude Code, Codex chat, Copilot chat) honor the session pin:

1. When the run enters any `*_ACTIVE`, `*_GATE_PENDING`, or `*_GATE_REVISE` state and `_lock.md` is held, set `session_pin: true` in `_state.md`.
2. Every subsequent user input in the same session — even without the keyword "admiral" — is interpreted as input to the active sub-orchestrator.
3. Routing precedence: explicit slash command > admiral session pin > free conversation.
4. The pin clears on `RUN_COMPLETE` (`DELIVERED`), the user command `release admiral` or `/exit-admiral`, or lock staleness; each release appends `SESSION_PIN_RELEASE` to `_audit-trail.md`.

Hosts without continuous turns ignore the pin and rely on explicit invocation each turn.

---

## Agent Mode Execution Flow

### Stage 0: Intake

1. Run Startup Save Activation and classify `skillset-saves/` before touching new run state.
2. If resuming, read the active lock and run-state records and validate ownership before writing to the run.
3. If no active run exists, activate persistence when file-system writes are available; otherwise mark the run transient.
4. Classify the request as full, partial, resume, create-skill, or create-team.
5. Write the normalized intake artifact to the active run directory when persistence is active; otherwise keep the artifact inline.
6. Update the run-state and lock records programmatically when writable, including `save_directory_status`, `persistence_activation_result`, and `resume_source`.
7. Present the intake summary to the user and request the single mandatory confirmation checkpoint.
8. After confirmation and before any Stage 1 delegation, engage `session-memory` to checkpoint the normalized intake. This engagement is **mandatory and unconditional** (it does not wait for context tier 3+ or the first gate). Append `session-memory` to the run-state `skills_engaged` list and append `DELEGATION_STARTED` / `DELEGATION_COMPLETED` (target: `session-memory`) to `_audit-trail.md`. This guarantees every run — including a single-stage or early-ending one — engages at least two catalog skills before delivery.

### Stage 1-4: Pipeline Execution

For each active stage:

1. **Pre-delegation**
   - Read the current run-state record to confirm the active stage.
   - Verify that the required upstream package exists, is approved, and matches the expected revision lineage.
   - Prepare the boundary handoff prompt from the current contracts and save-protocol context.

2. **Delegation**
   - Invoke the owning sub-orchestrator as a sub-agent using a handoff prompt that includes the input package, expected outputs, contracts, and save location.
   - Append the sub-orchestrator to the run-state `skills_engaged` list (append-once) when emitting `DELEGATION_STARTED`.
   - Require the sub-agent to return a structured package summary plus any blockers.

3. **Post-delegation**
   - Validate the returned package against the stage contract.
   - Write the package to the appropriate save-protocol location.
   - Generate a `submission_id` for the gatekeeper handoff.
   - Write the handoff record with pending status before the gate runs.

4. **Gate submission**
   - Submit the returned package plus `submission_id` to `gatekeeper-admiral`.
   - Route the verdict:
     - **APPROVED**: update the handoff record, advance the run state, proceed to the next stage.
     - **REVISE**: send the findings back to the same sub-orchestrator and re-run that boundary.
     - **ESCALATE**: freeze the boundary, preserve the state, and present the blocking issue to the user.

5. **State persistence**
   - Update the run-state record after every state transition.
   - Append to the audit-trail record after every significant event.
   - Refresh the lock heartbeat at least every 300 seconds, and at the same cadence re-run the write-capability probe and the three-capability mode probe. Reconcile any drift in place per the rules above.

### Skill-Creation Utility Path

When running create-skill or create-team mode:

1. Invoke `skill-maker` as a sub-agent with the skill or team brief.
2. Validate the returned package, delivery report, and scoring outcome.
3. Submit the result to `gatekeeper-admiral` as the skill-maker boundary.
4. Route the verdict with the same `APPROVED` / `REVISE` / `ESCALATE` rules used for the normal pipeline.

### Final Consolidation

1. Read all approved packages from their save-protocol locations.
2. Assemble the final delivery artifact using the approved package set and the active mode.
3. Mark the run delivered, release the lock record, and preserve any disputed items separately from approved outputs.
4. Present the delivery package to the user.

---

## Sub-Agent Delegation Protocol

### Handoff Prompt Structure

When invoking a sub-agent, the handoff prompt must include:

- Input package and revision lineage.
- Expected output contract.
- Required shared contracts.
- Save destination for the returned package.
- Completion format with summary, blockers, and recommended next action.

### Structured Response Format

Sub-agents should return:

```yaml
stage: "{stage-name}"
status: "complete" | "blocked" | "partial"
package_path: "{path to consolidated package}"
summary: "{one-paragraph summary of what was produced}"
findings_count: {N}
critical_findings: {N}
blockers: ["{description of any blocking issues}"]
recommended_action: "{what Admiral should do next}"
```

### Error Handling

| Error | Agent Mode Response |
| --- | --- |
| Sub-agent returns no result | Retry once, then record the failed delegation and escalate. |
| Sub-agent returns only a partial package | Preserve the partial result, note the gaps, and decide whether the same owner can remediate them without changing scope. |
| Sub-agent times out | Record the timeout, check for partial saved artifacts, and continue only if package integrity can still be proven. |
| Tool failure occurs mid-delegation | Fall back to skill mode for that boundary only and record the degraded path. |
| Lock conflict is detected | Stop, warn the user, and do not overwrite the other run's state. |

---

## Skill Mode Execution Flow

In skill mode, Admiral provides the same boundary logic as instructions for the host agent:

1. The host agent manages save-protocol files manually.
2. The host agent loads sub-orchestrator skills and follows their instructions.
3. The host agent applies gatekeeper-admiral's checklist inline instead of delegating programmatically.
4. The stage sequence, handoff rules, and escalation rules stay identical.

The skill-mode behavior is defined in `SKILL.md` and `references/workflow.md`.

---

## Platform-Specific Behavior

See the adapter files for platform-specific integration details:

- `adapters/copilot.md` for GitHub Copilot agent mode.
- `adapters/codex.md` for Codex agent mode.
- `adapters/claude.md` for Claude Code hybrid mode.

---

## State Machine Extensions For Agent Mode

Agent mode adds these fields to the run-state record:

```yaml
execution_mode: "agent" | "skill"
execution_mode_detected_at: "{ISO 8601}"
agent_platform: "copilot" | "codex" | "claude" | "other"
tools_verified: ["file-system", "terminal", "search", "sub-agent", "memory"]
persistence_active: true | false
persistence_probe_result: "ok" | "failed" | "skipped"
save_directory_status: "active" | "inactive" | "missing" | "unreadable" | "conflict"
persistence_activation_result: "activated" | "resumed" | "failed" | "skipped"
persistence_activation_checked_at: "{ISO 8601}"
resume_source: "latest" | "explicit" | "none"
activation_failure_reason: "{message or null}"
session_pin: true | false
mcp_registry_checked_at: "{ISO 8601}"
mcp_registry_age_hours: {N}
active_delegation:
  target: "{sub-orchestrator-name}" | null
  started_at: "{ISO 8601}" | null
  timeout_seconds: 600
last_heartbeat: "{ISO 8601}"
skills_engaged: ["{skill-name}", ...]   # canonical, append-once list of every catalog skill engaged this run
```

`skills_engaged` is the single source of truth for engagement. Append a skill the first time it is engaged
(starting with the mandatory `session-memory` intake checkpoint, then each sub-orchestrator on
`DELEGATION_STARTED`); re-engaging an already-listed skill does not duplicate the entry. Because the intake
checkpoint plus the first stage sub-orchestrator are both unconditional, this list always holds at least two
entries by the time any stage completes.

Agent mode adds these events to the audit-trail record:

```
- AGENT_MODE_DETECTED — execution_mode set to agent, platform: {platform}
- SAVE_STATUS_CHECK — status: {active|inactive|orphaned|missing|unreadable|conflict}, action: {resume|recover|activate|transient|stop}
- PERSISTENCE_ACTIVATION — result: {activated|failed|skipped}, reason: {message}
- MODE_RECHECK — cached: {old_mode}, detected: {new_mode}, action: {upgrade|downgrade|cache-hit}
- PERSISTENCE_PROBE — result: {ok|failed|skipped}, persistence_active: {true|false}
- RESUME_FALLBACK — source: {latest|explicit}, result: {resumed-read-only|transient}
- LATEST_POINTER_REBUILT — source: runs-scan, run: {run-id}, reason: {missing|stale|terminal}-latest-pointer
- MCP_REGISTRY_CHECK — action: {use-cache|refreshed}, age_hours: {N}
- SESSION_PIN_RELEASE — reason: {delivered|user-release|lock-stale}
- DELEGATION_STARTED — target: {name}, submission_id: {id}
- DELEGATION_COMPLETED — target: {name}, status: {complete|blocked|partial}
- DELEGATION_TIMEOUT — target: {name}, elapsed: {seconds}
- TOOL_FALLBACK — tool: {name}, reason: {why}, fallback: skill-mode
- HEARTBEAT_REFRESH — lock refreshed at {timestamp}
```
