# Runtime Harness

Doctrine in prose is advice. A registered hook that refuses a write is not. Where
the host allows interception the harness enforces; where it does not, the rule
stays advisory and says so. Specified in
[`skills/harness-doctrine.md`](../skills/harness-doctrine.md).

![The four lifecycle layers](assets/7_harness.jpg)

## Four layers

Every cross-cutting constraint belongs to one layer, the earliest where it can be
enforced.

| # | Layer | When | Where it lives |
|---|---|---|---|
| 1 | Environment Contract | before interaction | `design-doctrine.md`, `grill-me-doctrine.md`, `mcp-tools.md`, `tech-stacks/registry.yaml`, intake briefs |
| 2 | Procedural Skill | task conditioning | the skill library, `session-memory` learnings, `pipelines.yaml` |
| 3 | Action Realization | before execution | `careful`, `freeze`, `guard`, `unfreeze`, the save write probe, `pre_tool_use.py` |
| 4 | Trajectory Regulation | after execution | gatekeepers, checkpoints, rewind rules, `post_tool_use.py` |

An intervention that helps a weak model but gets in a strong one's way is a
defect. When in doubt, it does nothing.

## The hooks

Stdlib only. Fail open: an internal error exits 0 and the action proceeds. Each
rule fires only on a mechanically certain signal. The pre-tool hook is a text
guard, not a sandbox: it reads the command and the path a tool names and runs
nothing; the limits are listed in
[`skills/harness/hooks/README.md`](../skills/harness/hooks/README.md) under "What
the guard cannot see".

| File | Event | Layer | What it does |
|---|---|---|---|
| `pre_tool_use.py` | `PreToolUse` | 3 | Denies destructive commands; writes into a frozen or blocked boundary; writes outside a read-only run's save path; direct writes to the single-writer records (run, Taste, guard); edits to the hook scripts and their registration while a run is pinned or a boundary recorded; recognized writes whose target the analysis cannot place while a boundary or record is protected. Advises, never denies, on a coverage command with no destination |
| `post_tool_use.py` | `PostToolUse` | 4 | Records repeated failures, empty-output streaks and oscillation; refreshes the pinned run's heartbeat; sweeps coverage residue into the run |
| `user_prompt_submit.py` | `UserPromptSubmit` | routing | Points lifecycle work at `admiral`, reinforces the session pin, silent on slash commands |
| `save_run.py` | CLI | persistence | The only writer of the run record |
| `guard_state.py` | CLI | 3 | The only writer of the guard record |
| `guard_hook.py`, `_cmdscan.py`, `_paths.py`, `_program_paths.py` | modules | 3 | Rules A to G; the shell command analyser; the path canonicaliser; the bounded literal-target pass over inline Python |
| `_state.py`, `_fsutil.py`, `_bootstrap.py` | modules | 3, 4 | Fail-open helpers, the atomic write and advisory lock, `sys.path` setup and the enforcement file list |
| `run_heartbeat.py` | module | persistence | The throttled heartbeat refresh every hook runs |
| `verify_registration.py` | diagnostic | | Reads host hook config. Exit 0 registered, 1 missing, 2 unknown; `--host auto` judges only hosts that show evidence |
| `repair_registration.py` | diagnostic | | Previews a registration repair; writes only with `--apply` |
| `check_readiness.py` | diagnostic | | Python, hooks and saves as a capability map |

## Registration

