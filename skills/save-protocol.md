# Save Protocol

Authoritative contract for the persistent save system used by the top-level orchestrator in this skill set — `admiral` (design/build/review pipeline) — together with its sub-orchestrators, specialists, gatekeepers, and reviewers. Every reference to "save-protocol.md" elsewhere in the skill set resolves here. The protocol owns both persistence writes and the startup decision tree: detect an active `skillset-saves/` run, resume it when safe, activate persistence when no active run exists, and degrade gracefully when activation fails.

This document is host-agnostic. Per-host I/O details live in `admiral/agent/adapters/{claude,codex,copilot}.md` and are referenced where they matter.

## Orchestrator Scopes

| Orchestrator | Run holder name in `_lock.md` | Cross-boundary handoff file | Pipeline directory names |
|--------------|------------------------------|-----------------------------|--------------------------|
| `admiral` | `admiral` | `gatekeeper-admiral_handoff-{N}.md` | `design`, `build`, `review`, `skill-creation` |

The orchestrator owns the write-ownership shape (Section 3) within its run. All rules — probe, mode re-check, session pin, save triggers, save-context block, resume protocol — apply uniformly.

---

## 1. Directory Structure

All saves live under the workspace root in `skillset-saves/`. A run is a single end-to-end admiral invocation, identified by `run_id = {ISO-date}_{slug}_{random6}` (e.g. `2026-04-23_dashboard-redesign_a3f9k2`).

```
skillset-saves/
  _index.md                       # rolling list of all runs
  _latest.md                      # pointer to the most recent run
  runs/
    {run-id}/
      _run-manifest.md            # immutable run header (mode, host, scope)
      _state.md                   # current state machine snapshot (mutable)
      _lock.md                    # session ownership + heartbeat (mutable)
      _audit-trail.md             # append-only event log
      _save-protocol.md           # snapshot of this protocol's version + probe results
      admiral/
        intake.md                 # normalized user request
        standalone-context.md     # context bundle when sub-orchestrators run cold
        delivery-package.md       # final consolidated package (RUN_COMPLETE)
        gatekeeper-admiral_handoff-{N}.md    # one per cross-stage gate
      design/
        _phase-state.md
        _skip-record.md           # only when a skip is taken
        phase-{N}_{skill}/
          _phase-state.md
          gatekeeper-verdict.md
          deliverable_{name}.md
          review-packet.md
        design-package.md
        delegation-log.md
      build/        ...same shape...
      review/       ...same shape...
      skill-creation/   # only for create-skill / create-team runs
```

Paths recorded **inside** save files always use forward slashes and are relative to the workspace root. OS-native conversion (backslashes on Windows) happens at the I/O boundary in the adapter layer.

---

## 2. File Formats

Every file is markdown with optional YAML frontmatter. Mutable files (`_state.md`, `_lock.md`) are rewritten in full each update. Append-only files (`_audit-trail.md`) only ever grow.

### `_index.md`

```markdown
# Skillset Saves Index

| Run ID | Started | Mode | State | Scope |
|--------|---------|------|-------|-------|
| {run-id} | {ISO} | {agent|skill} | {STATE} | {scope summary} |
```

### `_latest.md`

```markdown
---
latest_run_id: {run-id}
updated_at: {ISO}
---
```

### `_run-manifest.md` (immutable after RUN_INIT)

```yaml
---
run_id: {run-id}
started_at: {ISO}
host: claude-code | codex | copilot | unknown
workspace_root: {forward-slash path the host advertises}
scope: full | partial | resume | create-skill | create-team
requested_endpoints: [design, build, review]
protocol_version: 2
---
```

### `_state.md` (mutable, rewritten in full)

```yaml
---
run_id: {run-id}
state: RUN_INIT | DESIGN_ACTIVE | DESIGN_GATE_PENDING | DESIGN_GATE_REVISE | BUILD_ACTIVE | ...
                  | DISPUTED_AWAITING_USER | DELIVERED
execution_mode: agent | skill
execution_mode_detected_at: {ISO}
persistence_active: true | false
persistence_probe_result: ok | failed | skipped
persistence_probed_at: {ISO}
save_directory_status: active | inactive | missing | unreadable | conflict
persistence_activation_result: activated | resumed | failed | skipped
persistence_activation_checked_at: {ISO}
resume_source: latest | explicit | none
activation_failure_reason: {string or null}
mcp_registry_checked_at: {ISO}
mcp_registry_age_hours: {number}
session_pin: true | false
gatekeeper_verdict_pending: true | false
active_delegation:
  target: {name} | null
  started_at: {ISO} | null
  timeout_seconds: 600
last_heartbeat: {ISO}
updated_at: {ISO}
---
```

