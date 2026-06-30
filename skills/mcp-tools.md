---
last_discovery_at: 2026-06-30T02:58:03.4574837+02:00
discovery_ttl_hours: 480
host: codex
workspace: SupremeTeam
protocol_version: 1
---

# MCP Tools Registry

Globally shared resource listing the MCP (Model Context Protocol) tools available in the current workspace and how they should be used. Lives at the skill set root alongside `design-doctrine.md` and `save-protocol.md`.

`admiral` reads this file at the start of every run. If it is empty (e.g. `last_discovery_at` is the unix epoch placeholder) or older than `discovery_ttl_hours` (default 480 hours = 20 days), the active orchestrator pauses at intake and prompts the user to confirm or refresh the inventory before continuing.

> **Canonical freshness window.** The `discovery_ttl_hours` frontmatter field above is the **single source of truth** for the staleness threshold. Skills and doctrines that mention "480 hours" are quoting this default for readability — when the window changes, edit `discovery_ttl_hours` here and treat the prose mentions as illustrative, not authoritative.

## How To Use This File

- **Sub-orchestrators and specialists**: read this file before reaching for a built-in tool. If a listed MCP tool covers the task better, prefer it.
- **Admiral**: enforce freshness, run the discovery prompt when needed, and rewrite the file with the new `last_discovery_at` after a confirmed discovery.
- **Reviewers**: cite this file when a deliverable used a built-in tool where a documented MCP tool would have been the better fit.
- **Frontend pipeline**: the design team's frontend/UI work (`design/architect`, `design-qa`) treats this file as the browser automation source of truth (preview rendering, contrast verification, component audits) instead of legacy `chrome-devtools` guidance.

The point is to make MCP tools first-class and discoverable instead of forgotten between sessions.

## Discovery Protocol

1. Read the frontmatter `last_discovery_at`. Compute `age_hours = now - last_discovery_at`.
2. If the file is missing, empty, or `age_hours > discovery_ttl_hours`, admiral pauses at intake and asks the user something like:
   > The MCP tool registry is missing or {N} hours stale. I detected the following MCP tools in this session: {auto-detected list}. Confirm, edit, or annotate before I proceed.
3. On confirmation, admiral rewrites this file with:
   - Updated frontmatter (`last_discovery_at`, `host`, `workspace`).
   - One row per tool under **Global Tools** or **Workspace Tools**.
   - A short "when to use" line per tool.
4. Append `MCP_REGISTRY_CHECK` to the run's `_audit-trail.md` with the action taken (`use-cache` or `refreshed`).
5. If `age_hours <= discovery_ttl_hours`, admiral proceeds without prompting and only logs the cache hit.

The discovery prompt fires **once per run**. It does not repeat mid-run unless the user explicitly invokes a refresh.

## Global Tools

MCP servers available across every workspace this host can reach. Populated by the active orchestrator on first discovery; do not hand-edit unless you are also updating `last_discovery_at`.

| Tool | Server | When To Use | Prefer Over |
|------|--------|-------------|-------------|
| browser_navigate, browser_snapshot, browser_take_screenshot, browser_click, browser_resize, browser_tabs | mcp__playwright | Drive and inspect local or remote browser pages, especially UI verification and accessibility-state checks | Blind DOM assumptions or manual screenshots without an action path |
| browser_console_messages, browser_network_requests, browser_network_request | mcp__playwright | Inspect client-side errors, warnings, and API traffic during frontend/runtime debugging | Guessing at browser failures from server logs alone |
| js, js_reset, js_add_node_module_dir | mcp__node_repl | Run JavaScript in the persistent Node-backed kernel for browser control, local JS inspection, generated visual checks, and Playwright-backed workflows | Ad hoc one-off scripts when a persistent REPL state is useful |
| automation_update | codex_app | Create, inspect, update, or delete Codex automations, reminders, recurring checks, and thread heartbeats | Raw automation directives or hand-written RRULE plumbing |
| GitHub issue and PR review helpers | mcp__codex_apps__github | Inspect and mutate GitHub issues, pull requests, labels, assignees, review threads, and review state when the user asks for GitHub work | Manual REST/GraphQL calls for repository collaboration |
| Sites hosting helpers | mcp__codex_apps__sites | Manage Sites project metadata, access, saved-version deployment, and available access groups for deployable web artifacts | Invented deployment IDs or unsaved local deployment attempts |
| Workspace agent helpers | mcp__codex_apps__workspace_agents | Search, inspect, and manage editable workspace agents, attached files, skill files, API channels, and Slack setup readiness | Manual Agent Studio instructions when connector state is available |
| resume_agent, close_agent | multi_agent_v1 | Resume or close existing sub-agents when a multi-agent workflow is already in progress | Leaving completed helper agents open or trying to recreate a closed collaborator |

## Workspace Tools

MCP servers scoped to this workspace or project. Populated by the active orchestrator on first discovery.

| Tool | Server | When To Use | Prefer Over |
|------|--------|-------------|-------------|
| Current Codex session | tool_search-discovered MCP surface | No additional workspace-scoped MCP servers were exposed beyond the global tools above during the 2026-06-30 refresh | Carrying stale workspace-only tool rows from another host |

## Notes For Admiral

- This file lives at the workspace root, not under `skillset-saves/`. It survives across runs and across hosts.
- Mirror copy at `~/.claude/skills/mcp-tools.md` (the global skill set) is a fallback for hosts whose workspace lacks one. The workspace copy always wins when both exist.
- When refreshing, preserve any user-added "when to use" or "prefer over" annotations — re-prompt only the tool list, not the guidance.
- Never silently overwrite existing entries with auto-detected ones; always show the user the diff before writing.
- The 2026-06-30 Codex refresh used `tool_search` discovery from the active session. Older Copilot rows for `microsoft-pla-browser`, Context7, AI Platform, app topology, agent registry, Cloud Assist, and Resource Manager were not observed as callable tools in this Codex thread.
- Host-specific MCP inventories may differ. Refresh this file when the host changes or when `last_discovery_at` exceeds `discovery_ttl_hours`.
