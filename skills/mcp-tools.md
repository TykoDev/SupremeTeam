---
last_discovery_at: 1970-01-01T00:00:00Z
discovery_ttl_hours: 480
host: ""
workspace: ""
protocol_version: 1
---

# MCP Tools Registry

This is a schema and cache, not a claim about live tools. `admiral` reads it at
intake. When the file is missing, empty, at the epoch placeholder, or older than
`discovery_ttl_hours`, discover tools through the active host, show the user the
diff, and ask them to confirm material changes before rewriting the registry.
Preserve user annotations, and record the outcome as `--set mcp_registry_check=use-cache`
or `--set mcp_registry_check=refreshed` on `save_run.py create` or the run's first
`checkpoint`: the audit trail has no operation that appends a line by name.

The `discovery_ttl_hours` frontmatter field is the single source of truth for
the staleness window. Prose elsewhere that says "480 hours" is quoting this
default for readability.

Record each confirmed tool as a row. Use `Server:tool_name` in skill
instructions. Never fabricate availability from this template, and never carry
tool state silently between hosts.

## Global tools

| Tool | Server | When to use | Prefer over |
|------|--------|-------------|-------------|

## Workspace tools

| Tool | Server | When to use | Prefer over |
|------|--------|-------------|-------------|

## Notes

- This copy is the blank template the installer ships: `last_discovery_at` is the
  epoch (`1970-01-01T00:00:00Z`) and both tables are empty, so the first intake on
  any host discovers that host's tools and asks the user to confirm them. Once the
  file holds a confirmed registry the installer never replaces it, so the registry
  survives upgrades; delete the file and re-run the installer to get the blank
  template back.
- The workspace copy always wins over a global mirror at
  `~/.claude/skills/mcp-tools.md`.
- Refresh when the host changes or `last_discovery_at` exceeds the TTL. The
  prompt fires once per run and does not repeat unless the user asks.
- The design and review pipelines treat this file as the browser-automation
  source of truth for preview rendering, contrast verification, and component
  audits.
- Reviewers cite this file when a deliverable used a built-in tool where a
  documented MCP tool was the better fit.