### `_lock.md` (mutable; the session-pin signal)

```yaml
---
run_id: {run-id}
holder: admiral
host: {claude-code|codex|copilot}
session_id: {host-supplied or admiral-generated}
acquired_at: {ISO}
last_heartbeat: {ISO}
heartbeat_interval_seconds: 300
stale_after_seconds: 1800
---
```

### `_audit-trail.md` (append-only)

```
{ISO}  RUN_INIT                    run={run-id} mode=agent host=claude-code
{ISO}  SAVE_STATUS_CHECK           status=inactive action=activate
{ISO}  PERSISTENCE_PROBE           result=ok path=skillset-saves/_probe-{run-id}.tmp
{ISO}  PERSISTENCE_ACTIVATION      result=activated run={run-id}
{ISO}  RESUME_FALLBACK             source=latest result=resumed-read-only
{ISO}  LATEST_POINTER_REBUILT      source=runs-scan run={run-id} reason=missing-latest-pointer
{ISO}  MCP_REGISTRY_CHECK          age_hours=12 action=use-cache
{ISO}  STATE_TRANSITION            from=RUN_INIT to=DESIGN_ACTIVE
{ISO}  MODE_RECHECK                cached=skill detected=agent action=upgrade
{ISO}  DELEGATION_SENT             target=commander submission_id={...}
{ISO}  GATE_VERDICT                stage=design verdict=APPROVED
{ISO}  HEARTBEAT_REFRESH           lock_age_seconds=298
{ISO}  SESSION_PIN_RELEASE         reason=user-command
{ISO}  RUN_COMPLETE                state=DELIVERED
```

### `gatekeeper-admiral_handoff-{N}.md` (two-phase write)

```yaml
---
submission_id: {run-id}_handoff-{N}_attempt-{M}_{ISO}
submission_status: PENDING | VERDICT_RECORDED
verdict: PENDING | APPROVED | REVISE | ESCALATE
package_path: {forward-slash relative path}
revision: {N}
submitted_at: {ISO}
verdict_at: {ISO}
---
{verdict body / findings list}
```

### `_save-protocol.md` (per-run snapshot)

```yaml
---
protocol_version: 2
captured_at: {ISO}
probe_results:
  write: ok | failed
  read: ok | failed
  delete: ok | failed
notes: {free text — e.g. "workspace read-only, persistence disabled"}
---
```

### `admiral/delivery-package.md`

Final approved package. Format owned by admiral; downstream consumers read only this.

### `{pipeline}/_skip-record.md`

```yaml
---
pipeline: design | build | review
skipped_at: {ISO}
reason: {one line}
approved_by: user | upstream-package-evidence
upstream_artifact: {forward-slash relative path}
---
```

---

## 3. Write Ownership

| Owner | Files |
|-------|-------|
| Admiral | `_index.md`, `_latest.md`, `_run-manifest.md`, `_lock.md`, `_state.md`, `_audit-trail.md`, `_save-protocol.md`, `gatekeeper-admiral_handoff-{N}.md`, `admiral/intake.md`, `admiral/standalone-context.md`, `admiral/delivery-package.md`, `{pipeline}/_skip-record.md` |
| Sub-orchestrators (`commander`, `build-management`, `code-chief`) | `{pipeline}/_phase-state.md`, `{pipeline}/gatekeeper-verdict.md`, `{pipeline}/{package}.md`, `{pipeline}/delegation-log.md` |
| Specialists (`researcher`, `planner`, `architect`, `bob-the-builder`, etc.) | `{phase-dir}/deliverable_{name}.md`, `{phase-dir}/review-packet.md` |
| Gatekeepers | **Do not write to `skillset-saves/`.** Return verdicts to the invoking orchestrator, which captures them. |

Anyone writing outside their column is a bug. Reviewers cite this table when finding it.

