# Copilot Adapter — Admiral Agent Mode for GitHub Copilot

## Contents

- [Registration](#registration)
- [Commands](#commands)
- [Tool Mapping](#tool-mapping)
- [Sub-Agent Delegation](#sub-agent-delegation)
- [State Management](#state-management)
- [Context Management](#context-management)
- [Error Recovery](#error-recovery)
- [Limitations](#limitations)
- [Write-Capability Probe](#write-capability-probe)
- [Missing Workspace](#missing-workspace)
- [Mode Re-Probe](#mode-re-probe)
- [Session Pin](#session-pin)

## Registration

Admiral registers as a VS Code chat participant with the identifier `@admiral`.
Users invoke it via `@admiral` in the Copilot Chat panel or through slash commands.

## Commands

| Command | Pipeline Mode | Description |
|---------|--------------|-------------|
| `/pipeline` | Full | Run the full design → build → review → delivery pipeline |
| `/design` | Partial (design-only) | Run design phase only through commander |
| `/build` | Partial (build-only) | Run build phase only through build-management |
| `/review` | Partial (review-only) | Run review phase only through code-chief |
| `/create-skill` | Create-skill | Create a new skill through skill-maker |
| `/create-team` | Create-team | Create a coordinated team of skills |
| `/resume` | Resume | Resume from saved pipeline state |
| `/status` | Status | Show current pipeline state and next action |

## Tool Mapping

Admiral agent mode maps its abstract tool requirements to Copilot's available tools:

| Admiral Requirement | Copilot Tool | Usage |
|--------------------|-------------|-------|
| file-system.read | `read_file` | Read save-protocol state, skill files |
| file-system.write | `create_file`, `replace_string_in_file` | Write state, packages, deliverables |
| file-system.list | `list_dir` | Enumerate run directories, skill directories |
| file-system.search | `file_search` | Find skills by pattern, locate artifacts |
| terminal.execute | `execution_subagent`, `run_in_terminal` | Run scripts, validation, packaging |
| search.semantic | `semantic_search` | Find relevant code and documentation |
| search.grep | `grep_search` | Exact text matches in workspace |
| memory.read | `memory` (view) | Read session and repo memory |
| memory.write | `memory` (create, str_replace) | Write session checkpoints |
| sub-agent.invoke | `runSubagent` | Delegate to sub-orchestrator agents |
| diagnostics | `get_errors` | Check for compile/lint errors |

## Sub-Agent Delegation

In Copilot, sub-orchestrators are invoked via `runSubagent`:

```
runSubagent(
  agentName: "Admiral",  // or specific sub-agent if registered
  prompt: "{handoff template with full context}",
  description: "{stage-name} pipeline execution"
)
```

Since Copilot's `runSubagent` creates stateless agents, each delegation must include
the complete handoff context in the prompt. The sub-agent cannot access prior
conversation history — all required inputs must be serialized in the prompt.

## State Management

Copilot agent mode uses the workspace file system for all state:

1. **Save location**: `{workspace}/skillset-saves/runs/{run-id}/`
2. **State reads**: Use `read_file` to inspect the run-state and lock records.
3. **State writes**: Use `create_file` or `apply_patch` to update state and package artifacts.
4. **Heartbeat**: Refresh the lock record whenever a stage transition or long-running delegation completes.
5. **Startup status**: Inspect `{workspace}/skillset-saves/_latest.md` before starting a new run; resume an active reclaimable run, stop on a fresh conflicting lock, or activate persistence when no active run exists.

## Context Management

Copilot conversations have context limits. Admiral manages this by:

1. Using the save-protocol as the source of truth (not conversation memory)
2. Summarizing stage outputs instead of carrying full packages in context
3. Reading artifacts from disk only when needed for the current stage
4. Using `manage_todo_list` for visible progress tracking

## Error Recovery

If a Copilot session ends mid-pipeline:

1. The lock record remains active with the last heartbeat timestamp.
2. On the next `/resume`, Admiral reads the run-state record to determine the last completed stage.
3. If the lock lease has expired, Admiral acquires it and continues.
4. If the lock is still fresh for another session, Admiral warns and waits.

## Limitations

- Sub-agents are stateless — cannot maintain conversation across delegations
- No parallel sub-agent execution — delegations must be sequential
- Context window limits may require tiered artifact handling for large projects
- Browser tools require explicit loading via `tool_search`

## Write-Capability Probe

The probe defined in `save-protocol.md` Section 4 maps to Copilot tools as:

1. `create_file` writes a short ASCII payload to `{workspace}/skillset-saves/_probe-{run-id}.tmp`. If `create_file` returns an error or the file is not created, the probe fails immediately.
2. `read_file` reads it back and admiral verifies byte equality.
3. `run_in_terminal` deletes it (`rm skillset-saves/_probe-{run-id}.tmp`).

A probe failure on any step downgrades the run to `Persistence active: no`, surfaces a single user-visible warning, and Admiral attempts read-only resume from any readable latest artifacts before continuing in transient mode.

## Missing Workspace

If no workspace is open in VS Code, `create_file` and `list_dir` operate against the user home or fail outright. Admiral MUST treat "no workspace" as a forced non-persistent run:

1. If the workspace root cannot be resolved at intake, set `Persistence active: no`, `persistence_probe_result: skipped`, and warn the user that resumes will not be possible.
2. Continue under transient mode — all save triggers become no-ops, and the run cannot be resumed across sessions.

## Mode Re-Probe

Per the agent-protocol re-probe rule, admiral re-runs the three-capability probe before every boundary. Common Copilot transitions:

- Browser tools loaded mid-run via `tool_search` — capability gain, no mode change but `tools_verified` updates.
- `runSubagent` revoked or quota-exhausted — admiral downgrades to skill mode for that boundary and emits the handoff as instruction text.

## Session Pin

Copilot Chat sessions are continuous within a panel. Once a run is `*_ACTIVE` and `_lock.md` is held, admiral honors the session pin and treats every subsequent `@admiral`-less message in that chat as input to the active sub-orchestrator. The pin clears on `RUN_COMPLETE`, the user message `release admiral`, the slash command `/exit-admiral`, or lock staleness. Routing precedence in this host: explicit slash command (`/design`, `/build`, ...) > admiral pin > free conversation.
