# Read-Only Boundary Reference

Read this before the first probe of a QA-only run, and again if a run ends without
releasing its boundary. SKILL.md Workflow steps 1 and 5 carry the two commands; this
file carries the run-id convention, the allow globs, the limits of the enforcement,
and the recovery path.

## Contents

1. Why the boundary is recorded rather than promised
2. Run id and allow glob per mode
3. What the boundary stops, and what it does not
4. Releasing, and who may release
5. Recovery from a record left unreleased
6. Reporting the boundary as evidence

## 1. Why the Boundary Is Recorded Rather Than Promised

A report-only run that quietly edits one file is indistinguishable, in its own output,
from one that did not. Recording the boundary moves the guarantee from the report into
the harness: `pre_tool_use.py` Rule D reads the record before every tool call, so a
write that escapes an install step, a test harness, or a well-meant one-line fix is
denied at the boundary instead of found in review — or not found at all.

## 2. Run Id and Allow Glob per Mode

The commands take `--run-id`, so both modes need one. Pipeline mode has a run; standalone
mode does not, and names one rather than omitting it, because the record is keyed by run
id and an empty key cannot be released precisely.

| Mode | Run id | Allow glob |
|------|--------|------------|
| Pipeline | The active run id from the `### Save Context` block or the run lock under `skillset-saves/` | `skillset-saves/runs/<run-id>/**` — the run's own phase directories, resolved with `skills/scripts/output_paths.py` |
| Standalone | A synthetic id in the form `qa-only-<YYYY-MM-DD>-<surface-slug>`, for example `qa-only-2026-04-19-checkout` | `.harness-state/packages/**`, the standalone report destination `python skills/scripts/output_paths.py --kind standalone_packages --name <report>.md` resolves |

The synthetic id carries the date and the surface so a stuck record names the run that
left it, and it stays a single safe path segment, which `output_paths.py` requires and
`guard_state.py` records verbatim. Reuse of a live id is refused: `read-only` rejects a
second record for a run that already has an active one, which is the intended behavior
when two sweeps overlap — the second sweep runs under the first boundary or waits.

## 3. What the Boundary Stops, and What It Does Not

Denied while the record is unreleased:

- Every `Edit`, `Write`, `MultiEdit`, `NotebookEdit`, and `apply_patch` whose target falls
  outside the allow globs.
- Every shell command with a write target outside the allow globs and `.harness-state/**`.
  The hook analyses the command (redirects, `tee`, `sed -i`, `cp` and `mv` destinations,
  `curl -o`, `git checkout --`, `cd`, and wrappers such as `sudo` and `sh -c`), and every
  write target must lie inside: naming one allowed path in a command that also writes
  somewhere else does not satisfy it. A git command that changes the repository and names
  no path (`git add -A`, `git push`, `git merge`) is denied too, and so are the index-only ones
  (`git restore --staged .`, `git reset HEAD f`): they write no file, but they change the repository.
  So are the usual package-manager commands that install, remove or update (`npm install`,
  `pip install -r requirements.txt`, `uv pip install`, `sudo apt-get install`): a table of the common
  managers, not every tool.
- Every write with no target in the command, because a target the hook cannot place cannot be shown to
  lie inside the allow globs: a mutating verb whose operands arrive on standard input (`cat list | xargs rm`,
  `xargs rm < list`, `Get-ChildItem | Remove-Item`) and an inline `awk`, `sed`, `perl`, `python`, `node` or `ruby`
  program that redirects or opens a file for writing (`awk '{print > "out"}'`, `sed -n 'w out'`,
  `python3 -c "open('x', 'w')"`). Name each target in the shell command itself, as an operand or a redirect, and
  it is judged like any other: `awk '{print}' f > <allowed path>` passes.

Passing untouched:

- Reads of any kind: `Read`, `Grep`, `Glob`, and read-only shell commands.
- Writes under the allow globs, so the evidence bundle and the report are still written.
- Writes under `.harness-state/**`, which the hook always allows so the record itself and
  the run journal keep working.
