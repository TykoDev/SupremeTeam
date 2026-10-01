---
last_discovery_at: 2026-06-30T02:58:03Z
discovery_ttl_hours: 480
host: codex
workspace: SupremeTeam
protocol_version: 1
---

# MCP Tools Registry

This is a schema and cache, not a claim about live tools. `admiral` reads it at
intake. When the file is missing, empty, at the epoch placeholder, or older than
`discovery_ttl_hours`, discover tools through the active host, show the user the
diff, and ask them to confirm material changes before rewriting the registry.
Preserve user annotations, and append `MCP_REGISTRY_CHECK` with `use-cache` or
`refreshed` to the run audit trail.

The `discovery_ttl_hours` frontmatter field is the single source of truth for
the staleness window. Prose elsewhere that says "480 hours" is quoting this
default for readability.

Record each confirmed tool as a row. Use `Server:tool_name` in skill
instructions. Never fabricate availability from this template, and never carry
tool state silently between hosts.

## Global tools

| Tool | Server | When to use | Prefer over |
|------|--------|-------------|-------------|
| browser_navigate, browser_snapshot, browser_take_screenshot, browser_click, browser_resize, browser_tabs | mcp__playwright | Drive and inspect browser pages for UI verification and accessibility-state checks | Blind DOM assumptions or screenshots without an action path |
| browser_console_messages, browser_network_requests, browser_network_request | mcp__playwright | Inspect client-side errors and API traffic during frontend debugging | Guessing at browser failures from server logs |
| js, js_reset, js_add_node_module_dir | mcp__node_repl | Run JavaScript in a persistent Node kernel for browser control and generated visual checks | One-off scripts when persistent REPL state helps |
| automation_update | codex_app | Create, inspect, update, or delete automations, reminders, and recurring checks | Hand-written RRULE plumbing |
| GitHub issue and PR helpers | mcp__codex_apps__github | Inspect and mutate issues, pull requests, labels, and review state | Manual REST or GraphQL calls |
| Sites hosting helpers | mcp__codex_apps__sites | Manage Sites project metadata, access, and saved-version deployment | Invented deployment ids or unsaved deployment attempts |
| Workspace agent helpers | mcp__codex_apps__workspace_agents | Search and manage editable workspace agents, attached files, and API channels | Manual Agent Studio instructions when connector state is available |
| resume_agent, close_agent | multi_agent_v1 | Resume or close sub-agents when a multi-agent workflow is in progress | Leaving completed helpers open or recreating a closed collaborator |

## Workspace tools

| Tool | Server | When to use | Prefer over |
|------|--------|-------------|-------------|
| Current Codex session | tool_search-discovered surface | No workspace-scoped MCP servers were exposed beyond the global tools during the 2026-06-30 refresh | Carrying stale workspace-only rows from another host |

## Notes

- The workspace copy always wins over a global mirror at
  `~/.claude/skills/mcp-tools.md`.
- Refresh when the host changes or `last_discovery_at` exceeds the TTL. The
  prompt fires once per run and does not repeat unless the user asks.
- The design and review pipelines treat this file as the browser-automation
  source of truth for preview rendering, contrast verification, and component
  audits.
- Reviewers cite this file when a deliverable used a built-in tool where a
  documented MCP tool was the better fit.
