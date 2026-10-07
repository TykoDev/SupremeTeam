---
last_discovery_at: 1970-01-01T00:00:00Z
discovery_ttl_hours: 480
host: ""
workspace: ""
protocol_version: 1
---

# MCP Tools Registry

## Contents

- Responsibility and intake
- Global tools
- Workspace tools
- Enforcement
- Failure paths

## Responsibility and intake

This shipped file is a blank discovery template, not a live inventory. The epoch
and empty tables mean **undiscovered**, not an expired confirmed cache and not a
reason to pause every fresh installation. Actual availability comes from the
active host's exposed tools; never fabricate a browser or MCP server from a row.

`admiral` owns the project cache at `.harness-state/mcp-tools.md`, declared in
`save-ownership.yaml`. Its `workspace` is the resolved project-root path and its
`host` names the active host. This cache wins over the installed template; no
host-specific mirror directory is a portable workspace cache. Do not rewrite the
installed skill-set file during intake. Preserve user annotations when refreshing
the project cache, and never silently reuse another host's inventory.

At intake run `python skills/scripts/mcp_registry.py --project-root . --host <host>`.
The frontmatter `discovery_ttl_hours` is the freshness window (default 480 hours).
For missing, blank, invalid, stale, or mismatched caches, inspect the active host's
tool catalog. Ask for confirmation only for material tool or permission changes,
not for the blank template itself. No MCP tools needed or exposed? Record
`mcp_registry_check=not-needed` and proceed with native tools. Discovery unavailable?
Record `mcp_registry_check=unavailable`; block only work requiring the missing
capability, not unrelated intake. A stale inventory is never availability proof.

After confirmed discovery, copy the template into the project cache, retain its
annotations, fill the host/workspace, tables and timezone-qualified discovery
timestamp. Record `--set mcp_registry_check=refreshed` on `save_run.py create` or
the first `checkpoint`; otherwise record `use-cache`, `not-needed`, or
`unavailable`. There is no operation that appends an audit line by name.

Use `Server:tool_name` in instructions for a discovered tool. Confirm its live
availability and authorization before invoking it even when the cache is fresh.
Installers preserve user-modified copies; they may replace an unedited shipped
copy from a recognized prior release. Project caches are runtime state and are
never installed or committed.

## Global tools

| Tool | Server | When to use | Prefer over |
|------|--------|-------------|-------------|

## Workspace tools

| Tool | Server | When to use | Prefer over |
|------|--------|-------------|-------------|

## Enforcement

`scripts/mcp_registry.py` reads metadata and compares timestamps against the
configured TTL and host/workspace identity. `scripts/test_mcp_registry.py`
exercises blank, missing, stale, future, invalid and mismatched caches. Neither
confirms live tools, authenticates discovery, checks permissions, nor forces an
orchestrator to run the diagnostic. Discovery, confirmation, annotation retention,
and choosing a better tool remain host-aware judgement. Empty tables promise no
browser automation; dependent rendering stages must report their real capability
gaps under their own evidence contracts.

## Failure paths

- Missing or blank cache: discover if needed; do not demand confirmation of an
  empty template or claim a refresh occurred.
- Invalid metadata, expired TTL, future timestamp or identity mismatch: do not
  trust the cache; refresh from the host or record discovery unavailable.
- Discovery or required tool unavailable: retain the cache unchanged, name the
  blocked evidence, and continue only independent work. Never substitute a pass.
- User declines material changes: keep annotations and prior cache unchanged;
  do not invoke the unconfirmed capability.
- Cache cannot be written: preserve the discovery evidence and report it as
  unpersisted; do not label the cache refreshed.
