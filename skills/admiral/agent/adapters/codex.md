# Codex Adapter — Admiral Agent Mode for Codex

## Registration

Admiral registers as an agent through the Codex agents configuration system.
The agent configuration lives in `.agents/` at the repository root.

## Tool Mapping

| Admiral Requirement | Codex Tool | Usage |
|--------------------|-----------|-------|
| file-system.read | File read | Read save-protocol state, skill files |
| file-system.write | File write/edit | Write state, packages, deliverables |
| file-system.list | File listing | Enumerate directories |
| file-system.search | File search | Find files by pattern |
| terminal.execute | Shell execution | Run scripts, validation |
| search.grep | Grep | Text search in workspace |
| sub-agent.invoke | Agent dispatch | Delegate to sub-agents |

## Configuration

```yaml
# .agents/admiral.yaml
name: admiral
description: >
  Autonomous pipeline orchestrator for design, build, review, and skill creation.
instructions: |
  Load and follow the instructions in admiral/SKILL.md.
  Detect agent mode capabilities and operate autonomously when tools are available.
tools:
  - file-system
  - shell
  - search
```

## Sub-Agent Delegation

Codex supports agent dispatch. Sub-orchestrators can be registered as separate agents:

- `commander-agent` → design pipeline
- `build-management-agent` → build pipeline
- `code-chief-agent` → review pipeline
- `skill-maker-agent` → skill creation pipeline

Each receives its handoff template as the agent prompt.

## Constraints

- Codex operates in a sandboxed environment with limited network access
- File system access is scoped to the repository
- Shell execution may have timeout limits
- No browser tools available — design QA phases must be skipped or deferred
- `suppressedResolvers` from the host config should be respected

## Boundary Instruction

Per the Codex host config, Admiral must respect:
> Do NOT read or execute any files under ~/.claude/... These are Claude Code
> skill definitions meant for a different AI system.

This means skill file paths must stay repository-relative or point at the local
`.agents/skills/` directory rather than Claude-specific paths.

## Sandbox Path Rule

Codex confines file writes to the repository root and any explicitly mounted workspaces. The save-protocol probe MUST run inside the repo root:

1. Compute the workspace root from the agent's `cwd` (do not hard-code drive letters).
2. Before probing, inspect `{workspace}/skillset-saves/_latest.md` and classify the save directory per `save-protocol.md` Section 4.0. If an active reclaimable run exists, resume it before creating a new run.
3. Probe path: `{workspace}/skillset-saves/_probe-{run-id}.tmp`. If the workspace root is read-only or writes return `EACCES`/`EPERM`, set `Persistence active: no`, surface a single user warning, attempt read-only resume from any readable latest artifacts, and continue in transient mode only if no coherent boundary can be proven.
4. Path normalization: record forward-slash, workspace-relative paths in every save file. Resolve to OS-native form only at the I/O boundary.
5. Never probe outside the workspace — the sandbox will deny the write and the failure will be misread as "no persistence" when the real cause is path scope.

## Mode Re-Probe

Codex tool surface is comparatively static within a session, but per the agent-protocol re-probe rule admiral still re-runs the three-capability probe at every boundary. The most likely transition is **agent -> skill** when the user revokes a tool category mid-run; the rule handles it by completing the current boundary in skill mode and continuing without forcing a retry.

## Session Pin

Codex chat sessions are continuous. Once a run is `*_ACTIVE` and `_lock.md` is held, every subsequent message is routed through admiral even when the user does not say "admiral". The pin clears on `RUN_COMPLETE`, `release admiral`, `/exit-admiral`, or lock staleness.