---

## 4. Write-Capability Probe (Mandatory)

### 4.0 Startup Activation and Resume Check

Before classifying a user request as a new run, the owning orchestrator MUST check whether `skillset-saves/` is already active:

1. Inspect `skillset-saves/_latest.md` if it exists.
2. If `_latest.md` points at a run, read `runs/{latest_run_id}/_state.md` and `_lock.md`.
3. Classify the save directory:
   - `active`: latest run is in any non-terminal state (`*_ACTIVE`, `*_GATE_PENDING`, `*_GATE_REVISE`, `DISPUTED_AWAITING_USER`) and the lock is current or stale/reclaimable.
   - `inactive`: latest run is `DELIVERED` or no incomplete boundary exists.
   - `orphaned`: the `_latest.md` pointer is absent, unreadable, or resolves to a missing or terminal run, **but** `runs/` still holds at least one run whose `_state.md` is parseable and non-terminal. This is the partial-persistence case the protocol exists to survive — recover it, do not treat it as a fresh start.
   - `missing`: `skillset-saves/` does not exist, or it exists with neither a usable `_latest.md` pointer nor any parseable non-terminal run under `runs/`.
   - `unreadable`: expected files exist but cannot be parsed or read.
   - `conflict`: latest lock is fresh and held by another session.

   The pointer is a convenience, not the source of truth: never conclude "no run to resume" from a missing `_latest.md` alone — scan `runs/` first (Section 10 step 1).
4. Record `SAVE_STATUS_CHECK` with the classification and update `_state.md` once a writable run state exists. If no writable state exists yet, carry the classification in memory and write it after activation succeeds.

Routing rules:

- `active` -> run the Resume Protocol (Section 10) before starting new work. Do not silently fork a second run over an incomplete one.
- `orphaned` -> recover instead of forking. Select the most recent run under `runs/` whose `_state.md` is non-terminal (run-ids sort chronologically; break ties with `updated_at`/`last_heartbeat`), rebuild `_latest.md` to point at it, append `LATEST_POINTER_REBUILT` to that run's `_audit-trail.md`, then run the Resume Protocol (Section 10). Never start a fresh run while a recoverable orphan exists.
- `conflict` -> warn the user that another session owns the run and stop unless the user explicitly tells admiral to create a new run or reclaim after the lock becomes stale.
- `inactive` or `missing` -> attempt persistence activation by creating `skillset-saves/`, running the probe below, and writing a fresh `RUN_INIT` record.
- `unreadable` -> attempt a read-only resume from any parseable artifacts. If no coherent run state can be proven, warn once and continue the current request in transient mode with `Persistence active: no`.

Activation is not optional when file-system write capability exists. The orchestrator MUST attempt it before falling back to transient mode. If activation fails:

1. Set `persistence_active: false`, `persistence_activation_result: failed`, and `activation_failure_reason` if a state record can be written.
2. Emit one warning: `Persistence activation failed for this run — continuing in transient mode; resume will use any readable saved artifacts only.`
3. If a previous latest run was detected, run the Resume Protocol in read-only mode and continue from the earliest provable incomplete boundary when possible.
4. If no provable resume boundary exists, continue the current request inline in transient mode. Do not loop on activation, and do not claim saves are active.

### 4.1 Probe Mechanics

The protocol **never** trusts host capability detection alone. Before the first save in a run:

1. Compute `probe_path = skillset-saves/_probe-{run-id}.tmp`.
2. Write a 12-byte payload to `probe_path` (e.g. `probe-{6 random hex}`).
3. Read it back. Compare bytes.
4. Delete it.
5. Record the outcome on `_state.md` (`persistence_probe_result`, `persistence_probed_at`) and append `PERSISTENCE_PROBE` to `_audit-trail.md`.

If any step fails:

- Set `persistence_active: false` for the entire run.
- Emit one user-visible warning: `Persistence disabled for this run — host could not write to skillset-saves/{reason}. Continuing in transient mode.`
- Continue execution; never silently re-enable persistence.

A re-probe runs at every `STATE_TRANSITION` by touching `_lock.md`. If the touch fails, downgrade to `persistence_active: false` mid-run, append `PERSISTENCE_DOWNGRADE` to the audit trail (in memory if needed), and warn the user once.

