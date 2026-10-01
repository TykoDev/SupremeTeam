# Changelog

All notable changes to Supreme Team are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The catalog has no
release tags yet, so everything sits under Unreleased; each skill carries its own
`version`, and [CONTRIBUTING.md](CONTRIBUTING.md) says when to bump it.

## [Unreleased]

### Added

- Installs carry the repository `LICENSE` at the install root (`skills/LICENSE`, a
  byte copy kept identical to the root file by a test).
- `--target copilot` (`-Target Copilot`) on both installers, hooks only; `auto` never
  picks it. The installers also probe `python3.13` and `python3.14` when looking for a
  compatible interpreter.
- `ruff.toml` and a `lint` CI job that pins the ruff version; the repository's unused
  imports, unused locals and dead code are removed so the job starts clean.
- `validate_manifests.py` is a command-line tool with `--help` that refuses unknown flags.
- Continuous integration. `.github/workflows/ci.yml` runs the seven test suites
  and the validators on Windows, macOS and Linux, on Python 3.13 and 3.14, with
  and without PyYAML. `skills/runtime-manifest.yaml` declares it (`ci_matrix`,
  `ci`) and `validate_manifests.py` fails when the workflow stops covering what
  the manifest declares.
- `LICENSE` (MIT, Copyright (c) 2026 TykoDev), `CONTRIBUTING.md` and this
  changelog.
- `skills/validation/_catalog.py`, shared test support that reads the catalog with
  the production parser, and a test that compares that parser with PyYAML on every
  YAML file and every skill frontmatter.
- Installer ownership records. Each install target gets a `.supremeteam-manifest`
  listing what was installed and every directory the installer creates carries a
  `.supremeteam-managed` marker. `scripts/install-items.txt` is the one item list
  both installers read, and `scripts/test_install.py` runs the real `install.sh`
  against a temporary home.
- `--hooks-scope` and `--hooks-yes` (`-HooksScope`, `-HooksYes`) on both installers.
  `scripts/install_hooks.py` now prints the diff of every file it would change and
  asks first when run from a terminal; `--yes` skips the question and exit 3 means
  the answer was no and nothing was written.
- Registration facts that warn without failing: matcher coverage, whether the
  registered interpreter exists and meets the Python floor, and whether a hook
  script still matches the sha256 recorded at registration
  (`.harness-state/hook-hashes.json`, `--record-hashes`).
- Save layout. `skills/scripts/save_taxonomy.py` states the save roots, run-record
  files, phases and staleness window once, for the writer, the reader and the
  resolver. `output_paths.py --kind phase_report` resolves the phase-root files the
  policy declares, including `intake/report_grilling.md`. A run directory with no
  record is classified `uninitialized`. `save_run.py checkpoint --drop-evidence`
  retires a registered path that moved or was pruned.
- The tech-stack registry records `verified_at`, `verification_ttl_days`, `support_ends` and a
  note on what its digests do and do not prove. A stack lock on an overlay whose support has
  ended (`vue-nuxt`, since 2026-07-31), or against a registry not re-read within its window,
  still passes and the gate's result lists a warning.
- The guard's modules and suites. `skills/harness/hooks/` gains `_cmdscan.py` (the
  shell command analyser), `_paths.py` (the path and glob canonicaliser),
  `_fsutil.py` (the one atomic write and OS advisory lock), `_bootstrap.py` and
  `_testkit.py`, and test files for the rules, the analyser, the paths, the
  hook-file protection, the state helpers and an end-to-end fuzz of the registered
  hooks (see [docs/directory-structure.md](docs/directory-structure.md)).
- `SUPREMETEAM_HARNESS_DEV=1`, set by the person who launches the host, lifts the
  protection of the hook scripts and their registration files for a maintenance
  session (see Security).

### Changed

- Deeply nested PowerShell blocks no longer trigger repeated near-identical
  command-scanner passes after the brace-depth safety bound; dormant pyenv shims
  are excluded from older-interpreter compatibility checks; and skills over 400
  lines now carry a task-oriented navigation index enforced by the catalog suite.
- `save_run.py block` refuses `--reason` instead of accepting and discarding it, and run
  ids are checked against the pattern the reader uses, so a writer can no longer create a
  run id the reader would not find; only `create` is held to it, every other operation
  takes any single path segment, so a run made under a looser id stays readable and
  closable.
