# Failure Modes Reference

`../SKILL.md` carries the five failures that change what Admiral does *next*
(input, degraded host, revise exhaustion, lost pointer, session pin). This file
carries the rest: the lineage, persistence, mode, and environment failures whose
handling is procedural rather than routing. Nothing here repeats a row stated in
`../SKILL.md`.

## Contents

1. Lineage and drift
2. Persistence and save state
3. Mode and environment
4. Registry and hook readiness

## Lineage And Drift

| Scenario | Response |
| --- | --- |
| A resume package claims approval but the revision lineage or gate record does not match the submitted artifact set | Rewind to the earliest affected boundary and explain exactly which approval chain broke. |
| An upstream package changes after downstream work has already started | Invalidate the dependent handoffs, preserve the superseded evidence, and replay only the boundaries affected by the drift. |
| Two handoff submissions refer to the same boundary but carry conflicting verdict histories | Preserve both records, treat the boundary as disputed, and escalate rather than silently normalizing the conflict. |

## Persistence And Save State

| Scenario | Response |
| --- | --- |
| Persistence activation fails after a missing or inactive `skillset-saves/` directory is detected | Warn once, record `persistence_activation_result: failed` when writable, try read-only resume from any readable latest artifacts, then continue in transient mode only if no coherent boundary can be proven. |
| A saved latest run is unreadable or partially corrupt | Preserve any readable artifacts, classify the directory as `unreadable`, attempt read-only resume from the earliest provable boundary, and otherwise continue transiently with a clear warning instead of overwriting the evidence. |
| Persistence write-probe fails at intake but admiral still emits `Persistence active: yes` | Treat as a contract violation. Downgrade the run to `Persistence active: no`, warn the user once, and rewrite every Save Context block accordingly before any sub-orchestrator delegation. |
| `skillset-saves/` contains an active latest run when the user sends a fresh-looking request | Treat the session pin and saved state as authoritative: run the resume protocol, present the active boundary, and do not fork a new run unless the user explicitly asks for one. |

## Mode And Environment

| Scenario | Response |
| --- | --- |
| Mode probe at a boundary disagrees with the cached `execution_mode` | Reconcile in place: update `_state.md`, append `MODE_RECHECK` with `cached`, `detected`, and `action`, continue under the new mode. Do not abort the delegation, do not force the user to retry. |
| A create-skill or create-team request arrives without usable trigger language, success criteria, or packaging target | Stop at intake, collect the missing intent, and do not hand skill-maker an underspecified brief. |

## Registry And Hook Readiness

| Scenario | Response |
| --- | --- |
| `mcp-tools.md` is missing or `last_discovery_at` exceeds `discovery_ttl_hours` (default 480h) at intake | Pause at intake, prompt the user with the auto-detected MCP list, and only proceed once the registry is confirmed or rewritten with a fresh `last_discovery_at`. |
| `verify_registration.py` reports MISSING or UNKNOWN at intake — one or more harness hooks are not registered for the active host | Surface the `REGISTER_PROMPT`, explain that entry routing is advisory-only until the prompt-submit hook is registered, and offer to register all three hooks by rerunning the installer with `-RegisterHooks` / `--register-hooks`. If the user declines, warn once and continue (the description/doctrine layer still applies). A new or changed hook config may need `/hooks` or a restart to load. |
| `check_readiness.py` reports Python too old, hooks missing, or no active pinned save run after startup | Record `RUNTIME_READINESS_CHECK`, surface the specific failed dimension, retry only the save startup check when saves are missing, and otherwise continue with an explicit degraded-mode note unless the user approves hook registration or Python installation. |
