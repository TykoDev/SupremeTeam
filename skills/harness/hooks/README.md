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
                              │  • Rule F: Hook scripts and registration files
                              │  • Rule G: A write after a directory chain the analysis cannot follow
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
| [`guard_hook.py`](guard_hook.py) | Engine (`PreToolUse`) | 3 | Action Realization engine enforcing Rules A through G, one function per rule (destructive commands, a write the analysis cannot place, boundaries, read-only runs, single writers, hook files) plus the Rule E advisory. |
| [`_cmdscan.py`](_cmdscan.py) | Internal Module | 3 | Shell command analyser: quoting, substitutions, heredocs, `cd`, wrappers (`sudo`, `env`, `xargs`, `sh -c`, `find -exec`, `powershell -Command`, `cmd /c`) and the write targets of the usual verbs, in time linear in the command. |
| [`_paths.py`](_paths.py) | Internal Module | 3 | Path and glob canonicaliser: separators, `.`/`..`, `~`, drive letters, links and case, one `Boundary` per glob for the deny direction and an anchored allow-list test. |
| [`post_tool_use.py`](post_tool_use.py) | `PostToolUse` | 4 | Trajectory Regulation engine: catches loops and repeated failures, sweeps coverage residue, refreshes heartbeats. |
| [`user_prompt_submit.py`](user_prompt_submit.py) | `UserPromptSubmit` | Routing | Entry-routing advisor steering lifecycle tasks to `admiral` and reinforcing held session pins. |
| [`save_run.py`](save_run.py) | CLI / Utility | Persistence | Sole sanctioned writer for canonical run records (`_state.md`, `_lock.md`, `_audit-trail.md`, `_journal.json`, `_latest.md`). |
| [`guard_state.py`](guard_state.py) | CLI / Utility | 3 | Sole sanctioned writer for `.harness-state/guard-state.json` (freeze, block, read-only, allow-dangerous). |
| [`size_audit.py`](size_audit.py) | CLI / Sub-hook | Maintenance | Periodic bounded scanner reporting oversized files/directories (>= 256 MiB) under generated runtime roots. |
| [`audit_improve.py`](audit_improve.py) | CLI / Sub-hook | Maintenance | Reads bounded, redacted failure telemetry and formats improvement handoffs for `audit-improve` and `skill-maker`. |
| [`check_readiness.py`](check_readiness.py) | CLI / Diagnostic | - | Evaluates runtime prerequisites: Python version (>= 3.13), hook registration, observed firing, and save state. Read-only. |
| [`verify_registration.py`](verify_registration.py) | CLI / Diagnostic | - | Non-mutating inspector checking whether hooks are configured, resolvable, and executable in host configs, whether their matchers cover the tools they need, and which interpreter they launch. |
| [`repair_registration.py`](repair_registration.py) | CLI / Diagnostic | - | Scoped dry-run diff preview and `--apply` repair tool for host hook configuration with timestamped backups; records the hook script hashes. |
| [`_state.py`](_state.py) | Internal Module | 3 & 4 | Fail-open foundation helper: the one project-root resolver, hook input decoding, trajectory recording, guard state access, and fault counting. It imports no module above it, which is why the heartbeat refresh is not here. |
| [`run_heartbeat.py`](run_heartbeat.py) | Internal Module | Persistence | The heartbeat refresh every registered hook runs on each host event (`refresh(data, event)`): throttled, fail-open, and written only through `save_run.py`. It sits above `_state` and `save_run`; neither imports it. |
| [`_fsutil.py`](_fsutil.py) | Internal Module | 3 & 4 | The one atomic write (per-process staging removed on any failure, retry, an in-place fallback a caller can refuse with `in_place=False`, an optional explicit file mode; the registration tool writes host configs and their backups through it) and the one OS advisory lock (`AdvisoryLock`) the hooks and writers share. |
| [`_bootstrap.py`](_bootstrap.py) | Internal Module | - | Puts this directory and `skills/scripts` on `sys.path` once, so modules import what they need by its real name, and lists the files a registered hook runs to decide (`enforcement_files()`, for the hash record). |
| [`_testkit.py`](_testkit.py) | Test Support | - | Shared scaffolding for the guard tests: an in-process `decide()` and a subprocess `run_hook()` that read the project from the environment as a host does. |
| [`_saves.py`](_saves.py) | Internal Module | Persistence | Shared parser and classifier for `skillset-saves/`: `SaveRecord` dataclass, state validation, and evidence resolution. |
| [`.gitignore`](.gitignore) | Config | - | Excludes runtime observations, temporary scratch files, and Python bytecode caches. |
| [`test_hooks.py`](test_hooks.py) | Test Suite | - | Unit and integration tests for `pre_tool_use.py`, `guard_hook.py`, `post_tool_use.py`, and `user_prompt_submit.py`. |
| [`test_hooks_hardening.py`](test_hooks_hardening.py) | Test Suite | - | Registration analysis, trajectory isolation per session, freeze record handling, registration repair and the readiness capability map. |
| [`test_hooks_robustness.py`](test_hooks_robustness.py) | Test Suite | - | The end-to-end hardening claims: path spellings and Windows/POSIX separators, symbolic links, a fixed-seed fuzz of the three registered hooks, and universal fail-open with a deny that stays a deny. |
| [`test_guard_rules.py`](test_guard_rules.py) | Test Suite | - | Rules A to G one by one (a positive and a negative case per destructive-command rule), the never-weaker differential against the old rules, fallbacks, rule isolation, working-directory tracking, and cost bounds for seventeen command shapes at 100 KB. |
| [`test_guard_cmdscan.py`](test_guard_cmdscan.py) | Test Suite | - | The command analyser: lexing, wrappers, write-target tables, nesting and cost. |
| [`test_guard_paths.py`](test_guard_paths.py) | Test Suite | - | The path and glob canonicaliser: spellings, links, case, allow versus deny direction. |
| [`test_guard_harness_files.py`](test_guard_harness_files.py) | Test Suite | - | Rule F: the hook scripts and registration files are protected while the guard is in use, and not otherwise. |
| [`test_pre_tool_entry.py`](test_pre_tool_entry.py) | Test Suite | - | The registered PreToolUse entry runs the guard on any interpreter (the real scripts under each older Python installed) and fails open readably, counted, on a real fault; every hook module imports on an older interpreter. |
| [`test_state_hardening.py`](test_state_hardening.py) | Test Suite | - | Hook input decoding, fault counting, trusted state directory, grant cap and the project-root order. |
| [`test_fsutil.py`](test_fsutil.py) | Test Suite | - | The shared atomic write and advisory lock. |
| [`test_hooks_maintenance.py`](test_hooks_maintenance.py) | Test Suite | - | The coverage sweep (read-only runs, active runs, isolated `coverage combine`), neutralised context text, the fault trace of the post-tool and prompt hooks, and import structure. |
| [`test_audit_improve_parts.py`](test_audit_improve_parts.py) | Test Suite | - | The audit as one function per record class, with a golden report pinning the output. |
| [`test_hooks_lifecycle.py`](test_hooks_lifecycle.py) | Test Suite | - | Persistence lifecycle tests: `save_run.py` state transitions, atomic journaling, and read-only run confinement. |
| [`test_run_state.py`](test_run_state.py) | Test Suite | - | The run-state writer: mutual exclusion between writers, evidence handling, closed runs, recovery, and the audit trail. |
| [`test_saves_reader.py`](test_saves_reader.py) | Test Suite | - | Classification of saved state by `_saves.inspect_saves` and `inspect_run`: corrupt, conflicting, orphaned, unreadable, stale and closed runs. |
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
- **Fail Open, and Say So:** Any internal fault, missing file, or unexpected exception exits 0 silently, allowing the host loop to proceed uninterrupted. A harness defect must never crash or deadlock an agent session. The fault is not lost: each hook counts what it swallowed by exception type (never by content) in its observation record (see [Fault trace](#fault-trace)).
- **A Deny Stays a Deny:** Fail open means a fault allows the action, never that a damaged state file turns a rule off. A guard record whose lists are in the wrong shape is read list by list, and an unusable state directory or a failing rule leaves the destructive-command rule and every other rule that can still run in force. A record that cannot be read at all (not JSON, not an object, a directory) names no boundary, so the frozen, blocked and read-only rules have nothing to enforce from it until it is repaired; the other rules keep running, and the hook says so: it counts a `GuardStateUnreadable` fault and adds a `[harness:guard-state]` note to the call's context, so a guard that stopped enforcing a boundary does not look the same as one with no boundary.
- **A Text Guard Is Not a Hard Lock:** the guard reads the command or path a tool is about to use. It cannot see what it is not shown (see [What the guard cannot see](#what-the-guard-cannot-see)), so a boundary that must hold against a determined actor also needs version-control protection or filesystem permissions.
- **Inert on Competent Actions:** Denials and warnings fire only on mechanically certain signals (a destructive command read from its arguments, a canonical path match, or a structured exit code) — never on ambiguous intent or fuzzy heuristic guesses.
- **Config vs. Observed Firing:** Inspecting a host configuration file confirms only that a command is *configured*, *resolvable*, and *executable*. It does not prove the host fired the hook. Readiness marks host firing as `hooks_observed: unverified` until real payloads containing host session IDs are recorded under `.harness-state/observations/`.
- **Single-Writer Protection:** Authoritative state classes (`skillset-saves/`, `.harness-state/guard-state.json`, `taste.*`) have dedicated writers. The harness actively denies direct edits and mutating shell writes to these files.

---

## Registered Lifecycle Hooks

### `pre_tool_use.py` and `guard_hook.py` (Layer 3 — Action Realization)

Invoked by the host before any write-capable or shell tool executes. `pre_tool_use.py` is the registered entry point that delegates to `guard_hook.py`.

`pre_tool_use.py` has no interpreter gate. The supported floor is Python 3.13 (`runtime-manifest.yaml`), but a guard that switched itself off below the floor would be weaker than no floor: the guard modules import and pass the guard suites on 3.10 to 3.12, so a host registered with an older bare `python` is still guarded, and the entry simply runs the guard. Only a real failure to import or run it fails open, and then the fault is counted (see [Fault trace](#fault-trace)) and, below the floor, one line on stderr names the interpreter and the floor. Readiness and the registration check warn about a registered interpreter below the floor; neither is a precondition of the guard working.

#### Rule Hierarchy and Enforcement Contract

`guard_hook.py` applies its rules in strict priority order (A, G, B, D, C, F; Rule E is advice, never a deny). Each rule is one function of the call, so each has its own tests, and a rule that faults is counted and skipped without switching off the others.

1. **Rule A — Dangerous Shell Commands:**
   - Detects destructive commands that almost never represent legitimate agent work, from the command's arguments rather than its raw text: `rm --no-preserve-root`, recursive wipes of a root, home or drive (`rm -rf /`, `rm -rf ~/`, `rm -rf "$HOME/"`, `/bin/rm -rf /*`, `rm -rf *`), the same inside `sh -c`, `$(...)`, `sudo`, `env`, `xargs` and `find -exec`; PowerShell and cmd recursive root deletions (`Remove-Item -Recurse C:\`, `rd /s C:\`, `format`); fork bombs; raw filesystem formats and block device overwrites (`mkfs`, `dd of=/dev/sd*`); recursive permission stripping (`chmod -R 000 /`); and force-pushing to protected branches (`git push --force origin main`, `git -C r push origin master -f`).
   - It is the union of the structural rules and the older textual rules, so it is never weaker than the textual rules were; a quoted mention of a destructive command (`echo "rm -rf /"`) is therefore still a false positive, as before.
   - **Exemption:** Bounded by an active, unexpired, owner-bearing grant in `.harness-state/guard-state.json` via `guard_state.py allow-dangerous`, never more than 8 hours (the writer refuses more, the reader treats a longer grant as malformed). A legacy bare `true` flag is rejected, and a grant is ignored when the state directory is a link or belongs to another user.

2. **Rule B — Frozen and Blocked Boundaries:**
   - Enforces write locks declared by `guard` and `freeze` (`frozen_globs` and `blocked_globs`). `blocked_globs` is a write boundary, never enforced against reads.
   - **Path tools (`Edit`, `Write`, `MultiEdit`, `NotebookEdit`, `apply_patch`; tool names match in any case; `file_path`, `filePath`, `path` and `target_file` are read):** denies any write whose canonical path lies in a frozen/blocked glob: `.`/`..` segments, doubled separators, backslashes, `~`, drive letters, links and case are resolved first.
   - **Shell tools (`Bash`, `PowerShell`):** the command is analysed; every write target (redirects, `tee`, `sed -i`, `cp`/`mv` destinations, `curl -o`, `dd of=`, `git checkout --`, `git apply`, PowerShell cmdlets, `cmd` verbs, and so on) is checked, `cd` is followed, and a tree verb (`rm -r`, `mv`, `git clean`) aimed at a directory above a boundary counts as hitting it. Reads (`cat`, `grep`, `ls`, `Get-Content`) pass.
   - A relative glob is anchored at the project root: `src/**` does not reach `docs/src/`.
   - `git restore --staged` (without `--worktree`) and a `git reset` that is not `--hard`, `--merge` or `--keep` only move the index: their pathspecs are not writes into a frozen tree. A `trap` handler is read as the command line it is, so what it writes is seen.

3. **Rule C — Single-Writer Record Protection:**
   - Denies edit tools and mutating shell commands from modifying core run persistence files (`skillset-saves/_latest.md`, `runs/*/_state.md`, `_lock.md`, `_audit-trail.md`, `_journal.json`, `_history/`, and the writer mutex `skillset-saves/_write.lock`), which only `save_run.py` may update; the Taste records (`taste.json`, `taste.md`, `taste.journal.jsonl`, `taste.lock`), which only `skills/taste/taste_prefs.py` may update; and `.harness-state/guard-state.json`, which only `guard_state.py` may update.
   - Matching is case-insensitive and canonical. A script that is the sanctioned writer is exempt structurally, because a script's arguments are data and never write targets: `python save_run.py checkpoint ...` passes, while a redirect from the same command into a core file is still denied. Removing or moving the directories that hold these records (`.harness-state`, `skillset-saves`, `runs`, a run, `_history`, `preferences`) is denied too.

4. **Rule D — Read-Only Run Enforcement:**
   - While an unreleased `read_only` entry exists (an investigation or security audit), every write target must lie inside `.harness-state/**` or the run's `allow` globs: naming one allowed path in a command that also writes elsewhere no longer satisfies it. Git commands that change the repository and name no path (`git add -A`, `git push`, `git merge`) are denied, and so are the index-only ones (`git restore --staged .`, `git reset HEAD f`): they write no file, so a freeze does not care, but they change the repository. So are the usual package-manager commands that install, remove or update (`npm install`, `pip install -r requirements.txt`, `python -m pip install`, `sudo apt-get install`, `uv pip install`, `npx playwright install`; a table of the common managers, not every tool). The coverage sweep obeys the same list.

5. **Rule E — Coverage Destination Advisory:**
   - If a shell command initiates test coverage without an explicit output destination (`coverage run -p` without `combine`, `pytest --cov` without `--cov-report`, `nyc`/`c8` without `--report-dir`), emits an advisory `additionalContext` message directing the agent to place coverage evidence under `evidence/coverage/`.
   - **Contract:** Never denies the command; provides guidance before execution.

6. **Rule F — Hook Scripts and Registration Files:**
   - Denies edit tools and shell writes to `skills/harness/hooks/` and to the host hook registration files (`.claude/settings.json`, `.claude/settings.local.json`, `.codex/hooks.json`, `.github/hooks.json` and their user-scope equivalents, including the Cursor and OpenCode plugin paths), because one edit to `guard_hook.py` would otherwise persist and switch the guard off while readiness kept reporting the hooks registered.
   - **Engaged only while the guard is in use:** a boundary is recorded or a run is pinned. Developing the hooks in a plain checkout is never blocked. A maintainer who has to edit them inside a run starts the host with `SUPREMETEAM_HARNESS_DEV=1`, which only the person launching the host can set. The sanctioned registration writers (`repair_registration.py`, `scripts/install_hooks.py`) are scripts and keep working. Detecting a change since registration is the registration tooling's job, not this rule's.
   - **Advisory, not a lock:** Rule F is the text guard applied to the guard's own files, so it sees what the guard sees and no more: an edit made outside a session (an editor, another process), through a tool the analyser has no entry for, or by a program's own code is not seen. It makes an honest or careless edit hard, not an adversarial one impossible. What catches the rest after the fact is the hash record registration writes (`.harness-state/hook-hashes.json`), which readiness compares with the files. That record covers every file a registered hook runs to decide: `_bootstrap.enforcement_files()` lists them (the three entry scripts and everything they import, which is where the rules are), one test pins that list to the import closure of the entry scripts and another pins the record to the list, so an edit of any of them reads `changed` in `verify_registration.py` and in readiness, with the file named.
   - **The cost is stated, not hidden:** the rule covers a registration file whole, so while it is engaged an edit to an unrelated key of `.claude/settings.json` (a permission, an `env` entry) is denied as well. `permissions`, `env` and `disableAllHooks` in that file can change what the hooks do as much as the `hooks` entries can, so scoping the rule to the hook entries is a settings-aware check plus a decision about which other keys are safe; until the owner makes that decision, the owner makes those edits (or starts the host with the variable above). The denial says so.

7. **Rule G — A Write the Analysis Cannot Place:**
   - A chain of relative `cd` is followed only up to 512 characters of directory. Past that the analyser stops, says so (`lost_directory`), and the directory of every later write is unknown, so a write could land on anything a rule protects. The command is denied whole, in every mode, with a reason that says why; a command with no write after such a chain is not affected. Following a chain costs time and memory that grow with the square of its length, and nobody works that way: use short paths from one directory, or split the command. Rule G runs second, because it is a flag the analyser already set and the rules after it would spend their time locating every write of a command it denies anyway.

#### What the guard cannot see

The guard is a text guard. It analyses the command a tool is about to run and the path an edit tool names; it does not run anything and it is not a sandbox. These are known limits, stated here so no one relies on more than it gives:

- a program that builds a path at run time, or reads it from a file, an environment variable it sets itself, or the network;
- a script file that writes somewhere its command line does not name (a build script, `make`, `npm run`, `bash ./scripts/install.sh`), and a package manager or installer that is not in Rule D's table;
- interpreter inline code (`python -c`, `node -e`, `perl -e`): it is searched for protected paths, not interpreted, so a read-only run is not enforced against what inline code does beyond naming a protected path;
- a tool name it does not know, and a tool input in a shape it cannot read, which are allowed through;
- a link created in the same command that then writes through it;
- a git command that rewrites the tree and names no path (`git reset --hard`, `git stash`, `git clean -fd`, `git merge`, `git checkout <branch>`): under a freeze it can change a frozen file and nothing sees it, because there is no path to compare; only a read-only run denies it (Rule D);
- a command it cannot parse (unbalanced quoting): the older textual rules still run on the raw text, which is never weaker than before, but it is not an analysis;
- the working directory after a `cd` chain longer than 512 characters, which Rule G refuses rather than guesses.

The hook also fails open on its own faults. Back anything that must not change with version control, filesystem permissions or a sandbox as well.

#### Fault trace

Every place a hook swallows an exception to fail open also counts it. `.harness-state/observations/<Event>.json` (`PreToolUse`, `PostToolUse`, `UserPromptSubmit`) carries `faults` (an integer) and `last_fault` (`{"type": <exception class name>, "at": <UTC timestamp>}`) beside the `observed` and `simulated` records. Only the type is recorded, never a message, path or command, so a fault cannot leak content into state. `_state.load_observations()` returns both fields, and `size_audit.py` and `audit_improve.py` report their own faults under `PostToolUse`. Readiness can surface the counts; they say whether a hook that fired also worked. A guard record that exists and cannot be used is counted as `GuardStateUnreadable` on every call that reads it (`PreToolUse` and the coverage sweep of `PostToolUse`), which readiness prints with the other faults; `PreToolUse` also puts a one-line notice in the context of every shell or write call while it lasts.

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
   - If a test command left coverage residue at the project root (`.coverage`, `.coverage.*`, `htmlcov/`, `.nyc_output/`), relocates the files into the active run's `evidence/coverage/` (or `.harness-state/test-work/coverage-residue/` if no run is active). A run is active in the sense `_saves.inspect_saves` uses: a coherent run with a fresh lock. A pointer that still names a completed, released, blocked or stale run does not make that run the owner of new evidence.
   - It is a write, so it obeys the boundaries: nothing inside a frozen or blocked glob is moved, and while a run is recorded read-only nothing is moved unless both the file and its destination lie in the run's allow list (the hint then says the residue was left in place, and why).
   - If multiple `.coverage.*` fragments exist, runs `python -P -m coverage combine --keep <destination>` from the interpreter's own directory, so no directory the project controls is on the import path and no project configuration file is read. Whether `coverage` is installed is answered by that process: when it is not, the fragments are kept uncombined and the hint says so.
   - Never sweeps into or out of generated roots (`skillset-saves/`, `.harness-state/`). Bounded to 5,000 entries. Run names and file names that reach the hint are neutralised and capped.

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

# Mark run blocked (preserves the run pointer; block refuses --reason, which belongs to recover and checkpoint --drop-evidence: say why with --next-action or --set)
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

#### Behaviour worth knowing
- **One spelling per boundary.** Every glob is normalised before it is compared or stored (`src\payments\**`, `./src/payments/**`, `src//payments/**` and the absolute form of a project path are all `src/payments/**`), so one boundary is one record and one release. A glob that can never match is refused, with the reason, rather than recorded as a boundary that enforces nothing: empty, `.`, climbing out of the project with `..`, a leading `!` (gitignore negation does not exist here), the root of a drive or of the file system, and an absolute path under a top-level directory this machine does not have. That last one is what `/src/payments/**` is: a leading slash means the file system root, not the project root, so the glob is refused and the message gives the project-relative spelling (`src/payments/**`). An absolute path under a directory that exists (`/etc/**`) is a real boundary outside the project and is recorded, as is a drive path a host on another system reports. `status` warns, with the reason, about a record already on disk that matches nothing. Records written before this and stored in another spelling are still matched by their normalised form.
- **One writer at a time.** Every command holds an OS advisory lock (`guard-state.json.lock`) from reading the record to replacing it, so two sessions cannot lose each other's change and a crashed holder never wedges it. `--lock-timeout SECONDS` (default 5) bounds the wait; a writer that cannot get the lock exits 1 and changes nothing.
- **Bounded grants.** `allow-dangerous --minutes` is capped at 480 (8 hours); the hook also reads a grant with more than that left as malformed.

#### Exit Codes
- `0`: Success.
- `1`: Refused (unauthorized requester, missing owner, malformed input, an unmatchable glob, a busy lock, or corrupt JSON).
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
- `hooks_coverage`: over the two hooks that need tools (`PreToolUse`, `PostToolUse`): `full`, `partial` (a registered matcher misses tools, or one of the two is not registered), or `unverified` (neither is registered; the prompt hook, which needs no tools, does not count).
- `hooks_interpreter`: `ok`, `too_old`, `not_found` (not on this PATH; a host may supply its own), or `unverified`.
- `hooks_observed`: Real host execution observed (`observed`, `partial`, `simulated`, or `unverified`).
- `hooks_faults`: Internal faults the hooks failed open on, when they record them. A hook that fires with faults is reported as `firing with N faults`.
- `saves_readable`: `skillset-saves/` is structurally readable. The text report prints the next step for any saves classification but `active` under `Saves:` (`saves.next_step` in the JSON), the one `save_run.py status` gives.
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
- Integrity: `unchanged`, `changed` or `unrecorded`, against the sha256 written to `.harness-state/hook-hashes.json` when the hook was registered. The record covers the hook script and every Python module in its directory (test modules excepted), found by listing the directory, so an edit of the module that holds the rules, a module added later, and a module removed all read `changed`, with the file names. It is a note, never a failure: it is expected after a deliberate edit or an upgrade, and if you made neither, restore the files. Record the new hashes with `repair_registration.py --host <host> --record-hashes`. The record belongs to the project the registration ran from; another project reports `unrecorded` until it records its own. The two modules the hooks import from `skills/scripts/` (`data_formats.py`, `save_taxonomy.py`) are recorded too, named `scripts/<file>`; a record made by an earlier release lacks them, so it reads `changed` once, naming both, until it is recorded again.
- Where a registration may point: this script's own directory, `SUPREMETEAM_HOOK_ROOT`, and the `harness/hooks` directory of each install root in your home (`~/.agents/skills`, `~/.codex/skills`, `~/.claude/skills`, `~/.cursor/skills`, `~/.config/opencode/skills`) that holds the hook scripts. A check run from a host mirror therefore recognises the registration the installer wrote for the common root.

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
- **Hashes:** `--apply` records the sha256 of each registered hook script, of every Python module in its directory and of the `skills/scripts` modules the hooks import, in `.harness-state/hook-hashes.json`.
- **Links:** a config file that is a symbolic link is never replaced by a regular file. The `user` file (a dotfiles manager's link) is written through to its target, with the backup beside the target and a warning that says so; a `project` or `local` file that is a link is refused (exit 2), because a cloned repository can plant one that points anywhere, and so is a link that leads to no file.

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
- **Safety:** a file that is not UTF-8 JSON is refused and the other hosts still proceed; every overwrite keeps a `.bak-` copy with the original's permission bits; a new user-level file is owner-only. A config that is a symbolic link is written through at user scope (and for a path named with `--claude-settings` and its siblings) and refused at project or local scope, as `repair_registration.py` does.
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
- `project_root()` / `find_project_root()`: the one project-root resolver (see [Environment Variables Reference](#environment-variables-reference) for the order); every hook, writer and reader in this directory uses it.
- `read_hook_input(event)`: Reads the JSON payload from stdin as bytes decoded as UTF-8 with replacement (a legacy console code page never makes a payload unreadable) and counts a payload that does not parse as a fault of `event`.
- `load_guard_state()`: Reads `.harness-state/guard-state.json` fail-open: a list in the wrong shape names nothing to enforce and does not stop the rest of the record from being read; a permissive grant is dropped when the state directory is a link or belongs to another user (`state_dir_trusted`); a grant with more than `MAX_GRANT_MINUTES` left is treated as malformed. `read_only_allow()` is the allow list Rule D and the coverage sweep share.
- `record_fault(event, error)` / `load_observations()`: the fault count described under [Fault trace](#fault-trace).
- `safe_text(value, limit)`: neutralises and caps text taken from state before it is shown to the model. `read_mapping(path)` reads a run record.
- `record_observation()`: Appends hook execution records under `.harness-state/observations/` with session ID tracking.
- `append_trajectory()`: Appends tool call signatures to `.harness-state/trajectories/` and prunes records older than 7 days.

### `_saves.py` (Core Helper — Save Classifier)

Shared parser for the canonical `skillset-saves/` layout:
- `classify_saves(project_root)`: Classifies save directory status (`active`, `inactive`, `complete`, `stale`, `orphaned`, `conflicting`, `corrupt`, `interrupted`, `uninitialized`, `missing`, `unreadable`).
- `has_active_run(project_root)`: Boolean probe returning `True` only when a coherent, fresh, unexpired run lock exists. The guard's hook-file rule and the prompt hook ask it on every call, so it reads each run's lock and classifies in full only the runs whose lock is held and the one the pointer names (`inspect_saves(only_held=True)`), which gives the classification's answer in about a third of the time at a thousand runs.
- `read_latest_pointer(project_root)`: Safely extracts the active run ID from `skillset-saves/_latest.md`.

---

## Heartbeat Refresh

To prevent active runs from going stale during long autonomous workflows, all three registered hooks (`pre_tool_use.py`, `post_tool_use.py`, `user_prompt_submit.py`) refresh the active run's heartbeat through `run_heartbeat.refresh`:
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

- **[`test_hooks.py`](test_hooks.py):** Testing of `pre_tool_use.py`, `guard_hook.py`, `post_tool_use.py`, and `user_prompt_submit.py` through the registered scripts, including coverage residue relocation and prompt routing.
- **[`test_guard_rules.py`](test_guard_rules.py), [`test_guard_cmdscan.py`](test_guard_cmdscan.py), [`test_guard_paths.py`](test_guard_paths.py), [`test_guard_harness_files.py`](test_guard_harness_files.py), [`test_pre_tool_entry.py`](test_pre_tool_entry.py):** the guard rule by rule: a positive and a negative case for each destructive-command rule, the differential proving the structural rules are never weaker than the old textual ones, the command analyser, the path canonicaliser, Rule F, and the entry point's fail-open.
- **[`test_hooks_robustness.py`](test_hooks_robustness.py):** the hardening claims, end to end through the registered hooks: path canonicalization (dot segments, doubled separators, absolute and mixed spellings), Windows backslash versus POSIX slash handling in paths, recorded globs and shell verbs, symlink protection (links into a frozen tree, out of an allow list, to the guard record, behind the state directory, and links the sweep and size scan must not follow), a fixed-seed malformed-JSON fuzz of the three hooks (exit 0, no traceback, no internal fault on a payload that parses, a dangerous command still denied inside any noise), and universal fail-open with a deny that stays a deny.
- **[`test_hooks_hardening.py`](test_hooks_hardening.py):** registration analysis, trajectory isolation per session, freeze record handling, registration repair, and the readiness capability map.
- **[`test_state_hardening.py`](test_state_hardening.py), [`test_fsutil.py`](test_fsutil.py), [`test_hooks_maintenance.py`](test_hooks_maintenance.py), [`test_audit_improve_parts.py`](test_audit_improve_parts.py):** input decoding, fault counting, the trusted state directory, the shared atomic write and lock, the coverage sweep and the text the hooks show the model, the post-tool and prompt hooks' fault trace and import structure, and the audit's per-record-class parts.
- **[`test_hooks_lifecycle.py`](test_hooks_lifecycle.py):** `save_run.py` lifecycle transitions, atomic publishing behind `_journal.json`, revision history, and `read_only` run confinement.
- **[`test_hooks_observed.py`](test_hooks_observed.py):** Tests the distinction between configured host configs and actual observed executions under `.harness-state/observations/`.
- **[`test_guard_state.py`](test_guard_state.py):** `guard_state.py` CLI testing: owner authorization, authority-validated release, `allow_dangerous` duration bounds, and single-writer lockouts.
- **[`test_registration_contract.py`](test_registration_contract.py):** Multi-host configuration syntax and schema validation across Claude Code, Codex, and GitHub Copilot.
- **[`test_size_audit.py`](test_size_audit.py):** Directory tree traversal caps, entry limits, threshold calculations, throttle timestamps, and protected file exemptions.
- **[`test_audit_improve.py`](test_audit_improve.py):** Telemetry aggregation limits, error classification, SHA-256 correlation key hashing, and improvement handoff payload generation.