Adapter-specific probe tools:

- **claude.md**: `Write` then `Read` then `Bash rm` (Unix shell on Windows: `rm` works in Git Bash; otherwise `del` via `cmd.exe`).
- **codex.md**: standard file-write / file-read / file-delete primitives — must run inside repo root or probe fails.
- **copilot.md**: `create_file` then `read_file` then `replace_string_in_file` to empty, then a follow-up delete via `run_in_terminal`. If `create_file` returns non-OK, downgrade immediately.

---

## 5. Path Normalization

- **Inside save files**: forward slashes, workspace-relative.
- **At the I/O boundary**: convert to OS-native if the host requires it.
- **Windows specifically**: never hard-code drive letters (e.g. `C:\`). Use the `workspace_root` recorded in `_run-manifest.md`. When the host advertises a path with backslashes, store the forward-slash form in save files and convert back only when calling tools that demand it.
- **Resume across hosts**: a run started in Claude Code (Windows) must resume in Codex (Linux) by reading the relative paths and re-resolving against the new `workspace_root`.

---

## 6. Mode Re-Check Rule

`execution_mode` is detected at `RUN_INIT` and recorded in `_state.md` with `execution_mode_detected_at`. Mode is **not** static.

Before each new boundary delegation:

1. Re-run the three-capability probe (sub-agent, file I/O, command execution) — cheap because results come from the host's tool list.
2. If the result differs from the cached `execution_mode`:
   - Update `_state.md` with the new mode and refresh `execution_mode_detected_at`.
   - Append `MODE_RECHECK` to `_audit-trail.md` with `cached`, `detected`, and `action` (`upgrade`/`downgrade`).
   - Continue under the new mode immediately. No retry, no user prompt, no aborted delegation.

On resume, admiral reads the saved `execution_mode` but **always** re-probes before the first delegation. The saved value is a hint, not the truth.

This rule directly fixes the plan-mode → agent-mode transition: when Claude Code exits plan mode, the next admiral turn re-probes, sees the Agent / Edit / Write tools now exist, and upgrades in place.

---

## 7. Session Pin (Auto-Routing)

While a run is in any `*_ACTIVE`, `*_GATE_PENDING`, or `*_GATE_REVISE` state and `_lock.md` is held by the current session, `session_pin: true` in `_state.md`.

When `session_pin` is true, every user input in the same session is treated as input to admiral, even when the user does not say "admiral". The owning sub-orchestrator interprets the input in scope.

Routing precedence:

1. Explicit slash command (e.g. `/help`, `/exit-admiral`).
2. Admiral session pin → route to active sub-orchestrator.
3. Free conversation (only when no pin or pin is released).

Pin clears on:

- `RUN_COMPLETE` (state set to `DELIVERED`).
- User command `release admiral` or `/exit-admiral`.
- Lock staleness (`now - last_heartbeat > stale_after_seconds`).

Each pin clear appends `SESSION_PIN_RELEASE` with reason to the audit trail.

---

## 8. Save Triggers

| Trigger | Owner | Files Written |
|---------|-------|---------------|
| `SAVE_STATUS_CHECK` | admiral | `_state.md` when writable, `_audit-trail.md` when writable |
| `PERSISTENCE_ACTIVATION` | admiral | `skillset-saves/` directory, `_index.md`, `_latest.md`, `_run-manifest.md`, `_lock.md`, `_state.md`, `_audit-trail.md`, `_save-protocol.md` |
| `RUN_INIT` | admiral | `_index.md`, `_latest.md`, `_run-manifest.md`, `_lock.md`, `_state.md`, `_audit-trail.md`, `_save-protocol.md`, `admiral/intake.md` |
| `PERSISTENCE_PROBE` | admiral | `_save-protocol.md`, `_state.md`, `_audit-trail.md` |
| `MCP_REGISTRY_CHECK` | admiral | `mcp-tools.md` (workspace root, only if refresh occurs), `_audit-trail.md` |
| `STATE_TRANSITION` | admiral | `_state.md`, `_audit-trail.md`, `_lock.md` (heartbeat) |
| `MODE_RECHECK` | admiral | `_state.md`, `_audit-trail.md` |
| `CROSS_PIPELINE_GATE` | admiral | `gatekeeper-admiral_handoff-{N}.md` (PENDING → VERDICT_RECORDED), `_state.md`, `_latest.md` |
| `SKIP_DECISION` | admiral | `{pipeline}/_skip-record.md`, `_run-manifest.md`, `_state.md`, `_audit-trail.md` |
| Specialist deliverable | specialist | `{phase-dir}/deliverable_{name}.md` |
| Phase verdict | sub-orchestrator | `{pipeline}/_phase-state.md`, `{pipeline}/gatekeeper-verdict.md` |
| `RUN_COMPLETE` | admiral | `admiral/delivery-package.md`, `_state.md` (`DELIVERED`), `_lock.md` (released), `_index.md`, `_latest.md`, `_audit-trail.md` |
| `SESSION_PIN_RELEASE` | admiral | `_state.md`, `_audit-trail.md`, `_lock.md` |

---

## 9. Save Context Block (Required in Every Delegation)

Admiral and sub-orchestrators include this block when delegating downstream:

```markdown
### Save Context
- **Run ID**: {run-id}
- **Save path**: skillset-saves/runs/{run-id}/{pipeline}/
- **Persistence active**: yes | no
- **Persistence probe result**: ok | failed | skipped
- **Context tier**: 1 | 2 | 3 | 4
- **Artifact mode**: inline | reference | best-effort-inline
- **Standalone fallback ref**: {forward-slash path or "none"}
- **Skipped upstream stages**: {none or list}
- **Session pin**: true | false
- **Execution mode**: agent | skill
```

When `Persistence active: no`, the receiving skill skips all save operations and returns inline. Never silently write to disk in transient mode.

---

## 10. Resume Protocol

0. Run the Startup Activation and Resume Check (Section 4.0). If it reports `inactive` or `missing`, activation owns the next step; if it reports `orphaned`, recover via the pointer rebuild in step 1; if it reports `conflict`, stop unless the lock can be reclaimed.
1. Read `skillset-saves/_latest.md`. If it is missing, unreadable, or resolves to a missing or terminal run, do **not** conclude "no run to resume": scan `runs/*/_state.md` and select the most recent run in a non-terminal state. When such a run exists (the `orphaned` case in Section 4.0), rebuild `_latest.md` to point at it and append `LATEST_POINTER_REBUILT` to that run's `_audit-trail.md`, then continue from it. Only when neither a usable pointer nor any parseable non-terminal run exists is there nothing to resume.
2. Read `runs/{latest_run_id}/_lock.md`.
   - If `now - last_heartbeat > stale_after_seconds` (default 1800 s) → lock is stale, may be reclaimed. Append `LOCK_RECLAIMED` to audit trail and write a new lock with the current session.
   - If still fresh and `session_id` differs → another session owns the run. Warn the user and stop.
3. Read `_state.md`. Identify the earliest incomplete boundary (`*_ACTIVE` or `*_GATE_PENDING`).
4. Re-run the persistence probe (Section 4) and the mode re-check (Section 6). Update `_state.md` if either changes. If the persistence probe fails but the saved state is readable, continue in read-only resume mode and emit `RESUME_FALLBACK`; if the saved state is not readable, fall back to transient mode.
5. If the run is in `DISPUTED_AWAITING_USER`, present the dispute and wait.
6. Otherwise, re-prepare the handoff for the earliest incomplete boundary and continue.

---

## 11. Adapter Notes

- **Claude Code** (`admiral/agent/adapters/claude.md`): `Write` / `Read` / `Bash` for the probe; Agent tool for delegation; ExitPlanMode does not auto-notify admiral, so the per-boundary mode re-check is the only signal.
- **Codex** (`admiral/agent/adapters/codex.md`): probe must stay inside repo root; sandbox may deny writes outside.
- **Copilot** (`admiral/agent/adapters/copilot.md`): `create_file` failure is the dominant downgrade trigger; `runSubagent` is stateless so the Save Context block must be repeated in every prompt.

---

## 12. Versioning

- `protocol_version: 2` is the current contract. Version 2 adds mandatory startup status classification, persistence activation, and read-only resume fallback.
- Bumping the version requires updating this file, the per-run `_save-protocol.md` template, and every adapter doc in the same change.