- `checkpoint --drop-evidence` refuses to leave a run with no evidence path. Records
  `save_run.py` writes are owner-only (0600). A hook that skips its heartbeat because a
  writer holds the lock is no longer counted as a fault. `check_readiness.py` prints the
  next step for the saves (`saves.next_step`) and counts only the tool hooks in
  `hooks_coverage`. The hook-hash record covers every Python module in the hook
  directory, and a changed file is named; `verify_registration.py` accepts a
  registration that names the harness in any install root; a host config that is a
  symbolic link is written through at user scope and for a path named on the command line
  (`install_hooks.py --claude-settings`, `--codex-hooks`, `--copilot-hooks`), and refused at project and
  local scope.
  `output_paths.py --kind product` refuses the version-control directory, the generated
  roots, `skills/harness/` and the host registration files. The installers replace an
  unedited registry from an earlier release (`scripts/superseded/`), report a failed
  hook registration in the summary and exit with its status, and say whether an item
  was removed because it was not selected or is no longer shipped; `install.ps1`
  follows links on a destination before judging it.
- The hook-hash record also covers the two `skills/scripts` modules the hooks import
  (`data_formats.py`, `save_taxonomy.py`), named `scripts/<file>`, so an edit of any file
  a registered hook runs to decide reads `changed` in `verify_registration.py` and
  `check_readiness.py` with the file named; a record made by an earlier release reads
  `changed` once, naming both, until `--record-hashes` records it again.
- The guard denies a hand edit of the writer mutex `skillset-saves/_write.lock` as it
  does the other core run files.
- The heartbeat refresh moved from `_state.py` to `run_heartbeat.py`, so the lowest hook
  module no longer imports the run-record writer.
- A run record that holds an integer literal past the interpreter's digit limit reads as
  unreadable in the hooks, as it does in the saves reader, and the hooks scope a run by
  the one grammar `save_run.py create` uses; a copy of the hooks without
  `skills/scripts/save_taxonomy.py` still guards and leaves the run scope at `no-run`.
- `repair_registration.py` writes host configs and their backups through the shared
  atomic write, which now also removes its staging file on an interrupt and takes
  `in_place=False` to refuse an overwrite in place.
