# Claude Adapter — Admiral Agent Mode for Claude Code

## Registration

Admiral loads as a skill via Claude Code's CLAUDE.md skill loading mechanism.
In Claude Code, agent mode is a hybrid — the skill provides instructions, and
Claude Code provides tool access natively.

## Tool Mapping

| Admiral Requirement | Claude Code Tool | Usage |
|--------------------|-----------------|-------|
| file-system.read | Read tool | Read save-protocol state, skill files |
| file-system.write | Write tool | Write state, packages, deliverables |
| file-system.list | Glob tool | Enumerate directories |
| file-system.search | Grep tool, Glob tool | Find files, text search |
| terminal.execute | Bash tool | Run scripts, validation |
| search.grep | Grep tool | Exact text matches |
| sub-agent.invoke | Agent tool | Delegate to sub-agents |
| memory | N/A | Use file-based session memory |

## Hybrid Execution

Claude Code occupies a unique position: it loads skills as instructions but has
native tool access. This means Admiral can operate in a hybrid mode:

1. **Skill content loaded**: SKILL.md provides the pipeline logic and contracts.
2. **Tools available**: Read, Write, Edit, Bash, Glob, Grep, Agent are all native.
3. **Agent tool for delegation**: Sub-orchestrators can be invoked via the Agent tool.
4. **No explicit registration**: No separate agent manifest needed; Claude Code
   infers capabilities from the loaded skill and available tools.

## Sub-Agent Delegation

Claude Code's Agent tool allows dispatching sub-tasks:

```
Use the Agent tool to delegate: "{handoff template}"
```

The Agent tool creates a sub-context that can access tools but does not carry
the parent's full conversation history. All required inputs must be in the prompt.

## State Management

Claude Code has native file access, so save-protocol management is direct:

1. Use Read and Write tools for the run-state, lock, and audit-trail records.
2. Use Bash for validation scripts and packaging.
3. Use the file system as the source of truth, exactly as the other platforms do.
4. At the start of every active turn, inspect `skillset-saves/_latest.md` before creating new state. Resume an active reclaimable run; if activation or probing fails, attempt read-only resume before degrading to transient mode.

## Constraints

- Claude Code is the primary development host (host config: `denylist` mode, no suppressions)
- All skill features are available (no `suppressedResolvers`)
- `learningsMode: full` — complete learning capability
- No description limit on frontmatter
- Co-author trailer: `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`

## Session Continuity

Claude Code sessions can be long-running. Admiral leverages this by:

1. Maintaining the save-protocol as persistent state across context compaction
2. Using the CLAUDE.md learnings file for cross-session knowledge
3. Relying on the lock/heartbeat mechanism for crash recovery

## Plan Mode Transition

Claude Code's plan mode disables Edit, Write, NotebookEdit, and Bash-write operations until ExitPlanMode runs. Admiral entered during plan mode probes as **skill mode** (no file-system.write, no terminal.execute). When the user exits plan mode, Claude Code does **not** notify admiral — the next turn simply allows the suppressed tools again.

Implication: admiral MUST re-probe execution mode at the start of every turn while a run is active, not only at intake. The cached `execution_mode: skill` from the plan-mode RUN_INIT will be stale immediately after ExitPlanMode. Without the re-probe, the first agent-mode delegation (e.g. an Agent tool call to a sub-orchestrator) will be emitted as instruction text instead of a programmatic call, and the user will see the run "stall" until they retry.

The mode re-probe rule in `agent-protocol.md` ("Per-Boundary Re-Probe") covers this case: detect the upgrade, write `MODE_RECHECK` with `action: upgrade`, and continue under agent mode in place.

## Write-Capability Probe

The probe defined in `save-protocol.md` Section 4 maps to Claude Code tools as:

1. `Write` to `skillset-saves/_probe-{run-id}.tmp` with a short ASCII payload.
2. `Read` the same path and verify byte equality.
3. `Bash` `rm "skillset-saves/_probe-{run-id}.tmp"` (use forward slashes; the shell is bash on Windows under Claude Code).

A probe failure on any step downgrades the run to `Persistence active: no` and surfaces a single user-visible warning. The most common cause on Claude Code is plan mode still being active — the probe writes will silently no-op or error. When that happens after an active latest run was detected, Admiral must still read the saved state and continue in read-only resume mode when the boundary can be proven.

## Session Pin

Claude Code supports continuous turns, so admiral honors the session pin. Once a run is `*_ACTIVE` with `_lock.md` held, every subsequent turn is routed through admiral even when the user does not type "admiral" or invoke `/admiral`. Routing precedence in this host: explicit slash command > admiral pin > free conversation. The user clears the pin with `release admiral`, `/exit-admiral`, or by waiting for `RUN_COMPLETE`.
