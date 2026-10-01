---
last_discovery_at: 2026-05-09T15:01:06.1849699+02:00
discovery_ttl_hours: 480
host: copilot
workspace: pa_deno
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
| navigate, snapshot, wait_for, tabs | microsoft-pla-browser | Navigate pages, inspect accessibility state, wait for UI transitions, manage tabs during browser-driven verification | Ad hoc screenshots or blind DOM assumptions |
| click, hover, press_key, type, fill_form, select_option, drag | microsoft-pla-browser | Drive browser UI flows, forms, and interaction-heavy verification | Manual speculative interaction logic |
| take_screenshot, evaluate, run_code | microsoft-pla-browser | Capture visual state or run narrow page-side inspection during browser verification, asset export review, and frontend/UI design preview and audit work | Rebuilding UI state from logs alone |
| network_requests, console_messages | microsoft-pla-browser | Inspect browser-side API traffic and console failures during frontend/UI preview/audit troubleshooting | Guessing at client/runtime failures |
| context7 docs | io.github.upstash/context7 | Pull current package and framework documentation when repo context is insufficient or stale | Guessing third-party APIs from memory |
| playwright automation | microsoft/playwright-mcp | Use the configured Playwright MCP server for browser-driven workflows in hosts that surface it from VS Code MCP config | Hand-rolled browser scripts without an MCP driver |
| AI Platform toolset | ai-platform | Reach Google AI Platform and reasoning-engine MCP capabilities when the host surfaces the configured server tools | Raw REST or gcloud probing for agent-platform exploration |
| App topology toolset | app-typology | Inspect deployed application topology and service relationships through the configured MCP server | Manual topology reconstruction from scattered resource listings |
| Agent registry toolset | agent-registry | Query registry and publication metadata through MCP when the host exposes the configured server tools | Direct API calls for read-heavy registry checks |
| Cloud Assist toolset | cloud-assist | Use Gemini Cloud Assist's guided GCP assistance when the configured server is available in-host | Searching docs manually for common GCP operational guidance |
| Resource Manager toolset | resource-manager | Inspect GCP project and hierarchy metadata through the configured MCP server | Repetitive gcloud resource enumeration |

## Workspace Tools

MCP servers scoped to this workspace or project. Populated by the active orchestrator on first discovery.

| Tool | Server | When To Use | Prefer Over |
|------|--------|-------------|-------------|
| mcp_microsoft_pla_browser_* | microsoft-pla-browser | Workspace session browser automation and UI verification for chat, skills, and preview flows | External browser tooling outside the active session |

## Notes For Admiral

- This file lives at the workspace root, not under `skillset-saves/`. It survives across runs and across hosts.
- Mirror copy at `~/.claude/skills/mcp-tools.md` (the global skill set) is a fallback for hosts whose workspace lacks one. The workspace copy always wins when both exist.
- When refreshing, preserve any user-added "when to use" or "prefer over" annotations — re-prompt only the tool list, not the guidance.
- Never silently overwrite existing entries with auto-detected ones; always show the user the diff before writing.
- The current VS Code MCP server inventory comes from the user config at `c:/Users/stoff/AppData/Roaming/Code/User/mcp.json`.
- In Copilot host sessions, `microsoft-pla-browser` appears as explicit callable tool wrappers, while other configured servers may remain editor-level MCP integrations rather than direct chat tool wrappers.