- A run record this account cannot read (records are owner-only, so a second operating-system
  account sharing the project directory cannot read the first one's) is no longer read as an
  absent one. `save_run.py status` and `check_readiness.py` classify it `corrupt` with
  `access_denied` naming the file and a next step that says permission; `create`, resuming a
  released run and `recover` refuse beside it, naming the path and the reason; every other
  operation on that run says the same instead of "no lock"; `has_active_run` counts it as held,
  so the hook-file gate and the session-pin reminder stay on; a directory on the way that cannot
  be searched or listed is classified the same way, and every `save_run.py` operation refuses
  beside it in the same words instead of raising (`status` and `create` raised an engine error,
  the rest a traceback). `access_denied` marks the records that may hold the pin (the pointer, a
  lock, a state beside a lock that says held); a refused state beside a readable released lock is
  a closed run, `corrupt` without it, and does not refuse `create`. In a shared directory the
  second account cannot `create` while the first account's records exist, closed runs included:
  completing or releasing a run only ends its claim and leaves its records unreadable, so they
  have to be made readable to it (a mode or an ACL) or, once the run is closed, removed by an
  account that may delete them; never overwrite them. A hook refresh by an account that may not
  search the saves is no longer counted as a fault.
- The installers recognise an unedited registry from an earlier release whatever line endings its
  checkout gave it: a CRLF copy compares equal once the CR of each CRLF is dropped, in
  `install.sh` and in `install.ps1`; a carriage return that ends no line, or a byte-order mark,
  is still an edit.
- The hook-hash record lives in the project the registration ran from, so another project reads
  `unrecorded` for the same hook files and an edit of them is not noticed there.
  `verify_registration.py` now prints an `integrity:` line naming the record it compared with, its
  changed note and the readiness warning name that record, readiness warns for a host whose hook
  files have no record in the project, and both JSON reports carry the path (`hash_record`,
  `hooks.hash_record`). Recording is still per project: `repair_registration.py --host <host>
  --record-hashes`.
- `_state.TRAJECTORY_LOCK_WAIT` names the quarter second a hook waits for the trajectory lock. The
  concurrent-append test raises it in its own processes, so it no longer fails under CPU load, and
  a test pins the production wait.
- `check_runtime.py` finds a root-level stack beside a nested package, combines the
  signals of a project into one classification (a Vite frontend with a FastAPI backend
  is `full-stack`; a tooling-only `package.json` does not make a project a frontend),
  and reads a large lockfile, a non-UTF-8 note or a symbolic link as a warning, not a
  failure. A project walk stopped by a limit is an error that says the inspection is
  incomplete, and generated output directories are skipped. The skill-creator packager
  and `package_check.py` read one residue list. The benchmark delta is the skill under
  test minus its baseline, whatever order the configurations are named in.
- The verifier and readiness print a repair command that exists where they run, not a
  checkout-relative one that fails in an installed copy.
- `quick_validate` rejects extension keys no skill uses.
- The `audit` evidence kind is removed from the gate spec and engine: no key mapped to it.
  Every document that still listed it no longer does, and a test compares the kind
  lists with `gates.yaml`.
- The gate documents say what the validator does and no more. A typed record is the
  submitter's own statement: the validator never compares an artifact's content with what
  its record claims (it reads `.md` and `.txt` artifacts only for blocked phrases and local
  links), and each gatekeeper skill says so. A flat schema-1 package outside a run still passes, with a warning, and
  the gatekeepers are told to return REVISE for a schema-2 manifest instead of reading
  that pass as the whole contract. A `stack_lock` needs every declared version to be one
  the registry entry offers, which `commander` and the design gatekeeper now state
  instead of "the versions intersect". `--blocked-phrases` is the wrapper scripts'
  option, not `check.py`'s. `package-manifest.yaml` lists the ten residue classes
  `package_check.py` matches and the file its secret names come from, and the typed-record rosters name `mock_parity` and
  `mock_rendering`.
- The guard keeps one record per boundary. `guard_state.py` normalises every glob
  before it compares or stores it, so `src\payments\**`, `./src/payments/**`,
  `src//payments/**` and the absolute form of a project path are one record and one
  release, and refuses a glob that can never match (empty, `.`, or climbing out of
  the project with `..`). A relative glob is anchored at the project root: `src/**`
  no longer reaches `docs/src/`, so a boundary meant for nested directories is
  recorded with a leading `**/`. Writers take an operating-system lock
  (`.harness-state/guard-state.json.lock`, `--lock-timeout` seconds, 5 by default)
  from reading the record to replacing it, so two sessions cannot lose each
  other's change. `blocked_globs` is a write boundary and is documented as one; the
  claim that reads were checked against it is gone. A `save_run.py` command is
  exempt from the single-writer rule because a script's arguments are data and not
  write targets, no longer because its name appears in the text; a redirect from
  that command into a core file is still denied.
- Hooks fail open and count it. Every place a hook swallows an exception records
  the exception type (never its message, a path or a command) under `faults` and
  `last_fault` in `.harness-state/observations/<Event>.json`, and
  `check_readiness.py` reports them as `hooks_faults`. A guard record in the wrong
  shape no longer switches rules off: its lists are read one by one, and the
  destructive-command rule needs none of the record. Hook input is read as UTF-8
  bytes instead of through the console code page (reproduced with a forced legacy
  code page on Linux; not run on Windows), the hooks share one atomic write, one
  lock and one project-root resolver, and hook modules import one another by name.
- The gate wrappers hold a slot optional when `gates.yaml` lets a submitter waive it
  or `pipelines.yaml` runs its stage only under a condition, so a valid skip record
  no longer fails the shape check while the boundary validator passes the same
  package. A file fills one slot, matched on its own name and on whole words. `--prior`
  reads a JSON verdict record as well as Markdown frontmatter, and revisions such
  as `r1` and `r2` are compared as tokens. The blocked-phrase list is one list with
  one case rule; a pattern that does not compile or a missing phrase file is an
  error, never a clean result.
- `scan_record.py` names the raw output relative to the manifest that embeds it, so
  a record in the documented layout reaches the gate without a hand edit. It records
  the command with its argument boundaries, runs `--version-command` without a
  shell, and `--fail-on-output` records a scanner that prints findings and exits 0
  as `fail`; `pass` still means only that the scanner exited 0. A `--version-command`
  that cannot start, such as an unquoted Windows path, is named in the record's
  limitations instead of leaving a null version with no reason.

- Installers replace and remove only what they installed. A directory or file of
  yours that shares a name with an installed item is moved to
  `<target>.supremeteam-backup/<timestamp>/` and listed in the summary, never
  deleted; each item is staged and swapped in, so an interrupted run leaves no
  half-copied item. `--destination` refuses the filesystem root, your home
  directory and its parents, and any folder that overlaps the checkout. `--dry-run`
  prints the plan. `install.sh` no longer aborts on the empty arrays that stock macOS
  bash 3.2 rejects (checked statically; it was not run on bash 3.2). An existing `mcp-tools.md` is
  never replaced, and the shipped copy is a blank template stamped at the epoch
  instead of a Codex snapshot.
- Hook registration has one answer across `verify_registration.py`,
  `repair_registration.py`, `check_readiness.py` and the installers.
  `--host auto` checks only the hosts that show a config file or a host variable
  and names them. `check_readiness.py` prints `Ready: yes` when hooks are missing,
  because hooks are optional, and `--require-hooks` makes them part of `Ready`.
  `repair_registration.py` registers the interpreter that runs it by default.
- `save_run.py` serialises writers with an operating-system lock on
  `skillset-saves/_write.lock` and waits `--lock-timeout` seconds (10 by default)
  before refusing; the hook heartbeat waits a quarter of a second, then skips. `create` refuses
  before it writes and leaves no directory behind, a rollback leaves a fresh
  heartbeat, and a closed run re-enters only through `checkpoint --reopen`.
- `check_runtime.py --detect-project` inspects the current directory by default,
  starts its report with `Inspecting: <root>` and warns when nothing under it
  looks like a project; it used to inspect the catalog's own `skills/` folder.
  `--root` is now also spelled `--catalog-root`. Its project inspector and secret
  redactor moved into their own modules.
- The gate compares the reason of every applicability record with the wording its
  boundary sanctions, takes policy fields as real strings, refuses a manifest that
  declares schema 1 inside a run, verifies the overlay file and every version of a
  `stack_lock`, and reports an engine fault as exit 2 with a JSON `engine_error`.
  All gate wrappers share one project-root finder, package guard and command line.
- Taste preferences are redacted by key and value shape instead of substring, so
  design words such as `design-tokens` or `skeleton-loading-states` are no longer
  refused, and `export` lists every field it drops. An abandoned store lock is
  reclaimed with a `lock_reclaimed` note in the journal.
- The skill-creator packager refuses symlinks, secrets and run state, and refuses
  an output folder inside the skill; its eval viewer embeds data safely, never
  follows symlinks and answers loopback hosts and its own origin only. A failed
  eval run is not scored as a measurement.
- `commands` in `skills/runtime-manifest.yaml` lists all seven suites. README,
  docs/harness.md and CONTRIBUTING.md list them too and say they need Python 3.13
  or newer.
- `validate_manifests.py` checks the documentation mirrors as tables and counts
  derived from the specs rather than English sentences, resolves manifest paths
  inside the directory it validates, and skips its repository-only checks, saying
  so in its report, in an installed copy.
- The evidence-key documentation check needs the key in backticks, so an ordinary
  English word no longer counts as documenting it.
- More of what the documents claim is compared with the code. The Submitter column of
  every boundary table (`docs/gatekeepers.md`, `workflow-protocol.md`, the four
  gatekeeper skills) is compared with `gates.yaml`; every class in
  `save-ownership.yaml` must name a writer of a declared kind and a tool that exists;
  `docs/harness.md` tests hold that every tabulated tool exists, that a mistyped
  option is exit 2 with nothing on stdout, and the named codes of `save_run.py` and
  `install_hooks.py`; the save-contract tests read the hook's deny envelope instead of
  searching its output. The documents that said these were not compared now say what is.
- The images in `docs/assets` are re-encoded (3.6 MB to 0.5 MB) with the same
  names and aspect ratios.
- BENCHMARK.md marks its one inferred figure (`skill-maker`'s 100, read from the deduction
  ledger because the round labelled two rows `ship`) and says so in its opening, instead
  of promising that nothing in it is inferred.
- `skills/taste/taste_prefs.py` is no longer the only executable file in the tree.
- `.gitignore` also ignores `.DS_Store`, `.env`, `.venv/` and `.claude/worktrees/`, and
  everything `package_check.py` refuses to package: key and certificate files,
  `id_*` keys, `.npmrc`, `.netrc`, `.pypirc`, `credentials*.json`, `*.zip`, `*.skill`,
  skill-eval workspaces and `.supremeteam/`. A test checks one path of each residue class.
- Documentation. Commands are written for a checkout; README, Install.md,
  QUICK-START.md, AGENTS.md and the admiral skill now say once how they read in an
  installed copy (`skills/` is the install root, `python` is `python3` or `py -3`)
  and give installed-copy verify commands. AGENTS.md and docs/routing.md repeat the
  seven routing classes of the doctrine, and every document says that a host
  registers the 22 root-level skills by name and reaches the 31 nested specialists
  by path. README drops its unmaintainable test and score figures, BENCHMARK.md
  says which catalog and date its figures describe, docs/harness.md tabulates the
  exit codes and streams of every tool, and several documents now say what their
  comparator actually checks.
- Documentation catch-up for the guard and the inventories. The freeze, guard,
  careful and unfreeze references, `save-protocol.md`, the admiral agent protocol and
  the QA-only boundary reference describe the guard as it is: one record per glob, a
  structural `save_run.py` exemption, the writer lock, the grant cap, and a text guard
  that is not a hard lock. AGENTS.md and docs/directory-structure.md list every file
  the packages added and their section counts add up to 53; BENCHMARK.md's Tests
  section gives the command for each suite instead of counts that go stale. The
  tech-stack registry says that `vue-nuxt` locks Nuxt 3, whose end of life passed on
  2026-07-31, and that choosing a supported major is the owner's decision.
  `skills/validation/test_docs_inventory.py` checks the section counts against the
  tree and that the engineer's preconditions name nothing the design pipeline orders
  after it.
- `design/engineer` and `design/architect` no longer require a stack lock, which
  `pipelines.yaml` orders after both; the engineer works from the detected stack
  and `design/commander` locks it afterwards. `unfreeze` is a declared owner of the
  guard record.

### Security

- Round-2 audit (`docs/quality-audit-2026-10-01-r2.md`), H-1: a copy, link, install, sync
  or extract into `.harness-state/` replaced the guard record and lifted every freeze and
  read-only run in one allowed command (`cp /tmp/guard-state.json .harness-state/`, with
  `install`, `ln -sf`, `rsync`, `tar -C`, `cp -t` and a `cd` first too), and the same
  reached the run records and the registration files. The analyser now names the file a
  copy, link or install lands as in a directory (`dir/<source name>`), and Rule C reads a
  sync, an extract, a recursive or contents copy, `git clean` and the in-place editors
  `find -exec` runs as writes into everything under the directory they name. A file that
  is no record (`cp notes.md .harness-state/`) still passes.
- H-3: under a freeze, `find src -exec sed -i ...`, `find src -exec truncate ...`,
  `rsync --delete ... src/`, `tar -xf a.tar -C src` and `cp -r x/. src` rewrote a frozen tree
  from the directory above it. Rule B counts them as tree writes, as it counts `rm -r` and
  `mv`; a plain copy beside the boundary (`cp a.py src/`) is judged by the file it lands as.
  `rsync` no longer reads its `-t` (`--times`) as a target directory.
- H-2: a target spelled through `$PWD` or `$CLAUDE_PROJECT_DIR` got past a freeze, a block
  and Rule F (`echo x > "$PWD/src/payments/a"`, `rm -rf "$CLAUDE_PROJECT_DIR/src"`, a write
  of `disableAllHooks` to `"$CLAUDE_PROJECT_DIR/.claude/settings.local.json"`). `$PWD` is
  now the shell's own directory, the project-directory variables `_state.PROJECT_ENV` names
  are the paths the host gave them, and a path led by a variable the analysis cannot resolve
  (`$OUT/src/payments/a`) is also judged without it. Rule F reads a launcher's commands and
  a write the analyser cannot place as Rule B does.
- H-4: an edit to `skills/scripts/save_taxonomy.py` or `data_formats.py`, which the hooks
  import, was allowed, and appending `raise SystemExit(0)` to either switched the guard off
  with no fault counted. Rule F now covers both, a rule that ends that way is counted and
  skipped so the others still run, a run-id grammar that fails its import is counted and
  leaves the run scope at `no-run`, and the entry treats a `SystemExit` the guard did not
  take after printing its decision as a fault.
- G-1: a gate manifest three or more directories below a run's phase directory was read
  as a detached package, where schema 1 is accepted and the run's rules do not apply, so
  a `review-to-delivery` package with an open Critical finding passed. `check.py` now finds
  the run from any depth.

- The pre-tool guard reads shell commands and canonicalises paths before it
  matches. It follows quoting, `cd`, redirects, wrappers (`sudo`, `env`, `xargs`,
  `sh -c`, `find -exec`, `powershell -Command`, `cmd /c`) and the write targets of
  the usual verbs, and resolves `.` and `..`, doubled separators, backslashes, `~`,
  drive letters, links and case first. A freeze, a block or a read-only run is no
  longer slipped by `>path` without a space, `tee`, `sed -i`, `curl -o`, a heredoc,
  inline code that names a protected path, a wrapper or another spelling of the path,
  and a read-only run
  judges every write target of a command, not whether one allowed path appears in
  it. Git commands that change the repository and name no path (`git add -A`,
  `git push`) are denied under a read-only run. The destructive-command rule is the
  union of the new structural rules and the old textual ones, so it never denies
  less than before (a differential test against the old patterns pins that), and
  its cost is linear in the command: a 72 KB command took 12 seconds. It is still a
  text guard, not a sandbox, and `skills/harness/hooks/README.md` lists what it
  cannot see.
- The hook scripts and the host files that register them (`.claude/settings.json`,
  `.codex/hooks.json`, `.github/hooks.json` and their user-scope equivalents) are
  protected, but only while a run is pinned or a boundary is recorded, so developing
  the hooks in a plain checkout is never blocked. A maintainer who has to edit them
  inside a run starts the host with `SUPREMETEAM_HARNESS_DEV=1`; nothing an agent
  runs can set it for the host. The Taste records, and the removal or move of a
  directory that holds a protected record, fall under the single-writer rule too.
- An `allow_dangerous` grant lasts at most 8 hours (the writer refuses more and the
  hook treats a longer one as malformed), and it is honoured only from a state
  directory this user owns that is not a link. Every restriction is kept
  regardless.
- The coverage sweep obeys a read-only run, writes residue only into the active
  run, and runs `coverage combine` with `-P` from a neutral directory, so a module
  planted in the destination is never imported.
- Waivers can no longer be written in the submitter's own words: the gate rejects
  an applicability record whose reason is not exactly the sanctioned wording for
  that key and boundary.
- The installers no longer run `rm -rf` on every managed name. The remote install
  recipe downloads an archive of a pinned tag or full commit SHA, fails on an HTTP
  error and checks the extracted folder before it runs anything.
- The package check refuses more credential-shaped files, symlinks, and a
  malformed manifest.
- The architect no longer runs `npx shadcn@latest` or follows an unapproved
  registry: the CLI is pinned to a version the project or the user approved, and a
  registry origin outside the project's own `components.json` needs the user's
  approval first.

- The guard's analysis costs time and memory in proportion to the length of the
  command: a chain of relative `cd` used to square (a 74 KB chain took 94 s and a
  100 KB one ran out of memory) and now takes a third of a second. `cd` back into a
  directory already visited is followed, so `cd src; cd x; cd ..; cd payments; touch
  a.py` is judged as a write into `src/payments`, which used to pass a freeze. Rule G
  denies a write that follows a directory chain longer than 512 characters, because
  past that point the analysis stops following it and the target directory is unknown.
- `guard_state.py` refuses a glob that can never match, with the reason: a leading
  `!`, the root of a drive or file system, or an absolute path under a top-level
  directory the machine does not have (`/src/payments/**` starts at the file system
  root; the refusal names `src/payments/**`). `status` warns about such a record
  already on disk.
- A guard record that cannot be read is counted (`GuardStateUnreadable`) and announced
  in the context of every shell or write call while it lasts; the destructive-command,
  single-writer and hook-file rules keep running without it. A guard entry that cannot
  import is counted; below Python 3.13 it also prints one readable line (interpreter, floor,
  exception type), and on 3.13 and newer it prints nothing.
- Index-only git commands (`git restore --staged`, `git reset HEAD <path>`) are no
  longer read as writes into a frozen tree; a read-only run denies them, and denies the
  usual package-manager install, remove and update commands.
- A read-only run denies a write whose target is not in the command. A mutating verb that
  `xargs`, `parallel`, `entr` or `watch` runs with no operand of its own (`cat list | xargs
  rm -rf`, `ls | parallel rm {}`), a shell, PowerShell, cmd or interpreter that reads its
  program from a pipe (`echo 'rm x' | sh`), a PowerShell cmdlet fed by the pipeline or run in
  a script block (`Get-ChildItem *.pyc | Remove-Item`, `... | ForEach-Object { Remove-Item
  $_ }`), `patch` and `git apply` (their targets are inside the diff; `--check`, `--dry-run`,
  `--stat`, `--numstat` and `--summary` still pass), and an inline `awk`, `sed`, `perl`,
  `python`, `node`, `ruby`, `php`, `lua` or R program that redirects, opens a file for writing
  or runs a command that mutates now read as writes with no named target, and Rule D refuses
  them with a reason that says to name each target in the command. Round 1 refused them by
  substring; since round 2 they passed. `awk '$1 > 5'` and every read still pass.
- A freeze, a block and the single-writer rule read what a launcher or script block runs
  (`watch`, `entr`, `parallel`, a PowerShell `{ ... }`) like the command line, and refuse a write
  whose target the guard cannot place (a program read from a pipe, operands from `xargs`, a
  diff fed to `patch`, a path built at run time) when the command also names a protected path,
  as the substring rule they replaced did: `echo 'rm src/payments/a' | sh` is refused under a
  freeze of `src/payments/**`, while `cat list | xargs rm` and `git checkout main` still pass.
  An abbreviated PowerShell parameter that fits a value parameter and a switch
  (`rm -f src/payments/a`) is a switch, so the path after it is a write target.
- `guard_state.py` warns on stderr (exit status unchanged) about any leading-slash glob that is
  not under the project root, whether or not its first directory exists on the machine:
  `freeze --glob /lib/payments/**` guards the file system's `/lib/payments`, not the project's
  `lib/payments/**`. `status` lists it under `absolute_entries` with the project-relative
  spelling. The refusal for a missing directory stays.
- The guard follows `cd -`, `pushd`, `popd` and a bare `cd`: after `cd
  skillset-saves/runs/r1/investigation && cd - && touch notes.md` a read-only run used to judge
  the write in the allowed directory the shell had left.
- `_bootstrap.enforcement_files()` lists the files a registered hook runs to decide.
  The README and the guard skill say Rule F is advisory (an edit made outside a
  session, or through a tool the analyser does not know, is not seen) and that the
  hash record of those files is what detects one afterwards. Rule F covers the whole
  of a host registration file, not only its hook entries, and the guard skill states
  that cost and that scoping it is the owner's decision.

### Fixed

- Round-2 audit O-1: twelve skills told their agent to checkpoint with `save_run.py
  checkpoint --owner <self>` (commander, redesign, build-management, code-chief, cso,
  investigate, bob-the-builder, test-builder, health-check, debugger,
  cross-check-build-confirm, session-memory; fifteen commands). `save_run.py` refuses
  every owner but the lock holder and admiral holds the lock for the whole run, so each
  failed with `lock is owned by 'admiral'` at the first checkpoint of every delegated
  phase. They pass `--owner admiral` and record the delegate with `--set delegated_to=`,
  and `validation/test_save_prose.py` refuses a documented save command whose `--owner` is
  not the writer's lock holder.

- Registered evidence under a directory the account may not search is reported as
  `evidence_unverifiable` beside the classification the run's own records give, where it turned
  the owner's run `corrupt` with the other-account step; the writer refuses such a path naming it
  (`evidence path cannot be read by this account (permission denied)`) where it raised an engine
  error.
- The save readers and the writer probe the run paths with `stat` (`_saves.path_exists`,
  `path_is_dir`) and not `Path.exists` or `Path.is_dir`, which raise on some interpreters and
  answer no on others where pathlib is built on `os.path`; where a directory may not be searched
  the answer is a refusal on all of them.
- `test_pipeline_workflows.py` ran no tests on a host without PyYAML while the
  suite still reported OK. It now reads its inputs the way the gate does.
- Running `test_catalog_contracts.py` directly silently dropped 8 of its tests.
- `runtime-manifest.yaml` listed PyYAML as used only by `quick_validate.py`;
  `validation/trigger_eval.py` requires it as well.
- Two overlapping `save_run.py` calls could lose an update or leave the lock and
  state at different revisions; a vanished evidence path could wedge a run; a run
  directory with only intake's report read as corrupt.
- `check_runtime.py` imports `tomllib` lazily, so the interpreter-floor report
  survives on Python below 3.11. It also detects TanStack Start by its current
  package name and root-level stacks beside nested packages, and no longer emits
  Spring Boot start commands without Spring Boot evidence.
- The responsibility matrix's specialist count was never compared, because the
  comparator's pattern accepted only "twenty-one"; it now reads spelled counts.
- The YAML subset reader dropped `#` lines, stripped a ` #` tail and collapsed blank
  lines inside block scalars, where all three are content; every YAML file and
  frontmatter in the tree parses to the same value as before. It also keeps a
  version such as `3.10` as text instead of the float `3.1`: a number is a float only
  when it prints back unchanged, so `.5`, `+1.5`, `1.`, `1.50` and `1.5e+3` stay text too,
  which PyYAML would read as floats (no shipped YAML holds an unquoted float).
- `check_parity.py` no longer lets a void element (`<input>`, `<img>`) leave a route
  open and credit a later shell-level state to it, and rejects an inventory with no
  routes or components instead of scoring it 1.0.
- `aggregate_benchmark.py` reads the layout `references/real-evals.md` tells agents
  to produce and exits 1 when no run was graded, where it used to write an empty
  benchmark with a delta of `+0.00`.
- `validation/run_eval.py` and `trigger_eval.py` no longer score a failed session: a
  missing CLI, a timeout, a non-zero exit or a reply flagged as an error is an error
  with exit 1, never "0 skills registered". `run_eval.py` lost the `--queries` and
  `--turns` flags it parsed and never read.

### Skill versions

Each skill whose behaviour or contract changed since the first review carries a new
`version`, by the rule in [CONTRIBUTING.md](CONTRIBUTING.md#skill-versions): a minor
bump for new behaviour, a patch for a fix. Skills not listed are unchanged at 1.0.0. A
test compares this list with the `version:` of every `SKILL.md`, so a bump that is not
recorded here, or a record the skill does not carry, fails it.

- `admiral` 2.1.1: how its commands read in an installed copy, the eleven save-directory
  classes, and what `create` carries.
- `design/architect` 1.0.1: works from the stack the project already fixes, not a lock
  that comes later in the pipeline.
- `design/engineer` 1.0.1: works from the detected stack, not a lock that comes later.
- `design/commander` 1.0.2: states the stack-lock rule the engine enforces (every
  declared version is one the registry offers), and its checkpoint command passes `--owner admiral`, the run's lock holder, and records itself with `--set delegated_to=`; `--owner <self>` was refused at every checkpoint.
- `design/design-mapper` 1.0.1: states what `check_parity.py` now refuses in an inventory.
- `careful` 1.0.1: describes the guard as it is (it reads the command, and counts faults).
- `freeze` 1.3.0: one record per boundary whatever the spelling, a refused glob that can
  never match (a leading `!`, a root, an absolute path under a directory the machine
  lacks), a warning for a leading-slash glob outside the project that names a directory that
  exists, relative globs anchored at the project root, a writer lock, and what an
  unreadable record means.
- `guard` 1.4.0: a grant is capped at 8 hours, the hook scripts are protected (Rule F,
  advisory, whole registration file), a write after an unfollowable directory chain is
  denied (Rule G, with its own failure-mode row), a read-only run denies writes with no
  named target (pipes, launchers, PowerShell blocks, diffs), an unreadable record is counted
  and announced, writers serialise on a lock, and Rule F covers the `skills/scripts`
  modules the hooks import.
- `unfreeze` 1.1.0: releases by the normalised glob and records the cap on a grant.
- `gatekeeper-admiral` 1.1.0: a REVISE row for a schema-1 result, the typed-record
  roster and what a typed record leaves unchecked.
- `design/gatekeeper-design` 1.1.0: as `gatekeeper-admiral`, and the stack-lock and
  selection rules the engine now enforces.
- `build/gatekeeper-build` 1.1.0: as `gatekeeper-admiral`, with its package guard and
  optional slots.
- `review/gatekeeper-code` 1.1.0: as `gatekeeper-admiral`, with its package guard and
  optional slots.
- `session-memory` 1.1.1: the writer lock, `checkpoint --drop-evidence`, the
  `uninitialized` class, the refusal reasons and the `access_denied` mark; its checkpoint
  example names the lock holder as `--owner` and a project-relative evidence path.
- `taste` 1.1.0: `propose` validation, redaction by shape, lock reclaim and the error codes.
- `skill-maker` 1.0.1: the Stage 5 hand-off names the output directory as an absolute path, the
  parent of the `path` that `output_paths.py` prints, and leaves it out outside a run.
- `skill-maker/skill-creator` 1.1.0: the packager takes an absolute output directory and
  refuses symlinks, secrets and run state; failed eval runs are not scored.
- `review/security-review` 1.1.0: `scan_record.py` names its output relative to the
  manifest and gains `--fail-on-output` and `--manifest-root`.
- `review/cso` 1.0.2: the waiver reason must be the sanctioned wording, scan output
  paths follow the manifest, and its checkpoint command passes `--owner admiral`, the run's lock holder, and records itself with `--set delegated_to=`; `--owner <self>` was refused at every checkpoint.
- `design/redesign` 1.0.1: its checkpoint command passes `--owner admiral`, the run's lock holder, and records itself with `--set delegated_to=`; `--owner <self>` was refused at every checkpoint.
- `build/build-management` 1.0.1: its checkpoint command passes `--owner admiral`, the run's lock holder, and records itself with `--set delegated_to=`; `--owner <self>` was refused at every checkpoint.
- `review/code-chief` 1.0.1: its checkpoint command passes `--owner admiral`, the run's lock holder, and records itself with `--set delegated_to=`; `--owner <self>` was refused at every checkpoint.
- `investigate` 1.0.1: its checkpoint command passes `--owner admiral`, the run's lock holder, and records itself with `--set delegated_to=`; `--owner <self>` was refused at every checkpoint.
- `build/bob-the-builder` 1.0.1: its checkpoint command passes `--owner admiral`, the run's lock holder; `--owner <self>` was refused.
- `build/test-builder` 1.0.1: its checkpoint command passes `--owner admiral`, the run's lock holder; `--owner <self>` was refused.
- `build/debugger` 1.0.1: its checkpoint command passes `--owner admiral`, the run's lock holder; `--owner <self>` was refused.
- `build/health-check` 1.0.1: its checkpoint command passes `--owner admiral`, the run's lock holder; `--owner <self>` was refused.
- `build/cross-check-build-confirm` 1.0.1: its checkpoint command passes `--owner admiral`, the run's lock holder; `--owner <self>` was refused.
- `qa-only` 1.0.3: the read-only boundary reference states what the hook now denies,
  including index-only git commands, package-manager installs and writes with no named
  target.
