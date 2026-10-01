# Runtime Harness Hooks

Deterministic runtime enforcement, trajectory regulation, save lifecycle management, registration diagnostics, and maintenance tooling for SupremeTeam.

These hooks implement the **Action Realization (Layer 3)** and **Trajectory Regulation (Layer 4)** boundaries defined in [`../../harness-doctrine.md`](../../harness-doctrine.md), enforce the single-writer persistence contract in [`../../save-protocol.md`](../../save-protocol.md), and provide self-healing diagnostics for host integrations.

---

## Contents

1. [Architecture and Layer Mapping](#architecture-and-layer-mapping)
2. [Complete Hook Directory Manifest](#complete-hook-directory-manifest)
3. [Design Guarantees and Principles](#design-guarantees-and-principles)
4. [Registered Lifecycle Hooks](#registered-lifecycle-hooks)
   - [`pre_tool_use.py` and `guard_hook.py` (Layer 3)](#pre_tool_usepy-and-guard_hookpy-layer-3--action-realization)
   - [`post_tool_use.py` (Layer 4)](#post_tool_usepy-layer-4--trajectory-regulation)
   - [`user_prompt_submit.py` (Entry Routing)](#user_prompt_submitpy-entry-routing)
5. [State and Boundary Writers](#state-and-boundary-writers)
   - [`save_run.py` (Run Persistence Writer)](#save_runpy-cli--run-persistence-writer)
   - [`guard_state.py` (Guard and Freeze Boundary Writer)](#guard_statepy-cli--guard-and-freeze-boundary-writer)
6. [Registration, Verification, and Repair](#registration-verification-and-repair)
   - [Supported Hosts and Config Locations](#supported-hosts-and-config-locations)
   - [`check_readiness.py` (Readiness Diagnostic)](#check_readinesspy-diagnostic--runtime-readiness)
   - [`verify_registration.py` (Config Inspector)](#verify_registrationpy-diagnostic--registration-verifier)
   - [`repair_registration.py` (Scoped Repair)](#repair_registrationpy-diagnostic--registration-repair)
   - [`install_hooks.py` (Registration Writer)](#scriptsinstall_hookspy-installer--registration-writer)
   - [Removing a Registration](#removing-a-registration)
7. [Maintenance and Telemetry Hooks](#maintenance-and-telemetry-hooks)
   - [`size_audit.py` (Oversized Runtime Scanner)](#size_auditpy-maintenance--runtime-storage-scan)
   - [`audit_improve.py` (Failure Telemetry and Improvement Handoff)](#audit_improvepy-maintenance--telemetry-audit)
8. [Shared Core Helpers](#shared-core-helpers)
   - [`_state.py` (Runtime State Helper)](#_statepy-core-helper--runtime-state)
   - [`_saves.py` (Save Contract Parser)](#_savespy-core-helper--save-classifier)
9. [Heartbeat Refresh](#heartbeat-refresh)
10. [Environment Variables Reference](#environment-variables-reference)
11. [Manual Smoke Test](#manual-smoke-test)
12. [Regression Test Suites](#regression-test-suites)

---

## Architecture and Layer Mapping

The harness hooks operate at multiple lifecycle layers to ensure safety, traceability, and workflow continuity:

```
[User Input] ────────► UserPromptSubmit (user_prompt_submit.py)
                              │  • Advisory routing to admiral
                              │  • Active session pin reinforcement
                              ▼
[Pending Action] ────► PreToolUse (pre_tool_use.py -> guard_hook.py) [Layer 3]
                              │  • Rule A: Dangerous shell patterns & allow_dangerous
                              │  • Rule B: Frozen & blocked globs (guard & freeze)
                              │  • Rule C: Single-writer records (save_run, taste, guard)
                              │  • Rule D: Read-only run boundaries
                              │  • Rule E: Coverage destination advisory
                              ▼
[Executed Action] ───► PostToolUse (post_tool_use.py) [Layer 4]
                              │  • Trajectory regulation (repeat fails, loops, streaks)
                              │  • Coverage residue sweep to evidence/coverage/
                              │  • Throttled maintenance size audits (size_audit.py)
                              │  • Run heartbeat refresh
                              ▼
[Run Management] ────► save_run.py / guard_state.py / check_readiness.py
```

---

## Complete Hook Directory Manifest

Every file in `skills/harness/hooks/` serves an explicit, non-overlapping architectural role:

| File | Type / Event | Layer | Description |
| :--- | :--- | :---: | :--- |
| [`pre_tool_use.py`](pre_tool_use.py) | `PreToolUse` | 3 | Registered host entry point wrapper; forwards directly to `guard_hook.py`. |
| [`guard_hook.py`](guard_hook.py) | Engine (`PreToolUse`) | 3 | Action Realization engine enforcing Rules A through E (destructive commands, boundaries, single writers). |
| [`post_tool_use.py`](post_tool_use.py) | `PostToolUse` | 4 | Trajectory Regulation engine: catches loops and repeated failures, sweeps coverage residue, refreshes heartbeats. |
| [`user_prompt_submit.py`](user_prompt_submit.py) | `UserPromptSubmit` | Routing | Entry-routing advisor steering lifecycle tasks to `admiral` and reinforcing held session pins. |
| [`save_run.py`](save_run.py) | CLI / Utility | Persistence | Sole sanctioned writer for canonical run records (`_state.md`, `_lock.md`, `_audit-trail.md`, `_journal.json`, `_latest.md`). |
| [`guard_state.py`](guard_state.py) | CLI / Utility | 3 | Sole sanctioned writer for `.harness-state/guard-state.json` (freeze, block, read-only, allow-dangerous). |
| [`size_audit.py`](size_audit.py) | CLI / Sub-hook | Maintenance | Periodic bounded scanner reporting oversized files/directories (>= 256 MiB) under generated runtime roots. |
| [`audit_improve.py`](audit_improve.py) | CLI / Sub-hook | Maintenance | Reads bounded, redacted failure telemetry and formats improvement handoffs for `audit-improve` and `skill-maker`. |
| [`check_readiness.py`](check_readiness.py) | CLI / Diagnostic | - | Evaluates runtime prerequisites: Python version (>= 3.13), hook registration, observed firing, and save state. Read-only. |
| [`verify_registration.py`](verify_registration.py) | CLI / Diagnostic | - | Non-mutating inspector checking whether hooks are configured, resolvable, and executable in host configs, whether their matchers cover the tools they need, and which interpreter they launch. |
| [`repair_registration.py`](repair_registration.py) | CLI / Diagnostic | - | Scoped dry-run diff preview and `--apply` repair tool for host hook configuration with timestamped backups; records the hook script hashes. |
| [`_state.py`](_state.py) | Internal Module | 3 & 4 | Fail-open foundation helper: project-root resolution, trajectory recording, guard state access, and heartbeat refresh. |
| [`_saves.py`](_saves.py) | Internal Module | Persistence | Shared parser and classifier for `skillset-saves/`: `SaveRecord` dataclass, state validation, and evidence resolution. |
| [`.gitignore`](.gitignore) | Config | - | Excludes runtime observations, temporary scratch files, and Python bytecode caches. |
| [`test_hooks.py`](test_hooks.py) | Test Suite | - | Unit and integration tests for `pre_tool_use.py`, `guard_hook.py`, `post_tool_use.py`, and `user_prompt_submit.py`. |
| [`test_hooks_hardening.py`](test_hooks_hardening.py) | Test Suite | - | Security and robustness tests: path normalization, injection attempts, malformed payloads, and fail-open guarantees. |
| [`test_hooks_lifecycle.py`](test_hooks_lifecycle.py) | Test Suite | - | Persistence lifecycle tests: `save_run.py` state transitions, atomic journaling, and read-only run confinement. |
| [`test_hooks_observed.py`](test_hooks_observed.py) | Test Suite | - | Verification tests for observed host hook firing vs synthetic simulation. |
| [`test_guard_state.py`](test_guard_state.py) | Test Suite | - | Authority and boundary tests for `guard_state.py` (freeze/block entries, owner checks, allow-dangerous expiries). |
| [`test_registration_contract.py`](test_registration_contract.py) | Test Suite | - | Multi-host registration tests for Claude Code, Codex, and GitHub Copilot configuration formats. |
| [`test_registration_hardening.py`](test_registration_hardening.py) | Test Suite | - | Host selection, matcher coverage, interpreter checks, project-root resolution, read-only diagnostics, file modes, and hook-script integrity for `verify_registration.py`, `repair_registration.py` and `check_readiness.py`. |
| [`test_installer_hooks.py`](test_installer_hooks.py) | Test Suite | - | `scripts/install_hooks.py` and the `--register-hooks` options of `install.sh` / `install.ps1`: non-UTF-8 files, the generated OpenCode plugin run under node, file modes, and the preview-and-ask step on a terminal. |
| [`test_documented_flags.py`](test_documented_flags.py) | Test Suite | - | Checks every documented command line in `README.md`, `QUICK-START.md`, `Install.md` and this README against the argument parser of the script it runs. |
| [`test_size_audit.py`](test_size_audit.py) | Test Suite | - | Traversal limits, threshold calculations, and throttle record tests for `size_audit.py`. |
| [`test_audit_improve.py`](test_audit_improve.py) | Test Suite | - | Telemetry analysis, correlation hashing, cooldown enforcement, and handoff formatting tests for `audit_improve.py`. |

---

## Design Guarantees and Principles

Per [`../../harness-doctrine.md`](../../harness-doctrine.md), every hook and helper adheres to strict engineering invariants:

- **Standard Library Only:** Zero external runtime dependencies (`pip install` is never required).
- **Fail Open:** Any internal fault, missing file, or unexpected exception exits 0 silently, allowing the host loop to proceed uninterrupted. A harness defect must never crash or deadlock an agent session.
- **Inert on Competent Actions:** Denials and warnings fire only on mechanically certain signals (literal destructive shell patterns, exact path glob matches, or structured exit codes) — never on ambiguous intent or fuzzy heuristic guesses.
- **Config vs. Observed Firing:** Inspecting a host configuration file confirms only that a command is *configured*, *resolvable*, and *executable*. It does not prove the host fired the hook. Readiness marks host firing as `hooks_observed: unverified` until real payloads containing host session IDs are recorded under `.harness-state/observations/`.
- **Single-Writer Protection:** Authoritative state classes (`skillset-saves/`, `.harness-state/guard-state.json`, `taste.*`) have dedicated writers. The harness actively denies direct edits and mutating shell writes to these files.

---

## Registered Lifecycle Hooks

### `pre_tool_use.py` and `guard_hook.py` (Layer 3 — Action Realization)

Invoked by the host before any write-capable or shell tool executes. `pre_tool_use.py` is the registered entry point that delegates to `guard_hook.py`.

#### Rule Hierarchy and Enforcement Contract

`guard_hook.py` applies five rules in strict priority order:

1. **Rule A — Dangerous Shell Patterns:**
   - Detects destructive commands that almost never represent legitimate agent work:
     - `rm --no-preserve-root`, recursive root/drive wipes (`rm -rf /`, `rm -rf ~`, `rm -rf $HOME`, `rm -rf *`).
     - PowerShell/cmd recursive root deletions (`Remove-Item -Recurse C:\`, `rd /s C:\`, `format`).
     - Shell fork bombs (`:(){ :|:& };:`).
     - Raw filesystem formats and block device overwrites (`mkfs`, `dd of=/dev/sd*`, `> /dev/sd*`).
     - Recursive permission stripping (`chmod -R 000 /`).
     - Force-pushing to protected branches (`git push --force origin main`, `git push origin master -f`).
   - **Exemption:** Bounded by an active, unexpired, owner-bearing grant in `.harness-state/guard-state.json` via `guard_state.py allow-dangerous`. A legacy bare `true` flag is rejected.

2. **Rule B — Frozen and Blocked Boundaries:**
   - Enforces write locks declared by `guard` and `freeze` (`frozen_globs` and `blocked_globs` in `guard-state.json`).
   - **Path tools (`Edit`, `Write`, `NotebookEdit`, `apply_patch`):** Denies any write targeting a path matching a frozen/blocked glob.
   - **Shell tools (`Bash`, `PowerShell`):** Denies only when the command is *mutating* (e.g. `rm`, `mv`, `cp`, `git commit`, `Set-Content`, `Out-File`, redirects `>`) **and** targets a frozen path token. Read-only commands (`cat`, `grep`, `ls`, `Get-Content`) pass freely.

3. **Rule C — Single-Writer Record Protection:**
   - Denies edit tools and mutating shell commands from directly modifying core run persistence files (`skillset-saves/_latest.md`, `runs/*/_state.md`, `_lock.md`, `_audit-trail.md`, `_journal.json`, `_history/`). These must be updated only via `save_run.py`.
   - Denies direct writes to Taste records (`taste.json`, `taste.md`, `taste.journal.jsonl`, `taste.lock`). These must be updated only via `skills/taste/taste_prefs.py`.
   - Denies direct writes to `.harness-state/guard-state.json`. It must be updated only via `guard_state.py`.

4. **Rule D — Read-Only Run Enforcement:**
   - While an unreleased `read_only` entry exists in `guard-state.json` (e.g. for an investigation or security audit), all file mutations outside `.harness-state/**` and the run's own declared save path are denied.

5. **Rule E — Coverage Destination Advisory:**
   - If a shell command initiates test coverage without an explicit output destination (`coverage run -p` without `combine`, `pytest --cov` without `--cov-report`, `nyc`/`c8` without `--report-dir`), emits an advisory `additionalContext` message directing the agent to place coverage evidence under `evidence/coverage/`.
   - **Contract:** Never denies the command; provides guidance before execution.

---

### `post_tool_use.py` (Layer 4 — Trajectory Regulation)

Invoked after tool execution completes. Watches for execution pathologies and injects recovery hints into the conversation.

#### Features and Behaviors

1. **Trajectory Degeneration Detection:**
   - **Repeated Failing Command:** Flags identical commands that fail $\ge 3$ consecutive times.
   - **Empty Output Streak:** Flags $\ge 3$ consecutive commands returning empty output.
   - **Two-State Oscillation:** Detects back-and-forth oscillations ($A \to B \to A \to B$) over the last 4 steps.
   - **Output:** Emits a `PostToolUse` `additionalContext` envelope with actionable diagnostic advice. Never blocks (the tool has already run).

2. **Coverage Residue Sweep:**
   - Runs for shell tools (`Bash`, `PowerShell`, `shell`).
   - If a test command left coverage residue at the project root (`.coverage`, `.coverage.*`, `htmlcov/`, `.nyc_output/`), relocates the files into the active run's `evidence/coverage/` (or `.harness-state/test-work/coverage-residue/` if no run is active).
   - If multiple `.coverage.*` fragments exist and the `coverage` package is available, runs `coverage combine --keep` *inside the destination directory*.
   - Never sweeps into or out of generated roots (`skillset-saves/`, `.harness-state/`). Bounded to 5,000 entries.

3. **Maintenance Scan Triggering:**
   - Checks if a 6-hour interval has elapsed since the last runtime size audit and invokes `size_audit.py`.

4. **Heartbeat Refresh:**
   - Refreshes the active run's heartbeat in `_state.md` and `_lock.md` via `save_run.py heartbeat`.

---

### `user_prompt_submit.py` (Entry Routing)

Invoked on every user prompt turn before agent execution begins.

#### Features and Behaviors

1. **Lifecycle Entry Routing:**
   - If no run is active, injects advisory context steering delivery lifecycle tasks (design, build, review, audit, security, QA, release, skill creation) to [`skills/admiral/SKILL.md`](../../admiral/SKILL.md), while noting the Tier 0 fast-path for minor reversible tasks.
2. **Session Pin Reinforcement:**
   - If a valid run is active (`session_pin: true` held in `_state.md`), reminds the model to treat input as session input to the active run and route work through the active sub-orchestrator.
3. **Slash Command Pass-Through:**
   - Explicit slash commands (e.g. `/admiral`, `/guard`, `/ship`) bypass routing reminders to allow host command handling.
4. **`/audit-improve` Command Support:**
   - Intercepts `/audit-improve` requests, forces an `audit_improve.py` execution, and injects the telemetry report as prompt context.

---

## State and Boundary Writers

### `save_run.py` (CLI — Run Persistence Writer)

The sole sanctioned writer for canonical run persistence under `skillset-saves/`. Hand-editing core run files is denied by Layer 3.

```bash
# Create a new run (verifies directory health, runs write probe, records intake evidence)
python skills/harness/hooks/save_run.py create --run-id <run-id> --evidence <evidence-path> [--owner <owner>]

# Checkpoint a stage transition (atomic publish behind _journal.json with history snapshot)
python skills/harness/hooks/save_run.py checkpoint --run-id <run-id> --expect-revision <rev> --evidence <path> [--set key=val]

# Refresh run heartbeat (throttled, updates timestamp without changing revision)
python skills/harness/hooks/save_run.py heartbeat --run-id <run-id> [--owner <owner>]

# Mark run complete (releases session pin, preserves final state)
python skills/harness/hooks/save_run.py complete --run-id <run-id> [--owner <owner>]

# Mark run blocked (preserves the run pointer; --reason belongs to recover and checkpoint --drop-evidence, block does not record it)
python skills/harness/hooks/save_run.py block --run-id <run-id> --next-action "<what unblocks it>" [--set blocked_reason=<text>]

# Release lock (clears session pin to allow other operations)
python skills/harness/hooks/save_run.py release --run-id <run-id> [--owner <owner>]

# Recover orphaned, stale, or interrupted run (rolls back incomplete journal if --rollback)
python skills/harness/hooks/save_run.py recover --run-id <run-id> --reason "<reason>" [--rollback]

# Check authoritative status of a run
python skills/harness/hooks/save_run.py status --run-id <run-id>
```

#### Exit Codes
- `0`: Success (`ok`).
- `1`: Refused (`refused` — contract violation, active lock held by another owner, or corrupt state).
- `2`: Degraded (`degraded` — disk or system write failure).
- `3`: Engine error (`engine_error` — an operating-system or value error the contract does not name, such as an unreadable record; the JSON goes to stderr).

---

### `guard_state.py` (CLI — Guard and Freeze Boundary Writer)

The sole sanctioned writer for `.harness-state/guard-state.json`. Direct file edits are denied by `guard_hook.py` Rule C.

```bash
# Freeze a path pattern under an owner
python skills/harness/hooks/guard_state.py freeze --glob "src/payments/**" --owner ops --scope "release freeze" [--approver sre]

# Block a path pattern (security boundary)
python skills/harness/hooks/guard_state.py block --glob "**/secrets/**" --owner security --scope "sensitive data"

# Release a frozen or blocked boundary (requires requester authority matching owner or approvers)
python skills/harness/hooks/guard_state.py release --glob "src/payments/**" --requester ops --reason "deployment verified"

# Grant bounded dangerous command authorization (default 30 min expiry)
python skills/harness/hooks/guard_state.py allow-dangerous --owner ops --reason "clean scratch" --scope "rm -rf ./scratch" [--minutes 30]

# Revoke dangerous command authorization immediately
python skills/harness/hooks/guard_state.py revoke-dangerous --requester ops

# Record a run as read-only (confines mutations to .harness-state and the run's save path)
python skills/harness/hooks/guard_state.py read-only --run-id run-123 --owner qa --allow "skillset-saves/runs/run-123/**"

# Release read-only status
python skills/harness/hooks/guard_state.py release-read-only --run-id run-123 --requester qa --reason "audit complete"

# Inspect current boundary state
python skills/harness/hooks/guard_state.py status [--json]
```

#### Exit Codes
- `0`: Success.
- `1`: Refused (unauthorized requester, missing owner, malformed input, or corrupt JSON).
- `2`: Usage error.

---

## Registration, Verification, and Repair

Registration is optional. Without it, entry routing and the write guards are advisory and nothing else changes; the diagnostics below say so and never treat it as a failure.

### Supported Hosts and Config Locations

| Host | Configuration File | Format | Scopes (`--scope`) |
| :--- | :--- | :--- | :--- |
| **Codex** | `~/.codex/hooks.json` or `.codex/hooks.json` | JSON | `user`, `project` |
| **Claude Code** | `~/.claude/settings.json`, `.claude/settings.json` or `.claude/settings.local.json` | JSON | `user`, `project`, `local` |
| **GitHub Copilot** | `~/.config/github-copilot/hooks.json` or `.github/hooks.json` | JSON | `user`, `project` |
| **Cursor** | `~/.cursor/plugins/local/supremeteam-hooks/` | Plugin | - |
| **OpenCode** | `~/.config/opencode/plugins/supremeteam-hooks.js` | Plugin | - |

`user` is the global file every project on the machine reads. `project` and `local` belong to the project around the working directory, found the way `find_project_root()` does it (see `_state.py`) by every tool in this section. A `project` file is usually committed and the registered commands hold machine-absolute paths, so for Claude Code prefer `local`, which is the per-machine file. GitHub Copilot has no skills directory: only its hook configuration is written, and only by `scripts/install_hooks.py --target copilot` or `repair_registration.py --host copilot`.

### `check_readiness.py` (Diagnostic — Runtime Readiness)

Verifies the prerequisites that orchestrators (`admiral`, `commander`) inspect at intake. It only reads: it never registers a hook, creates `.harness-state/` or save state, or installs Python.

```bash
# Check runtime readiness for the hosts that have an environment signal or a config file
python skills/harness/hooks/check_readiness.py --host auto

# Check readiness and require an active pinned run (used during resume)
python skills/harness/hooks/check_readiness.py --host auto --require-active-run

# Require working hooks as well (hooks are optional by default)
python skills/harness/hooks/check_readiness.py --host auto --require-hooks

# Inspect another project's saves and host configuration
python skills/harness/hooks/check_readiness.py --host auto --project-root /path/to/project

# Output structured JSON report
python skills/harness/hooks/check_readiness.py --host auto --json
```

**Ready.** `Ready: yes` (exit 0) means Python meets the floor, the hook check reached a definite answer, and, when asked for, a run is active. Hooks are optional, so hooks that are `missing` do not make a project not ready; the report lists them as a separate fact, with the repair preview. Two things do block: a hook state the verifier could not determine (`unknown`, for example no readable configuration for the host you named, because a check with no answer is not a pass) and `--require-hooks`, which also rejects a matcher that misses tools and an interpreter that is missing or too old. The JSON report lists the reasons under `blockers` and everything else worth knowing under `warnings`.

**Capability Matrix Dimensions:**
- `python_runtime`: Python at or above the floor in `runtime-manifest.yaml` (3.13).
- `hooks_configured`: Config entries present in the host configuration of every selected host.
- `hooks_executable`: Target scripts exist and have valid Python invocation syntax.
- `hooks_coverage`: `full`, `partial` (a registered matcher misses tools the hook needs), or `unverified`.
- `hooks_interpreter`: `ok`, `too_old`, `not_found` (not on this PATH; a host may supply its own), or `unverified`.
- `hooks_observed`: Real host execution observed (`observed`, `partial`, `simulated`, or `unverified`).
- `hooks_faults`: Internal faults the hooks failed open on, when they record them. A hook that fires with faults is reported as `firing with N faults`.
- `saves_readable`: `skillset-saves/` is structurally readable.
- `active_run`: Valid active run pointer and unexpired lock held.
- `deterministic_validators`: Catalog validator scripts are accessible.

### `verify_registration.py` (Diagnostic — Registration Verifier)

Inspects host configuration files without modifying them:

```bash
python skills/harness/hooks/verify_registration.py --host auto
python skills/harness/hooks/verify_registration.py --host claude
python skills/harness/hooks/verify_registration.py --host codex --json
```

`--host auto` (the default) checks the hosts that have an environment signal (`CODEX_*`, `CLAUDE*`, `COPILOT*`) or any config file, and names each with the reason, so a host you do not use is not reported as unregistered. `--host all` checks the three hosts regardless; a host name checks that host. User, project and (Claude Code) local files are read together.

Verifies for each hook (`PreToolUse`, `PostToolUse`, `UserPromptSubmit`):
- `configured`: Event is declared in the host configuration.
- `resolvable`: Target script path exists on disk.
- `executable`: Invocation uses a direct Python launcher syntax without swallowed arguments.
- Matcher: a registered `matcher` has to select the tools the hook needs (`Bash`, `PowerShell`, `Edit`, `Write`, `NotebookEdit`, plus `apply_patch` on Codex for the two tool hooks). A matcher that selects none of them is not a registration. A narrower one is `partial`: it is reported with the tools it misses, and `repair_registration.py` adds a group for them.

Reported next to REGISTERED without failing it:
- Interpreter: whether the registered launcher is found on this PATH and its version against the floor in `runtime-manifest.yaml`. The version is read by running that interpreter once with `-I -S -c`; an interpreter inside the project directory is never run.
- Integrity: `unchanged`, `changed` or `unrecorded`, against the sha256 written to `.harness-state/hook-hashes.json` when the hook was registered. A script edited on purpose reports `changed`; record the new hash with `repair_registration.py --host <host> --record-hashes`.

#### Exit Codes
- `0`: Every selected host is fully registered (warnings may still be printed).
- `1`: A selected host's readable config lacks required hooks, or `--host auto` found no host at all.
- `2`: The host or its config cannot be determined (a named host with no readable config, an unreadable file, or an internal error).

### `repair_registration.py` (Diagnostic — Registration Repair)

Calculates missing registrations and previews or applies minimal repairs:

```bash
# Preview changes (dry run prints unified diff without touching files)
python skills/harness/hooks/repair_registration.py --host claude --scope project

# Apply changes (creates timestamped backup <file>.bak-<timestamp> and writes atomically)
python skills/harness/hooks/repair_registration.py --host claude --scope project --apply

# Register another interpreter than the one running the script
python skills/harness/hooks/repair_registration.py --host claude --scope local --python "py -3.13" --apply

# Re-record the hook script hashes after a deliberate edit (changes no host config)
python skills/harness/hooks/repair_registration.py --host claude --record-hashes
```

- **Interpreter:** registers the interpreter running the script (an absolute path), started with `-X utf8` so a hook payload cannot fail to decode under a legacy code page. `--python` names another; `verify_registration.py` warns when the registered one is missing or older than the floor.
- **Minimal:** adds only what is missing, either a hook that does not launch its script or the group of tools a registered matcher leaves out. Every other key, matcher and hook is preserved.
- **Scope:** the dry run is the default and `--scope user` is never implied. It warns when the file is global (`user`) or usually committed (`project`).
- **Files:** a file that is not UTF-8 JSON is refused untouched (exit 2). The file and its `.bak-` backup keep the permission bits the original had; a new `user` file is owner-only.
- **Hashes:** `--apply` records the sha256 of each registered hook script in `.harness-state/hook-hashes.json`.

#### Exit Codes
- `0`: Nothing to do, or the change was applied.
- `1`: Changes are needed and `--apply` was not given.
- `2`: Refused (unreadable or invalid config, undefined scope) or a write failed.

### `scripts/install_hooks.py` (Installer — Registration Writer)

The helper behind `install.sh --register-hooks` and `install.ps1 -RegisterHooks`. It lives in the repository's `scripts/` directory, not in the installed skills, and takes its hook definitions from the installed harness under `--hook-root`, so an install and a later repair cannot disagree.

```bash
# Preview every file it would change; writes nothing
python scripts/install_hooks.py --target claude --hook-root "$HOME/.agents/skills/harness/hooks" --dry-run

# Register for the project's local file instead of the global one
python scripts/install_hooks.py --target claude --hook-root "$HOME/.agents/skills/harness/hooks" --scope local

# Register several hosts; no question asked
python scripts/install_hooks.py --target claude --target codex --target copilot --hook-root "$HOME/.agents/skills/harness/hooks" --yes
```

- **Default scope** is `user`, because the installer puts the hook scripts under your home directory. The wrappers forward `--hooks-scope user|project|local` (`-HooksScope`).
- **Preview and ask:** run from a terminal, it prints the unified diff of every file it would change and asks `Write these changes? [y/N]` first. `--yes` (`--hooks-yes`, `-HooksYes`) skips the question. With no terminal (CI, a pipe) it writes straight away, so automation is unchanged.
- **Safety:** a file that is not UTF-8 JSON is refused and the other hosts still proceed; every overwrite keeps a `.bak-` copy with the original's permission bits; a new user-level file is owner-only.
- **Cursor and OpenCode** get a plugin package it cannot verify. The OpenCode plugin starts the interpreter without a shell, so `--python-command "py -3"` is split into command and arguments, and it logs once when the interpreter cannot start.
- **Exit codes:** `0` registered (or already was, or a dry run); `2` a write was refused or a written hook did not verify; `3` you answered no and nothing was written.

### Removing a Registration

There is no unregister command; the registration is three entries in a config file, and every change kept a backup.

1. Open the file for each host (table above). Remove the `PreToolUse`, `PostToolUse` and `UserPromptSubmit` entries whose `command` points at `pre_tool_use.py`, `post_tool_use.py` and `user_prompt_submit.py`, or restore the newest `<file>.bak-<timestamp>` next to it if nothing else changed since.
2. Cursor and OpenCode: delete the plugin package (`~/.cursor/plugins/local/supremeteam-hooks/`) or file (`~/.config/opencode/plugins/supremeteam-hooks.js`).
3. Optional: delete `.harness-state/hook-hashes.json` in the projects that recorded one.
4. Restart the host. `python skills/harness/hooks/verify_registration.py --host auto` then reports `MISSING` for it, and `check_readiness.py` still reports ready.

---

## Maintenance and Telemetry Hooks

### `size_audit.py` (Maintenance — Runtime Storage Scan)

Periodically scans `.harness-state/` and `skillset-saves/` for storage growth exceeding thresholds (default: 256 MiB):

```bash
# Run manual on-demand size audit with JSON output
python skills/harness/hooks/size_audit.py --project-root . --force --json

# Override the threshold (bytes) and the throttle interval (seconds) through the environment
SUPREMETEAM_SIZE_AUDIT_THRESHOLD_BYTES=104857600 SUPREMETEAM_SIZE_AUDIT_INTERVAL_SECONDS=3600 python skills/harness/hooks/size_audit.py
```

- **Safety:** Never deletes files; reports cleanup candidates.
- **Protected Paths:** Core run files (`_state.md`, `_lock.md`, `guard-state.json`, `taste.*`) are never flagged as cleanup candidates.
- **Throttling:** Enforced via `.harness-state/observations/size-audit.json` (6 hours default).

### `audit_improve.py` (Maintenance — Telemetry Audit)

Gathers bounded runtime failure telemetry and prepares structured improvement packets:

```bash
# Run read-only audit across saved runs and tool trajectories (an explicit run ignores the cooldown)
python skills/harness/hooks/audit_improve.py --run --project-root .
```

- **Redaction:** Hashes run identifiers and trajectory file names using SHA-256 prefixes; never logs raw credentials or environment secrets.
- **Cooldown:** 6 hours between automatic advisories.
- **Handoff:** Supplies structured findings to `skills/audit-improve/SKILL.md` for routing to `admiral` and `skill-maker`.

---

## Shared Core Helpers

### `_state.py` (Core Helper — Runtime State)

Underlying fail-open utility for Layer 3 and Layer 4 hooks:
- `find_project_root()`: Traverses upwards from cwd searching for root markers (`skillset-saves/`, `.harness-state/`, `.git`) or environment overrides.
- `read_hook_input()`: Reads and parses JSON payloads from stdin safely.
- `load_guard_state()`: Reads `.harness-state/guard-state.json` fail-open.
- `record_observation()`: Appends hook execution records under `.harness-state/observations/` with session ID tracking.
- `refresh_run_heartbeat()`: Throttled update of the active run's heartbeat in `_state.md` and `_lock.md`.
- `record_trajectory_step()`: Appends tool call signatures to `.harness-state/trajectories/` and prunes records older than 7 days.

### `_saves.py` (Core Helper — Save Classifier)

Shared parser for the canonical `skillset-saves/` layout:
- `classify_saves(project_root)`: Classifies save directory status (`active`, `complete`, `stale`, `orphaned`, `conflicting`, `corrupt`, `interrupted`, `missing`, `unreadable`).
- `has_active_run(project_root)`: Boolean probe returning `True` only when a coherent, fresh, unexpired run lock exists.
- `read_latest_pointer(project_root)`: Safely extracts the active run ID from `skillset-saves/_latest.md`.

---

## Heartbeat Refresh

To prevent active runs from going stale during long autonomous workflows, all three registered hooks (`pre_tool_use.py`, `post_tool_use.py`, `user_prompt_submit.py`) refresh the active run's heartbeat:
- **Conditions:** Only when the hook payload contains a valid host `session_id`, an active run lock is held, the lock is coherent and uncorrupted, and the run is not interrupted.
- **Throttling:** Refreshes are throttled to at most once every 5 minutes.
- **Execution:** Calls `save_run.py heartbeat --run-id <run> --owner <owner>` internally.
- **Stale Expiry:** Without hook activity or checkpoints, a held run lock transitions to `stale` after 30 minutes.

---

## Environment Variables Reference

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `SUPREMETEAM_PROJECT_DIR` | Auto-detected | Explicit project root directory override. |
| `SUPREMETEAM_HOOK_ROOT` | Script parent directory | Explicit directory where harness hook scripts reside. |
| `SUPREMETEAM_SESSION_ID` | Host session ID | Session identifier used to correlate hook telemetry and heartbeats. |
| `SUPREMETEAM_SIZE_AUDIT_THRESHOLD_BYTES` | `268435456` (256 MiB) | File and directory size threshold for `size_audit.py`. |
| `SUPREMETEAM_SIZE_AUDIT_INTERVAL_SECONDS` | `21600` (6 hours) | Throttle duration between automatic size audits. |
| `CLAUDE_PROJECT_DIR` / `CODEX_WORKSPACE_DIR` / `GITHUB_WORKSPACE` | - | Host-specific workspace directory, tried in that order after `SUPREMETEAM_PROJECT_DIR`. |
| `SUPREMETEAM_HARNESS_DEV` | unset | Set to exactly `1` by the person who launches the host to lift the hook-file protection (guard Rule F) for that session while developing the hooks inside a pinned run. Nothing an agent runs can set it for the host. |
| `CLAUDE_SESSION_ID` / `CODEX_SESSION_ID` | - | Host-specific session ID fallback markers. |

**Project root order.** Every hook, writer and reader in this directory resolves the project root in one place, `_state.project_root()`: the first of `SUPREMETEAM_PROJECT_DIR`, `CLAUDE_PROJECT_DIR`, `CODEX_WORKSPACE_DIR`, `GITHUB_WORKSPACE` that is set wins, and with none set the nearest ancestor of the working directory holding `skillset-saves/`, `.harness-state/` or `.git` is used (the working directory itself when there is none). A test pins the order and that no other module in the directory reads these variables.

---

## Manual Smoke Test

Execute these piped invocations from the repository root to verify hook behavior:

```bash
# 1. Verify Rule A blocks dangerous commands
echo '{"tool_name":"Bash","tool_input":{"command":"rm -rf /"}}' | python skills/harness/hooks/pre_tool_use.py

# 2. Verify Rule E coverage destination advisory
echo '{"tool_name":"Bash","tool_input":{"command":"coverage run -p -m pytest"}}' | python skills/harness/hooks/pre_tool_use.py

# 3. Verify UserPromptSubmit routing advisory
echo '{"prompt":"design this feature"}' | python skills/harness/hooks/user_prompt_submit.py

# 4. Verify host registration status
python skills/harness/hooks/verify_registration.py --host auto

# 5. Check runtime readiness
python skills/harness/hooks/check_readiness.py --host auto
```

---

## Regression Test Suites

The hook test suite resides in this directory and runs via Python's standard `unittest`:

```bash
python -m unittest discover -s skills/harness/hooks -p "test_*.py"
```

### Coverage by Test Module

- **[`test_hooks.py`](test_hooks.py):** Comprehensive testing of `pre_tool_use.py`, `guard_hook.py`, `post_tool_use.py`, and `user_prompt_submit.py`, including Rules A through E, coverage residue relocation, and prompt routing.
- **[`test_hooks_hardening.py`](test_hooks_hardening.py):** Path canonicalization, Windows backslash vs POSIX slash handling, symlink protection, malformed JSON fuzzing, and universal fail-open guarantees.
- **[`test_hooks_lifecycle.py`](test_hooks_lifecycle.py):** `save_run.py` lifecycle transitions, atomic publishing behind `_journal.json`, revision history, and `read_only` run confinement.
- **[`test_hooks_observed.py`](test_hooks_observed.py):** Tests the distinction between configured host configs and actual observed executions under `.harness-state/observations/`.
- **[`test_guard_state.py`](test_guard_state.py):** `guard_state.py` CLI testing: owner authorization, authority-validated release, `allow_dangerous` duration bounds, and single-writer lockouts.
- **[`test_registration_contract.py`](test_registration_contract.py):** Multi-host configuration syntax and schema validation across Claude Code, Codex, and GitHub Copilot.
- **[`test_size_audit.py`](test_size_audit.py):** Directory tree traversal caps, entry limits, threshold calculations, throttle timestamps, and protected file exemptions.
- **[`test_audit_improve.py`](test_audit_improve.py):** Telemetry aggregation limits, error classification, SHA-256 correlation key hashing, and improvement handoff payload generation.