Always opt-in: `--register-hooks` (`-RegisterHooks`) on the installer, or
`scripts/install_hooks.py` from a checkout. Both preview every file they would
change and ask on a terminal; `--hooks-yes` skips the question; exit 3 means
declined, nothing written. Claude Code, Codex and Copilot take JSON config that
`verify_registration.py` reads back; Cursor and OpenCode take a plugin that is not
machine-verifiable. Which file each host and scope edits:
[Install.md](../Install.md#runtime-hooks).

An install that skips, declines or fails registration ends with a banner saying
so. Without hooks the guard, the routing reminder and the hook heartbeat are
advisory; `admiral` says so at intake and `check_readiness.py --require-hooks`
reports the host as not ready.

Repair from an installed copy:

```bash
python skills/harness/hooks/repair_registration.py --host claude --scope project
python skills/harness/hooks/repair_registration.py --host claude --scope project --apply
```

## Readiness

```bash
python skills/harness/hooks/check_readiness.py --host auto
python skills/harness/hooks/check_readiness.py --host auto --require-active-run   # on a resume
```

Capabilities are reported one by one: `python_runtime`, `hooks_configured`,
`hooks_executable`, `hooks_coverage`, `hooks_interpreter`, `hooks_observed`,
`hooks_faults`, `saves_readable`, `active_run`, `deterministic_validators`.
`Ready:` covers Python, the run with `--require-active-run`, and the hooks with
`--require-hooks`. `hooks_observed` stays `unverified` until a hook fires: config
proves registration, not execution. The diagnostic installs and registers
nothing.

## Guard and freeze

`pre_tool_use.py` enforces the boundary `guard` and `freeze` record in
`.harness-state/guard-state.json` (`frozen_globs`, `blocked_globs`,
`allow_dangerous`), resolved under `SUPREMETEAM_PROJECT_DIR`, then a host
workspace variable, then the nearest ancestor holding `skillset-saves/`,
`.harness-state/` or `.git`. Every generated file lands under `skillset-saves/`
or `.harness-state/`. With no record, only the destructive-pattern rule applies.
`unfreeze` clears `frozen_globs`.

The analyser reads literal text. A script file, a package manager, a tool with
no table entry, and a git tree command with no path at the project root are not
seen; a host path outside the project whose tail spells a boundary is refused
rather than guessed. Hooks prevent accidents, not attacks.

## Coverage residue

Coverage data belongs in the run at `<phase>/evidence/coverage/`
(`scripts/output_paths.py --kind coverage`). Point `COVERAGE_FILE`,
`--data-file`, `--cov-report`, `--coverage.reportsDirectory` or `--report-dir`
plus `--temp-dir` there, and never use parallel mode without a `coverage combine`.
`pre_tool_use.py` advises on a coverage command with no destination;
`post_tool_use.py` sweeps `.coverage`, `.coverage.*`, `.coverage/`, `htmlcov/`
and `.nyc_output/` from the project root into the run (or
`.harness-state/test-work/coverage-residue/<timestamp>/` with no run), combining
fragments where it can, skipping frozen and blocked globs, deleting nothing.

## Gate validation

Two validators run at a boundary: `check.py` validates a manifest against
[`skills/gates.yaml`](../skills/gates.yaml); `_gatecheck.py`, behind each
`gatekeeper-*/scripts/check.py`, validates the phase package's shape. Both report
facts and fail loud: a gate that cannot prove a package clean never approves it.
See [gatekeepers.md](gatekeepers.md).

## Exit codes and streams

The tools do not share one scheme; read a code with the tool that returned it.
A mistyped option is argparse's own exit 2 with nothing on stdout in every tool.

| Tool | 0 | 1 | 2 | 3 | Reports go to |
|---|---|---|---|---|---|
| `harness/gatekeeper/check.py` | facts pass | defects found | engine error | | JSON on stdout; an engine error writes JSON with `engine_error` to stderr |
| `gatekeeper-*/scripts/check.py` (`_gatecheck.py`) | no blocking finding | blocking finding | the gate could not run | | Markdown or JSON on stdout; a refused package directory writes `ERROR:` to stderr |
| `hooks/save_run.py` | `ok` | `refused`: a contract violation | `degraded`: the write failed, nothing published | engine error, JSON on stderr | JSON `result` on stdout for 0, 1 and 2 |
| `scripts/package_check.py` | clean | residue or a missing required file | manifest or engine error | | JSON on stdout |
| `scripts/validate_manifests.py` | clean | a contract is violated | | | JSON on stdout |
| `scripts/check_runtime.py` | ready | not ready | | | text on stdout |
| `scripts/check_parity.py` | coverage meets the threshold | scored ids missing | input or engine failure | | JSON on stdout |
| `scripts/scan_record.py` | record written | | wrapper error | | the record and sidecars; read `result.status` |
| `scripts/output_paths.py`, `content_hash.py` | JSON | unsafe, unknown or unreadable request | | | JSON on stdout |
| `hooks/verify_registration.py` | registered | hooks missing, or no host found | host or config undetermined | | text on stdout |
| `hooks/check_readiness.py` | `Ready: yes` | `Ready: no` | internal error | | text on stdout |
| `hooks/repair_registration.py` | nothing to do, or applied | changes needed, `--apply` not given | refused or engine error | | diff and text on stdout |
| `scripts/install_hooks.py` | registered or clean dry run | | a write was refused or a written hook did not verify | declined, nothing written | text on stdout |
| `hooks/guard_state.py` | ok | refused | usage error | | the refusal on stderr |
| the lifecycle hooks | always: a deny is a JSON permission decision, not an exit code | | | | JSON on stdout |

Read `result` in `save_run.py`'s JSON before treating a 2 as degraded; a usage
error prints nothing there. "Engine error" is 2 for the gates and the package
check and 3 for `save_run.py`.

## Classifying a failure

Take the earliest category that matches:

1. **Action-realization failure.** Reasonable intent, not executable form. Layer 3.
2. **Environment-contract mismatch.** Executable, but violates tool bounds or ordering. Layer 1.
3. **Trajectory degeneration.** Valid actions that loop, stall or burn budget. Layer 4.
4. **Residual reasoning failure.** The protocol was followed and the logic is wrong. Not the harness's problem.

Every intervention is local, evidence-triggered, never overrides ambiguous
reasoning, uses no hidden oracle, ships with a regression check, and fails open.

## Tests

Seven suites and three validators, Python 3.13 or newer, standard library only;
CI runs them on Windows, macOS and Linux with and without PyYAML, and
`validate_manifests.py` fails when the workflow drifts from
`skills/runtime-manifest.yaml`. Use `python3` on macOS and Linux, `py -3` on
Windows.

```bash
python -m unittest discover -s skills/harness/hooks -p "test_*.py"
python -m unittest discover -s skills/harness/gatekeeper -p "test_*.py"
python -m unittest discover -s skills/validation -p "test_*.py"
python -m unittest discover -s skills/scripts -p "test_*.py"
python -m unittest discover -s skills/taste -p "test_*.py"
python -m unittest discover -s scripts -p "test_*.py"
python -m unittest discover -s skills/skill-maker/skill-creator -p "test_*.py"
python skills/scripts/validate_manifests.py
python skills/scripts/check_runtime.py
python skills/scripts/package_check.py --root .
python skills/scripts/package_check.py --root . --out .harness-state/packages/supremeteam.zip
```