- The run's own `save_run.py` calls (`checkpoint`, `heartbeat`, `complete`). A script's
  arguments are data and not write targets, so the run can still record itself; a redirect
  from that command into a core run file is still denied, and so is a `save_run.py` command
  the analyser cannot tokenise (an unbalanced quote). `../../guard/references/enforcement.md`
  states this once, with the reason.

Outside the harness entirely: the boundary is a tool-call guard, not a filesystem
permission, and the hook is a text guard that reads the command a tool is about to run
(`../../harness/hooks/README.md` § What the guard cannot see lists its limits). A command
whose writes it cannot see still writes whatever the process it starts writes (a script
file, a program that builds its path at run time), so a test runner invoked read-only
can still drop `.coverage`,
`.coverage.*`, `htmlcov/`, or `.nyc_output/` at the project root. That is residue, not
evidence: resolve the destination with
`python skills/scripts/output_paths.py --run-id <run> --phase qa --kind coverage --name .coverage --mkdir`
and point `COVERAGE_FILE` / `--data-file`, `--cov-report`,
`--coverage.reportsDirectory`, or `--report-dir` + `--temp-dir` at it — it is inside the
allow glob, so the write is permitted and the surface still ends as it started. Never use
parallel or per-process mode without a `coverage combine` into that destination.
`post_tool_use.py` relocates anything left behind, but a report-only sweep that needed the
relocation did change the workspace, which is the one thing it promised not to do.

Product data created by exercising a flow — an account, an invite, a queued
job, a webhook the product emits — is not a tool call and is not stopped. That is the
expected shape of a real sweep; record those side effects in the report. When a flow's
side effects are not acceptable to the owner, stop and report the flow as untested
rather than exercising it and describing the damage afterwards.

## 4. Releasing, and Who May Release

```bash
python skills/harness/hooks/guard_state.py release-read-only --run-id <run> --requester <requester> [--reason "<why the run ended>"]
```

The release is authority-checked: `guard_state.py` accepts it only from the `--owner`
recorded at `read-only` time, so the boundary cannot be dropped by whoever happens to
be running the next command. There is no delegate path for this key — `cmd_read_only`
writes no `approvers` field, unlike a frozen glob — so name an owner who will still be
around to release it, or the run ends with a boundary nobody present can lift. Exit 0 is
released; exit 1 is refused, with the reason on stderr. A refusal is a contract violation
to resolve, never something to work around — and hand-editing `.harness-state/guard-state.json`
is itself denied by the hook, which routes every change through this writer.

## 5. Recovery from a Record Left Unreleased

The failure is silent and it outlives the session: an unreleased record keeps Rule D
denying every edit-tool write and every shell write outside the allow globs project-wide, so the next
session in the same project starts blocked with no indication of which run blocked it.

```bash
python skills/harness/hooks/guard_state.py status          # human-readable summary
python skills/harness/hooks/guard_state.py status --json    # run ids, owners, allow globs
```

`status` prints the active read-only run ids. Match the stuck run id to its recorded
owner, then release it as that owner — nobody else can — stating the reason:

```bash
python skills/harness/hooks/guard_state.py release-read-only --run-id qa-only-2026-04-19-checkout --requester <recorded-owner> --reason "sweep interrupted before step 5"
```

Two habits keep the recovery cheap. Name the owner in the report while the run is still
live, so a later session can find the one identity that can release the record. And
record the boundary with the narrowest allow globs the run needs, so a record that does
get stranded blocks the least surface.

## 6. Reporting the Boundary as Evidence

The result carries the boundary, not a claim about it: the run id, the owner, the allow
globs, and the `release-read-only` output or the `status` line showing no active record.
A QA-only report that states "no changes were made" without that evidence is asserting
exactly what this skill exists to prove, and a report that omits the release is the shape
most likely to leave the workspace blocked while reading as finished.
