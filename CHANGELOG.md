# Changelog

All notable changes to Supreme Team are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The catalog has no
release tags yet, so everything sits under Unreleased; each skill carries its own
`version`, and [CONTRIBUTING.md](CONTRIBUTING.md) says when to bump it.

## [Unreleased]

### Added

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
- The tech-stack registry records `verified_at`, `support_ends` and a note on what
  its digests do and do not prove.

### Changed

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
- The images in `docs/assets` are re-encoded (3.6 MB to 0.5 MB) with the same
  names and aspect ratios.
- `skills/taste/taste_prefs.py` is no longer the only executable file in the tree.
- `.gitignore` also ignores `.DS_Store`, `.env`, `.venv/` and `.claude/worktrees/`.
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
- `design/engineer` and `design/architect` no longer require a stack lock, which
  `pipelines.yaml` orders after both; the engineer works from the detected stack
  and `design/commander` locks it afterwards. `unfreeze` is a declared owner of the
  guard record. Skill versions: `design/engineer` 1.0.1, `design/architect` 1.0.1,
  `admiral` 2.1.1.

### Security

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

### Fixed

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
